"""
Personal Life Module — Health, Finance, Travel, Family.

Health: Pixel Watch biometrics, habit tracking, weekly health summary
Finance: Unified income view, expense tracking, net worth, subscription audit
Travel: Research, price tracking, trip prep, itinerary management
Family: Important dates, gift intelligence, relationship health
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("mira.modules.personal")

MANILA_TZ = ZoneInfo("Asia/Manila")


class PersonalModule:
    """Manages personal life domains — health, finance, travel, family."""

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Set up personal module — create required tables."""
        self.mira.sqlite.conn.executescript("""
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                target_frequency TEXT NOT NULL DEFAULT 'daily',
                category TEXT DEFAULT 'general',
                streak INTEGER DEFAULT 0,
                last_completed TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS habit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            );

            CREATE TABLE IF NOT EXISTS important_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_name TEXT NOT NULL,
                date_type TEXT NOT NULL DEFAULT 'birthday',
                date TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_habits_name ON habits(name);
            CREATE INDEX IF NOT EXISTS idx_habit_log_habit_id ON habit_log(habit_id);
            CREATE INDEX IF NOT EXISTS idx_important_dates_date ON important_dates(date);
        """)
        self.mira.sqlite.conn.commit()
        logger.info("Personal module initialised (habits, habit_log, important_dates tables ready).")

    # ── Habit Tracking ────────────────────────────────────────────────

    async def add_habit(
        self,
        name: str,
        target_frequency: str = "daily",
        category: str = "general",
    ) -> dict:
        """Register a new habit to track.

        Args:
            name: Habit name (e.g., "gym", "meditation", "hydration").
            target_frequency: "daily" or "weekly".
            category: Grouping category (e.g., "health", "productivity").

        Returns:
            dict with the created habit record.
        """
        conn = self.mira.sqlite.conn
        try:
            cursor = conn.execute(
                "INSERT INTO habits (name, target_frequency, category) VALUES (?, ?, ?)",
                (name.lower().strip(), target_frequency, category),
            )
            conn.commit()
            habit_id = cursor.lastrowid

            self.mira.sqlite.log_action(
                "personal", "habit_added",
                f"name={name}, frequency={target_frequency}, category={category}",
            )
            logger.info(f"Habit added: {name} ({target_frequency}, {category})")

            return {
                "id": habit_id,
                "name": name.lower().strip(),
                "target_frequency": target_frequency,
                "category": category,
                "streak": 0,
                "last_completed": None,
            }

        except Exception as e:
            if "UNIQUE constraint" in str(e):
                logger.warning(f"Habit '{name}' already exists")
                row = conn.execute(
                    "SELECT * FROM habits WHERE name = ?", (name.lower().strip(),)
                ).fetchone()
                return dict(row) if row else {"error": f"Habit '{name}' already exists"}
            raise

    async def log_habit(self, habit_name: str) -> dict:
        """Mark a habit as completed today and update streak.

        Args:
            habit_name: Name of the habit to log.

        Returns:
            dict with updated habit info and streak.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)
        today = now.strftime("%Y-%m-%d")

        row = conn.execute(
            "SELECT * FROM habits WHERE name = ? COLLATE NOCASE",
            (habit_name.lower().strip(),),
        ).fetchone()

        if not row:
            return {"error": f"Habit '{habit_name}' not found. Add it first with add_habit()."}

        habit = dict(row)
        habit_id = habit["id"]

        # Check if already logged today
        already = conn.execute(
            "SELECT id FROM habit_log WHERE habit_id = ? AND completed_at = ?",
            (habit_id, today),
        ).fetchone()

        if already:
            return {
                "status": "already_logged",
                "habit": habit["name"],
                "streak": habit["streak"],
                "message": f"'{habit_name}' already logged for today.",
            }

        # Insert completion record
        conn.execute(
            "INSERT INTO habit_log (habit_id, completed_at) VALUES (?, ?)",
            (habit_id, today),
        )

        # Calculate streak
        last_completed = habit["last_completed"]
        old_streak = habit["streak"] or 0

        if habit["target_frequency"] == "daily":
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            if last_completed == yesterday or last_completed == today:
                new_streak = old_streak + 1
            else:
                new_streak = 1  # streak broken, start fresh
        else:
            # Weekly: streak increments if completed at least once per week
            one_week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            if last_completed and last_completed >= one_week_ago:
                new_streak = old_streak + 1
            else:
                new_streak = 1

        conn.execute(
            "UPDATE habits SET streak = ?, last_completed = ? WHERE id = ?",
            (new_streak, today, habit_id),
        )
        conn.commit()

        self.mira.sqlite.log_action(
            "personal", "habit_logged",
            f"habit={habit_name}, streak={new_streak}",
        )
        logger.info(f"Habit logged: {habit_name} (streak: {new_streak})")

        return {
            "status": "logged",
            "habit": habit["name"],
            "streak": new_streak,
            "date": today,
        }

    async def check_habits(self) -> list[str]:
        """Check habit consistency — analyse streaks, identify missed habits,
        generate contextual non-nagging reminders via Haiku.

        Returns:
            List of reminder strings (empty if all habits are on track).
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)
        today = now.strftime("%Y-%m-%d")

        rows = conn.execute("SELECT * FROM habits ORDER BY category, name").fetchall()
        if not rows:
            return []

        habits_summary = []
        missed = []

        for row in rows:
            habit = dict(row)
            name = habit["name"]
            freq = habit["target_frequency"]
            streak = habit["streak"] or 0
            last = habit["last_completed"]

            if freq == "daily":
                is_done_today = last == today
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                is_missed = not is_done_today
                days_since = (now.date() - datetime.strptime(last, "%Y-%m-%d").date()).days if last else None
            else:
                # Weekly
                week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
                done_this_week = conn.execute(
                    "SELECT COUNT(*) as cnt FROM habit_log WHERE habit_id = ? AND completed_at >= ?",
                    (habit["id"], week_start),
                ).fetchone()["cnt"]
                is_done_today = done_this_week > 0
                is_missed = not is_done_today
                days_since = (now.date() - datetime.strptime(last, "%Y-%m-%d").date()).days if last else None

            status = "done" if is_done_today else "pending"
            habits_summary.append({
                "name": name,
                "frequency": freq,
                "category": habit["category"],
                "streak": streak,
                "status": status,
                "days_since_last": days_since,
            })
            if is_missed:
                missed.append(name)

        if not missed:
            return []

        # Use brain with Haiku tier to generate contextual reminders
        current_hour = now.hour
        time_context = "morning" if current_hour < 12 else "afternoon" if current_hour < 17 else "evening"

        prompt = f"""Based on these habit tracking stats, generate short, contextual, non-nagging reminders
for the missed habits only. Be encouraging, not guilt-tripping. Consider it's {time_context} in Manila.

Habits overview:
{json.dumps(habits_summary, indent=2)}

Missed today: {', '.join(missed)}

Return a JSON array of reminder strings. Each reminder should be 1-2 sentences max.
Example: ["Still time for a quick meditation before bed — you're on a 12-day streak, don't break it!"]"""

        try:
            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a wellness companion. Return ONLY a valid JSON array of strings.",
                max_tokens=512,
                tier="fast",
                task_type="habit_check",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            reminders = json.loads(cleaned)
            if isinstance(reminders, list):
                self.mira.sqlite.log_action(
                    "personal", "habit_check",
                    f"missed={len(missed)}, reminders={len(reminders)}",
                )
                return reminders

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Habit check AI response parse failed: {e}")

        # Fallback: plain reminders
        return [f"Don't forget: {h}" for h in missed]

    async def get_habit_stats(self) -> list[dict]:
        """Return all habits with streaks, completion rates, and trends.

        Returns:
            List of dicts with habit name, streak, completion_rate, recent_trend, etc.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)

        rows = conn.execute("SELECT * FROM habits ORDER BY category, name").fetchall()
        stats = []

        for row in rows:
            habit = dict(row)
            habit_id = habit["id"]

            # Completion rate over last 30 days
            thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            completions_30d = conn.execute(
                "SELECT COUNT(*) as cnt FROM habit_log WHERE habit_id = ? AND completed_at >= ?",
                (habit_id, thirty_days_ago),
            ).fetchone()["cnt"]

            # Completion rate over last 7 days
            seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            completions_7d = conn.execute(
                "SELECT COUNT(*) as cnt FROM habit_log WHERE habit_id = ? AND completed_at >= ?",
                (habit_id, seven_days_ago),
            ).fetchone()["cnt"]

            if habit["target_frequency"] == "daily":
                target_30d = 30
                target_7d = 7
            else:
                target_30d = 4  # ~4 weeks
                target_7d = 1

            rate_30d = round((completions_30d / target_30d) * 100, 1) if target_30d else 0
            rate_7d = round((completions_7d / target_7d) * 100, 1) if target_7d else 0

            # Trend: compare last 7d rate to overall 30d rate
            if rate_7d > rate_30d + 10:
                trend = "improving"
            elif rate_7d < rate_30d - 10:
                trend = "declining"
            else:
                trend = "stable"

            stats.append({
                "name": habit["name"],
                "category": habit["category"],
                "target_frequency": habit["target_frequency"],
                "streak": habit["streak"] or 0,
                "last_completed": habit["last_completed"],
                "completions_7d": completions_7d,
                "completions_30d": completions_30d,
                "completion_rate_7d": min(rate_7d, 100.0),
                "completion_rate_30d": min(rate_30d, 100.0),
                "trend": trend,
                "created_at": habit["created_at"],
            })

        return stats

    # ── Health & Wellbeing ────────────────────────────────────────────

    async def process_biometric_data(self, data: dict):
        """Process biometric data from Pixel Watch — HRV, sleep, steps, HR."""
        self.mira.sqlite.store_memory(
            content=f"Biometric data: {data}",
            category="health",
            importance=2,
            source="pixel_watch",
            metadata=data,
        )

    async def generate_health_summary(self) -> str:
        """Weekly health summary — sleep, activity, trends, one actionable suggestion."""
        health_memories = self.mira.sqlite.search_memories(category="health", limit=50)
        return await self.mira.brain.think(
            f"Generate a weekly health summary based on this data:\n{health_memories}",
            include_history=False,
        )

    # ── Financial Guardian ───────────────────────────────────────────

    async def get_income_overview(self) -> dict:
        """Unified view: salary, trading P&L, crypto, side income."""
        return {
            "salary": 0,
            "trading_pnl": 0,
            "crypto_pnl": 0,
            "side_income": 0,
            "total": 0,
        }

    async def generate_monthly_pnl(self) -> str:
        """Monthly personal P&L — where money came from, where it went."""
        return "Monthly P&L generation coming in Phase 10."

    async def generate_net_worth_update(self) -> str:
        """Monday morning net worth update — all assets, all liabilities, trend."""
        return "Net worth update coming in Phase 10."

    async def audit_subscriptions(self) -> list[dict]:
        """Identify unused subscriptions for cancellation."""
        return []

    # ── Travel Management ────────────────────────────────────────────

    async def research_destination(self, destination: str) -> str:
        """Research flights, hotels, experiences, costs."""
        return await self.mira.brain.think(
            f"Research travel to {destination}: flights from Manila, "
            f"best hotels, experiences, estimated costs, best time to visit.",
            include_history=False,
        )

    async def generate_trip_brief(self, destination: str, dates: str) -> str:
        """Trip prep brief — weather, customs, packing, currency, contacts."""
        return await self.mira.brain.think(
            f"Generate trip prep brief for {destination} ({dates}): "
            f"weather, local customs, what to pack, currency, time zone, "
            f"key contacts in destination.",
            include_history=False,
        )

    # ── Important Dates Tracker ──────────────────────────────────────

    async def add_important_date(
        self,
        person_name: str,
        date_type: str,
        date: str,
        notes: str = "",
    ) -> dict:
        """Store a birthday, anniversary, work anniversary, etc.

        Args:
            person_name: Who this date belongs to.
            date_type: "birthday", "anniversary", "work_anniversary", etc.
            date: Date string in MM-DD format (recurring yearly) or YYYY-MM-DD.
            notes: Any additional context (e.g., "loves whisky", "allergic to flowers").

        Returns:
            dict with the created record.
        """
        conn = self.mira.sqlite.conn
        cursor = conn.execute(
            "INSERT INTO important_dates (person_name, date_type, date, notes) VALUES (?, ?, ?, ?)",
            (person_name, date_type, date.strip(), notes),
        )
        conn.commit()

        self.mira.sqlite.log_action(
            "personal", "important_date_added",
            f"person={person_name}, type={date_type}, date={date}",
        )
        logger.info(f"Important date added: {person_name} — {date_type} on {date}")

        return {
            "id": cursor.lastrowid,
            "person_name": person_name,
            "date_type": date_type,
            "date": date.strip(),
            "notes": notes,
        }

    async def check_important_dates(self) -> list[dict]:
        """Check for upcoming birthdays, anniversaries, events in the next 14 days.
        Uses brain with Haiku to suggest gift ideas or preparation.

        Returns:
            List of dicts with date info and AI-generated suggestions.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)

        rows = conn.execute("SELECT * FROM important_dates").fetchall()
        if not rows:
            return []

        upcoming = []

        for row in rows:
            record = dict(row)
            date_str = record["date"]

            try:
                # Support MM-DD (recurring) and YYYY-MM-DD (specific year)
                if len(date_str) == 5:
                    # MM-DD format — check against this year
                    this_year_date = datetime.strptime(
                        f"{now.year}-{date_str}", "%Y-%m-%d"
                    ).date()
                    # If date has passed this year, check next year
                    if this_year_date < now.date():
                        this_year_date = datetime.strptime(
                            f"{now.year + 1}-{date_str}", "%Y-%m-%d"
                        ).date()
                else:
                    this_year_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    # For specific-year dates in the past, skip
                    if this_year_date < now.date():
                        continue

                days_until = (this_year_date - now.date()).days

                if 0 <= days_until <= 14:
                    upcoming.append({
                        "person_name": record["person_name"],
                        "date_type": record["date_type"],
                        "date": this_year_date.isoformat(),
                        "days_until": days_until,
                        "notes": record["notes"],
                    })

            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse date '{date_str}' for {record['person_name']}: {e}")
                continue

        if not upcoming:
            return []

        # Sort by soonest first
        upcoming.sort(key=lambda x: x["days_until"])

        # Use brain with Haiku to suggest gift ideas / preparation
        prompt = f"""These important dates are coming up in the next 14 days.
For each one, suggest a practical gift idea or preparation step based on the date type and notes.
Keep suggestions concise (1-2 sentences each). Be specific, not generic.

Upcoming dates:
{json.dumps(upcoming, indent=2)}

Return a JSON array of objects, each with: person_name, date_type, date, days_until, suggestion"""

        try:
            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a thoughtful personal assistant. Return ONLY valid JSON.",
                max_tokens=1024,
                tier="fast",
                task_type="important_dates_check",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            suggestions = json.loads(cleaned)
            if isinstance(suggestions, list):
                self.mira.sqlite.log_action(
                    "personal", "important_dates_check",
                    f"upcoming={len(upcoming)}, suggestions={len(suggestions)}",
                )
                return suggestions

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Important dates AI suggestion parse failed: {e}")

        # Fallback: return upcoming without AI suggestions
        for item in upcoming:
            item["suggestion"] = f"{item['date_type'].replace('_', ' ').title()} in {item['days_until']} days — start preparing."
        return upcoming

    async def get_upcoming_dates(self, days: int = 30) -> list[dict]:
        """List all important dates in the next N days.

        Args:
            days: Number of days to look ahead (default 30).

        Returns:
            List of dicts with person_name, date_type, date, days_until, notes.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)

        rows = conn.execute("SELECT * FROM important_dates").fetchall()
        upcoming = []

        for row in rows:
            record = dict(row)
            date_str = record["date"]

            try:
                if len(date_str) == 5:
                    this_year_date = datetime.strptime(
                        f"{now.year}-{date_str}", "%Y-%m-%d"
                    ).date()
                    if this_year_date < now.date():
                        this_year_date = datetime.strptime(
                            f"{now.year + 1}-{date_str}", "%Y-%m-%d"
                        ).date()
                else:
                    this_year_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    if this_year_date < now.date():
                        continue

                days_until = (this_year_date - now.date()).days

                if 0 <= days_until <= days:
                    upcoming.append({
                        "person_name": record["person_name"],
                        "date_type": record["date_type"],
                        "date": this_year_date.isoformat(),
                        "days_until": days_until,
                        "notes": record["notes"],
                    })

            except (ValueError, TypeError):
                continue

        upcoming.sort(key=lambda x: x["days_until"])
        return upcoming

    # ── Presence Prompting ───────────────────────────────────────────

    async def check_presence(self) -> Optional[str]:
        """Detect if user has been heads-down too long (>4 hours continuous work
        without a break) by analysing the action_log. Generate a gentle nudge
        via Haiku if intervention is needed.

        Returns:
            Nudge text string, or None if no intervention needed.
        """
        conn = self.mira.sqlite.conn
        now = datetime.now(MANILA_TZ)
        four_hours_ago = (now - timedelta(hours=4)).isoformat()

        # Get actions from the last 4 hours
        rows = conn.execute(
            """SELECT * FROM action_log
               WHERE created_at >= ?
               ORDER BY created_at ASC""",
            (four_hours_ago,),
        ).fetchall()

        if not rows:
            # No activity in the last 4 hours — user might not be working
            return None

        actions = [dict(r) for r in rows]

        # Check for break indicators — if any action suggests a break, no nudge needed
        break_keywords = ["break", "walk", "lunch", "coffee", "snack", "rest", "away", "idle"]
        for action in actions:
            action_text = f"{action.get('action', '')} {action.get('outcome', '')}".lower()
            if any(kw in action_text for kw in break_keywords):
                return None

        # Check if there's continuous activity spanning 4+ hours
        first_action_time = actions[0].get("created_at", "")
        last_action_time = actions[-1].get("created_at", "")

        try:
            first_dt = datetime.fromisoformat(first_action_time)
            last_dt = datetime.fromisoformat(last_action_time)
            span_hours = (last_dt - first_dt).total_seconds() / 3600
        except (ValueError, TypeError):
            return None

        if span_hours < 3.5:
            # Less than 3.5 hours of activity — not yet time for a nudge
            return None

        # Count distinct action types to understand what user has been doing
        modules_active = list({a.get("module", "unknown") for a in actions})
        action_count = len(actions)

        current_hour = now.hour
        time_context = "morning" if current_hour < 12 else "afternoon" if current_hour < 17 else "evening"

        prompt = f"""The user has been working continuously for approximately {span_hours:.1f} hours
