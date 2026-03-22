"""
Legal & Compliance Watchdog — contract review, compliance calendar,
regulatory monitoring, and NDA/non-compete tracking.

Spec reference: Section 11.4

Capabilities:
- Reads every contract before signing — flags unusual, one-sided, or risky clauses
- Compliance calendar across all jurisdictions (PH, MX, SA, CA)
- Regulatory change monitoring — alerts when rules change that affect trading or Boldr
- NDA and non-compete tracker — knows what you're bound by
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.legal")

# Jurisdictions tracked
JURISDICTIONS = {
    "PH": "Philippines",
    "MX": "Mexico",
    "SA": "South Africa",
    "CA": "Canada",
}

CONTRACT_TYPES = [
    "employment",
    "nda",
    "non_compete",
    "service_agreement",
    "vendor",
    "partnership",
    "lease",
    "licensing",
    "consulting",
    "subscription",
    "other",
]


class LegalWatchdog:
    """Legal & Compliance Watchdog — contract review, compliance deadlines,
    NDA/non-compete tracking, and restriction conflict detection."""

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create contracts and compliance_deadlines tables in SQLite."""
        self.mira.sqlite.conn.executescript("""
            -- Contracts reviewed by Mira
            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                counterparty TEXT NOT NULL,
                contract_type TEXT NOT NULL DEFAULT 'other',
                summary TEXT,
                risk_level TEXT DEFAULT 'medium',
                risk_flags TEXT DEFAULT '[]',
                unusual_clauses TEXT DEFAULT '[]',
                recommendations TEXT DEFAULT '[]',
                full_analysis TEXT,
                document_path TEXT,
                status TEXT DEFAULT 'reviewed',
                reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                signed_at TIMESTAMP,
                expires_at TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- Compliance deadlines across jurisdictions
            CREATE TABLE IF NOT EXISTS compliance_deadlines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                jurisdiction TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                due_date TEXT NOT NULL,
                responsible_person TEXT,
                related_documents TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                warning_sent_30d INTEGER DEFAULT 0,
                warning_sent_7d INTEGER DEFAULT 0,
                warning_sent_1d INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            -- NDA and non-compete agreements
            CREATE TABLE IF NOT EXISTS ndas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                counterparty TEXT NOT NULL,
                agreement_type TEXT NOT NULL DEFAULT 'nda',
                signed_date TEXT NOT NULL,
                expiry_date TEXT,
                key_restrictions TEXT DEFAULT '[]',
                restricted_activities TEXT DEFAULT '[]',
                geographic_scope TEXT,
                document_path TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_contracts_counterparty ON contracts(counterparty);
            CREATE INDEX IF NOT EXISTS idx_contracts_type ON contracts(contract_type);
            CREATE INDEX IF NOT EXISTS idx_compliance_due ON compliance_deadlines(due_date);
            CREATE INDEX IF NOT EXISTS idx_compliance_jurisdiction ON compliance_deadlines(jurisdiction);
            CREATE INDEX IF NOT EXISTS idx_compliance_status ON compliance_deadlines(status);
            CREATE INDEX IF NOT EXISTS idx_ndas_counterparty ON ndas(counterparty);
            CREATE INDEX IF NOT EXISTS idx_ndas_status ON ndas(status);
            CREATE INDEX IF NOT EXISTS idx_ndas_expiry ON ndas(expiry_date);
        """)
        self.mira.sqlite.conn.commit()
        logger.info("Legal Watchdog initialised — contracts, compliance_deadlines, ndas tables ready")

    # ── Contract Review ──────────────────────────────────────────────

    async def review_contract(
        self,
        contract_text: str,
        contract_type: str = "other",
        counterparty: str = "unknown",
    ) -> dict:
        """Use Opus to analyse a contract. Returns structured analysis with
        risk flags, unusual clauses, and plain-English recommendations.

        Args:
            contract_text: Full text of the contract to review.
            contract_type: One of CONTRACT_TYPES.
            counterparty: Name of the other party.

        Returns:
            Dict with keys: risk_level, risk_flags, unusual_clauses,
            recommendations, summary, full_analysis.
        """
        prompt = f"""You are a legal analyst reviewing a contract on behalf of your client.
Analyse this {contract_type} contract with {counterparty} thoroughly.

CONTRACT TEXT:
{contract_text}

Provide your analysis as ONLY valid JSON with these fields:
- risk_level: "low" | "medium" | "high" | "critical"
- risk_flags: list of specific risks identified, each as a short string
- unusual_clauses: list of objects, each with "clause" (the clause text or reference), "concern" (what's unusual), and "severity" ("low"|"medium"|"high")
- recommendations: list of specific actions to take before signing
- summary: 2-3 sentence plain-English summary of the contract and its key terms
- key_terms: object with "duration", "termination_notice", "liability_cap", "governing_law", "dispute_resolution", "payment_terms" (use null for any not found)
- one_sided_provisions: list of clauses that disproportionately favour the counterparty

Be direct. Flag anything a reasonable person would want to negotiate or push back on.
Do NOT be overly conservative — flag real risks, not theoretical ones."""

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a sharp legal analyst. Review contracts thoroughly. "
                "Return ONLY valid JSON. Be direct about risks — your client's "
                "interests come first. No hedging, no disclaimers."
            ),
            max_tokens=4096,
            tier="deep",
            task_type="contract_review",
        )

        # Parse the structured response
        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            analysis = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse contract analysis JSON, storing raw text")
            analysis = {
                "risk_level": "unknown",
                "risk_flags": ["Analysis parsing failed — review raw text"],
                "unusual_clauses": [],
                "recommendations": ["Manual review recommended"],
                "summary": "Automated analysis could not be parsed. See full_analysis.",
                "key_terms": {},
                "one_sided_provisions": [],
            }

        analysis["full_analysis"] = response

        # Store in database
        self.mira.sqlite.conn.execute(
            """INSERT INTO contracts
               (counterparty, contract_type, summary, risk_level, risk_flags,
                unusual_clauses, recommendations, full_analysis, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                counterparty,
                contract_type,
                analysis.get("summary", ""),
                analysis.get("risk_level", "unknown"),
                json.dumps(analysis.get("risk_flags", [])),
                json.dumps(analysis.get("unusual_clauses", [])),
                json.dumps(analysis.get("recommendations", [])),
                response,
                json.dumps({
                    "key_terms": analysis.get("key_terms", {}),
                    "one_sided_provisions": analysis.get("one_sided_provisions", []),
                }),
            ),
        )
        self.mira.sqlite.conn.commit()

        # Log the action
        self.mira.sqlite.log_action(
            "legal",
            "contract_reviewed",
            f"risk={analysis.get('risk_level', 'unknown')}",
            {
                "counterparty": counterparty,
                "contract_type": contract_type,
                "risk_flags_count": len(analysis.get("risk_flags", [])),
                "unusual_clauses_count": len(analysis.get("unusual_clauses", [])),
            },
        )

        # Notify via Telegram for high/critical risk
        risk = analysis.get("risk_level", "unknown")
        if risk in ("high", "critical") and hasattr(self.mira, "telegram"):
            flags = ", ".join(analysis.get("risk_flags", [])[:3])
            await self.mira.telegram.notify(
                "legal",
                f"{risk.upper()} risk contract: {counterparty}",
                f"Type: {contract_type} | Flags: {flags}",
            )

        logger.info(
            f"Contract reviewed: {counterparty} ({contract_type}) — "
            f"risk: {risk}, {len(analysis.get('risk_flags', []))} flags"
        )
        return analysis

    async def get_contract_history(self, counterparty: str = None, limit: int = 20) -> list[dict]:
        """Retrieve past contract reviews, optionally filtered by counterparty."""
        if counterparty:
            rows = self.mira.sqlite.conn.execute(
                """SELECT * FROM contracts WHERE counterparty LIKE ?
                   ORDER BY reviewed_at DESC LIMIT ?""",
                (f"%{counterparty}%", limit),
            ).fetchall()
        else:
            rows = self.mira.sqlite.conn.execute(
                "SELECT * FROM contracts ORDER BY reviewed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Compliance Calendar ──────────────────────────────────────────

    async def add_compliance_deadline(
        self,
        jurisdiction: str,
        category: str,
        description: str,
        due_date: str,
        responsible_person: str = None,
        related_documents: list = None,
    ) -> int:
        """Store a compliance deadline.

        Args:
            jurisdiction: Country code (PH, MX, SA, CA) or description.
            category: E.g. "tax_filing", "license_renewal", "regulatory_report".
            description: Plain-English description of what's due.
            due_date: ISO date string (YYYY-MM-DD).
            responsible_person: Who handles this.
            related_documents: List of document paths or references.

        Returns:
            The deadline ID.
        """
        cursor = self.mira.sqlite.conn.execute(
            """INSERT INTO compliance_deadlines
               (jurisdiction, category, description, due_date,
                responsible_person, related_documents)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                jurisdiction,
                category,
                description,
                due_date,
                responsible_person,
                json.dumps(related_documents or []),
            ),
        )
        self.mira.sqlite.conn.commit()

        self.mira.sqlite.log_action(
            "legal",
            "compliance_deadline_added",
            f"{jurisdiction}: {description} due {due_date}",
        )
        logger.info(f"Compliance deadline added: {jurisdiction} — {description} due {due_date}")
        return cursor.lastrowid

    async def get_upcoming_deadlines(self, days_ahead: int = 30) -> list[dict]:
        """Return all pending compliance deadlines within N days.

        Args:
            days_ahead: Number of days to look ahead (default 30).

        Returns:
            List of deadline dicts sorted by due_date ascending.
        """
        cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        rows = self.mira.sqlite.conn.execute(
            """SELECT * FROM compliance_deadlines
               WHERE status = 'pending' AND due_date <= ? AND due_date >= ?
               ORDER BY due_date ASC""",
            (cutoff, today),
        ).fetchall()
        return [dict(row) for row in rows]

    async def complete_deadline(self, deadline_id: int):
        """Mark a compliance deadline as completed."""
        self.mira.sqlite.conn.execute(
            """UPDATE compliance_deadlines
               SET status = 'completed', completed_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), deadline_id),
        )
        self.mira.sqlite.conn.commit()
        logger.info(f"Compliance deadline #{deadline_id} marked completed")

    async def check_deadline_warnings(self):
        """Scheduler callback: send advance warnings for upcoming deadlines.

        Sends Telegram alerts at 30-day, 7-day, and 1-day marks before
        each pending deadline. Idempotent — tracks which warnings have
        already been sent via warning_sent_* columns.
        """
        today = datetime.now().date()
        rows = self.mira.sqlite.conn.execute(
            "SELECT * FROM compliance_deadlines WHERE status = 'pending'"
        ).fetchall()

        for row in rows:
            row = dict(row)
            try:
                due = datetime.strptime(row["due_date"], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            days_until = (due - today).days
            jurisdiction = row.get("jurisdiction", "")
            jurisdiction_name = JURISDICTIONS.get(jurisdiction, jurisdiction)
            desc = row["description"]
            deadline_id = row["id"]

            # 30-day warning
            if days_until <= 30 and not row.get("warning_sent_30d"):
                if hasattr(self.mira, "telegram"):
                    await self.mira.telegram.notify(
                        "legal",
                        f"Compliance deadline in {days_until} days",
                        f"[{jurisdiction_name}] {desc} — due {row['due_date']}",
                    )
                self.mira.sqlite.conn.execute(
                    "UPDATE compliance_deadlines SET warning_sent_30d = 1 WHERE id = ?",
                    (deadline_id,),
                )
                self.mira.sqlite.conn.commit()

            # 7-day warning
            if days_until <= 7 and not row.get("warning_sent_7d"):
                if hasattr(self.mira, "telegram"):
                    await self.mira.telegram.notify(
                        "legal",
                        f"COMPLIANCE DUE IN {days_until} DAYS",
                        f"[{jurisdiction_name}] {desc} — due {row['due_date']}",
                    )
                self.mira.sqlite.conn.execute(
                    "UPDATE compliance_deadlines SET warning_sent_7d = 1 WHERE id = ?",
                    (deadline_id,),
                )
                self.mira.sqlite.conn.commit()

            # 1-day warning
            if days_until <= 1 and not row.get("warning_sent_1d"):
                if hasattr(self.mira, "telegram"):
                    await self.mira.telegram.notify(
                        "legal",
                        f"URGENT: Compliance deadline {'TODAY' if days_until == 0 else 'TOMORROW'}",
                        f"[{jurisdiction_name}] {desc} — due {row['due_date']}",
                    )
                self.mira.sqlite.conn.execute(
                    "UPDATE compliance_deadlines SET warning_sent_1d = 1 WHERE id = ?",
                    (deadline_id,),
                )
                self.mira.sqlite.conn.commit()

            # Overdue
            if days_until < 0:
                if hasattr(self.mira, "telegram"):
                    await self.mira.telegram.notify(
                        "legal",
                        f"OVERDUE: Compliance deadline missed by {abs(days_until)} days",
                        f"[{jurisdiction_name}] {desc} — was due {row['due_date']}",
                    )
                # Mark overdue (only once via the 1d flag check above)

        logger.info(f"Deadline warning check complete: {len(rows)} pending deadlines scanned")

    # ── NDA / Non-Compete Tracker ────────────────────────────────────

    async def track_nda(
        self,
        counterparty: str,
        signed_date: str,
        expiry_date: str = None,
        key_restrictions: list = None,
        document_path: str = None,
        agreement_type: str = "nda",
        restricted_activities: list = None,
        geographic_scope: str = None,
    ) -> int:
        """Store an NDA or non-compete agreement.

        Args:
            counterparty: The other party to the agreement.
            signed_date: ISO date string (YYYY-MM-DD).
            expiry_date: ISO date string, or None if perpetual.
            key_restrictions: List of plain-English restriction descriptions.
            document_path: Path to the signed document.
            agreement_type: "nda" or "non_compete".
            restricted_activities: Specific activities you cannot do.
            geographic_scope: Geographic limitations of the restriction.

        Returns:
            The NDA record ID.
        """
        cursor = self.mira.sqlite.conn.execute(
            """INSERT INTO ndas
               (counterparty, agreement_type, signed_date, expiry_date,
                key_restrictions, restricted_activities, geographic_scope,
                document_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                counterparty,
                agreement_type,
                signed_date,
                expiry_date,
                json.dumps(key_restrictions or []),
                json.dumps(restricted_activities or []),
                geographic_scope,
                document_path,
            ),
        )
        self.mira.sqlite.conn.commit()

        self.mira.sqlite.log_action(
            "legal",
            f"{agreement_type}_tracked",
            f"{counterparty}, expires {expiry_date or 'perpetual'}",
        )
        logger.info(
            f"NDA/non-compete tracked: {counterparty} ({agreement_type}) "
            f"signed {signed_date}, expires {expiry_date or 'perpetual'}"
        )
        return cursor.lastrowid

    async def get_active_restrictions(self) -> list[dict]:
        """List all active NDAs and non-competes.

        An agreement is active if:
        - status is 'active' AND
        - expiry_date is NULL (perpetual) or in the future
        """
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.mira.sqlite.conn.execute(
            """SELECT * FROM ndas
               WHERE status = 'active'
               AND (expiry_date IS NULL OR expiry_date >= ?)
               ORDER BY expiry_date ASC""",
            (today,),
        ).fetchall()

        results = []
        for row in rows:
            r = dict(row)
            # Parse JSON fields for easier consumption
            for field in ("key_restrictions", "restricted_activities"):
                if isinstance(r.get(field), str):
                    try:
                        r[field] = json.loads(r[field])
                    except json.JSONDecodeError:
                        pass
            results.append(r)

        return results

    async def expire_old_agreements(self):
        """Mark expired NDAs/non-competes as inactive. Run periodically."""
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.mira.sqlite.conn.execute(
            """UPDATE ndas SET status = 'expired'
               WHERE status = 'active' AND expiry_date IS NOT NULL AND expiry_date < ?""",
            (today,),
        )
        self.mira.sqlite.conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Expired {cursor.rowcount} NDA/non-compete agreements")

    async def check_restriction_conflict(self, proposed_action: str) -> dict:
        """Check if a proposed action conflicts with any active NDA/non-compete.

        Uses the fast tier to classify the action against all active
        restrictions, then escalates to Opus for any potential conflicts.

        Args:
            proposed_action: Plain-English description of what you want to do.
                E.g. "Consult for CompanyX on BPO operations in Philippines"

        Returns:
            Dict with keys:
            - has_conflict: bool
            - conflicts: list of dicts with agreement details and conflict explanation
            - recommendation: plain-English recommendation
        """
        active = await self.get_active_restrictions()

        if not active:
            return {
                "has_conflict": False,
                "conflicts": [],
                "recommendation": "No active NDAs or non-competes on file. Proceed freely.",
            }

        # Build a compact summary of active restrictions for the prompt
        restrictions_summary = []
        for a in active:
            restrictions_summary.append({
                "id": a["id"],
                "counterparty": a["counterparty"],
                "type": a["agreement_type"],
                "expiry": a.get("expiry_date", "perpetual"),
                "restrictions": a.get("key_restrictions", []),
                "restricted_activities": a.get("restricted_activities", []),
                "geographic_scope": a.get("geographic_scope"),
            })

        prompt = f"""Check whether this proposed action conflicts with any active legal restrictions.

PROPOSED ACTION:
{proposed_action}

ACTIVE RESTRICTIONS:
{json.dumps(restrictions_summary, indent=2)}

Return ONLY valid JSON with:
- has_conflict: true/false
- conflicts: list of objects, each with "agreement_id", "counterparty", "conflict_description", "severity" ("low"|"medium"|"high")
- recommendation: one paragraph of plain-English advice on how to proceed

Be precise. Only flag real conflicts, not theoretical stretches. But err on the side of caution for high-severity restrictions."""

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a legal compliance checker. Evaluate whether a proposed "
                "action conflicts with existing NDAs and non-compete agreements. "
                "Return ONLY valid JSON. Be precise and practical."
            ),
            max_tokens=2048,
            tier="deep",
            task_type="restriction_check",
        )

        try:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse restriction conflict check JSON")
            result = {
                "has_conflict": None,
                "conflicts": [],
                "recommendation": f"Automated check failed. Manual review needed. Raw analysis: {response[:500]}",
            }

        # Log the check
        self.mira.sqlite.log_action(
            "legal",
            "restriction_check",
            f"conflict={'yes' if result.get('has_conflict') else 'no'}",
            {
                "proposed_action": proposed_action[:200],
                "conflicts_found": len(result.get("conflicts", [])),
            },
        )

        # Alert via Telegram if conflict found
        if result.get("has_conflict") and hasattr(self.mira, "telegram"):
            conflict_summary = "; ".join(
                c.get("conflict_description", "")[:80]
                for c in result.get("conflicts", [])[:3]
            )
            await self.mira.telegram.notify(
                "legal",
                "Restriction conflict detected",
                f"Action: {proposed_action[:80]} | {conflict_summary}",
            )

        return result

    # ── Regulatory Change Monitoring ─────────────────────────────────

    async def scan_regulatory_changes(self, focus_areas: list = None) -> str:
        """Use Claude to assess potential regulatory changes that may affect
        trading or Boldr operations across tracked jurisdictions.

        This is an AI-powered analysis based on Claude's training data.
        For real-time monitoring, integrate with regulatory RSS feeds or APIs.

        Args:
            focus_areas: Optional list of specific areas to focus on.
                Defaults to trading, BPO, data privacy, employment law.

        Returns:
            Structured analysis of regulatory landscape.
        """
        areas = focus_areas or [
            "forex and crypto trading regulations",
            "BPO and outsourcing industry regulations",
            "data privacy and cross-border data transfer",
            "employment and labour law",
            "tax compliance for individuals and businesses",
        ]

        jurisdictions_str = ", ".join(
            f"{code} ({name})" for code, name in JURISDICTIONS.items()
        )

        prompt = f"""Provide a regulatory landscape briefing for someone operating across
these jurisdictions: {jurisdictions_str}

Focus areas:
{chr(10).join(f'- {area}' for area in areas)}

For each jurisdiction, identify:
1. Recent or upcoming regulatory changes that could affect these areas
2. Key compliance risks to watch
3. Any deadlines or transition periods to be aware of

Be specific and actionable. Skip areas where nothing significant is happening."""

        analysis = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            max_tokens=4096,
            tier="deep",
            task_type="regulatory_scan",
        )

        self.mira.sqlite.log_action(
            "legal",
            "regulatory_scan",
            f"jurisdictions: {', '.join(JURISDICTIONS.keys())}",
            {"focus_areas": areas},
        )

        return analysis

    # ── Summary / Dashboard Helpers ──────────────────────────────────

    async def get_legal_summary(self) -> dict:
        """Get a summary of the legal landscape for dashboard display."""
        active_ndas = await self.get_active_restrictions()
        upcoming = await self.get_upcoming_deadlines(days_ahead=30)

        # Count contracts reviewed
        row = self.mira.sqlite.conn.execute(
            "SELECT COUNT(*) as count FROM contracts"
        ).fetchone()
        contracts_reviewed = row["count"] if row else 0

        # High-risk contracts
        row = self.mira.sqlite.conn.execute(
            "SELECT COUNT(*) as count FROM contracts WHERE risk_level IN ('high', 'critical')"
        ).fetchone()
        high_risk_count = row["count"] if row else 0

        # Overdue deadlines
        today = datetime.now().strftime("%Y-%m-%d")
        row = self.mira.sqlite.conn.execute(
            "SELECT COUNT(*) as count FROM compliance_deadlines WHERE status = 'pending' AND due_date < ?",
            (today,),
        ).fetchone()
        overdue_count = row["count"] if row else 0

        return {
            "active_ndas": len(active_ndas),
            "upcoming_deadlines": len(upcoming),
            "overdue_deadlines": overdue_count,
            "contracts_reviewed": contracts_reviewed,
            "high_risk_contracts": high_risk_count,
            "next_deadline": upcoming[0] if upcoming else None,
            "ndas": active_ndas,
            "deadlines": upcoming,
        }
