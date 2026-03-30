"""
Mira Telegram Bot — primary interface for commands, notifications, and communication.
Full command set from the MVP spec.
"""

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import Config

logger = logging.getLogger("mira.telegram")


class MiraTelegramBot:
    """Handles all Telegram communication — commands in, notifications out."""

    def __init__(self, mira):
        self.mira = mira
        self.app = None
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.pending_drafts: dict[str, dict] = {}  # draft_id -> {text, type, metadata}
        self._draft_counter = 0

    async def start(self):
        """Initialise and start the Telegram bot."""
        token = Config.TELEGRAM_BOT_TOKEN
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not set in .env")
            return

        self.app = Application.builder().token(token).build()

        # ── Safety Commands ──────────────────────────────────────────
        self.app.add_handler(CommandHandler("killswitch", self._cmd_killswitch))
        self.app.add_handler(CommandHandler("resume", self._cmd_resume))
        self.app.add_handler(CommandHandler("ack", self._cmd_ack))

        # ── Core Commands ────────────────────────────────────────────
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("help", self._cmd_help))

        # ── Memory Commands ──────────────────────────────────────────
        self.app.add_handler(CommandHandler("remember", self._cmd_remember))
        self.app.add_handler(CommandHandler("recall", self._cmd_recall))
        self.app.add_handler(CommandHandler("weekly", self._cmd_weekly))

        # ── PA Commands ──────────────────────────────────────────────
        self.app.add_handler(CommandHandler("brief", self._cmd_brief))
        self.app.add_handler(CommandHandler("meeting", self._cmd_meeting))

        # ── Trading Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("trades", self._cmd_trades))
        self.app.add_handler(CommandHandler("close_all", self._cmd_close_all))
        self.app.add_handler(CommandHandler("pause_trading", self._cmd_pause_trading))
        self.app.add_handler(CommandHandler("resume_trading", self._cmd_resume_trading))
        self.app.add_handler(CommandHandler("daily_report", self._cmd_daily_report))
        self.app.add_handler(CommandHandler("risk", self._cmd_risk))
        self.app.add_handler(CommandHandler("portfolio", self._cmd_portfolio))

        # ── Social Commands ──────────────────────────────────────────
        self.app.add_handler(CommandHandler("post", self._cmd_post))
        self.app.add_handler(CommandHandler("queue", self._cmd_queue))

        # ── CRM Commands ──────────────────────────────────────────────
        self.app.add_handler(CommandHandler("people", self._cmd_people))

        # ── Finance Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("budget", self._cmd_budget))
        self.app.add_handler(CommandHandler("networth", self._cmd_networth))

        # ── Task Commands ─────────────────────────────────────────────
        self.app.add_handler(CommandHandler("tasks", self._cmd_tasks))

        # ── Email Commands ────────────────────────────────────────────
        self.app.add_handler(CommandHandler("email", self._cmd_email))

        # ── Research Commands ────────────────────────────────────────
        self.app.add_handler(CommandHandler("research", self._cmd_research))

        # ── Decision Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("decision", self._cmd_decision))

        # ── Gift Commands ────────────────────────────────────────────
        self.app.add_handler(CommandHandler("gift", self._cmd_gift))

        # ── Meeting Analysis Commands ────────────────────────────────
        self.app.add_handler(CommandHandler("meetings", self._cmd_meetings))

        # ── Capture Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("pause_listen", self._cmd_pause_listen))

        # ── Habit Commands ──────────────────────────────────────────────
        self.app.add_handler(CommandHandler("habit", self._cmd_habit))

        # ── Reminder Commands ───────────────────────────────────────────
        self.app.add_handler(CommandHandler("remind", self._cmd_remind))

        # ── Search Commands ─────────────────────────────────────────────
        self.app.add_handler(CommandHandler("search", self._cmd_search))

        # ── Schedule Commands ───────────────────────────────────────────
        self.app.add_handler(CommandHandler("schedule", self._cmd_schedule))

        # ── Earning Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("earn", self._cmd_earn))

        # ── Cost Tracking ───────────────────────────────────────────────
        self.app.add_handler(CommandHandler("cost", self._cmd_cost))

        # ── Learning Commands ────────────────────────────────────────────
        self.app.add_handler(CommandHandler("learn", self._cmd_learn))
        self.app.add_handler(CommandHandler("review", self._cmd_review))

        # ── New Intelligence Commands ────────────────────────────────────
        self.app.add_handler(CommandHandler("dca", self._cmd_dca))
        self.app.add_handler(CommandHandler("compliance", self._cmd_compliance))
        self.app.add_handler(CommandHandler("competitive", self._cmd_competitive))
        self.app.add_handler(CommandHandler("subscriptions", self._cmd_subscriptions))
        self.app.add_handler(CommandHandler("pnl", self._cmd_pnl))

        # ── Negotiation / Contract Commands ──────────────────────────────
        self.app.add_handler(CommandHandler("negotiate", self._cmd_negotiate))
        self.app.add_handler(CommandHandler("contract", self._cmd_contract))

        # ── Computer Use Commands ──────────────────────────────────────
        self.app.add_handler(CommandHandler("do", self._cmd_do))
        self.app.add_handler(CommandHandler("screen", self._cmd_screen))
        self.app.add_handler(CommandHandler("open", self._cmd_open))
        self.app.add_handler(CommandHandler("windows", self._cmd_windows))
        self.app.add_handler(CommandHandler("run", self._cmd_run))
        self.app.add_handler(CommandHandler("clipboard", self._cmd_clipboard))
        self.app.add_handler(CommandHandler("processes", self._cmd_processes))

        # ── System Commands ─────────────────────────────────────────────
        self.app.add_handler(CommandHandler("update", self._cmd_update))
        self.app.add_handler(CommandHandler("restart", self._cmd_restart))
        self.app.add_handler(CommandHandler("logs", self._cmd_logs))
        self.app.add_handler(CommandHandler("version", self._cmd_version))
        self.app.add_handler(CommandHandler("ask", self._cmd_ask))

        # ── Draft Approval (inline keyboard callbacks) ───────────────
        self.app.add_handler(CallbackQueryHandler(self._handle_draft_callback))

        # ── Photo handler (OCR + memory ingestion) ────────────────────
        self.app.add_handler(
            MessageHandler(filters.PHOTO, self._handle_photo_message)
        )

        # ── Voice message handler ──────────────────────────────────────
        self.app.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice_message)
        )

        # ── Catch-all for regular messages ───────────────────────────
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        # Start polling
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started — all commands registered.")

    async def stop(self):
        """Stop the Telegram bot."""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped.")

    async def send(self, text: str, chat_id: str = None):
        """Send a notification to the user."""
        target = chat_id or self.chat_id
        if self.app and target:
            # Split long messages (Telegram limit: 4096 chars)
            if len(text) > 4000:
                chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for chunk in chunks:
                    await self.app.bot.send_message(chat_id=target, text=chunk)
            else:
                await self.app.bot.send_message(chat_id=target, text=text)

    async def notify(self, module: str, action: str, outcome: str):
        """Send a formatted notification — every autonomous action gets one."""
        msg = Config.NOTIFICATION_FORMAT.format(
            module=module, action=action, outcome=outcome
        )
        await self.send(msg)

    async def send_voice(self, text: str, chat_id: str = None):
        """Generate TTS audio from text and send as a Telegram voice message.

        Uses VoiceInterface to generate speech, saves to temp file,
        sends via bot.send_voice(), then cleans up.
        """
        target = chat_id or self.chat_id
        if not self.app or not target:
            return

        voice_interface = getattr(self.mira, "voice", None)
        if not voice_interface:
            logger.warning("Voice interface not available, falling back to text")
            await self.send(text, chat_id=target)
            return

        tmp_path = None
        try:
            # Generate TTS audio to a temp file
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="mira_voice_")
            os.close(tmp_fd)

            audio_path = await voice_interface.speak(text, output_path=tmp_path)
            if not audio_path:
                logger.warning("TTS generation failed, falling back to text")
                await self.send(text, chat_id=target)
                return

            # Send as voice message
            with open(audio_path, "rb") as audio_file:
                await self.app.bot.send_voice(chat_id=target, voice=audio_file)

            logger.info(f"Voice message sent to {target}")

        except Exception as e:
            logger.error(f"Failed to send voice message: {e}")
            await self.send(text, chat_id=target)

        finally:
            # Clean up temp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ══════════════════════════════════════════════════════════════════
    # SAFETY COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_killswitch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Immediately pause ALL autonomous actions."""
        result = self.mira.kill_switch()
        await update.message.reply_text(f"KILL SWITCH ACTIVATED\n\n{result}")
        logger.warning(f"Kill switch triggered by user {update.effective_user.id}")

    async def _cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Restore full autonomous operation."""
        result = self.mira.resume()
        await update.message.reply_text(f"RESUMED\n\n{result}")

    async def _cmd_ack(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acknowledge a notification to stop escalation repeats."""
        nid = context.args[0] if context.args else ""
        if not nid:
            # List unacknowledged notifications
            pending = self.mira.unacknowledged_notifications
            if not pending:
                await update.message.reply_text("No unacknowledged notifications.")
                return
            msg = "Unacknowledged notifications:\n\n"
            for k, v in pending.items():
                msg += f"  {k}: [{v['module']}] {v['message'][:80]} (escalations: {v['escalation_count']})\n"
            msg += "\nUsage: /ack [notification_id] or /ack all"
            await update.message.reply_text(msg)
            return

        found = self.mira.acknowledge_notification(nid)
        if found:
            await update.message.reply_text(f"Acknowledged: {nid}")
            self.mira.sqlite.log_action("safety", "notification_ack", nid)
        else:
            await update.message.reply_text(f"Notification '{nid}' not found. Use /ack to list pending.")

    # ══════════════════════════════════════════════════════════════════
    # CORE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.chat_id = str(update.effective_chat.id)
        logger.info(f"Chat ID registered: {self.chat_id}")
        await update.message.reply_text(
            "Mira is online.\n\n"
            "I'm your autonomous digital twin. Send me a message or use /help."
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = self.mira.get_status()
        await update.message.reply_text(status)

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        commands = (
            "SAFETY\n"
            "/killswitch — Pause all autonomous actions\n"
            "/resume — Resume full operation\n"
            "/ack [id|all] — Acknowledge notification (stop escalation)\n\n"
            "CORE\n"
            "/status — Current status and memory stats\n"
            "/help — This message\n\n"
            "MEMORY\n"
            "/remember [fact] — Store a fact or note\n"
            "/recall [query] — Search second brain by meaning\n"
            "/weekly — Generate weekly review\n\n"
            "PA\n"
            "/brief — Generate daily briefing now\n"
            "/meeting [in X mins] — Generate brief for upcoming meeting\n\n"
            "TRADING\n"
            "/trades — Show open MT5 positions\n"
            "/close_all — Close all open positions\n"
            "/pause_trading — Halt new trade execution\n"
            "/resume_trading — Resume trading\n"
            "/daily_report — Generate today's trading report\n"
            "/risk [%] — Update daily drawdown limit\n"
            "/portfolio — Show full crypto portfolio\n\n"
            "TASKS\n"
            "/tasks — List pending tasks\n"
            "/tasks add [title] — Create a task\n"
            "/tasks done [id] — Complete a task\n\n"
            "EMAIL\n"
            "/email — Check and triage unread email\n\n"
            "SOCIAL\n"
            "/post [platform] [content] — Draft and queue a post\n"
            "/queue — Show pending posts in content queue\n\n"
            "CRM\n"
            "/people — List all tracked people\n"
            "/people [name] — Look up a specific person\n\n"
            "FINANCE\n"
            "/budget — This month's personal P&L\n"
            "/networth — Current net worth snapshot\n\n"
            "RESEARCH\n"
            "/research [topic] — Run deep research\n\n"
            "DECISIONS\n"
            "/decision [text] — Log a decision for tracking\n"
            "/decision score [id] [1-10] [outcome] — Score a past decision\n"
            "/decision review — Analyse decision patterns\n\n"
            "GIFTS\n"
            "/gift [person] — Personalised gift suggestions\n\n"
            "MEETINGS\n"
            "/meetings — Analyse 4-week meeting patterns\n\n"
            "CAPTURE\n"
            "/pause_listen — Pause audio capture for 30 min\n\n"
            "HABITS\n"
            "/habit — View all habits and streaks\n"
            "/habit add [name] — Track a new habit\n"
            "/habit log [name] — Mark habit done today\n"
            "/habit stats — Detailed habit statistics\n\n"
            "REMINDERS\n"
            "/remind [time] [message] — Set a timed reminder\n\n"
            "SEARCH\n"
            "/search [query] — Semantic search across all memory\n\n"
            "SCHEDULE\n"
            "/schedule — View all scheduled autonomous tasks\n\n"
            "EARNING\n"
            "/earn — Report on all earning modules\n\n"
            "LEARNING\n"
            "/learn [topic] — Track a learning topic\n"
            "/review [card_id] [quality] — Review a flashcard (0-5)\n\n"
            "NEGOTIATION\n"
            "/negotiate [counterparty] — Prepare negotiation brief\n"
            "/contract [text] — Review a contract or legal text\n\n"
            "COMPUTER USE\n"
            "/do [task] — Execute a desktop task (AI-driven)\n"
            "/screen [question] — Screenshot (+ AI analysis)\n"
            "/open [app] — Launch an application\n"
            "/windows [title] — List or focus windows\n"
            "/run [cmd] — Run a shell command\n"
            "/clipboard [text] — Read or set clipboard\n"
            "/processes [name] — List running processes\n\n"
            "COST\n"
            "/cost — API cost breakdown (today/week/month)\n\n"
            "SYSTEM\n"
            "/update — Git pull + restart (deploy from Mac)\n"
            "/restart — Restart Mira without pulling code\n"
            "/logs [n] — Show last n lines of mira.log\n"
            "/version — Show current git hash and last update\n"
            "/ask [question] — Screenshot + AI analysis"
        )
        await update.message.reply_text(commands)

    # ══════════════════════════════════════════════════════════════════
    # MEMORY COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_remember(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Store a specific fact or note."""
        text = " ".join(context.args) if context.args else ""
        if not text:
            await update.message.reply_text("Usage: /remember [fact or note to store]")
            return

        result = await self.mira.ingest.ingest_text(text, source="telegram_command")
        await update.message.reply_text(
            f"Stored. Memory #{result['memory_id']}\n"
            f"Category: {result['category']}\n"
            f"Importance: {result['importance']}/5\n"
            f"People found: {', '.join(result['people_found']) or 'none'}\n"
            f"Action items: {result['action_items_created']}"
        )

    async def _cmd_recall(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search the second brain by meaning."""
        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /recall [what you're looking for]")
            return

        result = await self.mira.recall(query)
        await update.message.reply_text(result)

    async def _cmd_weekly(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate weekly review."""
        await update.message.reply_text("Generating weekly review... (Phase 9)")

    # ══════════════════════════════════════════════════════════════════
    # PA COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_brief(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate daily briefing now."""
        await update.message.reply_text("Generating briefing...")

        costs_today = self.mira.sqlite.get_api_costs("today")
        costs_month = self.mira.sqlite.get_api_costs("month")

        briefing_data = {
            "date": datetime.now().strftime("%A, %B %d, %Y"),
            "time": datetime.now().strftime("%H:%M"),
            "timezone": "Asia/Manila (UTC+8)",
            "pending_tasks": self.mira.sqlite.get_pending_tasks(),
            "open_trades": self.mira.sqlite.get_open_trades(),
            "recent_memories": self.mira.sqlite.get_recent_memories(10),
            "actions_today": self.mira.sqlite.get_daily_actions(),
            "api_cost_today": f"${costs_today['total_cost']:.4f}",
            "api_cost_month": f"${costs_month['total_cost']:.4f}",
            "api_calls_today": costs_today["total_calls"],
        }

        # Add upcoming important dates if personal module available
        if hasattr(self.mira, "personal") and self.mira.personal:
            try:
                dates = await self.mira.personal.get_upcoming_dates(days=7)
                if dates:
                    briefing_data["upcoming_dates"] = dates
            except Exception:
                pass

        briefing = await self.mira.brain.generate_briefing(briefing_data)
        await update.message.reply_text(briefing)

    async def _cmd_meeting(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate brief for upcoming meeting."""
        await update.message.reply_text("Meeting intelligence coming in Phase 6.")

    # ══════════════════════════════════════════════════════════════════
    # TRADING COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        trades = self.mira.sqlite.get_open_trades()
        if not trades:
            await update.message.reply_text("No open trades.")
            return
        msg = "Open Trades:\n\n"
        for t in trades:
            msg += f"  {t['instrument']} {t['direction']} @ {t['entry_price']} ({t['strategy'] or 'manual'})\n"
        await update.message.reply_text(msg)

    async def _cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Close all open positions via computer use."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            await update.message.reply_text("Computer use not available — cannot close positions.")
            return

        open_trades = self.mira.sqlite.get_open_trades()
        if not open_trades:
            await update.message.reply_text("No open positions to close.")
            return

        # Confirm before executing
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Yes, close all", callback_data="confirm_close_all"),
            InlineKeyboardButton("Cancel", callback_data="cancel_close_all"),
        ]])
        await update.message.reply_text(
            f"Close ALL {len(open_trades)} open positions?\n\n"
            f"This will use computer use to close each position in MT5.",
            reply_markup=keyboard,
        )

    async def _cmd_pause_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.mira.sqlite.set_preference("trading_paused", "true", confidence=1.0, source="command")
        self.mira.sqlite.log_action("trading", "pause_trading", "paused")
        await update.message.reply_text("Trading execution paused. EAs still monitored.")

    async def _cmd_resume_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.mira.sqlite.set_preference("trading_paused", "false", confidence=1.0, source="command")
        self.mira.sqlite.log_action("trading", "resume_trading", "resumed")
        await update.message.reply_text("Trading execution resumed.")

    async def _cmd_daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate today's trading report from logged trades and risk data."""
        await update.message.reply_text("Generating trading report...")

        open_trades = self.mira.sqlite.get_open_trades()
        trade_history = self.mira.sqlite.get_trade_history(limit=20)
        session_info = self.mira.trading.get_current_session() if hasattr(self.mira.trading, "get_current_session") else {}

        report_data = {
            "date": datetime.now().strftime("%A, %B %d, %Y"),
            "open_positions": len(open_trades),
            "open_trades": open_trades,
            "recent_closed": [t for t in trade_history if t.get("closed_at")],
            "session": session_info,
            "risk_limit": Config.MAX_DAILY_DRAWDOWN_PCT if hasattr(Config, "MAX_DAILY_DRAWDOWN_PCT") else "3%",
        }

        report = await self.mira.brain.think(
            f"Generate a concise daily trading report based on this data:\n"
            f"{json.dumps(report_data, indent=2, default=str)}\n\n"
            f"Include: open positions summary, today's P&L if available, "
            f"current session context, risk status, and any notable observations. "
            f"Be direct and data-driven. Use your Mira personality.",
            tier="standard",
        )
        await update.message.reply_text(report)

    async def _cmd_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            current = Config.MAX_DAILY_DRAWDOWN_PCT
            await update.message.reply_text(f"Current daily drawdown limit: {current}%\nUsage: /risk [percentage]")
            return
        try:
            new_limit = float(context.args[0])
            self.mira.sqlite.set_preference("max_daily_drawdown_pct", str(new_limit), confidence=1.0, source="command")
            self.mira.sqlite.log_action("trading", "risk_update", f"set to {new_limit}%")
            await update.message.reply_text(f"Daily drawdown limit updated to {new_limit}%")
        except ValueError:
            await update.message.reply_text("Invalid number. Usage: /risk 3.0")

    async def _cmd_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all tracked positions — MT5 + crypto."""
        open_trades = self.mira.sqlite.get_open_trades()
        if not open_trades:
            await update.message.reply_text("No open positions tracked.\n\nLog trades via /remember or the trading module.")
            return

        msg = f"Portfolio — {len(open_trades)} open positions\n\n"
        for t in open_trades:
            direction = t.get("direction", "?").upper()
            instrument = t.get("instrument", "?")
            entry = t.get("entry_price", "?")
            size = t.get("size", "?")
            msg += f"  {direction} {instrument} @ {entry} (size: {size})\n"

        await update.message.reply_text(msg[:4000])

    # ══════════════════════════════════════════════════════════════════
    # SOCIAL COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Draft or queue a social media post."""
        if not context.args:
            await update.message.reply_text(
                "Usage:\n"
                "  /post x [content] — Queue a post for X/Twitter\n"
                "  /post linkedin [content] — Queue for LinkedIn\n"
                "  /post x — Auto-generate content for X\n\n"
                "Platforms: x, linkedin, instagram, tiktok, youtube, facebook"
            )
            return

        platform = context.args[0].lower()
        valid = ["x", "linkedin", "instagram", "tiktok", "youtube", "facebook"]
        if platform not in valid:
            await update.message.reply_text(f"Unknown platform '{platform}'. Options: {', '.join(valid)}")
            return

        content = " ".join(context.args[1:]) if len(context.args) > 1 else None

        if not content:
            # Auto-generate content
            await update.message.reply_text(f"Generating {platform} content...")
            result = await self.mira.social.generate_content(platform=platform)
            content = result.get("content", "")
            if not content:
                await update.message.reply_text("Content generation failed.")
                return
            # Send as draft for approval
            await self.send_draft_for_approval(
                draft_text=content,
                draft_type="social_post",
                metadata={"platform": platform},
            )
            return

        # Queue the post directly
        result = await self.mira.social.queue_post(platform=platform, content=content)
        await update.message.reply_text(
            f"Queued for {platform} (post #{result['id']})\n"
            f"Scheduled: {result['scheduled_at'][:16]}\n\n"
            f"{content[:200]}"
        )

    async def _cmd_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending social media posts in the queue."""
        posts = await self.mira.social.get_pending_posts()
        if not posts:
            await update.message.reply_text("No posts in queue.\n\nUse /post [platform] [content] to add one.")
            return

        msg = f"Content Queue ({len(posts)} pending):\n\n"
        for p in posts[:10]:
            msg += (
                f"  #{p['id']} [{p['platform']}] {p['scheduled_at'][:16]}\n"
                f"  {p['content'][:80]}...\n\n"
            )
        if len(posts) > 10:
            msg += f"  ...and {len(posts) - 10} more"
        await update.message.reply_text(msg[:4000])

    # ══════════════════════════════════════════════════════════════════
    # FINANCE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_people(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """CRM — list people or look up a specific person."""
        if context.args:
            name = " ".join(context.args)
            person = self.mira.sqlite.get_person(name)
            if not person:
                await update.message.reply_text(f"No one named '{name}' in CRM.\n\nUse /remember to add people.")
                return
            msg = f"Person: {person.get('name', name)}\n"
            msg += f"Type: {person.get('relationship_type', 'unknown')}\n"
            if person.get('email'):
                msg += f"Email: {person['email']}\n"
            if person.get('phone'):
                msg += f"Phone: {person['phone']}\n"
            if person.get('key_facts'):
                facts = person['key_facts']
                if isinstance(facts, str):
                    try:
                        facts = json.loads(facts)
                    except Exception:
                        facts = [facts]
                if facts:
                    msg += f"\nKey facts:\n"
                    for f in facts[:10]:
                        msg += f"  - {f}\n"
            if person.get('last_contact'):
                msg += f"\nLast contact: {person['last_contact']}"
            await update.message.reply_text(msg[:4000])
            return

        # List all people
        people = self.mira.sqlite.get_all_people()
        if not people:
            await update.message.reply_text("CRM is empty.\n\nMira learns people from your conversations automatically.")
            return

        msg = f"People ({len(people)}):\n\n"
        for p in people[:30]:
            ptype = p.get('relationship_type', '')
            pname = p.get('name', '?')
            msg += f"  {pname}"
            if ptype:
                msg += f" ({ptype})"
            msg += "\n"
        if len(people) > 30:
            msg += f"\n  ...and {len(people) - 30} more"
        msg += "\n\nUsage: /people [name] for details"
        await update.message.reply_text(msg[:4000])

    # ══════════════════════════════════════════════════════════════════
    # FINANCE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_budget(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Personal P&L tracking coming in Phase 10.")

    async def _cmd_networth(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Net worth tracking coming in Phase 10.")

    # ══════════════════════════════════════════════════════════════════
    # RESEARCH COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_research(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        topic = " ".join(context.args) if context.args else ""
        if not topic:
            await update.message.reply_text("Usage: /research [topic]")
            return

        await update.message.reply_text(f"Researching: {topic} (using Opus for deep analysis)...")
        result = await self.mira.brain.deep_research(topic)
        await update.message.reply_text(result)
        self.mira.sqlite.log_action("research", f"research: {topic}", "completed")

    # ══════════════════════════════════════════════════════════════════
    # TASK COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """View and manage pending tasks."""
        if context.args and context.args[0] == "add":
            # /tasks add Buy groceries
            title = " ".join(context.args[1:])
            if not title:
                await update.message.reply_text("Usage: /tasks add [title]")
                return
            task_id = self.mira.sqlite.add_task(title=title, module="manual", priority=3)
            await update.message.reply_text(f"Task added: {title} (#{task_id})")
            return

        if context.args and context.args[0] == "done":
            # /tasks done 5
            try:
                task_id = int(context.args[1])
                self.mira.sqlite.complete_task(task_id)
                await update.message.reply_text(f"Task #{task_id} marked complete.")
            except (IndexError, ValueError):
                await update.message.reply_text("Usage: /tasks done [id]")
            return

        # List pending tasks
        tasks = self.mira.sqlite.get_pending_tasks()
        if not tasks:
            await update.message.reply_text("No pending tasks.\n\nUse /tasks add [title] to create one.")
            return

        msg = f"Pending Tasks ({len(tasks)}):\n\n"
        for t in tasks[:20]:
            priority = t.get("priority", "?")
            title = t.get("title", "?")
            tid = t.get("id", "?")
            module = t.get("module", "")
            msg += f"  #{tid} [{priority}] {title}"
            if module:
                msg += f" ({module})"
            msg += "\n"
        if len(tasks) > 20:
            msg += f"\n  ...and {len(tasks) - 20} more"
        msg += "\n\nCommands: /tasks add [title] | /tasks done [id]"
        await update.message.reply_text(msg[:4000])

    # ══════════════════════════════════════════════════════════════════
    # EMAIL COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check email and show triage results."""
        if not hasattr(self.mira, "pa") or not self.mira.pa.gmail_service:
            await update.message.reply_text(
                "Gmail not connected.\n\n"
                "Set up Google OAuth credentials and run the auth flow first."
            )
            return

        await update.message.reply_text("Checking email...")
        try:
            emails = await self.mira.pa.check_email()
            if not emails:
                await update.message.reply_text("Inbox clear — no unread emails.")
                return

            msg = f"Email Triage ({len(emails)} unread):\n\n"
            for e in emails[:10]:
                sender = e.get("from", "?")[:30]
                subject = e.get("subject", "?")[:40]
                ev = e.get("evaluation", {})
                urgency = ev.get("urgency", "?")
                importance = ev.get("importance", "?")
                category = ev.get("category", "?")
                msg += f"  [{urgency}/{importance}] {sender}\n  {subject}\n  → {category}\n\n"

            if len(emails) > 10:
                msg += f"...and {len(emails) - 10} more"
            await update.message.reply_text(msg[:4000])
        except Exception as e:
            await update.message.reply_text(f"Email check failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # CAPTURE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_pause_listen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Audio capture paused for 30 minutes. (Phase 4)")

    # ══════════════════════════════════════════════════════════════════
    # DECISION COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_decision(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Log, score, or review decisions."""
        args = context.args or []

        if not args:
            # List recent decisions
            try:
                rows = self.mira.sqlite.conn.execute(
                    "SELECT id, decision, domain, outcome_score, decided_at FROM decisions ORDER BY decided_at DESC LIMIT 10"
                ).fetchall()
                if not rows:
                    await update.message.reply_text(
                        "No decisions logged yet.\n\n"
                        "Usage:\n"
                        "/decision [text] — Log a decision\n"
                        "/decision score [id] [1-10] [outcome]\n"
                        "/decision review — Analyse patterns"
                    )
                    return
                msg = "Recent Decisions\n\n"
                for r in rows:
                    d = dict(r)
                    score = f" [{d['outcome_score']}/10]" if d.get("outcome_score") else " [unscored]"
                    date = str(d.get("decided_at", ""))[:10]
                    msg += f"#{d['id']} ({date}) {d['decision'][:60]}{score}\n"
                msg += "\nUse /decision score [id] [1-10] [outcome] to score one."
                await update.message.reply_text(msg)
            except Exception as e:
                await update.message.reply_text(f"Error: {e}")
            return

        subcmd = args[0].lower()

        if subcmd == "score" and len(args) >= 3:
            try:
                decision_id = int(args[1])
                score = int(args[2])
                if score < 1 or score > 10:
                    await update.message.reply_text("Score must be 1-10.")
                    return
                outcome = " ".join(args[3:]) if len(args) > 3 else ""
                self.mira.sqlite.score_decision(decision_id, outcome, score)
                await update.message.reply_text(f"Decision #{decision_id} scored {score}/10.")
            except (ValueError, IndexError):
                await update.message.reply_text("Usage: /decision score [id] [1-10] [outcome text]")
            return

        if subcmd == "review":
            await update.message.reply_text("Analysing your decision patterns...")
            try:
                rows = self.mira.sqlite.conn.execute(
                    "SELECT * FROM decisions WHERE outcome_score IS NOT NULL ORDER BY decided_at DESC LIMIT 50"
                ).fetchall()

                if not rows:
                    await update.message.reply_text("No scored decisions yet. Score some decisions first with /decision score.")
                    return

                decisions = [dict(r) for r in rows]
                avg_score = sum(d["outcome_score"] for d in decisions) / len(decisions)

                # Group by domain
                by_domain = {}
                for d in decisions:
                    domain = d.get("domain", "general")
                    by_domain.setdefault(domain, []).append(d["outcome_score"])

                domain_avgs = {
                    k: round(sum(v) / len(v), 1) for k, v in by_domain.items()
                }

                analysis_data = {
                    "total_scored": len(decisions),
                    "avg_score": round(avg_score, 1),
                    "domain_averages": domain_avgs,
                    "worst_decisions": sorted(decisions, key=lambda x: x["outcome_score"])[:3],
                    "best_decisions": sorted(decisions, key=lambda x: x["outcome_score"], reverse=True)[:3],
                }

                prompt = f"""Analyse these decision patterns and identify blind spots.

{json.dumps(analysis_data, indent=2, default=str)}

Provide:
1. Overall decision quality assessment
2. Which domains you decide best/worst in
3. Common patterns in bad decisions (rushed? emotional? missing info?)
4. Specific blind spots based on the data
5. One actionable improvement for next week

Be direct and specific. This is for self-improvement, not ego protection."""

                analysis = await self.mira.brain.think(
                    message=prompt,
                    include_history=False,
                    max_tokens=1500,
                    tier="standard",
                    task_type="decision_review",
                )

                await update.message.reply_text(f"Decision Review\n\n{analysis[:4000]}")
            except Exception as e:
                logger.error(f"Decision review failed: {e}")
                await update.message.reply_text(f"Review failed: {e}")
            return

        # Default: log a new decision
        decision_text = " ".join(args)

        # Use AI to extract domain and reasoning
        try:
            prompt = f"""Classify this decision and extract key details. Return ONLY valid JSON.

Decision: {decision_text}

Return JSON with:
- decision: the decision restated clearly (1 sentence)
- domain: one of [trading, work, personal, finance, health, social, learning, general]
- reasoning: brief explanation of why this decision was likely made
- alternatives: list of 2-3 alternatives that were likely considered"""

            response = await self.mira.brain.think(
                message=prompt,
                include_history=False,
                system_override="You are a decision analyst. Return ONLY valid JSON.",
                max_tokens=512,
                tier="fast",
                task_type="decision_classification",
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
                cleaned = cleaned.rsplit("```", 1)[0]

            data = json.loads(cleaned)
            decision_id = self.mira.sqlite.log_decision(
                decision=data.get("decision", decision_text),
                context=decision_text,
                reasoning=data.get("reasoning", ""),
                domain=data.get("domain", "general"),
                alternatives=data.get("alternatives", []),
            )

            await update.message.reply_text(
                f"Decision logged (#{decision_id})\n\n"
                f"Domain: {data.get('domain', 'general')}\n"
                f"Decision: {data.get('decision', decision_text)[:200]}\n\n"
                f"Score it later with: /decision score {decision_id} [1-10] [outcome]"
            )

        except (json.JSONDecodeError, Exception):
            # Fallback: log without AI classification
            decision_id = self.mira.sqlite.log_decision(
                decision=decision_text,
                domain="general",
            )
            await update.message.reply_text(
                f"Decision logged (#{decision_id})\n\n"
                f"Score it later: /decision score {decision_id} [1-10] [outcome]"
            )

    # ══════════════════════════════════════════════════════════════════
    # GIFT COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_gift(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Generate personalised gift suggestions for a person."""
        name = " ".join(context.args) if context.args else ""
        if not name:
            await update.message.reply_text(
                "Usage: /gift [person name]\n\n"
                "Generates personalised gift ideas based on everything "
                "Mira knows about that person."
            )
            return

        personal = getattr(self.mira, "personal", None)
        if not personal:
            await update.message.reply_text("Personal module not available.")
            return

        await update.message.reply_text(f"Thinking about gifts for {name}...")

        try:
            suggestions = await personal.suggest_gift(name)
            await update.message.reply_text(f"Gift Ideas for {name}\n\n{suggestions[:4000]}")
        except Exception as e:
            logger.error(f"Gift suggestion failed: {e}")
            await update.message.reply_text(f"Could not generate gift suggestions: {e}")

    # ══════════════════════════════════════════════════════════════════
    # MEETING ANALYSIS COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_meetings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyse meeting patterns over the last 4 weeks."""
        pa = getattr(self.mira, "pa", None)
        if not pa:
            await update.message.reply_text("PA module not available.")
            return

        await update.message.reply_text("Analysing 4 weeks of meeting data...")

        try:
            analysis = await pa.analyse_meeting_patterns()
            # Split if too long
            if len(analysis) > 4000:
                parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
                for i, part in enumerate(parts):
                    prefix = f"Meeting Analysis ({i+1}/{len(parts)})\n\n" if i == 0 else ""
                    await update.message.reply_text(f"{prefix}{part}")
            else:
                await update.message.reply_text(f"Meeting Analysis\n\n{analysis}")
        except Exception as e:
            logger.error(f"Meeting analysis failed: {e}")
            await update.message.reply_text(f"Could not analyse meetings: {e}")

    # ══════════════════════════════════════════════════════════════════
    # HABIT COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_habit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Habit tracking — add, log, stats, or list all habits."""
        args = context.args or []
        personal = getattr(self.mira, "personal", None)
        if not personal:
            await update.message.reply_text("Personal module not available.")
            return

        if not args:
            # List all habits with streaks
            stats = await personal.get_habit_stats()
            if not stats:
                await update.message.reply_text(
                    "No habits tracked yet.\n\nUsage:\n"
                    "/habit add gym — Track a new habit\n"
                    "/habit log gym — Mark done today\n"
                    "/habit stats — Detailed statistics"
                )
                return

            msg = "Your Habits\n\n"
            for h in stats:
                status = "done" if h["last_completed"] == datetime.now().strftime("%Y-%m-%d") else "pending"
                icon = "[x]" if status == "done" else "[ ]"
                trend_arrow = {"improving": "^", "declining": "v", "stable": "="}.get(h["trend"], "")
                msg += (
                    f"{icon} {h['name']} — streak: {h['streak']}d, "
                    f"7d: {h['completion_rate_7d']:.0f}% {trend_arrow}\n"
                )
            await update.message.reply_text(msg)
            return

        subcmd = args[0].lower()

        if subcmd == "add":
            if len(args) < 2:
                await update.message.reply_text("Usage: /habit add [name] [daily|weekly] [category]")
                return
            name = args[1]
            freq = args[2] if len(args) > 2 and args[2] in ("daily", "weekly") else "daily"
            cat = args[3] if len(args) > 3 else "general"
            result = await personal.add_habit(name, freq, cat)
            if "error" in result:
                await update.message.reply_text(f"Already tracking: {name}")
            else:
                await update.message.reply_text(
                    f"Now tracking: {result['name']} ({freq}, {cat})"
                )

        elif subcmd == "log" or subcmd == "done":
            if len(args) < 2:
                await update.message.reply_text("Usage: /habit log [name]")
                return
            name = args[1]
            result = await personal.log_habit(name)
            if "error" in result:
                await update.message.reply_text(result["error"])
            elif result.get("status") == "already_logged":
                await update.message.reply_text(
                    f"Already logged '{name}' today. Streak: {result['streak']}d"
                )
            else:
                streak = result.get("streak", 0)
                fire = f" {'!' * min(streak // 7, 5)}" if streak >= 7 else ""
                await update.message.reply_text(
                    f"Logged: {result['habit']}\nStreak: {streak} days{fire}"
                )

        elif subcmd == "stats":
            stats = await personal.get_habit_stats()
            if not stats:
                await update.message.reply_text("No habits tracked yet.")
                return

            msg = "Habit Statistics (30-day)\n\n"
            for h in stats:
                msg += (
                    f"{h['name']} [{h['category']}]\n"
                    f"  Streak: {h['streak']}d | 7d: {h['completion_rate_7d']:.0f}% | "
                    f"30d: {h['completion_rate_30d']:.0f}% | Trend: {h['trend']}\n"
                )
            await update.message.reply_text(msg)

        else:
            # Treat single word as logging that habit
            result = await personal.log_habit(subcmd)
            if "error" in result:
                await update.message.reply_text(result["error"])
            elif result.get("status") == "already_logged":
                await update.message.reply_text(
                    f"Already logged '{subcmd}' today. Streak: {result['streak']}d"
                )
            else:
                await update.message.reply_text(
                    f"Logged: {result['habit']}\nStreak: {result.get('streak', 0)} days"
                )

    # ══════════════════════════════════════════════════════════════════
    # REMINDER COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_remind(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set a timed reminder — /remind 30m Call back the client."""
        import asyncio
        import re

        args = context.args or []
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /remind [time] [message]\n\n"
                "Examples:\n"
                "  /remind 30m Call the client\n"
                "  /remind 2h Check EA status\n"
                "  /remind 1d Review weekly report"
            )
            return

        time_str = args[0].lower()
        message = " ".join(args[1:])

        # Parse time string (e.g., 30m, 2h, 1d, 90s)
        match = re.match(r"^(\d+)(s|m|h|d)$", time_str)
        if not match:
            await update.message.reply_text(
                "Invalid time format. Use: 30s, 15m, 2h, 1d"
            )
            return

        amount = int(match.group(1))
        unit = match.group(2)
        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        delay_seconds = amount * multipliers[unit]

        # Cap at 7 days
        if delay_seconds > 604800:
            await update.message.reply_text("Maximum reminder time is 7 days.")
            return

        # Format display time
        if unit == "s":
            display = f"{amount} second{'s' if amount != 1 else ''}"
        elif unit == "m":
            display = f"{amount} minute{'s' if amount != 1 else ''}"
        elif unit == "h":
            display = f"{amount} hour{'s' if amount != 1 else ''}"
        else:
            display = f"{amount} day{'s' if amount != 1 else ''}"

        await update.message.reply_text(f"Reminder set for {display} from now:\n\"{message}\"")

        self.mira.sqlite.log_action("pa", "reminder_set", f"in {display}: {message[:100]}")

        # Schedule the reminder delivery
        async def _deliver_reminder():
            await asyncio.sleep(delay_seconds)
            await self.send(f"REMINDER\n\n{message}")
            self.mira.sqlite.log_action("pa", "reminder_delivered", message[:100])

        asyncio.create_task(_deliver_reminder())

    # ══════════════════════════════════════════════════════════════════
    # SEARCH COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Semantic search across all memory layers."""
        query = " ".join(context.args) if context.args else ""
        if not query:
            await update.message.reply_text("Usage: /search [query]\n\nSearches memories by meaning, not just keywords.")
            return

        await update.message.reply_text(f"Searching for: \"{query}\"...")

        results = []

        # 1. Semantic search via ChromaDB
        vector = getattr(self.mira, "vector", None)
        if vector:
            try:
                semantic = vector.search(query, n_results=5)
                for doc in semantic:
                    results.append({
                        "source": "semantic",
                        "content": doc.get("content", doc.get("document", ""))[:200],
                        "score": doc.get("distance", 0),
                    })
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # 2. Keyword search via SQLite
        try:
            keyword = self.mira.sqlite.search_memories(query=query, limit=5)
            for m in keyword:
                content = m.get("content", "")[:200]
                # Avoid duplicates
                if not any(content[:50] in r["content"] for r in results):
                    results.append({
                        "source": "sqlite",
                        "content": content,
                        "score": m.get("importance", 0),
                    })
        except Exception as e:
            logger.warning(f"SQLite search failed: {e}")

        # 3. Knowledge graph search
        graph = getattr(self.mira, "graph", None)
        if graph:
            try:
                graph_results = graph.find_nodes(label_contains=query)
                for g in graph_results[:3]:
                    label = g.get("label", str(g))[:200]
                    ntype = g.get("node_type", "")
                    content = f"({ntype}) {label}" if ntype else label
                    results.append({"source": "graph", "content": content, "score": 0})
            except Exception:
                pass

        if not results:
            await update.message.reply_text(f"No results found for \"{query}\".")
            return

        msg = f"Search: \"{query}\"\n{len(results)} results\n\n"
        for i, r in enumerate(results[:8], 1):
            source_tag = f"[{r['source']}]"
            msg += f"{i}. {source_tag} {r['content']}\n\n"

        if len(msg) > 4000:
            msg = msg[:3990] + "...\n(truncated)"

        await update.message.reply_text(msg)

    # ══════════════════════════════════════════════════════════════════
    # SCHEDULE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all scheduled autonomous tasks and their status."""
        scheduler = getattr(self.mira, "scheduler", None)
        if not scheduler or not scheduler.tasks:
            await update.message.reply_text("No scheduled tasks found.")
            return

        msg = f"Scheduled Tasks ({len(scheduler.tasks)})\n\n"

        # Group by schedule type
        by_type = {"daily": [], "weekly": [], "interval": []}
        for task in scheduler.tasks:
            by_type.get(task.schedule_type, []).append(task)

        if by_type["daily"]:
            msg += "DAILY\n"
            for t in sorted(by_type["daily"], key=lambda x: str(x.run_at or "")):
                time_str = t.run_at.strftime("%H:%M") if t.run_at else "?"
                status = "on" if t.enabled else "off"
                last = ""
                if t.last_run:
                    last = f" (last: {t.last_run.strftime('%m/%d %H:%M')})"
                msg += f"  [{status}] {t.name} @ {time_str}{last}\n"
            msg += "\n"

        if by_type["weekly"]:
            msg += "WEEKLY\n"
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for t in by_type["weekly"]:
                time_str = t.run_at.strftime("%H:%M") if t.run_at else "?"
                days = ", ".join(day_names[d] for d in (t.days or []))
                status = "on" if t.enabled else "off"
                msg += f"  [{status}] {t.name} @ {time_str} ({days})\n"
            msg += "\n"

        if by_type["interval"]:
            msg += "RECURRING\n"
            for t in by_type["interval"]:
                mins = t.interval_seconds // 60
                status = "on" if t.enabled else "off"
                runs = f" ({t.run_count} runs)" if t.run_count else ""
                msg += f"  [{status}] {t.name} every {mins}m{runs}\n"
            msg += "\n"

        msg += f"Total runs: {sum(t.run_count for t in scheduler.tasks)}"
        await update.message.reply_text(msg)

    # ══════════════════════════════════════════════════════════════════
    # EARNING COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_earn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show real earning module status with revenue data."""
        earning = getattr(self.mira, "earning", None)
        if not earning:
            await update.message.reply_text("Earning module not available.")
            return

        await update.message.reply_text("Fetching earning module data...")

        try:
            # Get revenue totals
            revenue = await earning.get_total_revenue("month")
            report = await earning.generate_report()

            msg = "Earning Modules\n\n"
            msg += f"Monthly Revenue: ${revenue.get('grand_total', 0):.2f}\n\n"

            # Breakdown by stream
            for stream, amount in revenue.get("streams", revenue).items():
                if stream == "grand_total":
                    continue
                status = "active" if amount > 0 else "pending"
                msg += f"  {stream.replace('_', ' ').title()}: ${amount:.2f} ({status})\n"

            msg += f"\n{report[:1500]}" if len(report) > 10 else ""

            await update.message.reply_text(msg[:4000])
        except Exception as e:
            logger.error(f"Earn command failed: {e}")
            await update.message.reply_text(
                "Earning Modules Status\n\n"
                "Freelance Agent: scanning for jobs\n"
                "Content Monetisation: queue active\n"
                "Polymarket Alpha: analysis ready\n"
                "Digital Products: setup pending\n"
                "Consulting Pipeline: outreach pending\n\n"
                f"Use /cost to see API spend."
            )

    # ══════════════════════════════════════════════════════════════════
    # COST TRACKING
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show API cost breakdown with projected monthly spend."""
        period = context.args[0] if context.args else "today"
        if period not in ("today", "week", "month", "all"):
            period = "today"

        costs = self.mira.sqlite.get_api_costs(period)
        today_costs = self.mira.sqlite.get_api_costs("today")

        msg = f"API Costs ({period})\n\n"
        msg += f"Total: ${costs['total_cost']:.4f} ({costs['total_calls']} calls)\n\n"

        if costs["by_tier"]:
            msg += "By Tier:\n"
            for t in costs["by_tier"]:
                msg += f"  {t['tier']}: ${t['cost']:.4f} ({t['calls']} calls, {t['input_tok']}in/{t['output_tok']}out)\n"
            msg += "\n"

        if costs["by_task"]:
            msg += "Top Tasks:\n"
            for t in sorted(costs["by_task"], key=lambda x: x["cost"], reverse=True)[:8]:
                msg += f"  {t['task_type']}: ${t['cost']:.4f} ({t['calls']}x)\n"
            msg += "\n"

        # Projected monthly cost based on today's spend
        daily_cost = today_costs["total_cost"]
        projected = daily_cost * 30
        msg += f"Today so far: ${daily_cost:.4f}\n"
        msg += f"Projected monthly: ${projected:.2f}\n"

        msg += f"\nUsage: /cost [today|week|month|all]"
        await update.message.reply_text(msg)

    # ══════════════════════════════════════════════════════════════════
    # LEARNING COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track a new learning topic."""
        topic = " ".join(context.args) if context.args else ""
        if not topic:
            await update.message.reply_text("Usage: /learn [topic to study]")
            return

        if not getattr(self.mira, "learning", None):
            await update.message.reply_text("Learning module not available.")
            return

        try:
            result = await self.mira.learning.add_topic(topic)
            await update.message.reply_text(result)
            self.mira.sqlite.log_action("learning", f"track_topic: {topic}", "added")
        except Exception as e:
            logger.error(f"Learn command failed: {e}")
            await update.message.reply_text(f"Failed to add topic: {e}")

    async def _cmd_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Review a flashcard with a quality rating."""
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /review [card_id] [quality 0-5]")
            return

        if not getattr(self.mira, "learning", None):
            await update.message.reply_text("Learning module not available.")
            return

        card_id = context.args[0]
        try:
            quality = int(context.args[1])
        except ValueError:
            await update.message.reply_text("Quality must be a number 0-5.")
            return

        try:
            result = await self.mira.learning.review_card(card_id, quality)
            await update.message.reply_text(result)
            self.mira.sqlite.log_action("learning", f"review_card: {card_id}", f"quality={quality}")
        except Exception as e:
            logger.error(f"Review command failed: {e}")
            await update.message.reply_text(f"Review failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # NEGOTIATION / CONTRACT COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_negotiate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start negotiation preparation for a counterparty."""
        counterparty = " ".join(context.args) if context.args else ""
        if not counterparty:
            await update.message.reply_text("Usage: /negotiate [counterparty name or context]")
            return

        if not getattr(self.mira, "negotiation", None):
            await update.message.reply_text("Negotiation module not available.")
            return

        try:
            await update.message.reply_text(f"Preparing negotiation brief for: {counterparty}...")
            result = await self.mira.negotiation.prepare(counterparty)
            await update.message.reply_text(result)
            self.mira.sqlite.log_action("negotiation", f"prepare: {counterparty}", "delivered")
        except Exception as e:
            logger.error(f"Negotiate command failed: {e}")
            await update.message.reply_text(f"Negotiation prep failed: {e}")

    async def _cmd_contract(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Review a contract or legal text."""
        contract_text = " ".join(context.args) if context.args else ""
        if not contract_text:
            await update.message.reply_text("Usage: /contract [paste contract text to review]")
            return

        if not getattr(self.mira, "negotiation", None):
            await update.message.reply_text("Negotiation module not available.")
            return

        try:
            await update.message.reply_text("Reviewing contract...")
            result = await self.mira.negotiation.review_contract(contract_text)
            await update.message.reply_text(result)
            self.mira.sqlite.log_action("negotiation", "contract_review", "delivered")
        except Exception as e:
            logger.error(f"Contract review failed: {e}")
            await update.message.reply_text(f"Contract review failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # COMPUTER USE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_do(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute a computer use task described in natural language."""
        task = " ".join(context.args) if context.args else ""
        if not task:
            await update.message.reply_text(
                "Usage: /do [task]\n\n"
                "Examples:\n"
                "  /do open Chrome and go to google.com\n"
                "  /do take a screenshot of MetaTrader\n"
                "  /do close the Notepad window"
            )
            return

        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            await update.message.reply_text("Computer use not available. Check pyautogui + Anthropic API.")
            return

        if self.mira.paused:
            await update.message.reply_text("Kill switch active — computer use blocked.")
            return

        await update.message.reply_text(f"Executing: {task[:100]}...")
        try:
            result = await cu.execute_task(task, max_steps=10)
            status = result.get("status", "unknown")
            steps = result.get("steps_taken", 0)
            msg = f"Task: {task[:80]}\nStatus: {status}\nSteps: {steps}"

            # Include last step summary if completed
            for step in reversed(result.get("steps", [])):
                if step.get("summary"):
                    msg += f"\n\nResult: {step['summary'][:500]}"
                    break

            await update.message.reply_text(msg)

            # Send a screenshot of the final state
            screenshot_path = await cu.screenshot_to_file()
            if screenshot_path:
                try:
                    with open(screenshot_path, "rb") as photo:
                        await self.app.bot.send_photo(
                            chat_id=update.effective_chat.id, photo=photo,
                            caption="Screen after task"
                        )
                finally:
                    import os
                    if os.path.exists(screenshot_path):
                        os.remove(screenshot_path)

        except Exception as e:
            logger.error(f"/do command failed: {e}")
            await update.message.reply_text(f"Task failed: {e}")

    async def _cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Take a screenshot and send it, optionally with AI analysis."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        question = " ".join(context.args) if context.args else None

        # Send screenshot as photo
        screenshot_path = await cu.screenshot_to_file()
        if not screenshot_path:
            await update.message.reply_text("Failed to capture screenshot.")
            return

        try:
            with open(screenshot_path, "rb") as photo:
                await self.app.bot.send_photo(
                    chat_id=update.effective_chat.id, photo=photo,
                    caption="Current screen"
                )
        finally:
            import os
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

        # If a question was asked, analyse the screen
        if question and cu.client:
            await update.message.reply_text(f"Analysing: {question[:100]}...")
            analysis = await cu.analyse_screen(task=question)
            await update.message.reply_text(analysis[:4000])

    async def _cmd_open(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Open an application by name."""
        app_name = " ".join(context.args) if context.args else ""
        if not app_name:
            await update.message.reply_text(
                "Usage: /open [app name]\n\n"
                "Examples: /open Chrome, /open MetaTrader 5, /open Excel, /open explorer"
            )
            return

        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        if self.mira.paused:
            await update.message.reply_text("Kill switch active — computer use blocked.")
            return

        try:
            from computer_use.actions import ComputerActions
            actions = ComputerActions(cu)
            result = await actions.open_application(app_name)
            await update.message.reply_text(f"Opened {app_name} ({result.get('method', 'unknown')})")
            self.mira.sqlite.log_action("computer_use", f"open: {app_name}", "success")
        except Exception as e:
            logger.error(f"/open failed: {e}")
            await update.message.reply_text(f"Failed to open {app_name}: {e}")

    async def _cmd_windows(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all open windows or focus one."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        focus_target = " ".join(context.args) if context.args else ""

        if focus_target:
            # Focus a specific window
            result = await cu.focus_window(focus_target)
            if result:
                await update.message.reply_text(f"Focused window matching: {focus_target}")
            else:
                await update.message.reply_text(f"No window found matching: {focus_target}")
            return

        # List all windows
        windows = await cu.list_windows()
        if not windows:
            await update.message.reply_text("No windows found (or detection not available).")
            return

        msg = f"Open Windows ({len(windows)}):\n\n"
        for i, w in enumerate(windows[:30], 1):
            msg += f"  {i}. {w['title'][:60]}\n"
        if len(windows) > 30:
            msg += f"\n  ... and {len(windows) - 30} more"
        msg += "\n\nUsage: /windows [title] to focus a window"
        await update.message.reply_text(msg)

    async def _cmd_run(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run a shell command on the desktop."""
        command = " ".join(context.args) if context.args else ""
        if not command:
            await update.message.reply_text("Usage: /run [command]\nExample: /run dir C:\\Users")
            return

        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        if self.mira.paused:
            await update.message.reply_text("Kill switch active — command execution blocked.")
            return

        result = await cu.run_command(command)
        status = result.get("status", "unknown")
        stdout = result.get("stdout", "")[:3500]
        stderr = result.get("stderr", "")[:500]

        msg = f"Command: {command[:100]}\nStatus: {status}"
        if stdout:
            msg += f"\n\nOutput:\n{stdout}"
        if stderr:
            msg += f"\n\nErrors:\n{stderr}"
        await update.message.reply_text(msg[:4000])

    async def _cmd_clipboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Read or set the clipboard."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        text = " ".join(context.args) if context.args else ""

        if text:
            # Set clipboard
            ok = await cu.set_clipboard(text)
            if ok:
                await update.message.reply_text(f"Clipboard set: {text[:100]}")
            else:
                await update.message.reply_text("Failed to set clipboard.")
        else:
            # Read clipboard
            content = await cu.get_clipboard()
            if content:
                await update.message.reply_text(f"Clipboard contents:\n\n{content[:3000]}")
            else:
                await update.message.reply_text("Clipboard is empty.")

    async def _cmd_processes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List running processes, optionally filtered."""
        cu = getattr(self.mira, "computer_use", None)
        if not cu:
            await update.message.reply_text("Computer use not available.")
            return

        filter_name = " ".join(context.args) if context.args else None
        processes = await cu.list_processes(filter_name=filter_name)

        if not processes:
            await update.message.reply_text("No processes found.")
            return

        label = f' matching "{filter_name}"' if filter_name else ''
        msg = f"Processes{label} ({len(processes)}):\n\n"
        for p in processes[:40]:
            msg += f"  {p['name']} (PID {p['pid']}) — {p.get('memory', '?')}\n"
        if len(processes) > 40:
            msg += f"\n  ... and {len(processes) - 40} more"
        await update.message.reply_text(msg[:4000])

    # ══════════════════════════════════════════════════════════════════
    # SYSTEM COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Take a screenshot and answer a question about what's on screen."""
        question = " ".join(context.args) if context.args else "What's currently visible on screen?"

        cu = getattr(self.mira, "computer_use", None)
        if not cu or not cu.client:
            await update.message.reply_text("Computer use not available.")
            return

        await update.message.reply_text("Looking at the screen...")

        # Take screenshot and send it
        path = await cu.screenshot_to_file()
        if path:
            try:
                with open(path, "rb") as photo:
                    await self.app.bot.send_photo(
                        chat_id=update.effective_chat.id, photo=photo,
                    )
            except Exception:
                pass
            finally:
                if os.path.exists(path):
                    os.remove(path)

        # Analyse with Claude Vision
        analysis = await cu.analyse_screen(task=question)
        await update.message.reply_text(analysis[:4000])

    async def _cmd_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Pull latest code from GitHub and restart Mira.

        This is the remote deploy command — push from Mac, then /update on Telegram
        to make the Windows desktop pick up the changes and restart.
        """
        import subprocess as sp
        agent_dir = Path(__file__).parent

        await update.message.reply_text("Pulling latest code from GitHub...")

        # Step 1: git pull
        try:
            result = sp.run(
                ["git", "pull", "origin", "main"],
                cwd=str(agent_dir),
                capture_output=True,
                text=True,
                timeout=60,
            )
            pull_output = result.stdout.strip() or result.stderr.strip()
            if result.returncode != 0:
                await update.message.reply_text(
                    f"Git pull failed (exit {result.returncode}):\n{pull_output[:1500]}"
                )
                return
        except sp.TimeoutExpired:
            await update.message.reply_text("Git pull timed out after 60s.")
            return
        except Exception as e:
            await update.message.reply_text(f"Git pull error: {e}")
            return

        # Step 2: Check if anything changed
        already_up_to_date = "Already up to date" in pull_output
        if already_up_to_date:
            await update.message.reply_text(
                f"Already up to date — no changes to deploy.\n\n{pull_output[:500]}"
            )
            return

        await update.message.reply_text(f"Code updated:\n{pull_output[:1500]}")

        # Step 3: Install any new dependencies
        try:
            req_file = agent_dir / "requirements.txt"
            if req_file.exists():
                await update.message.reply_text("Installing dependencies...")
                pip_result = sp.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q"],
                    cwd=str(agent_dir),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if pip_result.returncode != 0:
                    pip_err = pip_result.stderr.strip()[-500:]
                    await update.message.reply_text(f"pip install warning:\n{pip_err}")
        except Exception as pip_e:
            await update.message.reply_text(f"pip install skipped: {pip_e}")

        # Step 4: Report and restart
        await update.message.reply_text("Restarting Mira now...")
        self.mira.sqlite.log_action("system", "update", pull_output[:500])

        # Step 4: Restart — replace the current process with a fresh one
        await self._do_restart()

    async def _cmd_restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Restart Mira without pulling code."""
        await update.message.reply_text("Restarting Mira...")
        self.mira.sqlite.log_action("system", "restart", "manual restart via /restart")
        await self._do_restart()

    async def _do_restart(self):
        """Perform the actual restart — stop the bot cleanly, then os.execv into a new process."""
        import os as _os

        agent_dir = Path(__file__).parent
        python = sys.executable
        main_py = str(agent_dir / "main.py")

        # Give Telegram a moment to deliver the reply
        import asyncio
        await asyncio.sleep(1)

        # Stop the telegram bot gracefully
        try:
            await self.stop()
        except Exception:
            pass

        # Replace the current process with a fresh python main.py
        logger.info("Restarting via os.execv...")
        _os.execv(python, [python, main_py])

    async def _cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the last N lines of mira.log."""
        n = 30
        if context.args:
            try:
                n = int(context.args[0])
            except ValueError:
                pass
        n = min(n, 100)  # cap at 100 lines

        log_path = Config.LOG_DIR / "mira.log"
        if not log_path.exists():
            await update.message.reply_text("No log file found.")
            return

        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-n:]
            text = "".join(tail)
            if not text.strip():
                await update.message.reply_text("Log file is empty.")
                return
            # Truncate if too long for Telegram
            if len(text) > 3900:
                text = text[-3900:]
                text = "...(truncated)\n" + text
            await update.message.reply_text(f"Last {len(tail)} log lines:\n\n{text}")
        except Exception as e:
            await update.message.reply_text(f"Failed to read logs: {e}")

    async def _cmd_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show current git commit hash and last update time."""
        import subprocess as sp
        agent_dir = Path(__file__).parent

        try:
            # Get current commit hash
            hash_result = sp.run(
                ["git", "log", "-1", "--format=%h %s", "--date=short"],
                cwd=str(agent_dir), capture_output=True, text=True, timeout=10,
            )
            commit_info = hash_result.stdout.strip() if hash_result.returncode == 0 else "unknown"

            # Get last commit date
            date_result = sp.run(
                ["git", "log", "-1", "--format=%ci"],
                cwd=str(agent_dir), capture_output=True, text=True, timeout=10,
            )
            commit_date = date_result.stdout.strip() if date_result.returncode == 0 else "unknown"

            # Get branch
            branch_result = sp.run(
                ["git", "branch", "--show-current"],
                cwd=str(agent_dir), capture_output=True, text=True, timeout=10,
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"

            # Count total commits
            count_result = sp.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=str(agent_dir), capture_output=True, text=True, timeout=10,
            )
            commit_count = count_result.stdout.strip() if count_result.returncode == 0 else "?"

            # Python version
            import platform
            py_version = platform.python_version()
            os_info = platform.platform()

            uptime = ""
            if self.mira.start_time:
                delta = datetime.now() - self.mira.start_time
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                mins = rem // 60
                uptime = f"{hours}h {mins}m"

            await update.message.reply_text(
                f"Mira v1.0 — Build {commit_count}\n\n"
                f"Branch: {branch}\n"
                f"Last commit: {commit_info}\n"
                f"Date: {commit_date}\n\n"
                f"Runtime: Python {py_version}\n"
                f"OS: {os_info}\n"
                f"Uptime: {uptime or 'N/A'}"
            )
        except Exception as e:
            await update.message.reply_text(f"Version check failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # DRAFT APPROVAL (inline keyboards)
    # ══════════════════════════════════════════════════════════════════

    async def send_draft_for_approval(
        self, draft_text: str, draft_type: str, metadata: dict = None
    ) -> str:
        """Send a draft to the user with Accept / Edit / Reject inline buttons.

        Args:
            draft_text: The draft content (email body, social post, etc.)
            draft_type: Type of draft — "email_reply", "social_post", "message", etc.
            metadata: Extra context needed to send/post (thread_id, platform, recipient, etc.)

        Returns:
            The draft_id assigned to this pending draft.
        """
        self._draft_counter += 1
        draft_id = f"draft_{self._draft_counter}_{int(datetime.now().timestamp())}"

        self.pending_drafts[draft_id] = {
            "text": draft_text,
            "type": draft_type,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Accept", callback_data=f"accept:{draft_id}"),
                    InlineKeyboardButton("Edit", callback_data=f"edit:{draft_id}"),
                    InlineKeyboardButton("Reject", callback_data=f"reject:{draft_id}"),
                ]
            ]
        )

        label = draft_type.replace("_", " ").title()
        msg = f"DRAFT — {label}\n\n{draft_text}"

        if self.app and self.chat_id:
            await self.app.bot.send_message(
                chat_id=self.chat_id, text=msg, reply_markup=keyboard
            )

        logger.info(f"Draft {draft_id} ({draft_type}) sent for approval")
        return draft_id

    async def _handle_draft_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle Accept / Edit / Reject button presses on draft messages."""
        query = update.callback_query
        await query.answer()  # acknowledge the button press

        data = query.data  # e.g. "accept:draft_1_1711100000"
        if ":" not in data:
            return

        action, draft_id = data.split(":", 1)
        draft = self.pending_drafts.get(draft_id)

        if not draft:
            await query.edit_message_text("This draft has expired or already been handled.")
            return

        if action == "accept":
            # Execute the draft (send email, post, etc.)
            result = await self._execute_draft(draft)
            del self.pending_drafts[draft_id]
            await query.edit_message_text(
                f"SENT — {draft['type'].replace('_', ' ').title()}\n\n"
                f"{draft['text']}\n\n{result}"
            )
            self.mira.sqlite.log_action(
                "pa", f"draft_accepted:{draft['type']}", "sent"
            )

        elif action == "edit":
            # Ask the user for an edited version; keep draft pending
            self.pending_drafts[draft_id]["awaiting_edit"] = True
            await query.edit_message_text(
                f"EDITING — {draft['type'].replace('_', ' ').title()}\n\n"
                f"{draft['text']}\n\n"
                "Send your edited version as a message. I'll re-send it for approval."
            )

        elif action == "reject":
            del self.pending_drafts[draft_id]
            await query.edit_message_text(
                f"DISCARDED — {draft['type'].replace('_', ' ').title()}\n\n"
                "(Draft rejected and deleted.)"
            )
            self.mira.sqlite.log_action(
                "pa", f"draft_rejected:{draft['type']}", "discarded"
            )

    async def _execute_draft(self, draft: dict) -> str:
        """Send/post a draft after user approval. Returns outcome string."""
        draft_type = draft["type"]
        metadata = draft["metadata"]

        if draft_type == "email_reply" and hasattr(self.mira, "pa"):
            # Delegate to PA module for Gmail send
            try:
                await self.mira.pa.send_reply(
                    thread_id=metadata.get("thread_id"),
                    to=metadata.get("to"),
                    subject=metadata.get("subject"),
                    body=draft["text"],
                )
                return "Email sent via Gmail."
            except Exception as e:
                logger.error(f"Failed to send email draft: {e}")
                return f"Failed to send: {e}"

        if draft_type == "social_post" and hasattr(self.mira, "social"):
            platform = metadata.get("platform", "unknown")
            return f"Queued for {platform}. (Social posting in Phase 8)"

        return "Draft accepted. Execution handler not yet implemented for this type."

    # ══════════════════════════════════════════════════════════════════
    # PHOTO HANDLER
    # ══════════════════════════════════════════════════════════════════

    async def _handle_photo_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photos sent to Mira — OCR + ingest to memory."""
        caption = update.message.caption or ""
        logger.info(f"Photo received with caption: {caption[:80]}")

        # Download the highest-resolution photo
        photo = update.message.photo[-1]  # largest size
        file = await photo.get_file()

        tmp_path = None
        try:
            tmp_path = os.path.join(tempfile.gettempdir(), f"mira_photo_{photo.file_id}.jpg")
            await file.download_to_drive(tmp_path)

            # Process through ingestion (OCR + memory)
            if hasattr(self.mira, "ingest"):
                await update.message.reply_text("Processing image...")
                result = await self.mira.ingest.ingest_image(tmp_path, caption=caption, source="telegram_photo")
                await update.message.reply_text(
                    f"Image processed.\n"
                    f"Text extracted: {len(result.get('text', ''))} chars\n"
                    f"Memory ID: {result.get('memory_id', 'N/A')}"
                )
            else:
                await update.message.reply_text("Image received but ingestion module not available.")
        except Exception as e:
            logger.error(f"Photo processing failed: {e}")
            await update.message.reply_text(f"Failed to process image: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ══════════════════════════════════════════════════════════════════
    # VOICE HANDLER
    # ══════════════════════════════════════════════════════════════════

    async def _handle_voice_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle voice messages — transcribe with Whisper and process."""
        voice = getattr(self.mira, "voice", None)
        if not voice:
            await update.message.reply_text("Voice processing not available (Whisper not loaded).")
            return

        voice_file = update.message.voice or update.message.audio
        if not voice_file:
            return

        tmp_path = None
        try:
            file = await voice_file.get_file()
            tmp_path = os.path.join(tempfile.gettempdir(), f"mira_voice_{voice_file.file_id}.ogg")
            await file.download_to_drive(tmp_path)

            await update.message.reply_text("Transcribing...")
            transcript = await voice.transcribe(tmp_path)

            if not transcript:
                await update.message.reply_text("Could not transcribe the voice message.")
                return

            await update.message.reply_text(f"Heard: {transcript[:500]}")

            # Process the transcript as a regular message
            if not self.mira.paused:
                response = await self.mira.process_message(transcript, source="telegram_voice")
                await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            await update.message.reply_text(f"Voice processing failed: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ══════════════════════════════════════════════════════════════════
    # INTELLIGENCE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_dca(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show DCA position summary across instruments."""
        trading = getattr(self.mira, "trading", None)
        if not trading:
            await update.message.reply_text("Trading module not available.")
            return

        await update.message.reply_text("Checking DCA positions...")
        positions = await trading.check_dca_positions()

        if not positions:
            await update.message.reply_text("No DCA positions found. Log trades with strategy='dca' to track them.")
            return

        msg = f"DCA Positions ({len(positions)} instruments)\n\n"
        for p in positions:
            msg += (
                f"  {p['instrument']} ({p['platform']})\n"
                f"    Buys: {p['buy_count']} | Size: {p['total_size']}\n"
                f"    Avg Entry: ${p['avg_entry_price']}\n"
                f"    Realized P&L: ${p['realized_pnl']}\n\n"
            )
        await update.message.reply_text(msg[:4000])

    async def _cmd_compliance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check compliance deadlines. Usage: /compliance or /compliance add [name] [date] [jurisdiction]"""
        args = context.args or []

        if args and args[0] == "add":
            # /compliance add Payroll Filing 2026-04-15 PH
            if len(args) < 3:
                await update.message.reply_text(
                    "Usage: /compliance add [name] [YYYY-MM-DD] [jurisdiction]\n"
                    "Example: /compliance add Payroll Filing 2026-04-15 PH"
                )
                return

            # Parse: last arg is jurisdiction, second-to-last is date, rest is name
            jurisdiction = args[-1] if len(args) >= 4 else ""
            due_date = args[-2] if len(args) >= 4 else args[-1]
            name = " ".join(args[1:-2]) if len(args) >= 4 else " ".join(args[1:-1])

            import json
            raw = self.mira.sqlite.get_preference("compliance_deadlines")
            deadlines = json.loads(raw) if raw else []
            deadlines.append({
                "name": name,
                "due_date": due_date,
                "jurisdiction": jurisdiction,
                "category": "compliance",
            })
            self.mira.sqlite.set_preference("compliance_deadlines", json.dumps(deadlines))
            await update.message.reply_text(f"Added deadline: {name} (due {due_date}, {jurisdiction})")
            return

        pa = getattr(self.mira, "pa", None)
        if not pa:
            await update.message.reply_text("PA module not available.")
            return

        await update.message.reply_text("Checking compliance deadlines...")
        alerts = await pa.check_compliance_deadlines()

        if not alerts:
            await update.message.reply_text("No compliance deadlines flagged. Use /compliance add to track one.")
            return

        msg = f"Compliance Deadlines ({len(alerts)} flagged)\n\n"
        for a in alerts:
            days = a["days_until"]
            icon = "!!!" if a["alert_level"] == "critical" else "!!" if a["alert_level"] == "high" else "!"
            label = "OVERDUE" if days < 0 else f"in {days}d"
            msg += f"  {icon} {a['name']} — {label}"
            if a.get("jurisdiction"):
                msg += f" [{a['jurisdiction']}]"
            msg += f"\n    Due: {a['due_date']}\n\n"
        await update.message.reply_text(msg[:4000])

    async def _cmd_competitive(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Run competitive intelligence scan."""
        personal = getattr(self.mira, "personal", None)
        if not personal:
            await update.message.reply_text("Personal module not available.")
            return

        await update.message.reply_text("Running competitive intelligence scan... (this may take a moment)")
        report = await personal.run_competitive_intelligence()
        await update.message.reply_text(f"Competitive Intelligence\n\n{report[:3800]}")

    async def _cmd_subscriptions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Audit active subscriptions from memory."""
        personal = getattr(self.mira, "personal", None)
        if not personal:
            await update.message.reply_text("Personal module not available.")
            return

        await update.message.reply_text("Scanning memories for subscriptions...")
        result = await personal.audit_subscriptions()
        await update.message.reply_text(f"Subscription Audit\n\n{result[:3800]}")

    async def _cmd_pnl(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show monthly personal P&L."""
        personal = getattr(self.mira, "personal", None)
        if not personal:
            await update.message.reply_text("Personal module not available.")
            return

        await update.message.reply_text("Generating monthly P&L...")
        report = await personal.generate_monthly_pnl()
        await update.message.reply_text(f"Monthly P&L\n\n{report[:3800]}")

    # ══════════════════════════════════════════════════════════════════
    # MESSAGE HANDLER
    # ══════════════════════════════════════════════════════════════════

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages — Mira's conversational interface."""
        user_message = update.message.text
        logger.info(f"Message received: {user_message[:100]}")

        if not self.chat_id:
            self.chat_id = str(update.effective_chat.id)

        # Check if the user is sending an edited draft
        for draft_id, draft in list(self.pending_drafts.items()):
            if draft.get("awaiting_edit"):
                draft["text"] = user_message
                draft["awaiting_edit"] = False
                # Re-send for approval with updated text
                await self.send_draft_for_approval(
                    draft_text=user_message,
                    draft_type=draft["type"],
                    metadata=draft["metadata"],
                )
                del self.pending_drafts[draft_id]
                return

        if self.mira.paused:
            await update.message.reply_text(
                "I'm in listen-only mode (kill switch active). "
                "I can hear you but won't take autonomous actions. "
                "Use /resume to restore full operation."
            )
            return

        # Process through brain + memory
        await update.message.reply_text("Thinking...")
        response = await self.mira.process_message(user_message, source="telegram")
        await update.message.reply_text(response)
