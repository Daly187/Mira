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
