"""
Negotiation Coach Module — Pre-negotiation research, playbook generation,
real-time tactical advice, and post-negotiation review.

Spec reference: Section 11.3

Capabilities:
- Pre-negotiation research: full brief on counterparty, leverage, constraints, history
- Scenario planning: 3 likely positions they'll take and your response to each
- Written negotiation playbook with BATNA analysis
- Real-time tactical advice via Telegram during the negotiation
- Post-negotiation review: what worked, what didn't, lessons stored in memory
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger("mira.modules.negotiation")


class NegotiationCoach:
    """Negotiation preparation, live coaching, and post-mortem analysis."""

    def __init__(self, mira):
        self.mira = mira
        self._ensure_table()

    # ── Database Setup ───────────────────────────────────────────────

    def _ensure_table(self):
        """Create the negotiations table if it doesn't exist."""
        self.mira.sqlite.conn.executescript("""
            CREATE TABLE IF NOT EXISTS negotiations (
                id TEXT PRIMARY KEY,
                counterparty TEXT NOT NULL,
                context TEXT,
                stakes TEXT,
                goals TEXT DEFAULT '[]',
                constraints TEXT DEFAULT '[]',
                brief TEXT,
                playbook TEXT,
                status TEXT DEFAULT 'preparing',
                outcome TEXT,
                review TEXT,
                lessons_learned TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_negotiations_status
                ON negotiations(status);
            CREATE INDEX IF NOT EXISTS idx_negotiations_counterparty
                ON negotiations(counterparty);
            CREATE INDEX IF NOT EXISTS idx_negotiations_created
                ON negotiations(created_at);
        """)
        self.mira.sqlite.conn.commit()
        logger.info("Negotiations table ready")

    # ── Helper: persist updates ──────────────────────────────────────

    def _update_negotiation(self, negotiation_id: str, **fields):
        """Update one or more columns on a negotiation row."""
        fields["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [negotiation_id]
        self.mira.sqlite.conn.execute(
            f"UPDATE negotiations SET {set_clause} WHERE id = ?", values
        )
        self.mira.sqlite.conn.commit()

    def _get_negotiation(self, negotiation_id: str) -> Optional[dict]:
        """Fetch a negotiation row by ID."""
        row = self.mira.sqlite.conn.execute(
            "SELECT * FROM negotiations WHERE id = ?", (negotiation_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── 1. Pre-Negotiation Research Brief ────────────────────────────

    async def prepare_brief(
        self,
        counterparty: str,
        context: str,
        stakes: str,
    ) -> dict:
        """Generate a comprehensive pre-negotiation research brief.

        Uses Opus tier — this is high-stakes strategic work.

        Args:
            counterparty: Who you're negotiating with (person, company, role).
            context: What the negotiation is about, background information.
            stakes: What's at risk — financial, relational, strategic.

        Returns:
            dict with negotiation_id and the full brief text.
        """
        negotiation_id = uuid.uuid4().hex[:12]

        # Pull any existing knowledge about the counterparty from memory
        people_context = self.mira.sqlite.get_person(counterparty)
        related_memories = self.mira.sqlite.search_memories(
            query=counterparty, limit=10
        )

        memory_block = ""
        if people_context:
            memory_block += f"\nKnown info about {counterparty}:\n{json.dumps(people_context, indent=2, default=str)}\n"
        if related_memories:
            memory_block += "\nRelated memories:\n"
            for mem in related_memories:
                memory_block += f"- [{mem.get('category')}] {mem.get('content')}\n"

        prompt = f"""Prepare a comprehensive pre-negotiation research brief.

COUNTERPARTY: {counterparty}
CONTEXT: {context}
STAKES: {stakes}
{memory_block}

Structure your brief as follows:

1. COUNTERPARTY PROFILE
   - Who they are, their role, their authority level
   - Their likely priorities, incentives, and pressure points
   - Known negotiation style and past behaviour (if available)

2. POWER DYNAMICS & LEVERAGE
   - Their leverage over us
   - Our leverage over them
   - External factors that shift the balance (deadlines, alternatives, market conditions)

3. THEIR LIKELY CONSTRAINTS
   - Budget limits, approval chains, policy restrictions
   - Time pressure, reputational concerns, competing commitments
   - What they probably CANNOT concede even if they wanted to

4. HISTORICAL CONTEXT
   - Previous interactions, deals, or negotiations with this party
   - Patterns in their behaviour — what they've done before in similar situations
   - Relationship trajectory — improving, stable, deteriorating

5. KEY RISKS & BLIND SPOTS
   - What we might be wrong about
   - Information gaps that could change the picture
   - Traps to watch for

6. INITIAL STRATEGIC ASSESSMENT
   - Preliminary read on how this negotiation is likely to unfold
   - Recommended posture (aggressive, collaborative, defensive)
   - Timing considerations

Be thorough, direct, and actionable. This is a real negotiation with real consequences."""

        brief = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="negotiation_brief",
        )

        # Persist to database
        self.mira.sqlite.conn.execute(
            """INSERT INTO negotiations (id, counterparty, context, stakes, brief, status)
               VALUES (?, ?, ?, ?, ?, 'briefed')""",
            (negotiation_id, counterparty, context, stakes, brief),
        )
        self.mira.sqlite.conn.commit()

        self.mira.sqlite.log_action(
            "negotiation",
            "brief_prepared",
            f"counterparty={counterparty}, negotiation_id={negotiation_id}",
            {"negotiation_id": negotiation_id, "counterparty": counterparty},
        )

        logger.info(f"Negotiation brief prepared: {negotiation_id} vs {counterparty}")
        return {"negotiation_id": negotiation_id, "brief": brief}

    # ── 2. Playbook Generation ───────────────────────────────────────

    async def generate_playbook(
        self,
        negotiation_id: str,
        brief: str,
        goals: list[str],
        constraints: list[str],
    ) -> str:
        """Generate a detailed negotiation playbook with 3 scenarios and BATNA.

        Uses Opus tier — complex multi-scenario strategic reasoning.

        Args:
            negotiation_id: ID from prepare_brief.
            brief: The research brief (output of prepare_brief).
            goals: What you want to achieve (ordered by priority).
            constraints: Your hard limits and non-negotiables.

        Returns:
            The full playbook text.
        """
        prompt = f"""Based on the research brief below, create a detailed negotiation playbook.

RESEARCH BRIEF:
{brief}

OUR GOALS (priority order):
{chr(10).join(f'{i+1}. {g}' for i, g in enumerate(goals))}

OUR CONSTRAINTS (non-negotiables):
{chr(10).join(f'- {c}' for c in constraints)}

Structure the playbook as follows:

═══ NEGOTIATION PLAYBOOK ═══

1. BATNA ANALYSIS (Best Alternative to Negotiated Agreement)
   - Our BATNA: what happens if we walk away
   - Their BATNA: what happens if they walk away
   - Reservation price / walk-away point
   - ZOPA (Zone of Possible Agreement) — where overlap exists

2. OPENING STRATEGY
   - Recommended opening position and why
   - Anchoring approach — first number/offer and justification
   - Framing: how to set the tone in the first 5 minutes
   - Key talking points for the opener

3. SCENARIO A — OPTIMISTIC (they're more flexible than expected)
   - Signals you'd see: what they say/do that indicates this
   - Their likely position and underlying interests
   - Your response strategy: how to capitalise without overreaching
   - Target outcome in this scenario
   - Specific language and tactics to use

4. SCENARIO B — REALISTIC (tough but productive negotiation)
   - Signals you'd see
   - Their likely position and underlying interests
   - Your response strategy: concessions sequence, trade-offs
   - Target outcome in this scenario
   - Specific language and tactics to use

5. SCENARIO C — PESSIMISTIC (they play hardball or stonewall)
   - Signals you'd see
   - Their likely position and underlying interests
   - Your response strategy: when to hold, when to pivot, when to walk
   - Minimum acceptable outcome before invoking BATNA
   - De-escalation tactics and face-saving options

6. CONCESSION STRATEGY
   - What we can concede (ranked from easy to costly)
   - What we should never concede
   - Concession packaging: how to bundle trade-offs for maximum value
   - Pace: how quickly to make concessions

7. TACTICAL TOOLKIT
   - Power phrases for key moments
   - Questions to ask that reveal their true position
   - Silence and timing tactics
   - How to handle common pressure tactics (deadline, ultimatum, good-cop/bad-cop)

8. CLOSING STRATEGY
   - How to recognise when a deal is ready to close
   - Closing techniques appropriate to this negotiation
   - Next steps and follow-up commitments to secure

Be specific, practical, and ready to use in the room."""

        playbook = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="negotiation_playbook",
        )

        # Update the negotiation record
        self._update_negotiation(
            negotiation_id,
            goals=json.dumps(goals),
            constraints=json.dumps(constraints),
            playbook=playbook,
            status="ready",
        )

        self.mira.sqlite.log_action(
            "negotiation",
            "playbook_generated",
            f"negotiation_id={negotiation_id}",
            {"negotiation_id": negotiation_id, "goal_count": len(goals)},
        )

        logger.info(f"Playbook generated for negotiation {negotiation_id}")
        return playbook

    # ── 3. Real-Time Tactical Advice ─────────────────────────────────

    async def get_tactical_advice(
        self,
        negotiation_id: str,
        situation_update: str,
    ) -> str:
        """Provide real-time tactical advice during an active negotiation.

        Uses Sonnet tier — fast enough for live use, smart enough for tactics.

        Called via Telegram while the negotiation is happening. The user sends
        a quick update about what just happened, and Mira responds with
        immediate tactical guidance.

        Args:
            negotiation_id: The active negotiation ID.
            situation_update: What just happened / what they just said.

        Returns:
            Tactical advice text.
        """
        negotiation = self._get_negotiation(negotiation_id)
        if not negotiation:
            return f"Negotiation {negotiation_id} not found. Use /neg_list to see active negotiations."

        # Build context from the stored brief and playbook
        context_parts = [
            f"Counterparty: {negotiation['counterparty']}",
            f"Stakes: {negotiation.get('stakes', 'unknown')}",
        ]
        if negotiation.get("brief"):
            # Include a condensed version to stay within token limits
            context_parts.append(f"Brief summary:\n{negotiation['brief'][:2000]}")
        if negotiation.get("playbook"):
            context_parts.append(f"Playbook summary:\n{negotiation['playbook'][:2000]}")

        context_block = "\n\n".join(context_parts)

        prompt = f"""You are providing LIVE tactical advice during an active negotiation.

NEGOTIATION CONTEXT:
{context_block}

SITUATION UPDATE FROM USER:
{situation_update}

Respond with immediate, actionable tactical advice. Format:

READ: What this move likely means (1-2 sentences)
DO: What to do or say next (specific and concrete)
WATCH: What to look for in their response
AVOID: What NOT to do right now

Be concise — this is being read on a phone during a live negotiation. No fluff."""

        advice = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=1024,
            tier="standard",
            task_type="negotiation_tactical",
        )

        # Update status to active if not already
        if negotiation.get("status") != "active":
            self._update_negotiation(negotiation_id, status="active")

        self.mira.sqlite.log_action(
            "negotiation",
            "tactical_advice",
            f"negotiation_id={negotiation_id}",
            {
                "negotiation_id": negotiation_id,
                "situation": situation_update[:200],
            },
        )

        logger.info(f"Tactical advice given for negotiation {negotiation_id}")
        return advice

    # ── 4. Post-Negotiation Review ───────────────────────────────────

    async def post_review(
        self,
        negotiation_id: str,
        outcome: str,
        notes: str = "",
    ) -> str:
        """Generate a post-negotiation analysis and store lessons learned.

        Uses Opus tier — thorough analysis for long-term learning.

        Args:
            negotiation_id: The completed negotiation ID.
            outcome: What was the result — deal terms, no deal, ongoing.
            notes: Any additional observations or feelings about how it went.

        Returns:
            The review text.
        """
        negotiation = self._get_negotiation(negotiation_id)
        if not negotiation:
            return f"Negotiation {negotiation_id} not found."

        prompt = f"""Conduct a thorough post-negotiation review.

COUNTERPARTY: {negotiation['counterparty']}
ORIGINAL CONTEXT: {negotiation.get('context', 'N/A')}
STAKES: {negotiation.get('stakes', 'N/A')}
GOALS: {negotiation.get('goals', '[]')}
CONSTRAINTS: {negotiation.get('constraints', '[]')}

BRIEF USED:
{(negotiation.get('brief') or 'No brief generated')[:2000]}

PLAYBOOK USED:
{(negotiation.get('playbook') or 'No playbook generated')[:2000]}

OUTCOME: {outcome}
USER NOTES: {notes}

Structure the review as follows:

1. OUTCOME ASSESSMENT
   - What was achieved vs what was targeted
   - Score: 1-10 on how well the negotiation went overall
   - Value captured vs value left on the table

2. WHAT WORKED
   - Tactics and approaches that were effective
   - Preparation that paid off
   - Key moments where we gained ground

3. WHAT DIDN'T WORK
   - Where we lost ground or missed opportunities
   - Tactics that backfired or fell flat
   - Preparation gaps that hurt us

4. COUNTERPARTY ANALYSIS (for future reference)
   - Their actual style vs what we predicted
   - Surprises — what we didn't expect
   - Key patterns to remember for next time

5. LESSONS LEARNED
   - 3-5 specific, actionable lessons to carry forward
   - What to do differently next time with this counterparty
   - What to do differently in similar negotiations generally

6. FOLLOW-UP ACTIONS
   - Commitments made that need tracking
   - Relationship maintenance needed
   - Deadlines or milestones to monitor

Be honest and direct. The point is to learn, not to feel good."""

        review = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="negotiation_review",
        )

        # Extract lessons for memory storage
        lessons_prompt = f"""From this negotiation review, extract 3-5 concise lessons learned.
Return ONLY a valid JSON array of strings, each one a single actionable lesson.

Review:
{review}"""

        lessons_raw = await self.mira.brain.think(
            message=lessons_prompt,
            include_history=False,
            system_override="You are a precise extraction system. Return ONLY a valid JSON array of strings.",
            max_tokens=512,
            tier="fast",
            task_type="negotiation_lessons_extract",
        )

        try:
            cleaned = lessons_raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            lessons = json.loads(cleaned)
            if not isinstance(lessons, list):
                lessons = []
        except (json.JSONDecodeError, IndexError):
            lessons = []
            logger.warning("Could not extract structured lessons from review")

        # Update negotiation record
        self._update_negotiation(
            negotiation_id,
            outcome=outcome,
            review=review,
            lessons_learned=json.dumps(lessons),
            status="reviewed",
        )

        # Store lessons as memories for long-term learning
        for lesson in lessons:
            self.mira.sqlite.store_memory(
                content=f"Negotiation lesson ({negotiation['counterparty']}): {lesson}",
                category="work",
                importance=4,
                source="negotiation_review",
                tags=["negotiation", "lesson", negotiation["counterparty"]],
                metadata={
                    "negotiation_id": negotiation_id,
                    "counterparty": negotiation["counterparty"],
                },
            )

        # Store counterparty insights in the people CRM
        self.mira.sqlite.upsert_person(
            name=negotiation["counterparty"],
            key_facts=[f"Negotiation outcome ({datetime.now().strftime('%Y-%m-%d')}): {outcome[:100]}"],
            metadata={"last_negotiation_id": negotiation_id},
        )

        self.mira.sqlite.log_action(
            "negotiation",
            "post_review",
            f"negotiation_id={negotiation_id}, outcome={outcome[:100]}",
            {
                "negotiation_id": negotiation_id,
                "lessons_count": len(lessons),
                "counterparty": negotiation["counterparty"],
            },
        )

        logger.info(
            f"Post-review complete for negotiation {negotiation_id}: "
            f"{len(lessons)} lessons stored"
        )
        return review

    # ── Utility Methods ──────────────────────────────────────────────

    def list_negotiations(
        self, status: str = None, limit: int = 20
    ) -> list[dict]:
        """List negotiations, optionally filtered by status."""
        if status:
            rows = self.mira.sqlite.conn.execute(
                "SELECT id, counterparty, stakes, status, created_at, updated_at "
                "FROM negotiations WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.mira.sqlite.conn.execute(
                "SELECT id, counterparty, stakes, status, created_at, updated_at "
                "FROM negotiations ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_negotiation_detail(self, negotiation_id: str) -> Optional[dict]:
        """Get full negotiation record including brief, playbook, and review."""
        return self._get_negotiation(negotiation_id)
