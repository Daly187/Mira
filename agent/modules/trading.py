"""
Trading Module — MT5 computer use control, crypto/DalyKraken, Polymarket.

Autonomy level: FULL AUTO with kill switch.
Mira controls MT5 via computer use (screenshot + mouse/keyboard).
Does NOT use MT5 API directly — operates it the same way you would.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from config import Config

logger = logging.getLogger("mira.modules.trading")


class TradingModule:
    """Full autonomous trading — MT5, crypto, prediction markets."""

    def __init__(self, mira):
        self.mira = mira
        self.trading_paused = False
        self.daily_pnl = 0.0
        self.max_drawdown_pct = 3.0  # Default, loaded from config

    async def initialise(self):
        """Set up trading module."""
        pref = self.mira.sqlite.get_preference("max_daily_drawdown_pct")
        if pref:
            self.max_drawdown_pct = float(pref)
        paused = self.mira.sqlite.get_preference("trading_paused")
        if paused:
            self.trading_paused = paused == "true"
        logger.info(f"Trading module initialised. Drawdown limit: {self.max_drawdown_pct}%")

    # ── MT5 Operations (via Computer Use) ────────────────────────────

    async def check_ea_health(self):
        """Check all running EAs every 15 minutes via computer use.

        Takes a screenshot of MT5, uses Claude Vision to check EA status,
        and alerts if any EA appears stopped or errored.
        """
        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            return

        try:
            # Focus MT5 window first
            await cu.focus_window("MetaTrader")
            import asyncio
            await asyncio.sleep(1)

            analysis = await cu.analyse_screen(
                task="Look at the MetaTrader 5 window. Check: "
                     "1. Are any Expert Advisors (EAs) running? "
                     "2. Do any show errors or stopped status? "
                     "3. What is the current account balance and equity? "
                     "4. Are there any open positions? "
                     "Report concisely."
            )

            if analysis and not analysis.startswith("Could not"):
                self.mira.sqlite.log_action("trading", "ea_health_check", analysis[:300])

                # Alert if something looks wrong
                lower = analysis.lower()
                if any(w in lower for w in ["error", "stopped", "crashed", "disconnected", "no connection"]):
                    if hasattr(self.mira, "telegram"):
                        await self.mira.telegram.notify(
                            "trading",
                            "EA Health Alert",
                            analysis[:500],
                        )
        except Exception as e:
            logger.error(f"EA health check failed: {e}")

    async def read_dashboard(self) -> dict:
        """Read MT5 dashboard via screenshot + Claude Vision."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            return {"positions": [], "pnl": 0.0, "margin_level": 0.0}

        try:
            await cu.focus_window("MetaTrader")
            import asyncio
            await asyncio.sleep(1)

            analysis = await cu.analyse_screen(
                task="Read the MetaTrader 5 dashboard. Extract: "
                     "1. All open positions (instrument, direction, size, entry price, current P&L) "
                     "2. Account balance and equity "
                     "3. Margin level "
                     "Return as structured data."
            )
            return {"raw_analysis": analysis, "source": "computer_use"}
        except Exception as e:
            logger.error(f"Read dashboard failed: {e}")
            return {"positions": [], "pnl": 0.0, "margin_level": 0.0}

    # ── Session Awareness ────────────────────────────────────────────

    def get_current_session(self) -> str:
        """Return the current trading session based on UTC time.

        Sessions:
            Asian:    00:00-09:00 UTC (Tokyo/Sydney)
            London:   07:00-16:00 UTC (overlap 07:00-09:00 with Asian)
            New York: 13:00-22:00 UTC (overlap 13:00-16:00 with London)
            Off-hours: 22:00-00:00 UTC
        """
        utc_hour = datetime.now(timezone.utc).hour

        if 0 <= utc_hour < 7:
            return "asian"
        elif 7 <= utc_hour < 9:
            return "asian_london_overlap"
        elif 9 <= utc_hour < 13:
            return "london"
        elif 13 <= utc_hour < 16:
            return "london_newyork_overlap"
        elif 16 <= utc_hour < 22:
            return "newyork"
        else:
            return "off_hours"

    def get_session_context(self) -> dict:
        """Return a dict with session details: name, pairs_to_watch, volatility, notes."""
        session = self.get_current_session()

        session_data = {
            "asian": {
                "session_name": "Asian (Tokyo/Sydney)",
                "pairs_to_watch": ["USDJPY", "AUDUSD", "NZDUSD", "EURJPY"],
                "volatility_expectation": "low",
                "notes": "Range-bound markets typical. Watch for BoJ/RBA news.",
            },
            "asian_london_overlap": {
                "session_name": "Asian-London Overlap",
                "pairs_to_watch": ["USDJPY", "GBPJPY", "EURJPY", "EURUSD"],
                "volatility_expectation": "medium",
                "notes": "Increasing volatility as London opens. JPY crosses active.",
            },
            "london": {
                "session_name": "London",
                "pairs_to_watch": ["EURUSD", "GBPUSD", "EURGBP", "USDCHF"],
                "volatility_expectation": "high",
                "notes": "Highest liquidity period. Watch for ECB/BoE releases.",
            },
            "london_newyork_overlap": {
                "session_name": "London-New York Overlap",
                "pairs_to_watch": ["EURUSD", "GBPUSD", "USDCAD", "USDJPY"],
                "volatility_expectation": "very_high",
                "notes": "Peak volatility and volume. Major moves happen here.",
            },
            "newyork": {
                "session_name": "New York",
                "pairs_to_watch": ["EURUSD", "USDCAD", "USDMXN", "XAUUSD"],
                "volatility_expectation": "high",
                "notes": "US data releases. Watch Fed speakers and Treasury auctions.",
            },
            "off_hours": {
                "session_name": "Off-hours",
                "pairs_to_watch": [],
                "volatility_expectation": "very_low",
                "notes": "Thin liquidity. Spreads widened. Avoid new entries.",
            },
        }

        return session_data.get(session, session_data["off_hours"])

    # ── Trade Execution ───────────────────────────────────────────────

    async def execute_trade(
        self,
        instrument: str,
        direction: str,
        size: float,
        strategy: str,
        rationale: str,
    ) -> dict:
        """Execute a trade via computer use."""
        if self.trading_paused:
            return {"status": "paused", "message": "Trading is paused"}

        # Risk check
        allowed, reason = self._risk_check(instrument, direction, size)
        if not allowed:
            self.mira.sqlite.log_action(
                "trading", "trade_blocked", reason,
                {"instrument": instrument, "direction": direction, "size": size},
            )
            return {"status": "blocked", "message": reason}

        # Get session context for trade metadata
        session_ctx = self.get_session_context()

        # Phase 7: Computer use to open trade in MT5
        # Log the trade
        trade_id = self.mira.sqlite.log_trade(
            instrument=instrument,
            direction=direction,
            size=size,
            strategy=strategy,
            rationale=rationale,
        )

        self.mira.sqlite.log_action(
            "trading",
            f"open_{direction}",
            f"{instrument} {size} lots",
            {
                "trade_id": trade_id,
                "strategy": strategy,
                "session": session_ctx["session_name"],
                "volatility": session_ctx["volatility_expectation"],
            },
        )

        return {"status": "logged", "trade_id": trade_id, "session": session_ctx["session_name"]}

    async def send_daily_screenshot(self):
        """Screenshot MT5 dashboard and send to Telegram at market close."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            return

        try:
            # Focus MT5
            await cu.focus_window("MetaTrader")
            import asyncio
            await asyncio.sleep(1)

            # Take and send screenshot
            path = await cu.screenshot_to_file()
            if path and hasattr(self.mira, "telegram") and self.mira.telegram.chat_id:
                import os
                try:
                    with open(path, "rb") as photo:
                        await self.mira.telegram.app.bot.send_photo(
                            chat_id=self.mira.telegram.chat_id, photo=photo,
                            caption="MT5 Daily Screenshot"
                        )
                    self.mira.sqlite.log_action("trading", "daily_screenshot", "sent")
                finally:
                    if os.path.exists(path):
                        os.remove(path)
        except Exception as e:
            logger.error(f"Daily screenshot failed: {e}")

    def _risk_check(self, instrument: str, direction: str, proposed_size: float) -> tuple[bool, str]:
        """Enforce risk limits — hard stop, no overrides.

        Returns:
            (allowed, reason) — allowed=True means trade can proceed,
            otherwise reason explains why it was blocked.
        """
        # 1. Check if trading is paused via preferences
        paused_pref = self.mira.sqlite.get_preference("trading_paused")
        if paused_pref == "true":
            return False, "Trading is paused via preferences"

        # 2. Check position size against MAX_POSITION_SIZE
        max_size = Config.MAX_POSITION_SIZE
        size_pref = self.mira.sqlite.get_preference("max_position_size")
        if size_pref:
            try:
                max_size = float(size_pref)
            except ValueError:
                pass
        if proposed_size > max_size:
            return False, f"Position size {proposed_size} exceeds max allowed {max_size} lots"

        # 3. Check total open exposure against MAX_TOTAL_EXPOSURE
        max_exposure = Config.MAX_TOTAL_EXPOSURE
        exposure_pref = self.mira.sqlite.get_preference("max_total_exposure")
        if exposure_pref:
            try:
                max_exposure = float(exposure_pref)
            except ValueError:
                pass

        open_trades = self.mira.sqlite.get_open_trades()
        total_open_size = sum(t.get("size", 0) or 0 for t in open_trades)
        if (total_open_size + proposed_size) > max_exposure:
            return (
                False,
                f"Total exposure {total_open_size + proposed_size} lots would exceed max {max_exposure}",
            )

        # 4. Calculate today's realized P&L and check against MAX_DAILY_DRAWDOWN_PCT
        max_dd_pct = self.max_drawdown_pct
        dd_pref = self.mira.sqlite.get_preference("max_daily_drawdown_pct")
        if dd_pref:
            try:
                max_dd_pct = float(dd_pref)
            except ValueError:
                pass

        today = datetime.now().strftime("%Y-%m-%d")
        all_trades = self.mira.sqlite.get_trade_history(limit=200)
        todays_closed_pnl = 0.0
        for t in all_trades:
            closed_at = t.get("closed_at")
            if closed_at and str(closed_at).startswith(today) and t.get("pnl") is not None:
                todays_closed_pnl += t["pnl"]

        # If today's realized losses exceed the drawdown limit, block new trades
        # Drawdown is a negative number; we compare absolute loss against the percentage threshold
        if todays_closed_pnl < 0 and abs(todays_closed_pnl) >= max_dd_pct:
            return (
                False,
                f"Daily drawdown limit hit: realized P&L today is {todays_closed_pnl:.2f}, "
                f"limit is -{max_dd_pct}%",
            )

        return True, "Risk check passed"

    # ── Crypto / DalyKraken ──────────────────────────────────────────

    async def check_dca_positions(self) -> list[dict]:
        """Monitor all active DCA positions across exchanges.

        Scans the trades table for crypto positions with strategy='dca',
        aggregates by instrument, and evaluates performance.

        Returns:
            List of DCA position summaries.
        """
        try:
            rows = self.mira.sqlite.conn.execute(
                """SELECT instrument, direction, entry_price, size, pnl,
                          opened_at, closed_at, platform
                   FROM trades
                   WHERE strategy = 'dca' OR strategy LIKE '%dca%'
                   ORDER BY opened_at DESC""",
            ).fetchall()
        except Exception:
            rows = []

        if not rows:
            return []

        # Aggregate by instrument
        positions = {}
        for row in rows:
            r = dict(row)
            inst = r.get("instrument", "unknown")
            if inst not in positions:
                positions[inst] = {
                    "instrument": inst,
                    "total_size": 0.0,
                    "total_cost": 0.0,
                    "buy_count": 0,
                    "realized_pnl": 0.0,
                    "platform": r.get("platform", ""),
                    "last_buy": r.get("opened_at"),
                }
            entry = r.get("entry_price", 0) or 0
            size = r.get("size", 0) or 0
            positions[inst]["total_size"] += size
            positions[inst]["total_cost"] += entry * size
            positions[inst]["buy_count"] += 1
            if r.get("pnl"):
                positions[inst]["realized_pnl"] += r["pnl"]

        result = []
        for inst, data in positions.items():
            avg_entry = data["total_cost"] / data["total_size"] if data["total_size"] else 0
            result.append({
                "instrument": inst,
                "total_size": round(data["total_size"], 6),
                "avg_entry_price": round(avg_entry, 4),
                "buy_count": data["buy_count"],
                "realized_pnl": round(data["realized_pnl"], 2),
                "platform": data["platform"],
                "last_buy": data["last_buy"],
            })

        self.mira.sqlite.log_action(
            "trading", "dca_check", f"{len(result)} DCA positions tracked",
        )
        return result

    async def check_dual_investments(self) -> list[dict]:
        """Check for dual investment opportunities from action_log and memories.

        Scans for dual investment related entries to track active products
        and their maturity status.

        Returns:
            List of active dual investment summaries.
        """
        try:
            rows = self.mira.sqlite.conn.execute(
                """SELECT action, outcome, created_at FROM action_log
                   WHERE action LIKE '%dual%' OR action LIKE '%investment%'
                   ORDER BY created_at DESC LIMIT 20""",
            ).fetchall()
        except Exception:
            rows = []

        if not rows:
            return []

        entries = [dict(r) for r in rows]

        # Use AI to extract structured data from action log entries
        try:
            prompt = f"""Extract active dual investment positions from these log entries.
