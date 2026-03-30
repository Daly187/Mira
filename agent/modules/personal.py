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
        """Unified view: salary, trading P&L, crypto, side income.

        Pulls from:
        - Trades table for trading P&L (closed trades this month)
        - Action log for earning module activity
        - Preferences for salary figure
        """
        now = datetime.now(MANILA_TZ)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        conn = self.mira.sqlite.conn

        # Trading P&L this month
        trading_pnl = 0.0
        try:
            rows = conn.execute(
                "SELECT pnl FROM trades WHERE closed_at >= ? AND pnl IS NOT NULL",
                (month_start,),
            ).fetchall()
            trading_pnl = sum(r["pnl"] for r in rows)
        except Exception:
            pass

        # Earning module revenue (from action_log)
        side_income = 0.0
        try:
            rows = conn.execute(
                """SELECT outcome FROM action_log
                   WHERE module IN ('earning', 'freelance', 'consulting')
                     AND action LIKE '%revenue%' AND created_at >= ?""",
                (month_start,),
            ).fetchall()
            for r in rows:
                try:
                    val = float(r["outcome"].replace("$", "").replace(",", ""))
                    side_income += val
                except (ValueError, AttributeError):
                    pass
        except Exception:
            pass

        # Salary from preferences
        salary = 0.0
        try:
            sal_pref = self.mira.sqlite.get_preference("monthly_salary")
            if sal_pref:
                salary = float(sal_pref)
        except (ValueError, TypeError):
            pass

        total = salary + trading_pnl + side_income

        return {
            "salary": salary,
            "trading_pnl": round(trading_pnl, 2),
            "crypto_pnl": 0,  # Needs exchange API
            "side_income": round(side_income, 2),
            "total": round(total, 2),
            "month": now.strftime("%B %Y"),
        }

    async def generate_monthly_pnl(self) -> str:
        """Monthly personal P&L — where money came from, where it went.

        Aggregates income sources, API costs, and known expenses into
        a concise P&L report using AI to format and provide insights.
        """
        now = datetime.now(MANILA_TZ)
        income = await self.get_income_overview()

        # Get API costs this month
        api_costs = self.mira.sqlite.get_api_costs("month")
        total_api_cost = api_costs.get("total_cost", 0) if api_costs else 0

        # Get action count for activity level
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        conn = self.mira.sqlite.conn
        action_count = 0
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM action_log WHERE created_at >= ?",
                (month_start,),
            ).fetchone()
            action_count = row["cnt"] if row else 0
        except Exception:
            pass

        data = {
            "month": now.strftime("%B %Y"),
            "income": income,
            "expenses": {
                "api_costs": round(total_api_cost, 2),
                "total_known_expenses": round(total_api_cost, 2),
            },
            "net": round(income["total"] - total_api_cost, 2),
            "activity": {
                "total_actions": action_count,
                "mira_operational_days": now.day,
            },
        }

        prompt = f"""Generate a personal monthly P&L report.

{json.dumps(data, indent=2, default=str)}

Format as a concise financial summary:
1. Income breakdown (each source with amount)
2. Expenses breakdown
3. Net position
4. Key observations (trading performance, cost trends)
5. One recommendation for next month

If salary or some income sources show $0, note they need to be configured.
Keep it clean and financial — like a personal CFO report."""

        report = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1500,
            tier="standard",
            task_type="monthly_pnl",
        )

        self.mira.sqlite.log_action("personal", "monthly_pnl", f"generated for {now.strftime('%B %Y')}")
        return report

    async def generate_net_worth_update(self) -> str:
        """Monday morning net worth update — all assets, all liabilities, trend.

        Uses income overview + trading positions for a snapshot.
        """
        income = await self.get_income_overview()
        open_trades = self.mira.sqlite.get_open_trades()

        data = {
            "date": datetime.now(MANILA_TZ).strftime("%A, %B %d, %Y"),
            "income_this_month": income,
            "open_positions": len(open_trades),
            "note": "Full net worth tracking requires bank API connections. "
                    "This is a partial view based on available data.",
        }

        prompt = f"""Generate a Monday morning net worth / financial health snapshot.

{json.dumps(data, indent=2, default=str)}

Keep it brief (5-10 lines). Highlight:
1. Month-to-date income
2. Open trading positions
3. Any concerns or actions needed
4. What data sources are missing for a complete picture"""

        report = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=800,
            tier="fast",
            task_type="net_worth_update",
        )

        self.mira.sqlite.log_action("personal", "net_worth_update", "delivered")
        return report

    async def audit_subscriptions(self) -> list[dict]:
        """Identify subscriptions from memory and action log patterns.

        Scans memories and emails for recurring payment indicators
        and surfaces them for review.
        """
        conn = self.mira.sqlite.conn
        subscriptions = []

        # Search memories for subscription-related content
        sub_keywords = ["subscription", "monthly", "renewed", "billing", "charged",
                        "recurring", "plan", "premium", "pro plan"]
        for kw in sub_keywords:
            try:
                rows = conn.execute(
                    "SELECT content, source, created_at FROM memories WHERE content LIKE ? LIMIT 5",
                    (f"%{kw}%",),
                ).fetchall()
                for r in rows:
                    content = dict(r)["content"]
                    # Avoid duplicates
                    if not any(content[:50] in s.get("source_text", "") for s in subscriptions):
                        subscriptions.append({
                            "source_text": content[:200],
                            "detected_via": kw,
                            "source": dict(r).get("source", "memory"),
                            "date": dict(r).get("created_at", ""),
                        })
            except Exception:
                pass

        if not subscriptions:
            return []

        # Use AI to extract structured subscription data
        prompt = f"""Extract subscription/recurring payment information from these memory snippets.

{json.dumps(subscriptions[:15], indent=2, default=str)}

Return a JSON array of objects with:
- service: name of the service
- estimated_cost: monthly cost if mentioned (null if unknown)
- category: one of [streaming, productivity, cloud, finance, health, other]
- still_needed: true/false/unknown — based on context, does user likely still need this?
- recommendation: one sentence — keep, cancel, or review

Only include items that are clearly subscriptions or recurring payments."""

        try:
            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a financial analyst. Return ONLY valid JSON array.",
                max_tokens=1024,
                tier="fast",
                task_type="subscription_audit",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            result = json.loads(cleaned)
            if isinstance(result, list):
                self.mira.sqlite.log_action(
                    "personal", "subscription_audit",
                    f"found {len(result)} subscriptions",
                )
                return result

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Subscription audit AI parse failed: {e}")

        return subscriptions

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

    # ── Gift Intelligence ──────────────────────────────────────────────

    async def suggest_gift(self, person_name: str) -> str:
        """Generate personalised gift suggestions based on everything Mira knows.

        Pulls from:
        - Person's key_facts in CRM
        - Conversation memories mentioning this person
        - Important dates and past gift history
        - Semantic memory search for preferences

        Returns:
            AI-generated gift suggestions with reasoning.
        """
        # 1. Get person data from CRM
        person = self.mira.sqlite.get_person(person_name)
        person_data = dict(person) if person else {"name": person_name}

        # Parse key_facts
        key_facts = []
        try:
            key_facts = json.loads(person_data.get("key_facts", "[]") or "[]")
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Search memories for preferences, interests, hobbies
        memories = self.mira.sqlite.search_memories(query=person_name, limit=10)
        memory_texts = [m.get("content", "")[:200] for m in memories]

        # 3. Semantic search for deeper context
        vector = getattr(self.mira, "vector", None)
        semantic_results = []
        if vector:
            try:
                results = vector.search(f"{person_name} likes interests hobbies", n_results=5)
                semantic_results = [r.get("content", "")[:200] for r in results]
            except Exception:
                pass

        # 4. Check important dates
        important_dates = []
        try:
            conn = self.mira.sqlite.conn
            rows = conn.execute(
                "SELECT * FROM important_dates WHERE person_name LIKE ? COLLATE NOCASE",
                (f"%{person_name}%",),
            ).fetchall()
            important_dates = [dict(r) for r in rows]
        except Exception:
            pass

        prompt = f"""Generate thoughtful, personalised gift suggestions for {person_name}.

Person data:
- Relationship: {person_data.get('relationship_type', 'unknown')}
- Key facts: {json.dumps(key_facts)}
- Important dates: {json.dumps(important_dates, default=str)}

Relevant memories:
{chr(10).join(f'- {m}' for m in memory_texts[:5])}

Additional context:
{chr(10).join(f'- {s}' for s in semantic_results[:3])}

Rules:
1. Suggest 3-5 specific gift ideas (not generic "a nice book")
2. Include price range for each ($, $$, $$$)
3. Explain WHY each gift fits this person specifically
4. Include at least one experience-based gift (not physical)
5. Consider their relationship type when choosing formality level
6. If you don't have enough info, suggest gifts that help you learn more about them

Format each as: Gift name ($range) — Why it fits"""

        result = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1024,
            tier="standard",
            task_type="gift_suggestion",
        )

        self.mira.sqlite.log_action(
            "personal", "gift_suggestion", f"for {person_name}",
        )
        return result

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

    # ── Competitive Intelligence ────────────────────────────────────

    async def run_competitive_intelligence(self) -> str:
        """Weekly competitive intelligence scan.

        Pulls recent memories tagged with competitor names, searches the
        knowledge graph for company/industry connections, and generates a
        concise report of notable moves, threats, and opportunities.

        Returns:
            Formatted competitive intelligence report string.
        """
        # 1. Pull competitor-related memories from the last 7 days
        cutoff = (datetime.now(MANILA_TZ) - timedelta(days=7)).isoformat()
        competitor_keywords = []
        try:
            raw = self.mira.sqlite.get_preference("competitor_keywords")
            if raw:
                competitor_keywords = [k.strip() for k in raw.split(",") if k.strip()]
        except Exception:
            pass

        if not competitor_keywords:
            competitor_keywords = ["competitor", "rival", "market share", "industry",
                                   "launched", "acquired", "funding", "partnership"]

        # Search memories for competitor signals
        competitor_memories = []
        for kw in competitor_keywords[:10]:
            try:
                results = self.mira.sqlite.search_memories(query=kw, limit=5)
                for r in results:
                    created = r.get("created_at", "")
                    if created >= cutoff:
                        competitor_memories.append(r)
            except Exception:
                pass

        # 2. Search semantic memory for broader signals
        vector = getattr(self.mira, "vector", None)
        semantic_signals = []
        if vector:
            try:
                results = vector.search(
                    "competitor news industry moves market changes",
                    n_results=10,
                )
                for r in results:
                    created = r.get("created_at", "")
                    if created >= cutoff:
                        semantic_signals.append(r.get("content", "")[:200])
            except Exception:
                pass

        # 3. Check knowledge graph for company connections
        graph = getattr(self.mira, "graph", None)
        graph_insights = []
        if graph:
            try:
                company_nodes = graph.find_nodes(label_contains="company")
                for node in company_nodes[:10]:
                    connections = graph.get_connections(node["id"], depth=1)
                    if connections:
                        graph_insights.append({
                            "entity": node.get("label", ""),
                            "connections": len(connections),
                        })
            except Exception:
                pass

        # 4. Pull recent action_log entries related to industry/market
        market_actions = []
        try:
            rows = self.mira.sqlite.conn.execute(
                """SELECT action, outcome, created_at FROM action_log
                   WHERE created_at >= ?
                     AND (action LIKE '%market%' OR action LIKE '%trade%'
                          OR action LIKE '%polymarket%' OR action LIKE '%news%')
                   ORDER BY created_at DESC LIMIT 15""",
                (cutoff,),
            ).fetchall()
            market_actions = [dict(r) for r in rows]
        except Exception:
            pass

        # Deduplicate memories by content
        seen = set()
        unique_memories = []
        for m in competitor_memories:
            content = m.get("content", "")[:100]
            if content not in seen:
                seen.add(content)
                unique_memories.append(m.get("content", "")[:300])

        if not unique_memories and not semantic_signals and not market_actions:
            return "No competitive intelligence signals detected this week. Consider adding competitor keywords in settings (competitor_keywords preference)."

        prompt = f"""Generate a weekly competitive intelligence briefing.

Data sources:
- Memory signals ({len(unique_memories)} items): {json.dumps(unique_memories[:10], default=str)}
- Semantic signals ({len(semantic_signals)} items): {json.dumps(semantic_signals[:5], default=str)}
- Knowledge graph entities: {json.dumps(graph_insights[:5], default=str)}
- Market actions this week: {json.dumps(market_actions[:10], default=str)}

Format:
1. Executive Summary (2-3 sentences)
2. Key Competitor Moves (bullet points — what happened, why it matters)
3. Market Trends (patterns across data sources)
4. Threats (anything that could impact our position)
5. Opportunities (gaps or advantages to exploit)
6. Recommended Actions (specific, actionable next steps)

Be direct and specific. If data is thin, say so — don't fabricate intelligence.
Focus on signals that require action or awareness."""

        report = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=2000,
            tier="standard",
            task_type="competitive_intelligence",
        )

        self.mira.sqlite.log_action(
            "personal", "competitive_intelligence",
            f"weekly report generated ({len(unique_memories)} memory signals, {len(semantic_signals)} semantic signals)",
        )

        return report
