"""
Social Media Module — content generation, scheduling, posting across 6 platforms.

Autonomy level: FULL AUTO — posts on schedule, notifies after each post.
Persona is not designed upfront — it emerges from second brain data.

Platforms: X (Twitter), LinkedIn, Instagram, TikTok, YouTube, Facebook
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.social")


# Platform-specific configuration
PLATFORM_CONFIG = {
    "x": {
        "name": "X (Twitter)",
        "content_type": "Thoughts, market takes, sharp observations, threads",
        "frequency": "1-3x daily",
        "max_length": 280,
        "thread_max": 10,
    },
    "linkedin": {
        "name": "LinkedIn",
        "content_type": "Professional insights, Boldr/work wins, industry commentary",
        "frequency": "3-4x weekly",
        "max_length": 3000,
    },
    "instagram": {
        "name": "Instagram",
        "content_type": "Visual content, lifestyle, behind-the-scenes",
        "frequency": "4-5x weekly",
        "max_length": 2200,
    },
    "tiktok": {
        "name": "TikTok",
        "content_type": "Short-form video scripts",
        "frequency": "3-5x weekly",
    },
    "youtube": {
        "name": "YouTube",
        "content_type": "Long-form content — trading explainers, lifestyle, project updates",
        "frequency": "1-2x weekly",
    },
    "facebook": {
        "name": "Facebook",
        "content_type": "Community-oriented, broader audience, life updates",
        "frequency": "2-3x weekly",
        "max_length": 63206,
    },
}


class SocialModule:
    """Manages social media presence across all platforms."""

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Set up social media API connections and ensure content_queue table exists."""
        self._ensure_content_queue_table()
        logger.info("Social module initialised (API connections pending Phase 8)")

    def _ensure_content_queue_table(self):
        """Create the content_queue table in SQLite if it doesn't exist."""
        self.mira.sqlite.conn.executescript("""
            CREATE TABLE IF NOT EXISTS content_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                scheduled_at TIMESTAMP NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                posted_at TIMESTAMP,
                post_url TEXT,
                engagement_stats TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_content_queue_status ON content_queue(status);
            CREATE INDEX IF NOT EXISTS idx_content_queue_scheduled ON content_queue(scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_content_queue_platform ON content_queue(platform);
        """)
        self.mira.sqlite.conn.commit()
        logger.info("content_queue table ensured")

    # ── Content Generation ────────────────────────────────────────────

    async def generate_content(
        self,
        platform: str,
        topic: str = None,
        content_type: str = None,
    ) -> dict:
        """Generate platform-appropriate content from second brain."""
        config = PLATFORM_CONFIG.get(platform, {})

        # Pull relevant memories and voice patterns
        memories = self.mira.sqlite.get_recent_memories(20)

        prompt = f"""Generate a {platform} post.

Platform rules:
- Platform: {config.get('name', platform)}
- Content type: {config.get('content_type', 'general')}
- Max length: {config.get('max_length', 'no limit')} characters

Voice rules:
- English as primary language
- Authentic, not corporate. How the user actually talks.
- Topics: trading, crypto, F1, tech, AI, BPO, life in Manila, South Africa connections
- Same person across all platforms — different format, same voice

{"Topic: " + topic if topic else "Choose a topic based on recent memories and current events."}

Recent thoughts and memories for inspiration:
{chr(10).join(f'- {m["content"][:100]}' for m in memories[:10])}

Write ONLY the post text. No explanations or meta-commentary."""

        post_text = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1024,
        )

        return {
            "platform": platform,
            "content": post_text,
            "generated_at": datetime.now().isoformat(),
            "status": "draft",
        }

    # ── Queue Management (SQLite-backed) ──────────────────────────────

    async def queue_post(
        self,
        platform: str,
        content: str,
        scheduled_at: str = None,
    ) -> dict:
        """Add a post to the SQLite-backed publishing queue.

        Args:
            platform: Target platform (x, linkedin, instagram, etc.)
            content: Post text content.
            scheduled_at: ISO timestamp for when to post. Defaults to now + 1 hour.

        Returns:
            Dict with the queued post details including its ID.
        """
        if scheduled_at is None:
            scheduled_at = (datetime.now() + timedelta(hours=1)).isoformat()

        cursor = self.mira.sqlite.conn.execute(
            """INSERT INTO content_queue (platform, content, scheduled_at, status)
               VALUES (?, ?, ?, 'queued')""",
            (platform, content, scheduled_at),
        )
        self.mira.sqlite.conn.commit()
        post_id = cursor.lastrowid

        self.mira.sqlite.log_action(
            "social", f"queue_{platform}", f"post #{post_id} scheduled for {scheduled_at}",
            {"post_id": post_id, "content_preview": content[:200]},
        )
        logger.info(f"Queued post #{post_id} for {platform} at {scheduled_at}")

        return {
            "id": post_id,
            "platform": platform,
            "content": content,
            "scheduled_at": scheduled_at,
            "status": "queued",
        }

    async def get_pending_posts(self) -> list[dict]:
        """Return all queued posts not yet posted, ordered by scheduled_at."""
        rows = self.mira.sqlite.conn.execute(
            """SELECT * FROM content_queue
               WHERE status = 'queued'
               ORDER BY scheduled_at ASC"""
        ).fetchall()
        return [dict(row) for row in rows]

    async def get_post_history(self, platform: str = None, limit: int = 20) -> list[dict]:
        """View past posts, optionally filtered by platform.

        Args:
            platform: Filter to a specific platform, or None for all.
            limit: Max number of posts to return.

        Returns:
            List of post dicts ordered by most recent first.
        """
        if platform:
            rows = self.mira.sqlite.conn.execute(
                """SELECT * FROM content_queue
                   WHERE platform = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (platform, limit),
            ).fetchall()
        else:
            rows = self.mira.sqlite.conn.execute(
                """SELECT * FROM content_queue
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    async def process_queue(self):
        """Scheduler callback: check for posts due and attempt to publish them.

        Currently logs + marks as 'posted' since platform APIs aren't connected (Phase 8).
        Sends Telegram notification for each post processed.
        """
        now = datetime.now().isoformat()
        due_posts = self.mira.sqlite.conn.execute(
            """SELECT * FROM content_queue
               WHERE status = 'queued' AND scheduled_at <= ?
               ORDER BY scheduled_at ASC""",
            (now,),
        ).fetchall()

        if not due_posts:
            return

        for row in due_posts:
            post = dict(row)
            post_id = post["id"]
            platform = post["platform"]
            content = post["content"]

            # Phase 8: Actual API calls to each platform
            # For now, log the publish attempt and mark as posted
            logger.info(f"Publishing post #{post_id} to {platform}: {content[:80]}...")

            self.mira.sqlite.conn.execute(
                """UPDATE content_queue
                   SET status = 'posted', posted_at = ?
                   WHERE id = ?""",
                (datetime.now().isoformat(), post_id),
            )
            self.mira.sqlite.conn.commit()

            self.mira.sqlite.log_action(
                "social",
                f"post_{platform}",
                f"published post #{post_id}",
                {"content": content[:200]},
            )

            # Notify via Telegram
            if hasattr(self.mira, "telegram"):
                await self.mira.telegram.notify(
                    "social",
                    f"Posted to {PLATFORM_CONFIG.get(platform, {}).get('name', platform)}",
                    content[:200],
                )

        logger.info(f"Processed {len(due_posts)} due posts from queue")

    # ── Legacy publish (now uses queue) ───────────────────────────────

    async def publish_post(self, post: dict) -> dict:
        """Publish a post by adding it to the queue for immediate processing.

        This wraps queue_post with scheduled_at=now so the next process_queue()
        call picks it up immediately.
        """
        platform = post.get("platform", "x")
        content = post.get("content", "")

        queued = await self.queue_post(
            platform=platform,
            content=content,
            scheduled_at=datetime.now().isoformat(),  # due immediately
        )
        return {"status": "queued", "platform": platform, "queue_id": queued["id"]}

    # ── Engagement ────────────────────────────────────────────────────

    async def get_engagement_stats(self, platform: str = None) -> dict:
        """Get engagement metrics for posts."""
        # Phase 8: API calls to get stats
        return {"followers": 0, "engagement_rate": 0, "posts_this_week": 0}

    async def handle_engagement(self, platform: str, interaction: dict) -> Optional[str]:
        """Handle replies, comments — auto-respond to up to 50%."""
        # Phase 8: AI-powered community engagement
        return None
