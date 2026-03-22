"""
Earning Module — 5 active revenue streams that Mira manages autonomously.

1. Freelance Agent (Upwork, Fiverr, Freelancer, PeoplePerHour)
2. Content Monetisation (YouTube AdSense, TikTok, Instagram, affiliate links)
3. Polymarket Alpha Engine (prediction markets)
4. Digital Product Store (Gumroad, Etsy, own website)
5. Consulting Pipeline (LinkedIn leads, outreach, discovery calls)

Total potential: $3,600 - $27,000+/month across all modules.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.earning")

# ── User skill profile used across earning modules ────────────────────
USER_SKILLS = {
    "primary": ["BPO operations", "finance & accounting", "data analysis", "Excel / Google Sheets"],
    "secondary": ["AI automation", "process optimisation", "trading systems", "team management"],
    "tools": ["MT5", "Python", "React", "SQL", "Anthropic Claude API", "Telegram bots"],
    "industries": ["BPO", "fintech", "crypto", "AI/ML"],
    "years_experience": 10,
    "rate_range_usd": {"low": 30, "mid": 60, "high": 120},
}


class EarningModule:
    """Manages all earning streams — tracking, automation, reporting."""

    def __init__(self, mira):
        self.mira = mira
        self.modules = {
            "freelance": FreelanceAgent(mira),
            "content": ContentMonetisation(mira),
            "polymarket": PolymarketEngine(mira),
            "digital_products": DigitalProductStore(mira),
            "consulting": ConsultingPipeline(mira),
        }

    async def initialise(self):
        """Set up all earning modules."""
        for name, module in self.modules.items():
            try:
                await module.initialise()
            except Exception as e:
                logger.error(f"Failed to initialise earning module '{name}': {e}")
        logger.info("Earning module initialised.")

    async def generate_report(self) -> str:
        """Generate report across all earning modules."""
        report_parts = []
        for name, module in self.modules.items():
            try:
                status = await module.get_status()
            except Exception as e:
                status = f"Error fetching status: {e}"
            report_parts.append(f"**{name.replace('_', ' ').title()}**\n{status}")

        return "Earning Modules Report\n\n" + "\n\n".join(report_parts)

    async def get_total_revenue(self, period: str = "month") -> dict:
        """Aggregate revenue across all earning streams for a period."""
        totals = {}
        grand_total = 0.0
        for name, module in self.modules.items():
            try:
                if hasattr(module, "get_revenue_for_period"):
                    amount = await module.get_revenue_for_period(period)
                else:
                    amount = 0.0
                totals[name] = amount
                grand_total += amount
            except Exception as e:
                logger.error(f"Revenue fetch failed for {name}: {e}")
                totals[name] = 0.0

        return {"by_stream": totals, "total": round(grand_total, 2), "period": period}


# ─────────────────────────────────────────────────────────────────────
# Helper: parse JSON from brain responses that may include markdown
# ─────────────────────────────────────────────────────────────────────

def _parse_brain_json(text: str, fallback: dict | list | None = None):
    """Attempt to parse JSON from a brain response, stripping markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse brain JSON: {cleaned[:200]}")
        return fallback if fallback is not None else {}


def _date_filter_sql(period: str) -> str:
    """Return a SQL WHERE clause fragment for date filtering."""
    if period == "today":
        return "DATE(created_at) = DATE('now')"
    elif period == "week":
        return "created_at >= DATE('now', '-7 days')"
    elif period == "month":
        return "created_at >= DATE('now', '-30 days')"
    elif period == "year":
        return "created_at >= DATE('now', '-365 days')"
    return "1=1"


# =====================================================================
# 1. FREELANCE AGENT
# =====================================================================

