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
        """Check all running EAs every 15 minutes, restart any that crashed."""
        # Phase 7: Computer use to screenshot MT5, check EA status
        pass

    async def read_dashboard(self) -> dict:
        """Read MT5 dashboard — open positions, P&L, margin levels."""
        # Phase 7: Screenshot MT5, parse with Claude vision
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
        # Phase 7: Computer use screenshot + Telegram send
        pass

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

    async def check_dca_positions(self):
        """Monitor all active DCA positions across exchanges."""
        pass

    async def check_dual_investments(self):
        """15-minute cycle to check for new dual investment opportunities."""
        pass

    async def get_portfolio_snapshot(self) -> dict:
        """Real-time portfolio value across all exchanges."""
        return {"total_value": 0.0, "positions": []}

    # ── Polymarket ───────────────────────────────────────────────────

    async def scan_polymarket(self):
        """Scan prediction markets for mispriced probabilities."""
        pass

    async def place_polymarket_bet(
        self,
        market_id: str,
        position: str,
        amount: float,
        rationale: str,
    ) -> dict:
        """Place a bet on Polymarket within risk limits."""
        return {"status": "not_implemented"}

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
