"""
Learning Accelerator Module — Spaced repetition, knowledge tracking, misconception correction.

Tracks everything the user is learning (trading strategies, coding patterns, business concepts).
Implements SM-2 spaced repetition delivered via Telegram. Converts second brain captures into
flashcards automatically. Monthly learning report: what you've absorbed, what's fading, what to review.
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.learning")


class LearningAccelerator:
    """Tracks learning, generates flashcards, runs spaced repetition via Telegram."""

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create learning_topics and flashcards tables in SQLite if they don't exist."""
        conn = self.mira.sqlite.conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS learning_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT 'general',
                content TEXT NOT NULL,
                source TEXT DEFAULT 'manual',
                mastery_level REAL DEFAULT 0.0,
                times_reviewed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                easiness_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                next_review TIMESTAMP NOT NULL,
                last_reviewed TIMESTAMP,
                streak INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (topic_id) REFERENCES learning_topics(id)
            );

            CREATE INDEX IF NOT EXISTS idx_flashcards_next_review ON flashcards(next_review);
            CREATE INDEX IF NOT EXISTS idx_flashcards_topic ON flashcards(topic_id);
            CREATE INDEX IF NOT EXISTS idx_learning_topics_domain ON learning_topics(domain);
            CREATE INDEX IF NOT EXISTS idx_learning_topics_topic ON learning_topics(topic);
        """)
        conn.commit()
        logger.info("Learning Accelerator initialised — tables ready.")

    # ── Track Learning ───────────────────────────────────────────────

    async def track_learning(self, topic: str, content: str, source: str = "manual") -> dict:
        """Store a learning item and auto-classify its domain.

        Args:
            topic: The subject being learned (e.g. "fibonacci retracement")
            content: The actual content/notes captured
            source: Where it came from (telegram, capture, manual, etc.)

        Returns:
            dict with topic_id and domain.
        """
        # Use Haiku to classify the domain
        domain = await self._classify_domain(topic, content)

        conn = self.mira.sqlite.conn
        cursor = conn.execute(
            """INSERT INTO learning_topics (topic, domain, content, source)
               VALUES (?, ?, ?, ?)""",
            (topic, domain, content, source),
        )
        conn.commit()
        topic_id = cursor.lastrowid

        # Also store as a memory for cross-referencing
        self.mira.sqlite.store_memory(
            content=f"Learning: {topic} — {content[:200]}",
            category="learning",
            importance=3,
            source=source,
            tags=[topic, domain, "learning"],
        )

        self.mira.sqlite.log_action(
            "learning", "track_topic",
            f"topic={topic}, domain={domain}",
            {"topic_id": topic_id},
        )

        logger.info(f"Tracked learning topic #{topic_id}: {topic} [{domain}]")
        return {"topic_id": topic_id, "domain": domain}

    async def _classify_domain(self, topic: str, content: str) -> str:
        """Classify the learning domain using Haiku."""
        prompt = (
            f"Classify this learning topic into exactly one domain. "
            f"Return ONLY the domain name, nothing else.\n\n"
            f"Domains: trading, coding, business, crypto, finance, health, "
            f"productivity, leadership, general\n\n"
            f"Topic: {topic}\nContent: {content[:300]}"
        )
        result = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override="You are a classifier. Return ONLY a single domain word.",
            max_tokens=20,
            tier="fast",
            task_type="learning_classify",
        )
        domain = result.strip().lower().split()[0] if result.strip() else "general"
        valid = {"trading", "coding", "business", "crypto", "finance",
                 "health", "productivity", "leadership", "general"}
        return domain if domain in valid else "general"

    # ── Flashcard Generation ─────────────────────────────────────────

    async def generate_flashcards(self, topic: str, topic_id: int = None) -> list[dict]:
        """Use the brain to convert content into Q&A flashcards.

        If topic_id is provided, uses that specific topic's content.
        Otherwise, searches for the topic by name.

        Returns:
            List of created flashcard dicts with id, question, answer.
        """
        conn = self.mira.sqlite.conn

        if topic_id:
            row = conn.execute(
                "SELECT * FROM learning_topics WHERE id = ?", (topic_id,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM learning_topics WHERE topic LIKE ? ORDER BY created_at DESC LIMIT 1",
                (f"%{topic}%",),
            ).fetchone()

        if not row:
            logger.warning(f"No learning topic found for: {topic}")
            return []

        topic_id = row["id"]
        topic_name = row["topic"]
        content = row["content"]

        prompt = f"""Convert this learning content into 3-7 high-quality flashcards for spaced repetition.

Topic: {topic_name}
Content:
{content[:2000]}

