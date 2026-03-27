"""
Mira Telegram Bot — primary interface for commands, notifications, and communication.
Full command set from the MVP spec.
"""

import logging
import os
import tempfile
from datetime import datetime

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

        # ── Finance Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("budget", self._cmd_budget))
        self.app.add_handler(CommandHandler("networth", self._cmd_networth))

        # ── Research Commands ────────────────────────────────────────
        self.app.add_handler(CommandHandler("research", self._cmd_research))

        # ── Capture Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("pause_listen", self._cmd_pause_listen))

        # ── Earning Commands ─────────────────────────────────────────
        self.app.add_handler(CommandHandler("earn", self._cmd_earn))

        # ── Cost Tracking ───────────────────────────────────────────────
        self.app.add_handler(CommandHandler("cost", self._cmd_cost))

        # ── Learning Commands ────────────────────────────────────────────
        self.app.add_handler(CommandHandler("learn", self._cmd_learn))
        self.app.add_handler(CommandHandler("review", self._cmd_review))

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
            "SOCIAL\n"
            "/post [platform] [content] — Draft and queue a post\n\n"
            "FINANCE\n"
            "/budget — This month's personal P&L\n"
            "/networth — Current net worth snapshot\n\n"
            "RESEARCH\n"
            "/research [topic] — Run deep research\n\n"
            "CAPTURE\n"
            "/pause_listen — Pause audio capture for 30 min\n\n"
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
            "/cost — API cost breakdown (today/week/month)"
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

        briefing_data = {
            "date": datetime.now().strftime("%A, %B %d, %Y"),
            "time": datetime.now().strftime("%H:%M"),
            "pending_tasks": self.mira.sqlite.get_pending_tasks(),
            "open_trades": self.mira.sqlite.get_open_trades(),
            "recent_memories": self.mira.sqlite.get_recent_memories(5),
            "actions_today": self.mira.sqlite.get_daily_actions(),
        }

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
        await update.message.reply_text("Close all positions — requires computer use (Phase 7).")

    async def _cmd_pause_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.mira.sqlite.set_preference("trading_paused", "true", confidence=1.0, source="command")
        self.mira.sqlite.log_action("trading", "pause_trading", "paused")
        await update.message.reply_text("Trading execution paused. EAs still monitored.")

    async def _cmd_resume_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.mira.sqlite.set_preference("trading_paused", "false", confidence=1.0, source="command")
        self.mira.sqlite.log_action("trading", "resume_trading", "resumed")
        await update.message.reply_text("Trading execution resumed.")

    async def _cmd_daily_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Trading report generation coming in Phase 7.")

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
        await update.message.reply_text("Crypto portfolio view coming in Phase 7 (DalyKraken integration).")

    # ══════════════════════════════════════════════════════════════════
    # SOCIAL COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if len(context.args) < 2:
            await update.message.reply_text("Usage: /post [platform] [content]\nPlatforms: x, linkedin, instagram, tiktok, youtube, facebook")
            return
        platform = context.args[0]
        content = " ".join(context.args[1:])
        await update.message.reply_text(f"Social posting coming in Phase 8.\nQueued for {platform}: {content[:100]}...")

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
    # CAPTURE COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_pause_listen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Audio capture paused for 30 minutes. (Phase 4)")

    # ══════════════════════════════════════════════════════════════════
    # EARNING COMMANDS
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_earn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Earning Modules Status:\n\n"
            "Polymarket Alpha: Phase 7 (pending)\n"
            "Digital Product Store: Phase 8 (pending)\n"
            "Freelance Agent: Phase 8 (pending)\n"
            "Content Monetisation: Phase 9 (pending)\n"
            "Consulting Pipeline: Phase 9 (pending)\n"
            "Newsletter: Phase 11 (pending)"
        )

    # ══════════════════════════════════════════════════════════════════
    # COST TRACKING
    # ══════════════════════════════════════════════════════════════════

    async def _cmd_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show API cost breakdown."""
        period = context.args[0] if context.args else "today"
        if period not in ("today", "week", "month", "all"):
            period = "today"

        costs = self.mira.sqlite.get_api_costs(period)

        msg = f"API Costs ({period})\n\n"
        msg += f"Total: ${costs['total_cost']:.4f} ({costs['total_calls']} calls)\n\n"

        if costs["by_tier"]:
            msg += "By Tier:\n"
            for t in costs["by_tier"]:
                msg += f"  {t['tier']}: ${t['cost']:.4f} ({t['calls']} calls, {t['input_tok']}in/{t['output_tok']}out)\n"
            msg += "\n"

        if costs["by_task"]:
            msg += "By Task:\n"
            for t in costs["by_task"]:
                msg += f"  {t['task_type']}: ${t['cost']:.4f} ({t['calls']}x)\n"

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
