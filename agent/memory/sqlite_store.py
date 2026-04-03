"""
Structured memory layer — SQLite database for facts, events, decisions, relationships.
This is the queryable backbone of Mira's second brain.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.memory.sqlite")


class SQLiteStore:
    """Structured memory — facts, dates, people, decisions, preferences, events."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self._action_callback = None  # optional callback(module, action, outcome, details)

    def initialise(self):
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"SQLite memory initialised at {self.db_path}")

    def _create_tables(self):
        """Create all memory tables."""
        self.conn.executescript("""
            -- Core memories: facts, thoughts, decisions, observations
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                importance INTEGER DEFAULT 3,
                source TEXT DEFAULT 'telegram',
                tags TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- People / relationship CRM
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                aliases TEXT DEFAULT '[]',
                relationship_type TEXT DEFAULT 'unknown',
                email TEXT,
                phone TEXT,
                key_facts TEXT DEFAULT '[]',
                commitments TEXT DEFAULT '[]',
                important_dates TEXT DEFAULT '[]',
                last_interaction TIMESTAMP,
                relationship_health TEXT DEFAULT 'neutral',
                conversation_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Events: meetings, calls, decisions with outcomes
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_type TEXT DEFAULT 'general',
                description TEXT,
                participants TEXT DEFAULT '[]',
                outcome TEXT,
                action_items TEXT DEFAULT '[]',
                occurred_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Decisions: what was decided, why, outcome tracking
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                context TEXT,
                reasoning TEXT,
                alternatives_considered TEXT DEFAULT '[]',
                outcome TEXT,
                outcome_score INTEGER,
                domain TEXT DEFAULT 'general',
                decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Tasks: things Mira is tracking or working on
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 3,
                module TEXT DEFAULT 'general',
                due_date TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Trades: every trade logged with full context
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL,
                exit_price REAL,
                size REAL,
                pnl REAL,
                strategy TEXT,
                rationale TEXT,
                platform TEXT DEFAULT 'mt5',
                opened_at TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Action log: everything Mira does
            CREATE TABLE IF NOT EXISTS action_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                outcome TEXT,
                details TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Preferences: user preferences Mira learns over time
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'inferred',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- API usage tracking for cost monitoring
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT 'standard',
                task_type TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Create indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_decisions_domain ON decisions(domain);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
            CREATE INDEX IF NOT EXISTS idx_action_log_module ON action_log(module);
            CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);
            CREATE INDEX IF NOT EXISTS idx_api_usage_created ON api_usage(created_at);
            CREATE INDEX IF NOT EXISTS idx_api_usage_tier ON api_usage(tier);

            -- Telegram contacts: autonomous conversation whitelist + per-contact settings
            CREATE TABLE IF NOT EXISTS telegram_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                telegram_user_id TEXT,
                telegram_username TEXT,
                autonomy_level TEXT DEFAULT 'review_first',
                relationship_type TEXT DEFAULT 'unknown',
                communication_style TEXT DEFAULT 'casual and friendly',
                key_facts TEXT DEFAULT '[]',
                open_threads TEXT DEFAULT '[]',
                conversation_count INTEGER DEFAULT 0,
                last_message_at TIMESTAMP,
                last_synced_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Soul settings: per-relationship-type communication rules
            CREATE TABLE IF NOT EXISTS soul_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relationship_type TEXT UNIQUE NOT NULL,
                tone TEXT DEFAULT 'casual',
                formality INTEGER DEFAULT 3,
                humor_level INTEGER DEFAULT 3,
                emoji_usage TEXT DEFAULT 'minimal',
                response_length TEXT DEFAULT 'medium',
                proactive_outreach INTEGER DEFAULT 0,
                escalation_keywords TEXT DEFAULT '[]',
                custom_instructions TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Telegram message history for autonomous conversations
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                flagged_for_review INTEGER DEFAULT 0,
                review_status TEXT DEFAULT 'none',
                source TEXT DEFAULT 'bot',
                telegram_message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contact_id) REFERENCES telegram_contacts(id)
            );

            -- Scheduled messages for future delivery
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                send_at TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'pending',
                reason TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                error TEXT,
                FOREIGN KEY (contact_id) REFERENCES telegram_contacts(id)
            );

            CREATE INDEX IF NOT EXISTS idx_telegram_contacts_name ON telegram_contacts(name);
            CREATE INDEX IF NOT EXISTS idx_telegram_contacts_user_id ON telegram_contacts(telegram_user_id);
            CREATE INDEX IF NOT EXISTS idx_telegram_contacts_autonomy ON telegram_contacts(autonomy_level);
            CREATE INDEX IF NOT EXISTS idx_soul_settings_type ON soul_settings(relationship_type);
            CREATE INDEX IF NOT EXISTS idx_telegram_messages_contact ON telegram_messages(contact_id);
            CREATE INDEX IF NOT EXISTS idx_telegram_messages_created ON telegram_messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_telegram_messages_tg_id ON telegram_messages(telegram_message_id);
            CREATE INDEX IF NOT EXISTS idx_scheduled_messages_send_at ON scheduled_messages(send_at);
            CREATE INDEX IF NOT EXISTS idx_scheduled_messages_status ON scheduled_messages(status);
        """)
        self.conn.commit()

    # ── Memory CRUD ──────────────────────────────────────────────────

    def store_memory(
        self,
        content: str,
        category: str = "general",
        importance: int = 3,
        source: str = "telegram",
        tags: list = None,
        metadata: dict = None,
    ) -> int:
        """Store a new memory. Returns the memory ID."""
        cursor = self.conn.execute(
            """INSERT INTO memories (content, category, importance, source, tags, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                content,
                category,
                importance,
                source,
                json.dumps(tags or []),
                json.dumps(metadata or {}),
            ),
        )
        self.conn.commit()
        logger.info(f"Stored memory #{cursor.lastrowid}: {content[:80]}...")
        return cursor.lastrowid

    def search_memories(
        self,
        query: str = None,
        category: str = None,
        min_importance: int = None,
        limit: int = 20,
    ) -> list[dict]:
        """Search memories with optional filters."""
        conditions = []
        params = []

        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")
        if category:
            conditions.append("category = ?")
            params.append(category)
        if min_importance is not None:
            conditions.append("importance >= ?")
            params.append(min_importance)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM memories {where} ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_recent_memories(self, limit: int = 10) -> list[dict]:
        """Get most recent memories."""
        rows = self.conn.execute(
            "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    # ── People CRM ───────────────────────────────────────────────────

    def upsert_person(
        self,
        name: str,
        relationship_type: str = None,
        key_facts: list = None,
        email: str = None,
        phone: str = None,
        metadata: dict = None,
    ) -> int:
        """Create or update a person record."""
        existing = self.conn.execute(
            "SELECT * FROM people WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()

        if existing:
            updates = []
            params = []
            if relationship_type:
                updates.append("relationship_type = ?")
                params.append(relationship_type)
            if key_facts:
                # Merge with existing facts
                old_facts = json.loads(existing["key_facts"])
                merged = list(set(old_facts + key_facts))
                updates.append("key_facts = ?")
                params.append(json.dumps(merged))
            if email:
                updates.append("email = ?")
                params.append(email)
            if phone:
                updates.append("phone = ?")
                params.append(phone)

            updates.append("last_interaction = ?")
            params.append(datetime.now().isoformat())
            updates.append("conversation_count = conversation_count + 1")
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())

            params.append(existing["id"])
            self.conn.execute(
                f"UPDATE people SET {', '.join(updates)} WHERE id = ?", params
            )
            self.conn.commit()
            return existing["id"]
        else:
            cursor = self.conn.execute(
                """INSERT INTO people (name, relationship_type, key_facts, email, phone,
                   last_interaction, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    relationship_type or "unknown",
                    json.dumps(key_facts or []),
                    email,
                    phone,
                    datetime.now().isoformat(),
                    json.dumps(metadata or {}),
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def get_person(self, name: str) -> Optional[dict]:
        """Look up a person by name."""
        row = self.conn.execute(
            "SELECT * FROM people WHERE name LIKE ? COLLATE NOCASE", (f"%{name}%",)
        ).fetchone()
        return dict(row) if row else None

    def get_all_people(self) -> list[dict]:
        """Get all known people."""
        rows = self.conn.execute(
            "SELECT * FROM people ORDER BY last_interaction DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Telegram Contacts (Autonomous Conversations) ─────────────────

    def upsert_telegram_contact(
        self,
        name: str,
        telegram_user_id: str = None,
        telegram_username: str = None,
        autonomy_level: str = None,
        relationship_type: str = None,
        communication_style: str = None,
        key_facts: list = None,
        metadata: dict = None,
    ) -> int:
        """Create or update a Telegram contact for autonomous messaging."""
        existing = self.conn.execute(
            "SELECT * FROM telegram_contacts WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()

        if existing:
            updates = []
            params = []
            if telegram_user_id is not None:
                updates.append("telegram_user_id = ?")
                params.append(telegram_user_id)
            if telegram_username is not None:
                updates.append("telegram_username = ?")
                params.append(telegram_username)
            if autonomy_level is not None:
                updates.append("autonomy_level = ?")
                params.append(autonomy_level)
            if relationship_type is not None:
                updates.append("relationship_type = ?")
                params.append(relationship_type)
            if communication_style is not None:
                updates.append("communication_style = ?")
                params.append(communication_style)
            if key_facts is not None:
                old_facts = json.loads(existing["key_facts"])
                merged = list(set(old_facts + key_facts))
                updates.append("key_facts = ?")
                params.append(json.dumps(merged))
            if metadata is not None:
                updates.append("metadata = ?")
                params.append(json.dumps(metadata))

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(existing["id"])
            self.conn.execute(
                f"UPDATE telegram_contacts SET {', '.join(updates)} WHERE id = ?", params
            )
            self.conn.commit()
            return existing["id"]
        else:
            cursor = self.conn.execute(
                """INSERT INTO telegram_contacts
                   (name, telegram_user_id, telegram_username, autonomy_level,
                    relationship_type, communication_style, key_facts, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name,
                    telegram_user_id,
                    telegram_username,
                    autonomy_level or "review_first",
                    relationship_type or "unknown",
                    communication_style or "casual and friendly",
                    json.dumps(key_facts or []),
                    json.dumps(metadata or {}),
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def get_telegram_contact(self, name: str = None, telegram_user_id: str = None) -> Optional[dict]:
        """Look up a Telegram contact by name or user ID."""
        if telegram_user_id:
            row = self.conn.execute(
                "SELECT * FROM telegram_contacts WHERE telegram_user_id = ?", (telegram_user_id,)
            ).fetchone()
        elif name:
            row = self.conn.execute(
                "SELECT * FROM telegram_contacts WHERE name LIKE ? COLLATE NOCASE", (f"%{name}%",)
            ).fetchone()
        else:
            return None
        return dict(row) if row else None

    def get_all_telegram_contacts(self) -> list[dict]:
        """Get all Telegram contacts."""
        rows = self.conn.execute(
            "SELECT * FROM telegram_contacts ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_telegram_contact(self, contact_id: int) -> bool:
        """Delete a Telegram contact and their message history."""
        self.conn.execute("DELETE FROM telegram_messages WHERE contact_id = ?", (contact_id,))
        cursor = self.conn.execute("DELETE FROM telegram_contacts WHERE id = ?", (contact_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def save_telegram_message(self, contact_id: int, role: str, content: str,
                               flagged: bool = False, source: str = "bot",
                               telegram_message_id: int = None) -> int:
        """Store a message in the Telegram conversation history."""
        # Dedup by telegram_message_id if provided
        if telegram_message_id:
            existing = self.conn.execute(
                "SELECT id FROM telegram_messages WHERE telegram_message_id = ? AND contact_id = ?",
                (telegram_message_id, contact_id),
            ).fetchone()
            if existing:
                return existing["id"]

        cursor = self.conn.execute(
            """INSERT INTO telegram_messages
               (contact_id, role, content, flagged_for_review, source, telegram_message_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (contact_id, role, content, 1 if flagged else 0, source, telegram_message_id),
        )
        self.conn.execute(
            """UPDATE telegram_contacts SET last_message_at = ?, conversation_count = conversation_count + 1,
               updated_at = ? WHERE id = ?""",
            (datetime.now().isoformat(), datetime.now().isoformat(), contact_id),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_contact_synced(self, contact_id: int):
        """Update the last_synced_at timestamp for a contact."""
        self.conn.execute(
            "UPDATE telegram_contacts SET last_synced_at = ? WHERE id = ?",
            (datetime.now().isoformat(), contact_id),
        )
        self.conn.commit()

    def get_telegram_history(self, contact_id: int, limit: int = 20) -> list[dict]:
        """Get recent message history for a Telegram contact."""
        rows = self.conn.execute(
            """SELECT * FROM telegram_messages WHERE contact_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (contact_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_pending_reviews(self) -> list[dict]:
        """Get all messages flagged for review that haven't been approved/rejected."""
        rows = self.conn.execute(
            """SELECT m.*, tc.name as contact_name FROM telegram_messages m
               JOIN telegram_contacts tc ON m.contact_id = tc.id
               WHERE m.flagged_for_review = 1 AND m.review_status = 'none'
               ORDER BY m.created_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Soul Settings (Communication Rules per Relationship Type) ────

    def upsert_soul_setting(
        self,
        relationship_type: str,
        tone: str = None,
        formality: int = None,
        humor_level: int = None,
        emoji_usage: str = None,
        response_length: str = None,
        proactive_outreach: bool = None,
        escalation_keywords: list = None,
        custom_instructions: str = None,
        enabled: bool = None,
    ) -> int:
        """Create or update soul settings for a relationship type."""
        existing = self.conn.execute(
            "SELECT * FROM soul_settings WHERE relationship_type = ? COLLATE NOCASE",
            (relationship_type,),
        ).fetchone()

        if existing:
            updates = []
            params = []
            if tone is not None:
                updates.append("tone = ?"); params.append(tone)
            if formality is not None:
                updates.append("formality = ?"); params.append(formality)
            if humor_level is not None:
                updates.append("humor_level = ?"); params.append(humor_level)
            if emoji_usage is not None:
                updates.append("emoji_usage = ?"); params.append(emoji_usage)
            if response_length is not None:
                updates.append("response_length = ?"); params.append(response_length)
            if proactive_outreach is not None:
                updates.append("proactive_outreach = ?"); params.append(1 if proactive_outreach else 0)
            if escalation_keywords is not None:
                updates.append("escalation_keywords = ?"); params.append(json.dumps(escalation_keywords))
            if custom_instructions is not None:
                updates.append("custom_instructions = ?"); params.append(custom_instructions)
            if enabled is not None:
                updates.append("enabled = ?"); params.append(1 if enabled else 0)

            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(existing["id"])
            self.conn.execute(
                f"UPDATE soul_settings SET {', '.join(updates)} WHERE id = ?", params
            )
            self.conn.commit()
            return existing["id"]
        else:
            cursor = self.conn.execute(
                """INSERT INTO soul_settings
                   (relationship_type, tone, formality, humor_level, emoji_usage,
                    response_length, proactive_outreach, escalation_keywords,
                    custom_instructions, enabled)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    relationship_type,
                    tone or "casual",
                    formality if formality is not None else 3,
                    humor_level if humor_level is not None else 3,
                    emoji_usage or "minimal",
                    response_length or "medium",
                    1 if proactive_outreach else 0,
                    json.dumps(escalation_keywords or []),
                    custom_instructions or "",
                    1 if enabled is not False else 0,
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def get_soul_setting(self, relationship_type: str) -> Optional[dict]:
        """Get soul settings for a specific relationship type."""
        row = self.conn.execute(
            "SELECT * FROM soul_settings WHERE relationship_type = ? COLLATE NOCASE",
            (relationship_type,),
        ).fetchone()
        return dict(row) if row else None

    def get_all_soul_settings(self) -> list[dict]:
        """Get all soul settings."""
        rows = self.conn.execute(
            "SELECT * FROM soul_settings ORDER BY relationship_type"
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_soul_setting(self, relationship_type: str) -> bool:
        """Delete soul settings for a relationship type."""
        cursor = self.conn.execute(
            "DELETE FROM soul_settings WHERE relationship_type = ? COLLATE NOCASE",
            (relationship_type,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ── Scheduled Messages ──────────────────────────────────────────

    def save_scheduled_message(self, contact_id: int, content: str,
                                send_at: str, reason: str = "") -> int:
        """Schedule a message for future delivery."""
        cursor = self.conn.execute(
            """INSERT INTO scheduled_messages (contact_id, content, send_at, reason)
               VALUES (?, ?, ?, ?)""",
            (contact_id, content, send_at, reason),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_pending_scheduled_messages(self) -> list[dict]:
        """Get scheduled messages that are due for sending."""
        rows = self.conn.execute(
            """SELECT sm.*, tc.name as contact_name, tc.telegram_username
               FROM scheduled_messages sm
               JOIN telegram_contacts tc ON sm.contact_id = tc.id
               WHERE sm.status = 'pending' AND sm.send_at <= ?
               ORDER BY sm.send_at ASC""",
            (datetime.now().isoformat(),),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_scheduled_messages(self, contact_id: int = None, status: str = None) -> list[dict]:
        """Get scheduled messages with optional filters."""
        conditions = []
        params = []
        if contact_id:
            conditions.append("sm.contact_id = ?")
            params.append(contact_id)
        if status:
            conditions.append("sm.status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.conn.execute(
            f"""SELECT sm.*, tc.name as contact_name FROM scheduled_messages sm
                JOIN telegram_contacts tc ON sm.contact_id = tc.id
                {where} ORDER BY sm.send_at DESC""",
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_scheduled_sent(self, message_id: int):
        """Mark a scheduled message as sent."""
        self.conn.execute(
            "UPDATE scheduled_messages SET status = 'sent', sent_at = ? WHERE id = ?",
            (datetime.now().isoformat(), message_id),
        )
        self.conn.commit()

    def mark_scheduled_failed(self, message_id: int, error: str):
        """Mark a scheduled message as failed."""
        self.conn.execute(
            "UPDATE scheduled_messages SET status = 'failed', error = ? WHERE id = ?",
            (error, message_id),
        )
        self.conn.commit()

    def cancel_scheduled_message(self, message_id: int) -> bool:
        """Cancel a pending scheduled message."""
        cursor = self.conn.execute(
            "UPDATE scheduled_messages SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (message_id,),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ── Events ───────────────────────────────────────────────────────

    def log_event(
        self,
        title: str,
        event_type: str = "general",
        description: str = None,
        participants: list = None,
        outcome: str = None,
        action_items: list = None,
        occurred_at: str = None,
    ) -> int:
        """Log an event."""
        cursor = self.conn.execute(
            """INSERT INTO events (title, event_type, description, participants,
               outcome, action_items, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                title,
                event_type,
                description,
                json.dumps(participants or []),
                outcome,
                json.dumps(action_items or []),
                occurred_at or datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    # ── Decisions ────────────────────────────────────────────────────

    def log_decision(
        self,
        decision: str,
        context: str = None,
        reasoning: str = None,
        domain: str = "general",
        alternatives: list = None,
    ) -> int:
        """Log a decision for tracking."""
        cursor = self.conn.execute(
            """INSERT INTO decisions (decision, context, reasoning, domain,
               alternatives_considered)
               VALUES (?, ?, ?, ?, ?)""",
            (
                decision,
                context,
                reasoning,
                domain,
                json.dumps(alternatives or []),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def score_decision(self, decision_id: int, outcome: str, score: int):
        """Score a past decision (1-10) for learning."""
        self.conn.execute(
            """UPDATE decisions SET outcome = ?, outcome_score = ?,
               reviewed_at = ? WHERE id = ?""",
            (outcome, score, datetime.now().isoformat(), decision_id),
        )
        self.conn.commit()

    # ── Tasks ────────────────────────────────────────────────────────

    def add_task(
        self,
        title: str,
        description: str = None,
        priority: int = 3,
        module: str = "general",
        due_date: str = None,
    ) -> int:
        """Add a task."""
        cursor = self.conn.execute(
            """INSERT INTO tasks (title, description, priority, module, due_date)
               VALUES (?, ?, ?, ?, ?)""",
            (title, description, priority, module, due_date),
        )
        self.conn.commit()
        return cursor.lastrowid

    def complete_task(self, task_id: int):
        """Mark a task as completed."""
        self.conn.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), task_id),
        )
        self.conn.commit()

    def get_pending_tasks(self, module: str = None) -> list[dict]:
        """Get all pending tasks, optionally filtered by module."""
        if module:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status = 'pending' AND module = ? ORDER BY priority ASC",
                (module,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority ASC"
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Trades ───────────────────────────────────────────────────────

    def log_trade(
        self,
        instrument: str,
        direction: str,
        entry_price: float = None,
        size: float = None,
        strategy: str = None,
        rationale: str = None,
        platform: str = "mt5",
    ) -> int:
        """Log a trade entry."""
        cursor = self.conn.execute(
            """INSERT INTO trades (instrument, direction, entry_price, size,
               strategy, rationale, platform, opened_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                instrument,
                direction,
                entry_price,
                size,
                strategy,
                rationale,
                platform,
                datetime.now().isoformat(),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, pnl: float):
        """Close a trade with exit price and P&L."""
        self.conn.execute(
            "UPDATE trades SET exit_price = ?, pnl = ?, closed_at = ? WHERE id = ?",
            (exit_price, pnl, datetime.now().isoformat(), trade_id),
        )
        self.conn.commit()

    def get_open_trades(self) -> list[dict]:
        """Get all open (unclosed) trades."""
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE closed_at IS NULL ORDER BY opened_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_trade_history(self, limit: int = 50) -> list[dict]:
        """Get recent trade history."""
        rows = self.conn.execute(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Action Log ───────────────────────────────────────────────────

    def log_action(self, module: str, action: str, outcome: str = None, details: dict = None):
        """Log any action Mira takes — the audit trail."""
        self.conn.execute(
            "INSERT INTO action_log (module, action, outcome, details) VALUES (?, ?, ?, ?)",
            (module, action, outcome, json.dumps(details or {})),
        )
        self.conn.commit()
        # Fire optional callback for real-time WebSocket broadcast
        if self._action_callback:
            try:
                self._action_callback(module, action, outcome, details)
            except Exception:
                pass  # never let callback errors break action logging

    def get_daily_actions(self, date: str = None) -> list[dict]:
        """Get all actions for a given day."""
        target = date or datetime.now().strftime("%Y-%m-%d")
        rows = self.conn.execute(
            "SELECT * FROM action_log WHERE DATE(created_at) = ? ORDER BY created_at",
            (target,),
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Preferences ──────────────────────────────────────────────────

    def set_preference(self, key: str, value: str, confidence: float = 0.5, source: str = "inferred"):
        """Set or update a user preference."""
        self.conn.execute(
            """INSERT INTO preferences (key, value, confidence, source, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = ?, confidence = ?,
               source = ?, updated_at = ?""",
            (
                key, value, confidence, source, datetime.now().isoformat(),
                value, confidence, source, datetime.now().isoformat(),
            ),
        )
        self.conn.commit()

    def get_preference(self, key: str) -> Optional[str]:
        """Get a preference value."""
        row = self.conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # ── API Usage Tracking ──────────────────────────────────────────

    def log_api_usage(
        self,
        model: str,
        tier: str,
        task_type: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
    ):
        """Log an API call for cost tracking."""
        self.conn.execute(
            """INSERT INTO api_usage (model, tier, task_type, input_tokens, output_tokens, estimated_cost)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (model, tier, task_type, input_tokens, output_tokens, estimated_cost),
        )
        self.conn.commit()

    def get_api_costs(self, period: str = "today") -> dict:
        """Get API cost breakdown. Period: 'today', 'week', 'month', 'all'."""
        if period == "today":
            where = "WHERE DATE(created_at) = DATE('now')"
        elif period == "week":
            where = "WHERE created_at >= DATE('now', '-7 days')"
        elif period == "month":
            where = "WHERE created_at >= DATE('now', '-30 days')"
        else:
            where = ""

        # Total cost
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(estimated_cost), 0) as total, COUNT(*) as calls FROM api_usage {where}"
        ).fetchone()
        total_cost = row["total"]
        total_calls = row["calls"]

        # By tier
        tier_rows = self.conn.execute(
            f"""SELECT tier, COUNT(*) as calls, SUM(estimated_cost) as cost,
                SUM(input_tokens) as input_tok, SUM(output_tokens) as output_tok
                FROM api_usage {where} GROUP BY tier"""
        ).fetchall()

        # By task type
        task_rows = self.conn.execute(
            f"""SELECT task_type, COUNT(*) as calls, SUM(estimated_cost) as cost
                FROM api_usage {where} GROUP BY task_type ORDER BY cost DESC LIMIT 10"""
        ).fetchall()

        return {
            "period": period,
            "total_cost": round(total_cost, 4),
            "total_calls": total_calls,
            "by_tier": [dict(r) for r in tier_rows],
            "by_task": [dict(r) for r in task_rows],
        }

    # ── Encrypted Field Storage ─────────────────────────────────────

    # Sensitive fields that should be encrypted when ENCRYPT_AT_REST is True
    SENSITIVE_FIELDS = {
        "memories": ["content"],
        "people": ["key_facts"],
    }

    def store_encrypted(self, table: str, field: str, value: str, encryption_mgr) -> None:
        """Encrypt a value and store it in the specified table/field.

        This is a low-level helper. For normal writes, use the standard
        store_memory / upsert_person methods which call
        _maybe_encrypt_fields automatically.

        Args:
            table: Table name (e.g. "memories")
            field: Column name (e.g. "content")
            value: Plaintext value to encrypt and store
            encryption_mgr: EncryptionManager instance
        """
        encrypted = encryption_mgr.encrypt(value)
        # Store as base64 string so it fits in a TEXT column
        import base64
        encoded = base64.b64encode(encrypted).decode("ascii")
        logger.debug(f"Encrypting {table}.{field} ({len(value)} chars)")
        return encoded

    def read_encrypted(self, table: str, field: str, encrypted_value: str, encryption_mgr) -> str:
        """Decrypt a value previously stored with store_encrypted.

        Args:
            table: Table name (for logging context)
            field: Column name (for logging context)
            encrypted_value: Base64-encoded encrypted string from the database
            encryption_mgr: EncryptionManager instance

        Returns:
            Decrypted plaintext string
        """
        import base64
        encrypted_bytes = base64.b64decode(encrypted_value.encode("ascii"))
        plaintext = encryption_mgr.decrypt(encrypted_bytes)
        logger.debug(f"Decrypted {table}.{field} ({len(plaintext)} chars)")
        return plaintext

    def _maybe_encrypt_fields(self, table: str, data: dict, encryption_mgr=None) -> dict:
        """Encrypt sensitive fields in a data dict if encryption is enabled.

        Args:
            table: Table name to check against SENSITIVE_FIELDS
            data: Dict of {column: value} pairs
            encryption_mgr: EncryptionManager instance (None = skip encryption)

        Returns:
            New dict with sensitive fields encrypted (or original dict if no encryption)
        """
        from config import Config

        if not Config.ENCRYPT_AT_REST or encryption_mgr is None:
            return data

        sensitive = self.SENSITIVE_FIELDS.get(table, [])
        if not sensitive:
            return data

        result = dict(data)
        for field in sensitive:
            if field in result and result[field] is not None:
                result[field] = self.store_encrypted(table, field, str(result[field]), encryption_mgr)
        return result

    def _maybe_decrypt_fields(self, table: str, row: dict, encryption_mgr=None) -> dict:
        """Decrypt sensitive fields in a row dict if encryption is enabled.

        Args:
            table: Table name to check against SENSITIVE_FIELDS
            row: Dict from a database row
            encryption_mgr: EncryptionManager instance (None = skip decryption)

        Returns:
            New dict with sensitive fields decrypted (or original dict if no encryption)
        """
        from config import Config

        if not Config.ENCRYPT_AT_REST or encryption_mgr is None:
            return row

        sensitive = self.SENSITIVE_FIELDS.get(table, [])
        if not sensitive:
            return row

        result = dict(row)
        for field in sensitive:
            if field in result and result[field] is not None:
                try:
                    result[field] = self.read_encrypted(table, field, result[field], encryption_mgr)
                except Exception as e:
                    # If decryption fails, the value may be plaintext (pre-encryption data)
                    logger.debug(f"Decryption skipped for {table}.{field}: {e}")
        return result

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get memory system statistics."""
        stats = {}
        for table in ["memories", "people", "events", "decisions", "tasks", "trades", "action_log"]:
            row = self.conn.execute(f"SELECT COUNT(*) as count FROM {table}").fetchone()
            stats[table] = row["count"]
        return stats

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