class FreelanceAgent:
    """Autonomous freelance work — scan, evaluate, bid, deliver, collect."""

    TABLE_CONTRACTS = "freelance_contracts"
    TABLE_DELIVERIES = "freelance_deliveries"

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create freelance-specific tables."""
        db = self.mira.sqlite.conn
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_CONTRACTS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                platform TEXT DEFAULT 'upwork',
                title TEXT NOT NULL,
                client TEXT,
                description TEXT,
                budget REAL,
                agreed_rate REAL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'active',
                proposal_text TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE TABLE IF NOT EXISTS {self.TABLE_DELIVERIES} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                deliverable TEXT NOT NULL,
                hours_spent REAL DEFAULT 0,
                notes TEXT,
                delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES {self.TABLE_CONTRACTS}(id)
            );

            CREATE INDEX IF NOT EXISTS idx_fc_status ON {self.TABLE_CONTRACTS}(status);
            CREATE INDEX IF NOT EXISTS idx_fd_contract ON {self.TABLE_DELIVERIES}(contract_id);
        """)
        db.commit()
        logger.info("FreelanceAgent tables ready.")

    # ── Core methods ──────────────────────────────────────────────────

    async def scan_jobs(self) -> list[dict]:
        """Use brain to generate a job search strategy and structured search criteria."""
        skills_summary = json.dumps(USER_SKILLS, indent=2)

        prompt = (
            "Generate a structured freelance job search strategy. "
            "Return ONLY valid JSON with these fields:\n"
            "- search_queries: list of 5 specific search strings to use on Upwork/Fiverr\n"
            "- target_categories: list of job categories to filter\n"
            "- min_budget_usd: minimum budget worth pursuing\n"
            "- max_competition: max number of proposals before skipping (e.g. 15)\n"
            "- red_flags: list of client/job red flags to avoid\n"
            "- green_flags: list of signals that indicate a good fit\n"
            "- platforms_priority: ordered list of platforms to check first\n\n"
            f"User skill profile:\n{skills_summary}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a freelance strategy advisor. Return ONLY valid JSON. "
                "Be specific and practical — these search strings will be used directly."
            ),
            max_tokens=1024,
            tier="standard",
            task_type="freelance_scan",
        )

        result = _parse_brain_json(response, fallback={
            "search_queries": [],
            "target_categories": [],
            "min_budget_usd": 100,
            "max_competition": 15,
            "red_flags": [],
            "green_flags": [],
            "platforms_priority": ["upwork", "fiverr"],
        })

        self.mira.sqlite.log_action(
            "earning.freelance", "scan_jobs",
            f"Generated {len(result.get('search_queries', []))} search queries",
            {"strategy": result},
        )
        return result

    async def evaluate_job(
        self,
        job_description: str,
        budget: float = 0,
        client_info: str = "",
    ) -> dict:
        """Score a job for fit, estimate effort, recommend bid price."""
        skills_summary = json.dumps(USER_SKILLS, indent=2)

        prompt = (
            "Evaluate this freelance job opportunity. Return ONLY valid JSON with:\n"
            "- fit_score: 1-10 (how well it matches skills)\n"
            "- effort_hours: estimated hours to complete\n"
            "- recommended_bid_usd: suggested bid price\n"
            "- confidence: 1-10 in the estimate\n"
            "- recommendation: 'bid', 'skip', or 'watch'\n"
            "- reasoning: one paragraph explaining the recommendation\n"
            "- risks: list of potential risks\n"
            "- key_selling_points: list of why we'd win this job\n\n"
            f"Job description:\n{job_description}\n\n"
            f"Budget: ${budget}\n"
            f"Client info: {client_info}\n\n"
            f"User skills:\n{skills_summary}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override="You are a freelance bid analyst. Return ONLY valid JSON.",
            max_tokens=1024,
            tier="standard",
            task_type="freelance_evaluate",
        )

        result = _parse_brain_json(response, fallback={
            "fit_score": 0,
            "effort_hours": 0,
            "recommended_bid_usd": 0,
            "confidence": 0,
            "recommendation": "skip",
            "reasoning": "Could not evaluate.",
            "risks": [],
            "key_selling_points": [],
        })

        self.mira.sqlite.log_action(
            "earning.freelance", "evaluate_job",
            result.get("recommendation", "unknown"),
            {"fit_score": result.get("fit_score"), "bid": result.get("recommended_bid_usd")},
        )
        return result

    async def submit_proposal(self, job_id: str, job_description: str) -> dict:
        """Draft a personalised proposal in the user's voice."""
        skills_summary = json.dumps(USER_SKILLS, indent=2)

        # Pull relevant past work from memory
        related = self.mira.vector.search(job_description, n_results=3)
        context_snippets = "\n".join(
            f"- {r['content'][:200]}" for r in related
        ) if related else "No directly related past context."

        prompt = (
            "Write a winning freelance proposal for this job. "
            "Write as if you ARE the user — direct, confident, not generic.\n\n"
            "The proposal should:\n"
            "1. Open with a hook showing you understand the problem\n"
            "2. Briefly describe relevant experience (be specific, not vague)\n"
            "3. Outline your approach in 2-3 steps\n"
            "4. Mention a concrete deliverable and timeline\n"
            "5. Close with a confident call to action\n\n"
            "Keep it under 200 words. No fluff, no 'Dear Hiring Manager'.\n\n"
            f"Job description:\n{job_description}\n\n"
            f"User skills:\n{skills_summary}\n\n"
            f"Related experience from memory:\n{context_snippets}"
        )

        proposal_text = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are writing as the user — a senior BPO/finance professional "
                "with deep data and automation skills. Be direct and authentic."
            ),
            max_tokens=1024,
            tier="standard",
            task_type="freelance_proposal",
        )

        # Store the contract draft
        db = self.mira.sqlite.conn
        cursor = db.execute(
            f"""INSERT INTO {self.TABLE_CONTRACTS}
                (job_id, title, description, proposal_text, status, started_at)
                VALUES (?, ?, ?, ?, 'proposed', ?)""",
            (job_id, job_description[:100], job_description, proposal_text,
             datetime.now().isoformat()),
        )
        db.commit()
        contract_id = cursor.lastrowid

        self.mira.sqlite.log_action(
            "earning.freelance", "submit_proposal",
            f"Drafted proposal for job {job_id}",
            {"contract_id": contract_id, "job_id": job_id},
        )

        return {
            "status": "drafted",
            "contract_id": contract_id,
            "proposal": proposal_text,
        }

    async def get_active_contracts(self) -> list[dict]:
        """Query SQLite for active freelance contracts."""
        rows = self.mira.sqlite.conn.execute(
            f"SELECT * FROM {self.TABLE_CONTRACTS} WHERE status = 'active' "
            "ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    async def log_delivery(
        self,
        contract_id: int,
        deliverable: str,
        hours_spent: float = 0,
        notes: str = None,
    ) -> dict:
        """Log completed work on a contract."""
        db = self.mira.sqlite.conn
        cursor = db.execute(
            f"""INSERT INTO {self.TABLE_DELIVERIES}
                (contract_id, deliverable, hours_spent, notes)
                VALUES (?, ?, ?, ?)""",
            (contract_id, deliverable, hours_spent, notes),
        )
        db.commit()
        delivery_id = cursor.lastrowid

        self.mira.sqlite.log_action(
            "earning.freelance", "log_delivery",
            f"Delivered on contract #{contract_id}",
            {"delivery_id": delivery_id, "hours": hours_spent, "deliverable": deliverable[:100]},
        )

        return {"delivery_id": delivery_id, "contract_id": contract_id, "status": "logged"}

    async def get_revenue_for_period(self, period: str = "month") -> float:
        """Sum agreed rates for completed contracts in the period."""
        where = _date_filter_sql(period)
        row = self.mira.sqlite.conn.execute(
            f"SELECT COALESCE(SUM(agreed_rate), 0) as total FROM {self.TABLE_CONTRACTS} "
            f"WHERE status = 'completed' AND {where}"
        ).fetchone()
        return float(row["total"]) if row else 0.0

    async def get_status(self) -> str:
        active = await self.get_active_contracts()
        total_deliveries = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as c FROM {self.TABLE_DELIVERIES}"
        ).fetchone()["c"]
        month_rev = await self.get_revenue_for_period("month")
        return (
            f"Active contracts: {len(active)}\n"
            f"Total deliveries: {total_deliveries}\n"
            f"Month revenue: ${month_rev:,.2f}\n"
            f"Platforms: Upwork, Fiverr, Freelancer, PeoplePerHour"
        )


