"""
Reputation & Personal PR Module — monitors mentions, flags PR opportunities,
tracks competitors/people you admire, and identifies authority-building venues.

Autonomy level: NOTIFY — surfaces opportunities and intelligence, user decides action.
Runs weekly scan + on-demand queries via Telegram/dashboard.

Capabilities:
- Mention monitoring: your name, companies, projects across web/social
- PR opportunity flagging: podcast invites, speaking slots, guest posts, press
- Competitive intelligence: weekly digest on tracked people/orgs
- Authority building: finds forums, publications, communities for expertise placement
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.reputation")


# Entity types for tracking
ENTITY_TYPES = {
    "self": "Your own name and aliases",
    "company": "Companies you're associated with (e.g. Boldr)",
    "project": "Projects you lead or contribute to (e.g. Mira, DalyKraken)",
    "competitor": "People or companies you want to monitor",
    "admired": "People whose moves you want to track for inspiration",
}

# PR opportunity types
OPPORTUNITY_TYPES = {
    "podcast": "Podcast guest invitation",
    "speaking": "Speaking slot at event or conference",
    "guest_post": "Guest post or contributed article request",
    "press": "Press mention or interview request",
    "panel": "Panel discussion or webinar",
    "award": "Award nomination or recognition",
    "collaboration": "Collaboration or partnership opportunity",
    "other": "Other PR or visibility opportunity",
}


class ReputationMonitor:
    """Monitors reputation, flags PR opportunities, tracks competitive landscape."""

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create reputation-specific tables in SQLite."""
        self.mira.sqlite.conn.executescript("""
            -- Tracked entities: people, companies, projects to monitor
            CREATE TABLE IF NOT EXISTS tracked_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'competitor',
                keywords TEXT DEFAULT '[]',
                notes TEXT,
                is_active INTEGER DEFAULT 1,
                last_scanned_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Reputation alerts: mentions, opportunities, intelligence hits
            CREATE TABLE IF NOT EXISTS reputation_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL DEFAULT 'mention',
                entity_name TEXT,
                title TEXT NOT NULL,
                summary TEXT,
                source TEXT,
                source_url TEXT,
                relevance_score INTEGER DEFAULT 3,
                sentiment TEXT DEFAULT 'neutral',
                status TEXT DEFAULT 'new',
                action_taken TEXT,
                brain_assessment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_tracked_entities_type ON tracked_entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_tracked_entities_active ON tracked_entities(is_active);
            CREATE INDEX IF NOT EXISTS idx_reputation_alerts_type ON reputation_alerts(alert_type);
            CREATE INDEX IF NOT EXISTS idx_reputation_alerts_status ON reputation_alerts(status);
            CREATE INDEX IF NOT EXISTS idx_reputation_alerts_created ON reputation_alerts(created_at);
        """)
        self.mira.sqlite.conn.commit()
        logger.info("Reputation module tables initialised")

    # ── Entity Tracking ──────────────────────────────────────────────

    async def add_tracked_entity(
        self,
        name: str,
        entity_type: str = "competitor",
        keywords: list = None,
        notes: str = None,
    ) -> int:
        """Add a person, company, or project to the tracking list.

        Args:
            name: Display name of the entity
            entity_type: One of self, company, project, competitor, admired
            keywords: Additional search terms associated with this entity
            notes: Context about why you're tracking them

        Returns:
            ID of the new tracked entity row
        """
        if entity_type not in ENTITY_TYPES:
            logger.warning(f"Unknown entity type '{entity_type}', defaulting to 'competitor'")
            entity_type = "competitor"

        cursor = self.mira.sqlite.conn.execute(
            """INSERT INTO tracked_entities (name, entity_type, keywords, notes)
               VALUES (?, ?, ?, ?)""",
            (name, entity_type, json.dumps(keywords or []), notes),
        )
        self.mira.sqlite.conn.commit()

        self.mira.sqlite.log_action(
            "reputation",
            "add_tracked_entity",
            f"Added {entity_type}: {name}",
            {"entity_id": cursor.lastrowid, "keywords": keywords or []},
        )
        logger.info(f"Now tracking {entity_type} '{name}' (id={cursor.lastrowid})")
        return cursor.lastrowid

    def get_tracked_entities(self, entity_type: str = None, active_only: bool = True) -> list[dict]:
        """Get all tracked entities, optionally filtered by type."""
        conditions = []
        params = []

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)
        if active_only:
            conditions.append("is_active = 1")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.mira.sqlite.conn.execute(
            f"SELECT * FROM tracked_entities {where} ORDER BY entity_type, name", params
        ).fetchall()
        return [dict(row) for row in rows]

    def deactivate_entity(self, entity_id: int):
        """Stop tracking an entity without deleting its history."""
        self.mira.sqlite.conn.execute(
            "UPDATE tracked_entities SET is_active = 0, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), entity_id),
        )
        self.mira.sqlite.conn.commit()

    # ── Mention Scanning ─────────────────────────────────────────────

    async def scan_mentions(self, entity_name: str = None) -> dict:
        """Generate a web search strategy for mention scanning.

        Uses brain to craft optimal search queries for the entity.
        Actual web search execution requires API integration (Google Custom Search,
        SerpAPI, etc.) — this method prepares the strategy and logs the parameters.

        Args:
            entity_name: Specific entity to scan. If None, scans all active entities.

        Returns:
            Dict with search strategies per entity and any simulated results.
        """
        if entity_name:
            entities = self.mira.sqlite.conn.execute(
                "SELECT * FROM tracked_entities WHERE name = ? COLLATE NOCASE AND is_active = 1",
                (entity_name,),
            ).fetchall()
        else:
            entities = self.mira.sqlite.conn.execute(
                "SELECT * FROM tracked_entities WHERE is_active = 1"
            ).fetchall()

        if not entities:
            return {"status": "no_entities", "message": "No active entities to scan."}

        results = {}
        for entity in entities:
            entity = dict(entity)
            keywords = json.loads(entity.get("keywords", "[]"))

            # Ask brain to generate an optimal search strategy
            strategy = await self.mira.brain.think(
                message=f"""Generate a web monitoring strategy for tracking mentions of this entity.

Entity: {entity['name']}
Type: {entity['entity_type']}
Additional keywords: {', '.join(keywords) if keywords else 'none'}
Notes: {entity.get('notes') or 'none'}

Return a JSON object with:
- search_queries: list of 3-5 Google search queries optimised for finding recent mentions
- social_queries: list of 2-3 social media search terms (X/Twitter, LinkedIn)
- news_queries: list of 2-3 news-specific search terms
- alert_keywords: list of high-signal phrases that would indicate something noteworthy
- monitoring_priority: "high", "medium", or "low" based on entity type

Return ONLY valid JSON.""",
                include_history=False,
                system_override="You are a reputation monitoring strategist. Return ONLY valid JSON.",
                max_tokens=1024,
                tier="fast",
                task_type="reputation_scan_strategy",
            )

            # Parse the strategy
            try:
                cleaned = strategy.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1]
                    cleaned = cleaned.rsplit("```", 1)[0]
                parsed_strategy = json.loads(cleaned)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse scan strategy for {entity['name']}")
                parsed_strategy = {
                    "search_queries": [f'"{entity["name"]}"'],
                    "social_queries": [entity["name"]],
                    "news_queries": [entity["name"]],
                    "alert_keywords": [],
                    "monitoring_priority": "medium",
                }

            # Update last scanned timestamp
            self.mira.sqlite.conn.execute(
                "UPDATE tracked_entities SET last_scanned_at = ?, updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), datetime.now().isoformat(), entity["id"]),
            )
            self.mira.sqlite.conn.commit()

            results[entity["name"]] = {
                "entity_type": entity["entity_type"],
                "strategy": parsed_strategy,
                "scanned_at": datetime.now().isoformat(),
                "note": "Search strategy generated. Actual web search requires API integration.",
            }

        self.mira.sqlite.log_action(
            "reputation",
            "scan_mentions",
            f"Generated strategies for {len(results)} entities",
            {"entities": list(results.keys())},
        )

        return {"status": "strategies_generated", "entities_scanned": len(results), "results": results}

    # ── PR Opportunity Evaluation ────────────────────────────────────

    async def evaluate_pr_opportunity(
        self,
        opportunity_type: str,
        details: str,
        source: str = None,
    ) -> dict:
        """Evaluate a PR opportunity for fit, value, and recommended action.

        Args:
            opportunity_type: One of the OPPORTUNITY_TYPES keys
            details: Full description of the opportunity
            source: Where this came from (email, DM, website, etc.)

        Returns:
            Dict with assessment, score, and recommendation stored as a reputation alert.
        """
        if opportunity_type not in OPPORTUNITY_TYPES:
            opportunity_type = "other"

        # Pull user context for better evaluation
        people_context = self.mira.sqlite.get_all_people()[:10]
        recent_actions = self.mira.sqlite.get_daily_actions()

        assessment = await self.mira.brain.think(
            message=f"""Evaluate this PR opportunity for your user.

Opportunity type: {OPPORTUNITY_TYPES.get(opportunity_type, opportunity_type)}
Details: {details}
Source: {source or 'unknown'}

User context:
- Works at Boldr (BPO), senior operations/finance role
- Active trader (forex, crypto, prediction markets)
- Based in Manila, South African background
- Building AI projects (Mira, DalyKraken, DalyConnect)
- Interests: trading, crypto, F1, tech, AI, BPO operations

Evaluate:
1. Relevance (1-10): How well does this align with user's expertise and brand?
2. Reach (1-10): What's the potential audience/impact?
3. Effort (1-10, 10=very low effort): How much time/prep would this require?
4. Strategic value: Does this advance any long-term positioning goals?
5. Risks: Any reputational risks or downsides?
6. Recommendation: ACCEPT, CONSIDER, DECLINE, or NEED_MORE_INFO
7. Suggested response: If accepting, a brief outline of how to approach it

Return valid JSON with fields: relevance, reach, effort, strategic_value, risks,
recommendation, suggested_response, overall_score (1-10), reasoning""",
            include_history=False,
            tier="standard",
            task_type="pr_evaluation",
        )

        # Parse the assessment
        try:
            cleaned = assessment.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = {
                "relevance": 5,
                "reach": 5,
                "effort": 5,
                "recommendation": "CONSIDER",
                "reasoning": assessment,
                "overall_score": 5,
            }

        # Store as a reputation alert
        alert_id = self._store_alert(
            alert_type="pr_opportunity",
            entity_name="self",
            title=f"{OPPORTUNITY_TYPES.get(opportunity_type, opportunity_type)}: {details[:80]}",
            summary=parsed.get("reasoning", assessment[:500]),
            source=source,
            relevance_score=parsed.get("overall_score", 5),
            sentiment="positive",
            brain_assessment=json.dumps(parsed),
            metadata={"opportunity_type": opportunity_type, "full_details": details},
        )

        self.mira.sqlite.log_action(
            "reputation",
            "evaluate_pr_opportunity",
            parsed.get("recommendation", "CONSIDER"),
            {"alert_id": alert_id, "type": opportunity_type, "score": parsed.get("overall_score")},
        )

        return {
            "alert_id": alert_id,
            "assessment": parsed,
            "opportunity_type": opportunity_type,
            "evaluated_at": datetime.now().isoformat(),
        }

    # ── Competitive Intelligence ─────────────────────────────────────

    async def generate_competitive_update(self) -> dict:
        """Generate a weekly competitive intelligence digest.

        Pulls all tracked competitors and admired people, asks brain to
        synthesise what's noteworthy and what moves you should watch.

        Returns:
            Dict with the update text and metadata.
        """
        competitors = self.get_tracked_entities(entity_type="competitor")
        admired = self.get_tracked_entities(entity_type="admired")
        companies = self.get_tracked_entities(entity_type="company")

        if not competitors and not admired:
            return {
                "status": "no_entities",
                "message": "No competitors or admired people being tracked. Add some first.",
            }

        # Build entity profiles for context
        entity_profiles = []
        for e in competitors + admired:
            keywords = json.loads(e.get("keywords", "[]"))
            entity_profiles.append({
                "name": e["name"],
                "type": e["entity_type"],
                "keywords": keywords,
                "notes": e.get("notes", ""),
                "last_scanned": e.get("last_scanned_at"),
            })

        # Pull any recent reputation alerts for these entities
        entity_names = [e["name"] for e in competitors + admired]
        placeholders = ",".join("?" * len(entity_names))
        recent_alerts = []
        if entity_names:
            rows = self.mira.sqlite.conn.execute(
                f"""SELECT * FROM reputation_alerts
                    WHERE entity_name IN ({placeholders})
                    AND created_at >= DATE('now', '-7 days')
                    ORDER BY created_at DESC LIMIT 20""",
                entity_names,
            ).fetchall()
            recent_alerts = [dict(r) for r in rows]

        update = await self.mira.brain.think(
            message=f"""Generate a weekly competitive intelligence update.

Tracked entities:
{json.dumps(entity_profiles, indent=2, default=str)}

Recent alerts (last 7 days):
{json.dumps(recent_alerts, indent=2, default=str) if recent_alerts else 'None captured yet.'}

Your associated companies:
{json.dumps([dict(c) for c in companies], indent=2, default=str) if companies else 'None tracked yet.'}

Generate a concise competitive intelligence digest covering:
1. Key moves: What have these people/companies done this week that matters?
2. Trends: Any patterns across your competitive landscape?
3. Opportunities: Gaps or openings you could exploit based on competitor activity
4. Threats: Anything that could impact your positioning
5. Recommended actions: 1-3 specific things you should consider doing

Note: You may not have real-time data on all entities. Where you lack specific recent
information, note what SHOULD be monitored and provide general strategic observations
based on the entity profiles.

Tone: Sharp, analytical, no fluff. Like a weekly intel brief from a trusted strategist.""",
            include_history=False,
            tier="standard",
            task_type="competitive_intelligence",
        )

        # Store the update as an alert for reference
        alert_id = self._store_alert(
            alert_type="competitive_update",
            entity_name="competitive_landscape",
            title=f"Weekly Competitive Update — {datetime.now().strftime('%d %b %Y')}",
            summary=update[:500],
            relevance_score=4,
            brain_assessment=update,
        )

        self.mira.sqlite.log_action(
            "reputation",
            "competitive_update",
            "completed",
            {
                "competitors_tracked": len(competitors),
                "admired_tracked": len(admired),
                "alerts_referenced": len(recent_alerts),
                "alert_id": alert_id,
            },
        )

        return {
            "update": update,
            "competitors_tracked": len(competitors),
            "admired_tracked": len(admired),
            "recent_alerts": len(recent_alerts),
            "generated_at": datetime.now().isoformat(),
        }

    # ── Authority Building ───────────────────────────────────────────

    async def find_authority_opportunities(self, expertise_areas: list[str]) -> dict:
        """Identify communities, publications, and forums for authority building.

        Args:
            expertise_areas: List of topics where you want to build authority
                            e.g. ["BPO operations", "AI agents", "forex trading"]

        Returns:
            Dict with categorised opportunities and strategic recommendations.
        """
        if not expertise_areas:
            return {"status": "error", "message": "Provide at least one expertise area."}

        # Pull existing tracked entities for context
        self_entities = self.get_tracked_entities(entity_type="self")
        project_entities = self.get_tracked_entities(entity_type="project")

        analysis = await self.mira.brain.think(
            message=f"""Identify the best venues for building authority in these expertise areas.

Expertise areas: {', '.join(expertise_areas)}

User profile:
- Senior operations/finance at Boldr (BPO company)
- Active trader: forex, crypto, prediction markets
- Building AI projects: Mira (autonomous AI agent), DalyKraken (trading), DalyConnect
- Based in Manila, South African
- Current tracked entities: {json.dumps([dict(e) for e in self_entities + project_entities], default=str)}

For each expertise area, identify:
1. Online communities: Subreddits, Discord servers, Slack groups, forums where
   these topics are actively discussed and expertise is valued
2. Publications: Blogs, newsletters, magazines, websites that accept guest contributions
   or expert commentary in these areas
3. Events: Conferences, meetups, webinars (especially in Asia-Pacific) where
   speaking opportunities exist
4. Social media strategy: Specific hashtags, accounts to engage with, content angles
   that would build credibility
5. Quick wins: Low-effort, high-impact actions to establish presence this week

Return a JSON object with keys for each expertise area, each containing:
- communities: list of {{name, url_hint, relevance_note}}
- publications: list of {{name, type, audience_size_estimate, how_to_pitch}}
- events: list of {{name, frequency, region, how_to_get_involved}}
- social_angles: list of content ideas or engagement strategies
- quick_wins: list of 2-3 immediate actions

Return ONLY valid JSON.""",
            include_history=False,
            system_override=(
                "You are a personal brand and authority-building strategist. "
                "Return ONLY valid JSON with actionable, specific recommendations."
            ),
            max_tokens=3072,
            tier="standard",
            task_type="authority_building",
        )

        # Parse the analysis
        try:
            cleaned = analysis.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse authority opportunity analysis as JSON")
            parsed = {"raw_analysis": analysis}

        # Store recommendations as alerts
        for area in expertise_areas:
            self._store_alert(
                alert_type="authority_opportunity",
                entity_name="self",
                title=f"Authority building: {area}",
                summary=f"Opportunities identified for building authority in {area}",
                relevance_score=4,
                brain_assessment=json.dumps(parsed.get(area, parsed)),
                metadata={"expertise_area": area},
            )

        self.mira.sqlite.log_action(
            "reputation",
            "find_authority_opportunities",
            f"Analysed {len(expertise_areas)} areas",
            {"areas": expertise_areas},
        )

        return {
            "opportunities": parsed,
            "expertise_areas": expertise_areas,
            "generated_at": datetime.now().isoformat(),
        }

    # ── Weekly Report ────────────────────────────────────────────────

    async def get_weekly_reputation_report(self) -> str:
        """Generate a comprehensive weekly reputation and PR report.

        Combines: mention scan results, PR opportunities, competitive intelligence,
        and authority-building progress into a single digest.

        Returns:
            Formatted report string for Telegram/dashboard delivery.
        """
        # Gather all data for the report
        all_entities = self.get_tracked_entities()
        entity_summary = {}
        for e in all_entities:
            t = e["entity_type"]
            entity_summary[t] = entity_summary.get(t, 0) + 1

        # Recent alerts from last 7 days
        recent_alerts = self.mira.sqlite.conn.execute(
            """SELECT * FROM reputation_alerts
               WHERE created_at >= DATE('now', '-7 days')
               ORDER BY relevance_score DESC, created_at DESC"""
        ).fetchall()
        recent_alerts = [dict(r) for r in recent_alerts]

        # Categorise alerts
        alerts_by_type = {}
        for a in recent_alerts:
            t = a["alert_type"]
            alerts_by_type.setdefault(t, []).append(a)

        # PR opportunities pending review
        pending_opportunities = self.mira.sqlite.conn.execute(
            """SELECT * FROM reputation_alerts
               WHERE alert_type = 'pr_opportunity' AND status = 'new'
               ORDER BY relevance_score DESC"""
        ).fetchall()
        pending_opportunities = [dict(r) for r in pending_opportunities]

        # Generate the report using brain
        report = await self.mira.brain.think(
            message=f"""Generate Mira's weekly reputation and personal PR report.

Tracking overview:
{json.dumps(entity_summary, indent=2)}
Total entities tracked: {len(all_entities)}

Alerts this week: {len(recent_alerts)}
Alerts by type: {json.dumps({k: len(v) for k, v in alerts_by_type.items()}, indent=2)}

Alert details:
{json.dumps(recent_alerts[:15], indent=2, default=str)}

Pending PR opportunities:
{json.dumps(pending_opportunities, indent=2, default=str) if pending_opportunities else 'None pending.'}

Structure the report as:
1. **Reputation Pulse** — Overall status, any urgent items
2. **Mentions & Visibility** — What was detected, sentiment summary
3. **PR Opportunities** — Pending opportunities with recommendations
4. **Competitive Moves** — Key competitor/admired figure activity
5. **Authority Progress** — Status of authority-building efforts
6. **This Week's Actions** — 2-3 specific things to do this week

Tone: Strategic advisor giving a weekly brief. Sharp, concise, actionable.
If data is sparse (early days), note what needs to be set up and focus on strategy.""",
            include_history=False,
            tier="standard",
            task_type="reputation_weekly_report",
        )

        self.mira.sqlite.log_action(
            "reputation",
            "weekly_report",
            "completed",
            {
                "entities_tracked": len(all_entities),
                "alerts_this_week": len(recent_alerts),
                "pending_opportunities": len(pending_opportunities),
            },
        )

        return report

    # ── Alert Management ─────────────────────────────────────────────

    def _store_alert(
        self,
        alert_type: str,
        title: str,
        entity_name: str = None,
        summary: str = None,
        source: str = None,
        source_url: str = None,
        relevance_score: int = 3,
        sentiment: str = "neutral",
        brain_assessment: str = None,
        metadata: dict = None,
    ) -> int:
        """Store a reputation alert in the database."""
        cursor = self.mira.sqlite.conn.execute(
            """INSERT INTO reputation_alerts
               (alert_type, entity_name, title, summary, source, source_url,
                relevance_score, sentiment, brain_assessment, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert_type,
                entity_name,
                title,
                summary,
                source,
                source_url,
                relevance_score,
                sentiment,
                brain_assessment,
                json.dumps(metadata or {}),
            ),
        )
        self.mira.sqlite.conn.commit()
        return cursor.lastrowid

    def get_alerts(
        self,
        alert_type: str = None,
        status: str = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get reputation alerts with optional filters."""
        conditions = []
        params = []

        if alert_type:
            conditions.append("alert_type = ?")
            params.append(alert_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self.mira.sqlite.conn.execute(
            f"""SELECT * FROM reputation_alerts {where}
                ORDER BY relevance_score DESC, created_at DESC LIMIT ?""",
            params + [limit],
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_alert_reviewed(self, alert_id: int, action_taken: str = None):
        """Mark an alert as reviewed with optional action note."""
        self.mira.sqlite.conn.execute(
            """UPDATE reputation_alerts
               SET status = 'reviewed', action_taken = ?, reviewed_at = ?
               WHERE id = ?""",
            (action_taken, datetime.now().isoformat(), alert_id),
        )
        self.mira.sqlite.conn.commit()

    def dismiss_alert(self, alert_id: int):
        """Dismiss an alert."""
        self.mira.sqlite.conn.execute(
            "UPDATE reputation_alerts SET status = 'dismissed', reviewed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), alert_id),
        )
        self.mira.sqlite.conn.commit()

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get reputation module statistics."""
        entities = self.mira.sqlite.conn.execute(
            "SELECT entity_type, COUNT(*) as count FROM tracked_entities WHERE is_active = 1 GROUP BY entity_type"
        ).fetchall()

        alerts_new = self.mira.sqlite.conn.execute(
            "SELECT COUNT(*) as count FROM reputation_alerts WHERE status = 'new'"
        ).fetchone()

        alerts_week = self.mira.sqlite.conn.execute(
            "SELECT COUNT(*) as count FROM reputation_alerts WHERE created_at >= DATE('now', '-7 days')"
        ).fetchone()

        return {
            "tracked_entities": {dict(e)["entity_type"]: dict(e)["count"] for e in entities},
            "total_entities": sum(dict(e)["count"] for e in entities),
            "new_alerts": alerts_new["count"],
            "alerts_this_week": alerts_week["count"],
        }