Return a JSON array of objects with: product_name, amount, strike_price, maturity_date, status.
If no clear dual investments found, return an empty array [].

Log entries:
{json.dumps(entries[:10], default=str)}"""

            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="Extract investment data. Return ONLY valid JSON array.",
                max_tokens=512,
                tier="fast",
                task_type="dual_investment_check",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]

            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
        except Exception:
            pass

        return []

    async def get_portfolio_snapshot(self) -> dict:
        """Portfolio snapshot from trades table — open positions + P&L summary.

        Aggregates all open trades and recent closed trades to produce a
        unified view of the trading portfolio.

        Returns:
            Dict with total_value, positions, daily_pnl, and summary stats.
        """
        open_trades = self.mira.sqlite.get_open_trades()
        recent_closed = self.mira.sqlite.get_trade_history(limit=20)

        # Calculate aggregates
        total_unrealized = 0.0
        total_realized = 0.0
        positions = []

        for trade in open_trades:
            entry = trade.get("entry_price", 0) or 0
            size = trade.get("size", 0) or 0
            positions.append({
                "instrument": trade.get("instrument", ""),
                "direction": trade.get("direction", ""),
                "entry_price": entry,
                "size": size,
                "strategy": trade.get("strategy", ""),
                "platform": trade.get("platform", "mt5"),
                "opened_at": trade.get("opened_at"),
                "notional": round(entry * size, 2),
            })

        # Today's realized P&L from closed trades
        today = datetime.now().strftime("%Y-%m-%d")
        for trade in recent_closed:
            closed_at = str(trade.get("closed_at", ""))
            if today in closed_at:
                pnl = trade.get("pnl", 0) or 0
                total_realized += pnl

        # Group open positions by platform
        by_platform = {}
        for p in positions:
            platform = p["platform"]
            by_platform.setdefault(platform, {"count": 0, "notional": 0.0})
            by_platform[platform]["count"] += 1
            by_platform[platform]["notional"] += p["notional"]

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "open_positions": len(positions),
            "positions": positions,
            "daily_realized_pnl": round(total_realized, 2),
            "platforms": by_platform,
            "recent_closed_count": len([t for t in recent_closed if today in str(t.get("closed_at", ""))]),
        }

        self.mira.sqlite.log_action(
            "trading", "portfolio_snapshot",
            f"{len(positions)} open, daily P&L: ${total_realized:.2f}",
        )
        return snapshot

    # ── Polymarket ───────────────────────────────────────────────────

    async def scan_polymarket(self) -> list[dict]:
        """Scan prediction markets for mispriced opportunities.

        Uses brain to generate market analysis based on recent news and
        memory signals. Returns structured list of market opportunities.
        """
        # Pull recent polymarket-related memories
        memories = self.mira.sqlite.search_memories(query="polymarket prediction market", limit=10)
        memory_texts = [m.get("content", "")[:200] for m in memories]

        # Pull recent polymarket actions
        try:
            actions = self.mira.sqlite.conn.execute(
                """SELECT action, outcome, created_at FROM action_log
                   WHERE module = 'trading' AND action LIKE '%polymarket%'
                   ORDER BY created_at DESC LIMIT 10""",
            ).fetchall()
            action_texts = [f"{dict(a)['action']}: {dict(a).get('outcome', '')}" for a in actions]
        except Exception:
            action_texts = []

        # Get risk budget from preferences
        risk_budget = self.mira.sqlite.get_preference("polymarket_risk_budget") or "100"

        prompt = f"""Analyse current prediction market landscape and suggest opportunities.

