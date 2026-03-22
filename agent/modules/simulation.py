"""
Future Simulation Engine — probabilistic projections grounded in real user data.

Section 11.5 of the Mira spec. Runs "what if" simulations using accumulated
memory, trade history, spending patterns, and work data, then reasons about
outcomes via Claude.

Example outputs:
- "If you maintain this DCA strategy for 24 months, projected portfolio range
   is $X–$Y based on historical volatility."
- "Based on your spending patterns, you will reach your savings target in X months."
- "Your current workload pattern historically precedes burnout in 6–8 weeks."
"""

import json
import logging
import math
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("mira.modules.simulation")

SIMULATION_SYSTEM = """You are Mira's Future Simulation Engine. You run probabilistic projections
grounded in real user data — trade history, spending, workload, memories.

Rules:
- Always produce THREE scenarios: optimistic, realistic, pessimistic.
- Back every number with the data provided. Never invent data points.
- Be honest about uncertainty. State confidence level (low/medium/high) for each projection.
- Use Mira's direct, no-fluff communication style.
- Return ONLY valid JSON matching the requested schema. No markdown, no commentary."""


class SimulationEngine:
    """Runs probabilistic simulations grounded in the user's real data."""

    def __init__(self, mira):
        self.mira = mira

    # ── Public API ────────────────────────────────────────────────────

    async def run_financial_projection(
        self,
        scenario: str,
        timeframe_months: int = 12,
        parameters: dict = None,
    ) -> dict:
        """Project portfolio value, savings, or income based on historical patterns.

        Args:
            scenario: Description of what to project (e.g. "portfolio growth",
                      "monthly income trajectory", "crypto allocation impact").
            timeframe_months: How many months to project forward.
            parameters: Optional overrides (e.g. {"monthly_contribution": 500}).

        Returns:
            Dict with optimistic/realistic/pessimistic projections and reasoning.
        """
        parameters = parameters or {}

        # Pull historical financial data
        trades = self.mira.sqlite.get_trade_history(limit=200)
        financial_memories = self.mira.sqlite.search_memories(
            category="trading", limit=50
        )
        spending_memories = self.mira.sqlite.search_memories(
            query="spend", limit=30
        )
        income_memories = self.mira.sqlite.search_memories(
            query="income", limit=30
        )

        # Compute trade statistics
        trade_stats = self._compute_trade_stats(trades)

        data_package = {
            "scenario": scenario,
            "timeframe_months": timeframe_months,
            "parameters": parameters,
            "trade_stats": trade_stats,
            "financial_memory_samples": [
                m["content"][:200] for m in financial_memories[:15]
            ],
            "spending_memory_samples": [
                m["content"][:200] for m in spending_memories[:10]
            ],
            "income_memory_samples": [
                m["content"][:200] for m in income_memories[:10]
            ],
        }

        prompt = f"""Run a financial projection simulation.

Input data:
{json.dumps(data_package, indent=2, default=str)}

Return JSON with this exact structure:
{{
  "scenario": "<scenario description>",
  "timeframe_months": <int>,
  "projections": {{
    "optimistic": {{
      "outcome": "<description>",
      "projected_value": "<number or range>",
      "monthly_growth_rate": "<percentage>",
      "key_assumptions": ["<assumption1>", "<assumption2>"],
      "confidence": "low|medium|high"
    }},
    "realistic": {{
      "outcome": "<description>",
      "projected_value": "<number or range>",
      "monthly_growth_rate": "<percentage>",
      "key_assumptions": ["<assumption1>", "<assumption2>"],
      "confidence": "low|medium|high"
    }},
    "pessimistic": {{
      "outcome": "<description>",
      "projected_value": "<number or range>",
      "monthly_growth_rate": "<percentage>",
      "key_assumptions": ["<assumption1>", "<assumption2>"],
      "confidence": "low|medium|high"
    }}
  }},
  "data_quality_note": "<honest assessment of data sufficiency>",
  "recommendation": "<one actionable takeaway>"
}}"""

        result = await self._run_simulation(
            prompt=prompt,
            tier="deep",
            task_type="financial_projection",
        )
        return result

    async def run_workload_analysis(self) -> dict:
        """Analyse work patterns from memory and predict burnout risk.

        Pulls action logs, work memories, and task data to assess workload
        trajectory and flag early burnout indicators.
        """
        # Pull work-related data
        work_memories = self.mira.sqlite.search_memories(
            category="work", limit=60
        )
        recent_actions = self.mira.sqlite.conn.execute(
            "SELECT * FROM action_log WHERE created_at >= DATE('now', '-30 days') ORDER BY created_at"
        ).fetchall()
        pending_tasks = self.mira.sqlite.get_pending_tasks()
        all_tasks = self.mira.sqlite.conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100"
        ).fetchall()

        # Compute action density by day
        action_density = {}
        for a in recent_actions:
            row = dict(a)
            day = row["created_at"][:10] if row.get("created_at") else "unknown"
            action_density[day] = action_density.get(day, 0) + 1

        # Task completion rate
        completed_tasks = [dict(t) for t in all_tasks if dict(t).get("status") == "completed"]
        completion_rate = (
            len(completed_tasks) / len(all_tasks) * 100
            if all_tasks
            else 0
        )

        data_package = {
            "work_memory_samples": [m["content"][:200] for m in work_memories[:20]],
            "action_density_last_30d": action_density,
            "avg_daily_actions": (
                round(sum(action_density.values()) / max(len(action_density), 1), 1)
            ),
            "pending_tasks_count": len(pending_tasks),
            "pending_tasks_high_priority": len(
                [t for t in pending_tasks if t.get("priority", 3) <= 2]
            ),
            "task_completion_rate_pct": round(completion_rate, 1),
            "total_tasks_tracked": len(all_tasks),
        }

        prompt = f"""Analyse the user's workload and predict burnout risk.

Input data:
{json.dumps(data_package, indent=2, default=str)}

Return JSON with this exact structure:
{{
  "burnout_risk": "low|moderate|high|critical",
  "risk_score": <1-10>,
  "current_workload_assessment": "<2-3 sentence assessment>",
  "projections": {{
    "optimistic": {{
      "outcome": "<what happens if they adjust now>",
      "timeline": "<when things improve>",
      "confidence": "low|medium|high"
    }},
    "realistic": {{
      "outcome": "<what happens on current trajectory>",
      "timeline": "<expected timeframe>",
      "confidence": "low|medium|high"
    }},
    "pessimistic": {{
      "outcome": "<what happens if workload increases>",
      "timeline": "<when burnout likely hits>",
      "confidence": "low|medium|high"
    }}
  }},
  "warning_signals": ["<signal1>", "<signal2>"],
  "recommended_offloads": ["<thing1 to delegate/drop>", "<thing2>"],
  "data_quality_note": "<honest assessment of data sufficiency>"
}}"""

        result = await self._run_simulation(
            prompt=prompt,
            tier="standard",
            task_type="workload_analysis",
        )
        return result

    async def run_savings_projection(
        self,
        target_amount: float,
        current_amount: float,
        monthly_contribution: float,
    ) -> dict:
        """Project when a savings target will be reached.

        Args:
            target_amount: Goal amount (e.g. 50000).
            current_amount: Current savings balance.
            monthly_contribution: Expected monthly deposit.

        Returns:
            Dict with three scenarios and estimated months to target.
        """
        # Pull spending and income patterns for context
        spending_memories = self.mira.sqlite.search_memories(
            query="spend", limit=20
        )
        income_memories = self.mira.sqlite.search_memories(
            query="income", limit=20
        )
        financial_memories = self.mira.sqlite.search_memories(
            category="trading", limit=20
        )

        # Simple math baseline (no interest)
        remaining = target_amount - current_amount
        if monthly_contribution > 0:
            months_simple = math.ceil(remaining / monthly_contribution)
        else:
            months_simple = None  # Can't reach target without contributions

        data_package = {
            "target_amount": target_amount,
            "current_amount": current_amount,
            "monthly_contribution": monthly_contribution,
            "remaining": remaining,
            "simple_months_estimate": months_simple,
            "spending_context": [m["content"][:200] for m in spending_memories[:10]],
            "income_context": [m["content"][:200] for m in income_memories[:10]],
            "trading_context": [m["content"][:200] for m in financial_memories[:10]],
        }

        prompt = f"""Project when the user will reach their savings target.

Input data:
{json.dumps(data_package, indent=2, default=str)}

Factor in:
- The simple math baseline (remaining / monthly_contribution)
- Potential interest or investment returns
- Their historical spending patterns (do they tend to dip into savings?)
- Income variability from memories

Return JSON with this exact structure:
{{
  "target_amount": {target_amount},
  "current_amount": {current_amount},
  "monthly_contribution": {monthly_contribution},
  "projections": {{
    "optimistic": {{
      "months_to_target": <int>,
      "target_date": "<YYYY-MM>",
      "assumptions": "<what goes right>",
      "monthly_effective_rate": "<percentage including returns>",
      "confidence": "low|medium|high"
    }},
    "realistic": {{
      "months_to_target": <int>,
      "target_date": "<YYYY-MM>",
      "assumptions": "<base case>",
      "monthly_effective_rate": "<percentage>",
      "confidence": "low|medium|high"
    }},
    "pessimistic": {{
      "months_to_target": <int or null>,
      "target_date": "<YYYY-MM or 'unlikely at current rate'>",
      "assumptions": "<what could delay it>",
      "monthly_effective_rate": "<percentage>",
      "confidence": "low|medium|high"
    }}
  }},
  "tip": "<one actionable suggestion to reach target faster>",
  "data_quality_note": "<honest assessment>"
}}"""

        result = await self._run_simulation(
            prompt=prompt,
            tier="standard",
            task_type="savings_projection",
        )
        return result

    async def run_dca_simulation(
        self,
        strategy: str,
        monthly_amount: float,
        months: int = 24,
        asset_class: str = "crypto",
    ) -> dict:
        """Project DCA outcomes using Monte Carlo reasoning via Claude.

        Rather than running thousands of random walks locally, we give Claude
        the historical data and ask it to reason through scenario distributions
        — a "Claude Monte Carlo" that incorporates qualitative context a pure
        random walk would miss.

        Args:
            strategy: Description (e.g. "50% BTC / 30% ETH / 20% stables").
            monthly_amount: Dollar amount per month.
            months: Number of months to simulate.
            asset_class: "crypto", "forex", "equities", or "mixed".
        """
        # Pull trade history for the relevant asset class
        trades = self.mira.sqlite.get_trade_history(limit=200)
        relevant_trades = [
            t for t in trades
            if (asset_class == "crypto" and t.get("platform") in ("kraken", "binance", "crypto.com"))
            or (asset_class == "forex" and t.get("platform") == "mt5")
            or asset_class in ("equities", "mixed")
        ]

        trade_stats = self._compute_trade_stats(relevant_trades)

        # Pull any market-related memories
        market_memories = self.mira.sqlite.search_memories(
            query=asset_class, limit=20
        )

        data_package = {
            "strategy": strategy,
            "monthly_amount": monthly_amount,
            "months": months,
            "asset_class": asset_class,
            "total_invested": monthly_amount * months,
            "historical_trade_stats": trade_stats,
            "market_memory_samples": [m["content"][:200] for m in market_memories[:10]],
        }

        prompt = f"""Run a Monte Carlo-style DCA simulation using reasoning.

Input data:
{json.dumps(data_package, indent=2, default=str)}

Think through this like a Monte Carlo simulation:
1. Consider the historical volatility of {asset_class} assets.
2. Model different market regimes (bull, sideways, bear, crash+recovery).
3. Factor in DCA's natural cost-averaging benefit.
4. Weight scenarios by rough historical probability.

Return JSON with this exact structure:
{{
  "strategy": "{strategy}",
  "monthly_amount": {monthly_amount},
  "months": {months},
  "total_invested": {monthly_amount * months},
  "projections": {{
    "optimistic": {{
      "portfolio_value": "<projected value>",
      "total_return_pct": "<percentage>",
      "scenario_description": "<what market conditions lead here>",
      "probability_estimate": "<rough % chance>",
      "confidence": "low|medium|high"
    }},
    "realistic": {{
      "portfolio_value": "<projected value>",
      "total_return_pct": "<percentage>",
      "scenario_description": "<what market conditions lead here>",
      "probability_estimate": "<rough % chance>",
      "confidence": "low|medium|high"
    }},
    "pessimistic": {{
      "portfolio_value": "<projected value>",
      "total_return_pct": "<percentage>",
      "scenario_description": "<what market conditions lead here>",
      "probability_estimate": "<rough % chance>",
      "confidence": "low|medium|high"
    }}
  }},
  "dca_advantage_note": "<how DCA specifically helps in this scenario>",
  "risk_factors": ["<risk1>", "<risk2>"],
  "recommendation": "<one actionable takeaway>",
  "data_quality_note": "<honest assessment>"
}}"""

        result = await self._run_simulation(
            prompt=prompt,
            tier="deep",
            task_type="dca_simulation",
        )
        return result

    async def run_custom_simulation(
        self,
        question: str,
        relevant_data: dict = None,
    ) -> dict:
        """Use Opus to reason about any "what if" scenario using accumulated memory.

        This is the open-ended simulation endpoint. Pass any question and
        optionally pre-gathered data; the engine pulls additional context from
        memory automatically.

        Args:
            question: The "what if" question (e.g. "What if I quit Boldr and
                      went full-time on consulting?").
            relevant_data: Optional dict of pre-gathered context.
        """
        relevant_data = relevant_data or {}

        # Auto-gather broad context from memory
        memories = self.mira.sqlite.search_memories(limit=40)
        recent_decisions = self.mira.sqlite.conn.execute(
            "SELECT decision, context, reasoning, outcome, domain FROM decisions "
            "ORDER BY decided_at DESC LIMIT 20"
        ).fetchall()
        trades = self.mira.sqlite.get_trade_history(limit=30)
        people = self.mira.sqlite.get_all_people()
        pending_tasks = self.mira.sqlite.get_pending_tasks()

        data_package = {
            "question": question,
            "user_provided_data": relevant_data,
            "memory_context": [m["content"][:200] for m in memories[:20]],
            "recent_decisions": [dict(d) for d in recent_decisions[:10]],
            "trade_summary": self._compute_trade_stats(trades),
            "people_count": len(people),
            "key_relationships": [
                {"name": p["name"], "type": p.get("relationship_type")}
                for p in people[:10]
            ],
            "pending_tasks_count": len(pending_tasks),
        }

        prompt = f"""Run a custom future simulation for this question:

"{question}"

All available context about the user:
{json.dumps(data_package, indent=2, default=str)}

Think deeply. Consider second-order effects, emotional impact, financial
implications, relationship dynamics, and opportunity costs.

Return JSON with this exact structure:
{{
  "question": "{question}",
  "projections": {{
    "optimistic": {{
      "outcome": "<detailed description of best-case>",
      "timeline": "<when this plays out>",
      "key_factors": ["<factor1>", "<factor2>"],
      "confidence": "low|medium|high"
    }},
    "realistic": {{
      "outcome": "<detailed description of likely case>",
      "timeline": "<when this plays out>",
      "key_factors": ["<factor1>", "<factor2>"],
      "confidence": "low|medium|high"
    }},
    "pessimistic": {{
      "outcome": "<detailed description of worst-case>",
      "timeline": "<when this plays out>",
      "key_factors": ["<factor1>", "<factor2>"],
      "confidence": "low|medium|high"
    }}
  }},
  "blind_spots": ["<thing they might not have considered>"],
  "second_order_effects": ["<downstream consequence>"],
  "recommendation": "<honest, direct advice>",
  "data_quality_note": "<honest assessment of how much real data backed this>"
}}"""

        result = await self._run_simulation(
            prompt=prompt,
            tier="deep",
            task_type="custom_simulation",
        )
        return result

    # ── Internal helpers ──────────────────────────────────────────────

    async def _run_simulation(
        self,
        prompt: str,
        tier: str = "standard",
        task_type: str = "simulation",
    ) -> dict:
        """Execute a simulation prompt via brain.think() and parse the JSON response.

        Handles JSON extraction from markdown fences, logs to action_log,
        and returns a fallback dict on parse failure.
        """
        response = await self.mira.brain.think(
            message=prompt,
            include_history=False,
            system_override=SIMULATION_SYSTEM,
            max_tokens=4096,
            tier=tier,
            task_type=task_type,
        )

        # Parse JSON from response (may be wrapped in markdown fences)
        parsed = self._parse_json_response(response)

        # Log the simulation run
        self.mira.sqlite.log_action(
            module="simulation",
            action=task_type,
            outcome="success" if parsed.get("_parse_ok") else "parse_error",
            details={
                "tier": tier,
                "task_type": task_type,
                "has_projections": "projections" in parsed,
            },
        )

        # Remove internal parse flag before returning
        parsed.pop("_parse_ok", None)
        return parsed

    def _parse_json_response(self, response: str) -> dict:
        """Extract JSON from a Claude response, handling markdown fences."""
        text = response.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            # Remove closing fence
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]

        text = text.strip()

        try:
            result = json.loads(text)
            result["_parse_ok"] = True
            return result
        except json.JSONDecodeError:
            # Try to find JSON object in the response
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    result = json.loads(text[start : end + 1])
                    result["_parse_ok"] = True
                    return result
                except json.JSONDecodeError:
                    pass

            logger.warning(f"Failed to parse simulation JSON: {text[:300]}")
            return {
                "_parse_ok": False,
                "error": "Failed to parse simulation result",
                "raw_response": response,
            }

    def _compute_trade_stats(self, trades: list) -> dict:
        """Compute summary statistics from a list of trade records."""
        if not trades:
            return {
                "total_trades": 0,
                "closed_trades": 0,
                "open_trades": 0,
                "win_rate_pct": None,
                "total_pnl": 0,
                "avg_pnl": None,
                "best_trade": None,
                "worst_trade": None,
                "instruments": [],
                "platforms": [],
            }

        closed = [t for t in trades if t.get("pnl") is not None]
        open_trades = [t for t in trades if t.get("closed_at") is None]
        winners = [t for t in closed if t["pnl"] > 0]
        losers = [t for t in closed if t["pnl"] <= 0]

        pnls = [t["pnl"] for t in closed]
        total_pnl = sum(pnls) if pnls else 0

        return {
            "total_trades": len(trades),
            "closed_trades": len(closed),
            "open_trades": len(open_trades),
            "win_rate_pct": round(len(winners) / len(closed) * 100, 1) if closed else None,
            "total_pnl": round(total_pnl, 2),
            "avg_pnl": round(total_pnl / len(closed), 2) if closed else None,
            "best_trade": round(max(pnls), 2) if pnls else None,
            "worst_trade": round(min(pnls), 2) if pnls else None,
            "instruments": list(set(t.get("instrument", "") for t in trades)),
            "platforms": list(set(t.get("platform", "") for t in trades)),
        }