# =====================================================================
# 2. CONTENT MONETISATION
# =====================================================================

class ContentMonetisation:
    """Revenue from content — AdSense, creator funds, brand deals, affiliates."""

    TABLE_CONTENT_REVENUE = "content_revenue"
    TABLE_BRAND_DEALS = "brand_deals"

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create content monetisation tables."""
        db = self.mira.sqlite.conn
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_CONTENT_REVENUE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                description TEXT,
                period TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE TABLE IF NOT EXISTS {self.TABLE_BRAND_DEALS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT NOT NULL,
                offer_amount REAL,
                counter_amount REAL,
                platform TEXT,
                status TEXT DEFAULT 'evaluating',
                fit_score INTEGER,
                evaluation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE INDEX IF NOT EXISTS idx_cr_source ON {self.TABLE_CONTENT_REVENUE}(source);
            CREATE INDEX IF NOT EXISTS idx_bd_status ON {self.TABLE_BRAND_DEALS}(status);
        """)
        db.commit()
        logger.info("ContentMonetisation tables ready.")

    async def track_affiliate_links(self) -> dict:
        """Delegate to AffiliateTracker if available, otherwise pull from SQLite."""
        affiliate = getattr(self.mira, "affiliate", None)
        if affiliate and hasattr(affiliate, "get_summary"):
            try:
                return await affiliate.get_summary()
            except Exception as e:
                logger.warning(f"AffiliateTracker unavailable, falling back to SQLite: {e}")

        # Fallback: aggregate from content_revenue where source is affiliate
        row = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as total_links, COALESCE(SUM(amount), 0) as total_revenue "
            f"FROM {self.TABLE_CONTENT_REVENUE} WHERE source = 'affiliate'"
        ).fetchone()

        return {
            "total_links": row["total_links"] if row else 0,
            "total_revenue": float(row["total_revenue"]) if row else 0.0,
            "source": "sqlite_fallback",
        }

    async def evaluate_brand_deal(
        self,
        brand: str,
        offer_details: str,
        audience_fit: str = "",
    ) -> dict:
        """Evaluate a brand sponsorship opportunity using brain."""
        prompt = (
            "Evaluate this brand deal / sponsorship opportunity. "
            "Return ONLY valid JSON with:\n"
            "- fit_score: 1-10 (audience alignment)\n"
            "- recommendation: 'accept', 'counter', 'decline'\n"
            "- counter_offer: suggested counter-offer amount (USD) if applicable\n"
            "- reasoning: one paragraph\n"
            "- talking_points: list of negotiation points\n"
            "- risks: list of potential downsides\n\n"
            f"Brand: {brand}\n"
            f"Offer details: {offer_details}\n"
            f"Audience fit notes: {audience_fit}\n\n"
            "The user creates content about trading, crypto, AI, BPO operations, and finance."
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override="You are a creator economy advisor. Return ONLY valid JSON.",
            max_tokens=1024,
            tier="standard",
            task_type="brand_deal_eval",
        )

        result = _parse_brain_json(response, fallback={
            "fit_score": 0,
            "recommendation": "evaluate",
            "counter_offer": None,
            "reasoning": "Could not evaluate.",
            "talking_points": [],
            "risks": [],
        })

        # Persist the evaluation
        db = self.mira.sqlite.conn
        db.execute(
            f"""INSERT INTO {self.TABLE_BRAND_DEALS}
                (brand, offer_amount, counter_amount, status, fit_score, evaluation)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (
                brand,
                None,  # raw offer amount not always a single number
                result.get("counter_offer"),
                result.get("recommendation", "evaluating"),
                result.get("fit_score", 0),
                json.dumps(result),
            ),
        )
        db.commit()

        self.mira.sqlite.log_action(
            "earning.content", "evaluate_brand_deal",
            result.get("recommendation", "unknown"),
            {"brand": brand, "fit_score": result.get("fit_score")},
        )
        return result

    async def generate_content_calendar(
        self,
        platforms: list[str],
        weeks_ahead: int = 4,
    ) -> dict:
        """Use brain to plan a content schedule based on second brain topics."""
        # Pull recent high-importance memories for content ideas
        recent = self.mira.sqlite.search_memories(min_importance=4, limit=10)
        topics_context = "\n".join(
            f"- [{m['category']}] {m['content'][:150]}" for m in recent
        ) if recent else "No recent high-importance topics."

        prompt = (
            f"Create a {weeks_ahead}-week content calendar for these platforms: "
            f"{', '.join(platforms)}.\n\n"
            "Return ONLY valid JSON with:\n"
            "- weeks: list of week objects, each with:\n"
            "  - week_number: int\n"
            "  - start_date: string\n"
            "  - posts: list of post objects with:\n"
            "    - platform: string\n"
            "    - content_type: 'video', 'short', 'carousel', 'thread', 'article'\n"
            "    - topic: string\n"
            "    - hook: one-line hook\n"
            "    - best_day: day of week\n"
            "    - best_time: time string\n"
            "    - monetisation: 'affiliate', 'sponsored', 'organic', 'product_plug'\n"
            "- themes: list of overarching themes for the period\n\n"
            f"The user creates content about trading, crypto, AI, BPO, and finance.\n"
            f"Recent topics from their second brain:\n{topics_context}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a content strategist for a finance/tech creator. "
                "Return ONLY valid JSON. Be specific with topic ideas, not generic."
            ),
            max_tokens=2048,
            tier="standard",
            task_type="content_calendar",
        )

        result = _parse_brain_json(response, fallback={
            "weeks": [],
            "themes": [],
        })

        self.mira.sqlite.log_action(
            "earning.content", "generate_content_calendar",
            f"{weeks_ahead} weeks for {', '.join(platforms)}",
            {"platforms": platforms, "weeks": weeks_ahead},
        )
        return result

    async def get_revenue_summary(self, period: str = "month") -> dict:
        """Aggregate content revenue from content_revenue table and action_log."""
        where = _date_filter_sql(period)

        # From dedicated table
        rows = self.mira.sqlite.conn.execute(
            f"SELECT source, COALESCE(SUM(amount), 0) as total "
            f"FROM {self.TABLE_CONTENT_REVENUE} WHERE {where} GROUP BY source"
        ).fetchall()

        by_source = {r["source"]: float(r["total"]) for r in rows}
        grand = sum(by_source.values())

        return {
            "period": period,
            "by_source": by_source,
            "total": round(grand, 2),
        }

    async def get_revenue_for_period(self, period: str = "month") -> float:
        summary = await self.get_revenue_summary(period)
        return summary["total"]

    async def get_status(self) -> str:
        summary = await self.get_revenue_summary("month")
        affiliate = await self.track_affiliate_links()
        active_deals = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as c FROM {self.TABLE_BRAND_DEALS} "
            "WHERE status NOT IN ('declined', 'completed')"
        ).fetchone()["c"]
        return (
            f"Month revenue: ${summary['total']:,.2f}\n"
            f"Sources: {', '.join(summary['by_source'].keys()) or 'none yet'}\n"
            f"Affiliate links tracked: {affiliate['total_links']}\n"
            f"Active brand deals: {active_deals}"
        )


# =====================================================================
# 3. POLYMARKET ALPHA ENGINE
# =====================================================================

class PolymarketEngine:
    """Prediction market alpha — research, identify mispricing, place bets."""

    TABLE_PM_POSITIONS = "polymarket_positions"

    # Risk limits
    MAX_SINGLE_BET_USD = 100
    MAX_TOTAL_EXPOSURE_USD = 500

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create Polymarket-specific tables."""
        db = self.mira.sqlite.conn
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_PM_POSITIONS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT,
                market_question TEXT NOT NULL,
                position TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                entry_odds REAL,
                current_odds REAL,
                exit_odds REAL,
                pnl REAL,
                status TEXT DEFAULT 'open',
                research_summary TEXT,
                confidence INTEGER DEFAULT 5,
                opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE INDEX IF NOT EXISTS idx_pm_status ON {self.TABLE_PM_POSITIONS}(status);
            CREATE INDEX IF NOT EXISTS idx_pm_market ON {self.TABLE_PM_POSITIONS}(market_id);
        """)
        db.commit()
        logger.info("PolymarketEngine tables ready.")

    async def scan_markets(self) -> dict:
        """Use brain to identify market categories where user has edge."""
        # Pull knowledge context
        related = self.mira.vector.search("prediction markets trading edge", n_results=5)
        context_snippets = "\n".join(
            f"- {r['content'][:200]}" for r in related
        ) if related else "No specific market context in memory."

        prompt = (
            "Identify prediction market categories where the user likely has "
            "an informational edge. Return ONLY valid JSON with:\n"
            "- categories: list of objects with:\n"
            "  - name: category name (e.g. 'crypto regulation', 'AI milestones')\n"
            "  - edge_reason: why the user has an edge here\n"
            "  - confidence: 1-10\n"
            "  - example_markets: list of 2-3 example market questions to look for\n"
            "- avoid_categories: list of categories to avoid (no edge)\n"
            "- general_strategy: one-paragraph strategy recommendation\n\n"
            "The user is a senior BPO/finance professional, active crypto/forex trader, "
            "AI enthusiast, based in Philippines. Follows F1, tech, and crypto closely.\n\n"
            f"Relevant knowledge from second brain:\n{context_snippets}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a prediction market strategist. Return ONLY valid JSON. "
                "Focus on categories where real expertise provides informational advantage."
            ),
            max_tokens=1536,
            tier="standard",
            task_type="polymarket_scan",
        )

        result = _parse_brain_json(response, fallback={
            "categories": [],
            "avoid_categories": [],
            "general_strategy": "",
        })

        self.mira.sqlite.log_action(
            "earning.polymarket", "scan_markets",
            f"Identified {len(result.get('categories', []))} edge categories",
            {"categories": [c.get("name") for c in result.get("categories", [])]},
        )
        return result

    async def research_market(
        self,
        market_question: str,
        current_odds: float = 0.5,
    ) -> dict:
        """Deep research on a specific market using Opus for best reasoning."""
        # Pull any related knowledge
        related = self.mira.vector.search(market_question, n_results=5)
        context_snippets = "\n".join(
            f"- {r['content'][:200]}" for r in related
        ) if related else "No directly related context."

        prompt = (
            "Perform deep analysis on this prediction market.\n\n"
            f"Market question: {market_question}\n"
            f"Current market odds: {current_odds:.0%}\n\n"
            "Provide:\n"
            "1. Your estimated true probability (with reasoning)\n"
            "2. Key factors the market may be underweighting\n"
            "3. Key factors the market may be overweighting\n"
            "4. Information you'd want before betting\n"
            "5. Recommended position: YES / NO / ABSTAIN\n"
            "6. Confidence level: 1-10\n"
            "7. Suggested bet size as % of max position ($100)\n\n"
            "Return ONLY valid JSON with fields: estimated_probability, "
            "underweighted_factors (list), overweighted_factors (list), "
            "missing_info (list), position, confidence, bet_size_pct, reasoning.\n\n"
            f"Related knowledge:\n{context_snippets}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a prediction market researcher. Think step by step. "
                "Be calibrated — most markets are approximately efficient. "
                "Only recommend a position if you have genuine conviction. "
                "Return ONLY valid JSON."
            ),
            max_tokens=2048,
            tier="deep",
            task_type="polymarket_research",
        )

        result = _parse_brain_json(response, fallback={
            "estimated_probability": current_odds,
            "position": "ABSTAIN",
            "confidence": 3,
            "bet_size_pct": 0,
            "reasoning": "Could not complete analysis.",
        })

        self.mira.sqlite.log_action(
            "earning.polymarket", "research_market",
            result.get("position", "ABSTAIN"),
            {
                "market": market_question[:100],
                "odds": current_odds,
                "est_prob": result.get("estimated_probability"),
                "confidence": result.get("confidence"),
            },
        )
        return result

    async def evaluate_bet(
        self,
        market_id: str,
        position: str,
        amount: float,
        market_question: str = "",
    ) -> dict:
        """Risk check a proposed bet against defined limits."""
        # Check single-bet limit
        if amount > self.MAX_SINGLE_BET_USD:
            return {
                "approved": False,
                "reason": f"Amount ${amount} exceeds single-bet limit of ${self.MAX_SINGLE_BET_USD}",
            }

        # Check total exposure
        row = self.mira.sqlite.conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) as exposure "
            f"FROM {self.TABLE_PM_POSITIONS} WHERE status = 'open'"
        ).fetchone()
        current_exposure = float(row["exposure"]) if row else 0.0

        if current_exposure + amount > self.MAX_TOTAL_EXPOSURE_USD:
            return {
                "approved": False,
                "reason": (
                    f"Would bring total exposure to ${current_exposure + amount:.2f}, "
                    f"exceeding limit of ${self.MAX_TOTAL_EXPOSURE_USD}"
                ),
                "current_exposure": current_exposure,
            }

        # Log the approved evaluation
        self.mira.sqlite.log_action(
            "earning.polymarket", "evaluate_bet",
            "approved",
            {
                "market_id": market_id,
                "position": position,
                "amount": amount,
                "current_exposure": current_exposure,
            },
        )

        return {
            "approved": True,
            "market_id": market_id,
            "position": position,
            "amount": amount,
            "current_exposure": current_exposure,
            "remaining_capacity": self.MAX_TOTAL_EXPOSURE_USD - current_exposure - amount,
        }

    async def get_performance(self, period: str = "month") -> dict:
        """Aggregate Polymarket P&L from positions table and trades table."""
        where = _date_filter_sql(period)

        # From polymarket_positions
        pm_row = self.mira.sqlite.conn.execute(
            f"SELECT COALESCE(SUM(pnl), 0) as pnl, COUNT(*) as trades "
            f"FROM {self.TABLE_PM_POSITIONS} WHERE status = 'closed' AND {where}"
        ).fetchone()

        # Also check trades table for platform = 'polymarket'
        trades_row = self.mira.sqlite.conn.execute(
            f"SELECT COALESCE(SUM(pnl), 0) as pnl, COUNT(*) as trades "
            f"FROM trades WHERE platform = 'polymarket' AND closed_at IS NOT NULL AND {where}"
        ).fetchone()

        open_row = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as c, COALESCE(SUM(amount), 0) as exposure "
            f"FROM {self.TABLE_PM_POSITIONS} WHERE status = 'open'"
        ).fetchone()

        total_pnl = float(pm_row["pnl"]) + float(trades_row["pnl"])
        total_trades = pm_row["trades"] + trades_row["trades"]

        return {
            "period": period,
            "total_pnl": round(total_pnl, 2),
            "total_closed_trades": total_trades,
            "open_positions": open_row["c"] if open_row else 0,
            "current_exposure": float(open_row["exposure"]) if open_row else 0.0,
        }

    async def get_revenue_for_period(self, period: str = "month") -> float:
        perf = await self.get_performance(period)
        return max(perf["total_pnl"], 0)  # Only count positive P&L as revenue

    async def get_status(self) -> str:
        perf = await self.get_performance("month")
        return (
            f"Month P&L: ${perf['total_pnl']:+,.2f}\n"
            f"Closed trades (month): {perf['total_closed_trades']}\n"
            f"Open positions: {perf['open_positions']}\n"
            f"Current exposure: ${perf['current_exposure']:,.2f} / ${self.MAX_TOTAL_EXPOSURE_USD}"
        )


# =====================================================================
# 4. DIGITAL PRODUCT STORE
# =====================================================================

class DigitalProductStore:
    """Digital product sales — templates, guides, tools on Gumroad/Etsy/own site."""

    TABLE_PRODUCTS = "digital_products"
    TABLE_SALES = "digital_product_sales"

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create digital product tables."""
        db = self.mira.sqlite.conn
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_PRODUCTS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                listing_copy TEXT,
                price REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                platform TEXT DEFAULT 'gumroad',
                status TEXT DEFAULT 'draft',
                total_sales INTEGER DEFAULT 0,
                total_revenue REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE TABLE IF NOT EXISTS {self.TABLE_SALES} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                platform TEXT DEFAULT 'gumroad',
                buyer_info TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES {self.TABLE_PRODUCTS}(id)
            );

            CREATE INDEX IF NOT EXISTS idx_dp_status ON {self.TABLE_PRODUCTS}(status);
            CREATE INDEX IF NOT EXISTS idx_ds_product ON {self.TABLE_SALES}(product_id);
        """)
        db.commit()
        logger.info("DigitalProductStore tables ready.")

    async def generate_product_idea(self) -> dict:
        """Generate a product idea from second brain insights and expertise areas."""
        # Pull high-value knowledge
        knowledge = self.mira.sqlite.search_memories(min_importance=4, limit=15)
        context = "\n".join(
            f"- [{m['category']}] {m['content'][:150]}" for m in knowledge
        ) if knowledge else "No high-importance memories yet."

        # Check existing products to avoid duplicates
        existing = self.mira.sqlite.conn.execute(
            f"SELECT name, description FROM {self.TABLE_PRODUCTS} LIMIT 10"
        ).fetchall()
        existing_list = "\n".join(
            f"- {r['name']}: {(r['description'] or '')[:80]}" for r in existing
        ) if existing else "None yet."

        prompt = (
            "Generate a digital product idea based on the user's expertise. "
            "Return ONLY valid JSON with:\n"
            "- name: product name\n"
            "- type: 'template', 'guide', 'course', 'tool', 'dashboard'\n"
            "- description: 2-3 sentence description\n"
            "- target_audience: who would buy this\n"
            "- price_usd: recommended price\n"
            "- platform: 'gumroad', 'etsy', or 'own_site'\n"
            "- effort_hours: estimated hours to create\n"
            "- monthly_revenue_estimate: realistic monthly revenue\n"
            "- unique_angle: what makes this different from existing products\n"
            "- outline: list of 5-8 sections/components\n\n"
            "User expertise: BPO operations, finance/accounting, data analysis, "
            "Excel/Sheets, trading systems, AI automation, process optimisation.\n\n"
            f"Knowledge from second brain:\n{context}\n\n"
            f"Existing products (avoid duplicates):\n{existing_list}"
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a digital product strategist. Return ONLY valid JSON. "
                "Focus on products that leverage unique expertise and can generate passive income."
            ),
            max_tokens=1536,
            tier="standard",
            task_type="product_idea",
        )

        result = _parse_brain_json(response, fallback={
            "name": "",
            "type": "guide",
            "description": "",
            "target_audience": "",
            "price_usd": 0,
            "platform": "gumroad",
            "effort_hours": 0,
            "monthly_revenue_estimate": 0,
            "unique_angle": "",
            "outline": [],
        })

        self.mira.sqlite.log_action(
            "earning.digital_products", "generate_product_idea",
            result.get("name", "unnamed"),
            {"type": result.get("type"), "price": result.get("price_usd")},
        )
        return result

    async def create_product_listing(
        self,
        product_name: str,
        description: str,
        price: float,
        platform: str = "gumroad",
    ) -> dict:
        """Generate platform-ready listing copy and store the product."""
        prompt = (
            f"Write a compelling product listing for '{product_name}' on {platform}.\n\n"
            f"Description: {description}\n"
            f"Price: ${price}\n\n"
            "Write:\n"
            "1. A headline that grabs attention (max 10 words)\n"
            "2. A short description (2-3 sentences)\n"
            "3. Key features / what's included (bullet list, 5-8 items)\n"
            "4. Who this is for (2-3 bullet points)\n"
            "5. A social proof line (even if placeholder)\n"
            "6. Call to action\n\n"
            "Write in a confident, direct tone. No hype, no fluff."
        )

        listing_copy = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a conversion copywriter for digital products. "
                "Write copy that sells without being sleazy."
            ),
            max_tokens=1024,
            tier="standard",
            task_type="product_listing",
        )

        # Store in database
        db = self.mira.sqlite.conn
        cursor = db.execute(
            f"""INSERT INTO {self.TABLE_PRODUCTS}
                (name, description, listing_copy, price, platform, status)
                VALUES (?, ?, ?, ?, ?, 'listed')""",
            (product_name, description, listing_copy, price, platform),
        )
        db.commit()
        product_id = cursor.lastrowid

        self.mira.sqlite.log_action(
            "earning.digital_products", "create_listing",
            f"Listed '{product_name}' at ${price} on {platform}",
            {"product_id": product_id},
        )

        return {
            "product_id": product_id,
            "listing_copy": listing_copy,
            "status": "listed",
        }

    async def get_sales_report(self, period: str = "month") -> dict:
        """Query sales data from SQLite."""
        where = _date_filter_sql(period)

        rows = self.mira.sqlite.conn.execute(
            f"""SELECT p.name, p.platform, COUNT(s.id) as sales, COALESCE(SUM(s.amount), 0) as revenue
                FROM {self.TABLE_SALES} s
                JOIN {self.TABLE_PRODUCTS} p ON s.product_id = p.id
                WHERE s.{where}
                GROUP BY p.id
                ORDER BY revenue DESC"""
        ).fetchall()

        products = [
            {
                "name": r["name"],
                "platform": r["platform"],
                "sales": r["sales"],
                "revenue": float(r["revenue"]),
            }
            for r in rows
        ]

        total_revenue = sum(p["revenue"] for p in products)
        total_sales = sum(p["sales"] for p in products)

        return {
            "period": period,
            "products": products,
            "total_sales": total_sales,
            "total_revenue": round(total_revenue, 2),
        }

    async def log_sale(
        self,
        product_id: int,
        amount: float,
        platform: str = "gumroad",
        buyer_info: str = None,
    ) -> dict:
        """Record a sale."""
        db = self.mira.sqlite.conn

        db.execute(
            f"INSERT INTO {self.TABLE_SALES} (product_id, amount, platform, buyer_info) "
            "VALUES (?, ?, ?, ?)",
            (product_id, amount, platform, buyer_info),
        )

        # Update product totals
        db.execute(
            f"UPDATE {self.TABLE_PRODUCTS} "
            "SET total_sales = total_sales + 1, total_revenue = total_revenue + ? "
            "WHERE id = ?",
            (amount, product_id),
        )
        db.commit()

        self.mira.sqlite.log_action(
            "earning.digital_products", "sale",
            f"${amount:.2f} on {platform}",
            {"product_id": product_id, "amount": amount},
        )

        return {"status": "recorded", "product_id": product_id, "amount": amount}

    async def get_revenue_for_period(self, period: str = "month") -> float:
        report = await self.get_sales_report(period)
        return report["total_revenue"]

    async def get_status(self) -> str:
        report = await self.get_sales_report("month")
        total_products = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as c FROM {self.TABLE_PRODUCTS}"
        ).fetchone()["c"]
        listed = self.mira.sqlite.conn.execute(
            f"SELECT COUNT(*) as c FROM {self.TABLE_PRODUCTS} WHERE status = 'listed'"
        ).fetchone()["c"]
        return (
            f"Products: {total_products} total, {listed} listed\n"
            f"Month sales: {report['total_sales']} units, ${report['total_revenue']:,.2f}\n"
            f"Platforms: Gumroad, Etsy, own website"
        )


# =====================================================================
# 5. CONSULTING PIPELINE
# =====================================================================

class ConsultingPipeline:
    """Consulting lead generation and management — LinkedIn leads, outreach, discovery."""

    TABLE_LEADS = "consulting_leads"
    TABLE_ENGAGEMENTS = "consulting_engagements"

    def __init__(self, mira):
        self.mira = mira

    async def initialise(self):
        """Create consulting pipeline tables."""
        db = self.mira.sqlite.conn
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_LEADS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                role TEXT,
                linkedin_url TEXT,
                email TEXT,
                source TEXT DEFAULT 'linkedin',
                stage TEXT DEFAULT 'identified',
                outreach_message TEXT,
                notes TEXT,
                score INTEGER DEFAULT 0,
                next_action TEXT,
                next_action_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{{}}'
            );

            CREATE TABLE IF NOT EXISTS {self.TABLE_ENGAGEMENTS} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                title TEXT NOT NULL,
                scope TEXT,
                monthly_rate REAL DEFAULT 0,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES {self.TABLE_LEADS}(id)
            );

            CREATE INDEX IF NOT EXISTS idx_cl_stage ON {self.TABLE_LEADS}(stage);
            CREATE INDEX IF NOT EXISTS idx_ce_status ON {self.TABLE_ENGAGEMENTS}(status);
        """)
        db.commit()
        logger.info("ConsultingPipeline tables ready.")

    async def scan_linkedin_leads(self) -> dict:
        """Use brain to generate ideal client profiles and search criteria."""
        prompt = (
            "Generate a LinkedIn lead generation strategy for consulting services. "
            "Return ONLY valid JSON with:\n"
            "- ideal_client_profiles: list of 3-5 profiles, each with:\n"
            "  - industry: target industry\n"
            "  - company_size: e.g. '50-500 employees'\n"
            "  - titles: list of job titles to target\n"
            "  - pain_points: list of problems they likely have\n"
            "  - service_fit: what we'd offer them\n"
            "- search_strings: list of 5 LinkedIn search queries\n"
            "- outreach_channels: ordered list of best channels\n"
            "- qualification_criteria: list of must-have signals\n"
            "- disqualifiers: list of red flags to skip\n\n"
            "The user offers consulting in:\n"
            "- BPO operations setup and optimisation\n"
            "- Finance systems and process automation\n"
            "- AI/automation implementation for operations teams\n"
            "- Data analysis and reporting frameworks\n"
            "Rate range: $60-$120/hr or $5,000-$15,000/month retainer."
        )

        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are a B2B lead generation strategist. Return ONLY valid JSON. "
                "Be specific and actionable — these search strings will be used directly."
            ),
            max_tokens=1536,
            tier="standard",
            task_type="consulting_lead_scan",
        )

        result = _parse_brain_json(response, fallback={
            "ideal_client_profiles": [],
            "search_strings": [],
            "outreach_channels": [],
            "qualification_criteria": [],
            "disqualifiers": [],
        })

        self.mira.sqlite.log_action(
            "earning.consulting", "scan_linkedin_leads",
            f"Generated {len(result.get('ideal_client_profiles', []))} client profiles",
            {"search_strings_count": len(result.get("search_strings", []))},
        )
        return result

    async def draft_outreach(
        self,
        lead_name: str,
        company: str,
        context: str = "",
    ) -> dict:
        """Draft a personalised outreach message using brain."""
        # Check if we know this person
        person = self.mira.sqlite.get_person(lead_name)
        person_context = ""
        if person:
            facts = json.loads(person.get("key_facts", "[]"))
            person_context = f"Known facts: {', '.join(facts)}" if facts else ""

        prompt = (
            f"Write a personalised LinkedIn outreach message to {lead_name} at {company}.\n\n"
            "Rules:\n"
            "- Max 150 words\n"
            "- No 'I hope this finds you well' or generic openings\n"
            "- Lead with a specific observation about their company or role\n"
            "- Connect it to a relevant problem you solve\n"
            "- End with a low-friction CTA (not 'book a call' — too aggressive)\n"
            "- Sound like a peer, not a salesperson\n\n"
            f"Context about {lead_name}: {context}\n"
            f"{person_context}\n\n"
            "Services offered: BPO operations, finance automation, AI implementation, "
            "data analysis frameworks."
        )

        message = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=(
                "You are writing as the user — a senior operations/finance professional. "
                "Write in first person, be direct and authentic. No corporate speak."
            ),
            max_tokens=512,
            tier="standard",
            task_type="consulting_outreach",
        )

        # Store or update the lead
        db = self.mira.sqlite.conn
        existing = db.execute(
            f"SELECT id FROM {self.TABLE_LEADS} WHERE name = ? AND company = ?",
            (lead_name, company),
        ).fetchone()

        if existing:
            lead_id = existing["id"]
            db.execute(
                f"UPDATE {self.TABLE_LEADS} SET outreach_message = ?, stage = 'outreach_drafted', "
                "updated_at = ? WHERE id = ?",
                (message, datetime.now().isoformat(), lead_id),
            )
        else:
            cursor = db.execute(
                f"INSERT INTO {self.TABLE_LEADS} (name, company, outreach_message, stage) "
                "VALUES (?, ?, ?, 'outreach_drafted')",
                (lead_name, company, message),
            )
            lead_id = cursor.lastrowid
        db.commit()

        self.mira.sqlite.log_action(
            "earning.consulting", "draft_outreach",
            f"Drafted outreach to {lead_name} at {company}",
            {"lead_id": lead_id},
        )

        return {
            "lead_id": lead_id,
            "message": message,
            "status": "drafted",
        }

    async def schedule_discovery(
        self,
        lead_id: int,
        proposed_times: list[str],
    ) -> dict:
        """Create a follow-up task for discovery call scheduling."""
        # Get lead info
        lead = self.mira.sqlite.conn.execute(
            f"SELECT * FROM {self.TABLE_LEADS} WHERE id = ?", (lead_id,)
        ).fetchone()

        if not lead:
            return {"status": "error", "reason": f"Lead #{lead_id} not found"}

        lead_name = lead["name"]
        company = lead["company"] or "unknown company"

        # Create a task for follow-up
        times_str = ", ".join(proposed_times)
        task_id = self.mira.sqlite.add_task(
            title=f"Schedule discovery call with {lead_name} ({company})",
            description=f"Proposed times: {times_str}",
            priority=2,
            module="earning.consulting",
            due_date=proposed_times[0] if proposed_times else None,
        )

        # Update lead stage
        db = self.mira.sqlite.conn
        db.execute(
            f"UPDATE {self.TABLE_LEADS} SET stage = 'discovery_pending', "
            "next_action = 'schedule_discovery', next_action_date = ?, updated_at = ? WHERE id = ?",
            (proposed_times[0] if proposed_times else None, datetime.now().isoformat(), lead_id),
        )
        db.commit()

        self.mira.sqlite.log_action(
            "earning.consulting", "schedule_discovery",
            f"Created follow-up task for {lead_name}",
            {"lead_id": lead_id, "task_id": task_id, "proposed_times": proposed_times},
        )

        return {
            "status": "task_created",
            "task_id": task_id,
            "lead_id": lead_id,
            "proposed_times": proposed_times,
        }

    async def get_pipeline_status(self) -> dict:
        """Get full pipeline status from SQLite."""
        db = self.mira.sqlite.conn

        # Leads by stage
        stage_rows = db.execute(
            f"SELECT stage, COUNT(*) as count FROM {self.TABLE_LEADS} GROUP BY stage"
        ).fetchall()
        by_stage = {r["stage"]: r["count"] for r in stage_rows}

        # Active engagements
        engagements = db.execute(
            f"SELECT * FROM {self.TABLE_ENGAGEMENTS} WHERE status = 'active'"
        ).fetchall()

        monthly_revenue = sum(float(e["monthly_rate"]) for e in engagements)

        # Recent leads
        recent = db.execute(
            f"SELECT id, name, company, stage, score, next_action "
            f"FROM {self.TABLE_LEADS} ORDER BY updated_at DESC LIMIT 10"
        ).fetchall()

        return {
            "leads_by_stage": by_stage,
            "total_leads": sum(by_stage.values()),
            "active_engagements": len(engagements),
            "monthly_retainer_revenue": round(monthly_revenue, 2),
            "recent_leads": [dict(r) for r in recent],
        }

    async def get_revenue_for_period(self, period: str = "month") -> float:
        """Sum active engagement revenue (monthly retainers)."""
        row = self.mira.sqlite.conn.execute(
            f"SELECT COALESCE(SUM(monthly_rate), 0) as total "
            f"FROM {self.TABLE_ENGAGEMENTS} WHERE status = 'active'"
        ).fetchone()
        return float(row["total"]) if row else 0.0

    async def get_status(self) -> str:
        pipeline = await self.get_pipeline_status()
        stages = pipeline["leads_by_stage"]
        stage_str = ", ".join(f"{k}: {v}" for k, v in stages.items()) if stages else "empty"
        return (
            f"Pipeline: {pipeline['total_leads']} leads ({stage_str})\n"
            f"Active engagements: {pipeline['active_engagements']}\n"
            f"Monthly retainer revenue: ${pipeline['monthly_retainer_revenue']:,.2f}\n"
            f"Target: BPO ops, finance systems, AI automation"
        )