Context from memory:
{chr(10).join(f'- {m}' for m in memory_texts[:5]) if memory_texts else '- No recent Polymarket memories'}

Recent Polymarket activity:
{chr(10).join(f'- {a}' for a in action_texts[:5]) if action_texts else '- No recent activity'}

Risk budget: ${risk_budget}

Return a JSON array (max 5 items) of market opportunities with:
- market_name: descriptive title
- thesis: why this is mispriced (1-2 sentences)
- suggested_position: "yes" or "no"
- confidence: 1-10
- suggested_amount: dollar amount within risk budget
- category: politics/sports/crypto/tech/science/other

If insufficient data for good recommendations, return an empty array with a note.
Return ONLY valid JSON."""

        try:
            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a prediction market analyst. Return ONLY valid JSON array.",
                max_tokens=1500,
                tier="deep",
                task_type="polymarket_scan",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]

            opportunities = json.loads(cleaned)
            if isinstance(opportunities, list):
                self.mira.sqlite.log_action(
                    "trading", "polymarket_scan",
                    f"{len(opportunities)} opportunities identified",
                )
                return opportunities
        except Exception as e:
            logger.warning(f"Polymarket scan failed: {e}")

        return []

    async def place_polymarket_bet(
        self,
        market_id: str,
        position: str,
        amount: float,
        rationale: str,
    ) -> dict:
        """Place a bet on Polymarket within risk limits.

        Validates against risk budget, logs the bet as a trade, and
        sends approval request via Telegram. Does NOT auto-execute —
        requires user confirmation.
        """
        # Check risk budget
        risk_budget = float(self.mira.sqlite.get_preference("polymarket_risk_budget") or "100")

        # Check existing polymarket exposure
        try:
            rows = self.mira.sqlite.conn.execute(
                """SELECT SUM(size) as total FROM trades
                   WHERE platform = 'polymarket' AND closed_at IS NULL""",
            ).fetchone()
            current_exposure = dict(rows).get("total", 0) or 0
        except Exception:
            current_exposure = 0

        if current_exposure + amount > risk_budget:
            return {
                "status": "rejected",
                "reason": f"Would exceed risk budget (${current_exposure:.0f} + ${amount:.0f} > ${risk_budget:.0f})",
            }

        # Log as trade (pending confirmation)
        trade_id = self.mira.sqlite.log_trade(
            instrument=market_id,
            direction=position,
            entry_price=amount,
            size=1.0,
            strategy="polymarket",
            rationale=rationale,
            platform="polymarket",
        )

        # Send for approval via Telegram
        telegram = getattr(self.mira, "telegram", None)
        if telegram:
            await telegram.send(
                f"Polymarket Bet Request\n\n"
                f"Market: {market_id}\n"
                f"Position: {position}\n"
                f"Amount: ${amount:.2f}\n"
                f"Rationale: {rationale}\n\n"
                f"Current exposure: ${current_exposure:.0f} / ${risk_budget:.0f}\n\n"
                f"Approve? (Trade #{trade_id})"
            )

        self.mira.sqlite.log_action(
            "trading", "polymarket_bet_request",
            f"{market_id} {position} ${amount:.2f} (awaiting approval)",
        )

        return {
            "status": "pending_approval",
            "trade_id": trade_id,
            "current_exposure": current_exposure,
            "risk_budget": risk_budget,
        }

    # ── Reports ──────────────────────────────────────────────────────

    async def generate_daily_report(self) -> str:
        """Generate comprehensive daily trading report."""
        trades = self.mira.sqlite.get_trade_history(limit=20)
        open_trades = self.mira.sqlite.get_open_trades()

        report_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "open_trades": open_trades,
            "recent_trades": trades,
            "daily_pnl": self.daily_pnl,
            "drawdown_limit": self.max_drawdown_pct,
        }

        return await self.mira.brain.think(
            f"Generate a concise daily trading report from this data:\n{report_data}",
            include_history=False,
        )