Rules:
- Each card tests ONE concept
- Questions should require recall, not recognition
- Answers should be concise but complete
- Include "why" questions, not just "what"
- For trading/coding: include practical application questions

Return ONLY valid JSON array:
[
  {{"question": "...", "answer": "..."}},
  ...
]"""

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override="You are a flashcard generation system. Return ONLY a valid JSON array of flashcards.",
            max_tokens=2048,
            tier="standard",
            task_type="flashcard_generation",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            cards_data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse flashcard JSON: {response[:200]}")
            return []

        if not isinstance(cards_data, list):
            logger.error("Flashcard response is not a list")
            return []

        now = datetime.now().isoformat()
        created = []
        for card in cards_data:
            q = card.get("question", "").strip()
            a = card.get("answer", "").strip()
            if not q or not a:
                continue

            cursor = conn.execute(
                """INSERT INTO flashcards (topic_id, question, answer, next_review)
                   VALUES (?, ?, ?, ?)""",
                (topic_id, q, a, now),
            )
            created.append({
                "id": cursor.lastrowid,
                "question": q,
                "answer": a,
                "topic_id": topic_id,
            })

        conn.commit()

        self.mira.sqlite.log_action(
            "learning", "flashcards_generated",
            f"{len(created)} cards for '{topic_name}'",
            {"topic_id": topic_id, "card_count": len(created)},
        )

        logger.info(f"Generated {len(created)} flashcards for '{topic_name}'")
        return created

    # ── SM-2 Spaced Repetition ───────────────────────────────────────

    async def get_due_reviews(self, limit: int = 10) -> list[dict]:
        """Get flashcards due for review using SM-2 scheduling.

        Returns cards where next_review <= now, ordered by oldest first.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now().isoformat()

        rows = conn.execute(
            """SELECT f.*, lt.topic
               FROM flashcards f
               JOIN learning_topics lt ON f.topic_id = lt.id
               WHERE f.next_review <= ?
               ORDER BY f.next_review ASC
               LIMIT ?""",
            (now, limit),
        ).fetchall()

        return [dict(row) for row in rows]

    async def review_card(self, card_id: int, quality: int) -> dict:
        """Update a flashcard's interval based on recall quality using SM-2 algorithm.

        SM-2 Algorithm (simplified):
        - quality: 0-5 (0=complete blackout, 5=perfect recall)
        - If quality >= 3: card passes, interval grows
        - If quality < 3: card fails, reset to beginning

        Easiness Factor (EF) update:
        EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        EF is never less than 1.3

        Interval calculation:
        - rep 0: 1 day
        - rep 1: 6 days
        - rep n: previous_interval * EF

        Args:
            card_id: The flashcard ID
            quality: 0-5 rating of recall quality

        Returns:
            dict with next_review, interval_days, easiness_factor, streak
        """
        quality = max(0, min(5, quality))
        conn = self.mira.sqlite.conn

        row = conn.execute(
            "SELECT * FROM flashcards WHERE id = ?", (card_id,)
        ).fetchone()
        if not row:
            logger.warning(f"Flashcard #{card_id} not found")
            return {}

        ef = row["easiness_factor"]
        interval = row["interval_days"]
        reps = row["repetitions"]
        streak = row["streak"]

        # SM-2 easiness factor update
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ef = max(1.3, ef)

        if quality >= 3:
            # Correct response
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = math.ceil(interval * ef)
            reps += 1
            streak += 1
        else:
            # Incorrect — reset
            reps = 0
            interval = 1
            streak = 0

        now = datetime.now()
        next_review = (now + timedelta(days=interval)).isoformat()

        conn.execute(
            """UPDATE flashcards
               SET easiness_factor = ?, interval_days = ?, repetitions = ?,
                   next_review = ?, last_reviewed = ?, streak = ?
               WHERE id = ?""",
            (round(ef, 4), interval, reps, next_review, now.isoformat(), streak, card_id),
        )
        conn.commit()

        # Update the parent topic's mastery level
        await self._update_topic_mastery(row["topic_id"])

        result = {
            "card_id": card_id,
            "quality": quality,
            "easiness_factor": round(ef, 4),
            "interval_days": interval,
            "next_review": next_review,
            "streak": streak,
            "passed": quality >= 3,
        }

        logger.info(
            f"Reviewed card #{card_id}: q={quality}, "
            f"next in {interval}d, EF={ef:.2f}, streak={streak}"
        )
        return result

    async def _update_topic_mastery(self, topic_id: int):
        """Recalculate mastery level for a topic based on its flashcards.

        Mastery = weighted average of card performance:
        - Cards with long intervals and high EF contribute more
        - Recently failed cards pull mastery down
        """
        conn = self.mira.sqlite.conn
        rows = conn.execute(
            "SELECT easiness_factor, interval_days, repetitions, streak FROM flashcards WHERE topic_id = ?",
            (topic_id,),
        ).fetchall()

        if not rows:
            return

        total_score = 0.0
        for r in rows:
            # Normalize each card's performance to 0-1
            ef_norm = min((r["easiness_factor"] - 1.3) / (2.5 - 1.3), 1.0)
            interval_norm = min(r["interval_days"] / 60.0, 1.0)  # 60 days = fully learned
            rep_norm = min(r["repetitions"] / 5.0, 1.0)

            card_score = (ef_norm * 0.3 + interval_norm * 0.4 + rep_norm * 0.3)
            total_score += card_score

        mastery = round(total_score / len(rows), 4)
        total_reviews = sum(r["repetitions"] for r in rows)

        conn.execute(
            """UPDATE learning_topics SET mastery_level = ?, times_reviewed = ?,
               updated_at = ? WHERE id = ?""",
            (mastery, total_reviews, datetime.now().isoformat(), topic_id),
        )
        conn.commit()

    # ── Telegram Review Prompts ──────────────────────────────────────

    async def send_review_prompts(self):
        """Called by scheduler. Sends due flashcards via Telegram for review.

        Sends up to 5 cards at a time. Each card shows the question and waits
        for the user to self-rate their recall.
        """
        due_cards = await self.get_due_reviews(limit=5)

        if not due_cards:
            logger.debug("No flashcards due for review.")
            return

        if not hasattr(self.mira, "telegram"):
            logger.warning("Telegram not available — skipping review prompts.")
            return

        header = f"Time to review! {len(due_cards)} card{'s' if len(due_cards) != 1 else ''} due.\n"
        messages = [header]

        for card in due_cards:
            topic = card.get("topic", "Unknown")
            streak_indicator = ""
            if card["streak"] >= 5:
                streak_indicator = f" (streak: {card['streak']})"

            msg = (
                f"--- Card #{card['id']} [{topic}]{streak_indicator} ---\n\n"
                f"Q: {card['question']}\n\n"
                f"(Think of your answer, then reply with:\n"
                f"/review {card['id']} <0-5>\n"
                f"0=blackout, 1=wrong, 2=hard, 3=ok, 4=good, 5=perfect)"
            )
            messages.append(msg)

        full_message = "\n\n".join(messages)
        await self.mira.telegram.send(full_message)

        self.mira.sqlite.log_action(
            "learning", "review_prompts_sent",
            f"{len(due_cards)} cards sent for review",
            {"card_ids": [c["id"] for c in due_cards]},
        )

        logger.info(f"Sent {len(due_cards)} review prompts via Telegram.")

    # ── Misconception Detection ──────────────────────────────────────

    async def check_misconception(self, message: str) -> Optional[str]:
        """Check if the user's message contains a misconception about something
        they've been learning. Returns a correction if found, None otherwise.

        This is meant to be called during normal conversation processing.
        """
        # Get recent learning topics for context
        conn = self.mira.sqlite.conn
        topics = conn.execute(
            """SELECT topic, content, domain FROM learning_topics
               ORDER BY updated_at DESC LIMIT 15"""
        ).fetchall()

        if not topics:
            return None

        topic_context = "\n".join(
            f"- {t['topic']} ({t['domain']}): {t['content'][:150]}"
            for t in topics
        )

        prompt = f"""The user said: "{message}"

They are learning these topics:
{topic_context}

Does their message contain a factual error or misconception about any of these topics?

If YES: Return a brief, friendly correction. Be direct but not condescending.
Start with "Quick note:" and explain the correct concept.

If NO: Return exactly "NO_MISCONCEPTION"

Return ONLY the correction or "NO_MISCONCEPTION", nothing else."""

        result = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a knowledge checker. Identify misconceptions in the user's "
                "message based on their learning topics. Only flag clear factual errors, "
                "not opinions or preferences."
            ),
            max_tokens=300,
            tier="fast",
            task_type="misconception_check",
        )

        result = result.strip()
        if "NO_MISCONCEPTION" in result:
            return None

        logger.info(f"Misconception detected: {result[:100]}")
        self.mira.sqlite.log_action(
            "learning", "misconception_detected", result[:200],
        )
        return result

    # ── Resource Finder ──────────────────────────────────────────────

    async def find_resources(self, knowledge_gap: str) -> str:
        """Find the best resources for a specific knowledge gap.

        Uses the brain to suggest resources based on the user's learning style
        and existing knowledge.
        """
        # Get related topics for context
        conn = self.mira.sqlite.conn
        related = conn.execute(
            """SELECT topic, domain, mastery_level FROM learning_topics
               WHERE topic LIKE ? OR domain LIKE ?
               ORDER BY updated_at DESC LIMIT 5""",
            (f"%{knowledge_gap}%", f"%{knowledge_gap}%"),
        ).fetchall()

        related_context = ""
        if related:
            related_context = "Related topics already being learned:\n" + "\n".join(
                f"- {r['topic']} (mastery: {r['mastery_level']:.0%})"
                for r in related
            )

        prompt = f"""The user wants to learn about: {knowledge_gap}

{related_context}

Suggest 5-7 specific, high-quality learning resources. For each, include:
1. Resource name/title
2. Type (book, video, course, article, practice tool)
3. Why it's good for THIS gap specifically
4. Estimated time to complete
5. Difficulty level (beginner/intermediate/advanced)

Prioritise:
- Free resources over paid
- Practical over theoretical
- Resources relevant to trading, crypto, and tech (the user's interests)
- Interactive/hands-on over passive consumption

Be specific — real resource names, not generic categories."""

        result = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1500,
            tier="standard",
            task_type="resource_finder",
        )

        self.mira.sqlite.log_action(
            "learning", "resources_found", f"gap: {knowledge_gap}",
        )

        return result

    # ── Monthly Learning Report ──────────────────────────────────────

    async def generate_monthly_report(self) -> str:
        """Summarize learning progress for the past 30 days.

        Covers:
        - New topics tracked
        - Flashcard review stats (total reviews, average quality)
        - Topics with improving mastery
        - Topics that are fading (not reviewed, low mastery)
        - Recommendations for what to review and what to learn next
        """
        conn = self.mira.sqlite.conn
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

        # New topics in last 30 days
        new_topics = conn.execute(
            """SELECT topic, domain, mastery_level, created_at
               FROM learning_topics WHERE created_at >= ?
               ORDER BY created_at DESC""",
            (thirty_days_ago,),
        ).fetchall()

        # All topics with mastery info
        all_topics = conn.execute(
            """SELECT id, topic, domain, mastery_level, times_reviewed, updated_at
               FROM learning_topics ORDER BY mastery_level DESC"""
        ).fetchall()

        # Card review stats in last 30 days
        reviewed_cards = conn.execute(
            """SELECT COUNT(*) as total, AVG(easiness_factor) as avg_ef,
                      AVG(streak) as avg_streak, MAX(streak) as max_streak
               FROM flashcards WHERE last_reviewed >= ?""",
            (thirty_days_ago,),
        ).fetchone()

        # Cards due now (backlog)
        now = datetime.now().isoformat()
        overdue = conn.execute(
            "SELECT COUNT(*) as count FROM flashcards WHERE next_review <= ?",
            (now,),
        ).fetchone()

        # Topics fading: not reviewed in 14+ days with mastery < 0.5
        fading_topics = conn.execute(
            """SELECT topic, domain, mastery_level, updated_at
               FROM learning_topics
               WHERE updated_at < ? AND mastery_level < 0.5
               ORDER BY mastery_level ASC LIMIT 5""",
            ((datetime.now() - timedelta(days=14)).isoformat(),),
        ).fetchall()

        # Top mastered topics
        mastered = conn.execute(
            """SELECT topic, domain, mastery_level
               FROM learning_topics
               WHERE mastery_level >= 0.7
               ORDER BY mastery_level DESC LIMIT 5"""
        ).fetchall()

        # Total counts
        total_topics = conn.execute("SELECT COUNT(*) as c FROM learning_topics").fetchone()
        total_cards = conn.execute("SELECT COUNT(*) as c FROM flashcards").fetchone()

        report_data = {
            "period": "Last 30 days",
            "total_topics": total_topics["c"],
            "total_flashcards": total_cards["c"],
            "new_topics_count": len(new_topics),
            "new_topics": [
                {"topic": t["topic"], "domain": t["domain"],
                 "mastery": f"{t['mastery_level']:.0%}"}
                for t in new_topics
            ],
            "review_stats": {
                "cards_reviewed": reviewed_cards["total"] if reviewed_cards else 0,
                "avg_easiness": round(reviewed_cards["avg_ef"] or 0, 2) if reviewed_cards else 0,
                "avg_streak": round(reviewed_cards["avg_streak"] or 0, 1) if reviewed_cards else 0,
                "max_streak": reviewed_cards["max_streak"] or 0 if reviewed_cards else 0,
            },
            "overdue_cards": overdue["count"],
            "fading_topics": [
                {"topic": t["topic"], "domain": t["domain"],
                 "mastery": f"{t['mastery_level']:.0%}",
                 "last_reviewed": t["updated_at"]}
                for t in fading_topics
            ],
            "mastered_topics": [
                {"topic": t["topic"], "domain": t["domain"],
                 "mastery": f"{t['mastery_level']:.0%}"}
                for t in mastered
            ],
            "domain_breakdown": {},
        }

        # Domain breakdown
        for t in all_topics:
            d = t["domain"]
            if d not in report_data["domain_breakdown"]:
                report_data["domain_breakdown"][d] = {
                    "count": 0, "avg_mastery": 0.0, "total_mastery": 0.0,
                }
            report_data["domain_breakdown"][d]["count"] += 1
            report_data["domain_breakdown"][d]["total_mastery"] += t["mastery_level"]

        for d, info in report_data["domain_breakdown"].items():
            if info["count"] > 0:
                info["avg_mastery"] = f"{info['total_mastery'] / info['count']:.0%}"
            del info["total_mastery"]

        # Use the brain to write the narrative report
        prompt = f"""Generate a monthly learning report based on this data.

{json.dumps(report_data, indent=2, default=str)}

Write it as Mira delivering a learning progress update. Be direct and actionable.

Structure:
1. Headline stat (e.g. "You learned 12 new concepts this month")
2. What's sticking — topics with strong mastery
3. What's fading — topics that need attention before they slip
4. Review backlog status
5. Domain breakdown (where time is being spent)
6. Specific recommendations: what to review this week, what to learn next

Keep it conversational but data-driven. No fluff."""

        report = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=2048,
            tier="standard",
            task_type="learning_report",
        )

        self.mira.sqlite.log_action(
            "learning", "monthly_report",
            f"topics={total_topics['c']}, cards={total_cards['c']}",
        )

        return report

    # ── Bulk Import from Second Brain ────────────────────────────────

    async def import_from_memories(self, category: str = "learning", limit: int = 20) -> int:
        """Convert existing second brain captures into learning topics and flashcards.

        Scans recent memories tagged as 'learning' (or specified category) and
        creates topics + flashcards for any not yet tracked.

        Returns:
            Number of new topics created.
        """
        memories = self.mira.sqlite.search_memories(category=category, limit=limit)
        conn = self.mira.sqlite.conn
        created = 0

        for mem in memories:
            content = mem["content"]
            # Skip if already tracked (basic dedup by content prefix)
            existing = conn.execute(
                "SELECT id FROM learning_topics WHERE content LIKE ? LIMIT 1",
                (f"%{content[:80]}%",),
            ).fetchone()
            if existing:
                continue

            # Extract a topic name from the content
            topic_name = await self._extract_topic_name(content)
            if not topic_name:
                continue

            result = await self.track_learning(
                topic=topic_name,
                content=content,
                source=mem.get("source", "second_brain"),
            )

            # Auto-generate flashcards
            await self.generate_flashcards(topic_name, topic_id=result["topic_id"])
            created += 1

        logger.info(f"Imported {created} topics from second brain memories.")
        return created

    async def _extract_topic_name(self, content: str) -> Optional[str]:
        """Extract a concise topic name from learning content."""
        prompt = (
            f"Extract a concise topic name (3-6 words max) from this learning content. "
            f"Return ONLY the topic name, nothing else.\n\n"
            f"Content: {content[:400]}"
        )
        result = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override="Return ONLY a concise topic name (3-6 words). Nothing else.",
            max_tokens=30,
            tier="fast",
            task_type="topic_extraction",
        )
        name = result.strip().strip('"').strip("'")
        return name if name and len(name) < 100 else None

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get learning module statistics."""
        conn = self.mira.sqlite.conn
        now = datetime.now().isoformat()

        topics = conn.execute("SELECT COUNT(*) as c FROM learning_topics").fetchone()
        cards = conn.execute("SELECT COUNT(*) as c FROM flashcards").fetchone()
        due = conn.execute(
            "SELECT COUNT(*) as c FROM flashcards WHERE next_review <= ?", (now,)
        ).fetchone()
        avg_mastery = conn.execute(
            "SELECT AVG(mastery_level) as avg FROM learning_topics"
        ).fetchone()

        return {
            "total_topics": topics["c"],
            "total_flashcards": cards["c"],
            "cards_due": due["c"],
            "avg_mastery": round(avg_mastery["avg"] or 0, 4),
        }