without a detected break. It's {time_context} in Manila ({now.strftime('%H:%M')}).

They've been active in: {', '.join(modules_active)} ({action_count} actions logged).

Generate a single gentle nudge (1-2 sentences) encouraging them to take a short break.
Be warm but not annoying. Vary the suggestion — could be stretching, water, a short walk,
looking away from the screen, etc. Don't be preachy.

Return ONLY the nudge text, no JSON or formatting."""

        try:
            nudge = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a caring wellness companion. Be brief and natural.",
                max_tokens=128,
                tier="fast",
                task_type="presence_check",
            )

            nudge_text = nudge.strip().strip('"')

            self.mira.sqlite.log_action(
                "personal", "presence_nudge",
                f"hours={span_hours:.1f}, nudge_sent=true",
            )
            logger.info(f"Presence nudge generated after {span_hours:.1f}h continuous work")

            return nudge_text

        except Exception as e:
            logger.warning(f"Presence check AI call failed: {e}")
            return None

    # ── Family & Relationships ───────────────────────────────────────

    async def check_relationship_health(self) -> list[dict]:
        """Analyse relationship health across all tracked contacts.

        Checks:
        - Time since last interaction (flags > 14 days for close, > 30 for others)
        - Conversation frequency trend (declining = warning)
        - Sentiment scoring via AI on recent interaction memories
        - Unmet commitments

        Returns:
            List of dicts with person info, health_score, and suggestions.
        """
        people = self.mira.sqlite.get_all_people()
        if not people:
            return []

        now = datetime.now(MANILA_TZ)
        flagged = []

        for person in people:
            name = person.get("name", "")
            rel_type = person.get("relationship_type", "unknown")
            last_interaction_str = person.get("last_interaction")
            conversation_count = person.get("conversation_count", 0) or 0
            commitments = []
            try:
                commitments = json.loads(person.get("commitments", "[]") or "[]")
            except (json.JSONDecodeError, TypeError):
                pass

            # Calculate days since last interaction
            days_since = None
            if last_interaction_str:
                try:
                    last_dt = datetime.fromisoformat(str(last_interaction_str))
                    days_since = (now - last_dt.replace(tzinfo=MANILA_TZ if last_dt.tzinfo is None else last_dt.tzinfo)).days
                except (ValueError, TypeError):
                    pass

            # Determine expected contact frequency by relationship type
            close_types = {"family", "partner", "close_friend", "mentor"}
            work_types = {"colleague", "manager", "report", "client"}
            if rel_type in close_types:
                max_gap_days = 14
            elif rel_type in work_types:
                max_gap_days = 21
            else:
                max_gap_days = 30

            # Score: 100 = healthy, lower = needs attention
            health_score = 100
            issues = []

            if days_since is not None:
                if days_since > max_gap_days * 2:
                    health_score -= 40
                    issues.append(f"No contact in {days_since} days (expected every {max_gap_days}d)")
                elif days_since > max_gap_days:
                    health_score -= 20
                    issues.append(f"Last contact {days_since} days ago")

            if commitments:
                health_score -= 10
                issues.append(f"{len(commitments)} unmet commitments")

            if conversation_count == 0 and days_since and days_since > 7:
                health_score -= 15
                issues.append("No recorded conversations")

            # Only flag people who need attention
            if health_score >= 80:
                continue

            flagged.append({
                "name": name,
                "relationship_type": rel_type,
                "health_score": max(0, health_score),
                "days_since_contact": days_since,
                "conversation_count": conversation_count,
                "issues": issues,
                "commitments": commitments[:3],
            })

        if not flagged:
            return []

        # Sort by health score (worst first)
        flagged.sort(key=lambda x: x["health_score"])

        # Use AI to generate suggestions for the top flagged relationships
        if len(flagged) > 0:
            prompt = f"""These relationships need attention. For each person, suggest a specific,
