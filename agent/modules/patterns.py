"""
Pattern Recognition Engine — analyses accumulated memory to surface insights.

Runs weekly, delivers insights in the weekly review (not as interruptions).
Patterns detected:
- Performance patterns (trading + sleep/energy correlation)
- Energy patterns (time-of-day productivity)
- Habit patterns (gym, sleep, consistency)
- Relationship patterns (contact frequency, declining relationships)
- Work patterns (EOW summary length vs compliance items)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.patterns")


class PatternEngine:
    """Analyses memory to surface patterns you haven't noticed."""

    def __init__(self, mira):
        self.mira = mira

    async def run_weekly_analysis(self) -> dict:
        """Run full pattern analysis. Called weekly."""
        logger.info("Running weekly pattern analysis...")

        # Gather data from the last 7 days
        recent_memories = self.mira.sqlite.search_memories(limit=200)
        recent_trades = self.mira.sqlite.get_trade_history(limit=50)
        recent_decisions = self.mira.sqlite.conn.execute(
            "SELECT * FROM decisions ORDER BY decided_at DESC LIMIT 30"
        ).fetchall()
        recent_actions = self.mira.sqlite.conn.execute(
            "SELECT * FROM action_log WHERE created_at >= DATE('now', '-7 days') ORDER BY created_at"
        ).fetchall()
        all_people = self.mira.sqlite.get_all_people()

        analysis_data = {
            "memories_count": len(recent_memories),
            "memory_categories": self._count_categories(recent_memories),
            "trades_count": len(recent_trades),
            "trades_pnl": sum(t.get("pnl", 0) or 0 for t in recent_trades if t.get("pnl")),
            "decisions_count": len(recent_decisions),
            "actions_count": len(recent_actions),
            "people_count": len(all_people),
            "recent_memories_sample": [m["content"][:100] for m in recent_memories[:20]],
            "trade_summary": self._summarise_trades(recent_trades),
            "relationship_health": self._check_relationships(all_people),
            "action_breakdown": self._action_breakdown(recent_actions),
        }

        # Use Claude to find patterns
        insights = await self.mira.brain.think(
            message=f"""Analyse this week's data and identify patterns the user might not have noticed.

Data:
{json.dumps(analysis_data, indent=2, default=str)}

Look for:
1. Performance patterns — are there correlations between activity and outcomes?
2. Energy patterns — when are they most/least productive?
3. Habit patterns — any consistency changes or declining habits?
4. Relationship patterns — anyone they haven't spoken to who usually gets monthly contact?
5. Work patterns — any unusual workload or focus shifts?
6. Trading patterns — any strategy or timing patterns in wins/losses?

Be specific and data-driven. Give 3-5 actionable insights.
Don't pad with generic advice — only surface genuine patterns from the data.""",
            include_history=False,
            tier="standard",
            task_type="pattern_analysis",
        )

        self.mira.sqlite.log_action("patterns", "weekly_analysis", "completed")

        return {
            "insights": insights,
            "data_points_analysed": sum(analysis_data[k] for k in analysis_data if isinstance(analysis_data[k], int)),
            "generated_at": datetime.now().isoformat(),
        }

    async def generate_weekly_review(self) -> str:
        """Generate the full weekly review delivered via Telegram."""
        analysis = await self.run_weekly_analysis()

        review = await self.mira.brain.think(
            message=f"""Generate Mira's weekly review. This is delivered every Sunday evening.
It should be reflective, honest, and genuinely useful.

Pattern analysis results:
{analysis['insights']}

Data points analysed: {analysis['data_points_analysed']}

Structure:
1. Week in brief — what happened (2-3 sentences)
2. Patterns noticed — the insights from analysis (the most valuable part)
3. Wins — what went well
4. Watch — what needs attention
5. Suggestion — one specific, actionable thing for next week

Tone: More reflective than the daily briefing. Honest assessment. Like a trusted advisor
giving you the honest weekly debrief you'd never do yourself.""",
            include_history=False,
            tier="standard",
            task_type="weekly_review",
        )

        return review

    def _count_categories(self, memories: list) -> dict:
        counts = {}
        for m in memories:
            cat = m.get("category", "general")
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _summarise_trades(self, trades: list) -> dict:
        if not trades:
            return {"total": 0}

        closed = [t for t in trades if t.get("pnl") is not None]
        return {
            "total": len(trades),
            "closed": len(closed),
            "total_pnl": sum(t["pnl"] for t in closed),
            "winners": len([t for t in closed if t["pnl"] > 0]),
            "losers": len([t for t in closed if t["pnl"] <= 0]),
            "instruments": list(set(t.get("instrument", "") for t in trades)),
        }

    def _check_relationships(self, people: list) -> list:
        """Flag relationships that may need attention."""
        flagged = []
        now = datetime.now()
        for p in people:
            last = p.get("last_interaction")
            if not last:
                continue
            try:
                last_dt = datetime.fromisoformat(last)
                days_since = (now - last_dt).days
                if days_since > 30 and p.get("relationship_type") in ("personal", "family"):
                    flagged.append({
                        "name": p["name"],
                        "type": p["relationship_type"],
                        "days_since_contact": days_since,
                    })
            except (ValueError, TypeError):
                continue
        return flagged

    def _action_breakdown(self, actions: list) -> dict:
        breakdown = {}
        for a in actions:
            module = a["module"] if isinstance(a, dict) else a[1]
            breakdown[module] = breakdown.get(module, 0) + 1
        return breakdown