natural way to reconnect (not generic "send a message"). Consider their relationship type
and the issues flagged.

Flagged relationships:
{json.dumps(flagged[:8], indent=2, default=str)}

Return a JSON array of objects with: name, suggestion (1-2 sentences, specific and natural)"""

            try:
                response = await self.mira.brain.think(
                    message=prompt,
                    include_history=False,
                    system_override="You are a relationship advisor. Return ONLY valid JSON.",
                    max_tokens=1024,
                    tier="fast",
                    task_type="relationship_health",
                )

                cleaned = response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1]
                    cleaned = cleaned.rsplit("```", 1)[0]

                suggestions = json.loads(cleaned)
                if isinstance(suggestions, list):
                    suggestion_map = {s.get("name", ""): s.get("suggestion", "") for s in suggestions}
                    for f in flagged:
                        f["suggestion"] = suggestion_map.get(f["name"], "")

            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Relationship health AI suggestion failed: {e}")

        # Update health status in DB
        for f in flagged:
            try:
                health_label = "good" if f["health_score"] >= 60 else "needs_attention" if f["health_score"] >= 30 else "at_risk"
                self.mira.sqlite.conn.execute(
                    "UPDATE people SET relationship_health = ? WHERE name = ? COLLATE NOCASE",
                    (health_label, f["name"]),
                )
            except Exception:
                pass
        self.mira.sqlite.conn.commit()

        self.mira.sqlite.log_action(
            "personal", "relationship_health_check",
            f"flagged={len(flagged)} contacts needing attention",
        )

        return flagged
