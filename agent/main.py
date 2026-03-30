"""
Mira — Autonomous Digital Twin
Core agent loop: Listen → Plan → Execute → Log → Notify → Learn → Sleep → Repeat
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, time
from pathlib import Path

from config import Config
from brain import MiraBrain
from telegram_bot import MiraTelegramBot
from helpers.backup import create_backup
from memory.sqlite_store import SQLiteStore
from memory.vector_store import VectorStore
from memory.knowledge_graph import KnowledgeGraph
from capture.ingest import IngestionPipeline
from scheduler import Scheduler, ScheduledTask
from modules.pa import PAModule
from modules.trading import TradingModule
from modules.social import SocialModule
from modules.earning import EarningModule
from modules.personal import PersonalModule
from modules.patterns import PatternEngine

# Optional modules — imported with try/except so missing files don't break startup
try:
    from modules.learning import LearningAccelerator
except ImportError:
    LearningAccelerator = None
    logging.getLogger("mira").warning("LearningAccelerator module not found — skipping.")

try:
    from modules.negotiation import NegotiationCoach
except ImportError:
    NegotiationCoach = None
    logging.getLogger("mira").warning("NegotiationCoach module not found — skipping.")

try:
    from modules.affiliate import AffiliateTracker
except ImportError:
    AffiliateTracker = None
    logging.getLogger("mira").warning("AffiliateTracker module not found — skipping.")

try:
    from orchestrator import Orchestrator
except ImportError:
    Orchestrator = None
    logging.getLogger("mira").warning("Orchestrator module not found — skipping.")

try:
    from computer_use.agent import ComputerUseAgent
except ImportError:
    ComputerUseAgent = None
    logging.getLogger("mira").warning("ComputerUseAgent module not found — skipping.")

try:
    from helpers.voice import VoiceInterface
except ImportError:
    VoiceInterface = None
    logging.getLogger("mira").warning("VoiceInterface not found — skipping.")

# Ensure data directories exist
Config.ensure_dirs()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_DIR / "mira.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("mira")


class Mira:
    """Core Mira agent — the main loop that orchestrates everything."""

    KILL_SWITCH_STATE_FILE = Config.DATA_DIR / "kill_switch.state"

    def __init__(self):
        self.running = False
        self.paused = False  # Kill switch state
        self.start_time = None
        self.unacknowledged_notifications = {}  # id → {message, sent_at, module, escalation_count}
        self._notification_counter = 0

        # Core systems
        self.brain = MiraBrain(sqlite_store=None)
        self.sqlite = SQLiteStore(Config.MEMORY_DB_PATH)
        self.vector = VectorStore(Config.CHROMA_DIR)
        self.graph = KnowledgeGraph(Config.KNOWLEDGE_GRAPH_PATH)
        self.ingest = IngestionPipeline(self.brain, self.sqlite, self.vector, self.graph)
        self.telegram = MiraTelegramBot(self)
        self.scheduler = Scheduler()

        # Modules
        self.pa = PAModule(self)
        self.trading = TradingModule(self)
        self.social = SocialModule(self)
        self.earning = EarningModule(self)
        self.personal = PersonalModule(self)
        self.patterns = PatternEngine(self)

        # Optional modules (graceful if not yet built)
        self.learning = LearningAccelerator(self) if LearningAccelerator else None
        self.negotiation = NegotiationCoach(self) if NegotiationCoach else None
        self.affiliate = AffiliateTracker(self) if AffiliateTracker else None
        self.orchestrator = Orchestrator(self) if Orchestrator else None
        self.computer_use = ComputerUseAgent(self) if ComputerUseAgent else None

        # Voice interface
        self.voice = VoiceInterface() if VoiceInterface else None
        if self.voice:
            self.voice.set_mira(self)

        logger.info("Mira initialised.")

    async def start(self):
        """Start the core agent loop."""
        self.running = True
        self.start_time = datetime.now()
        logger.info("Mira is starting up...")

        # Validate config
        issues = Config.validate()
        if issues:
            for issue in issues:
                logger.warning(f"Config issue: {issue}")

        # Initialise core systems
        self.sqlite.initialise()
        self.vector.initialise()
        self.graph.initialise()
        self.brain.sqlite = self.sqlite
        brain_ok = self.brain.initialise()

        if brain_ok:
            logger.info("Brain online — Claude API connected.")
        else:
            logger.warning("Brain offline — will echo messages without AI processing.")

        # Restore kill switch state from previous session
        if self.KILL_SWITCH_STATE_FILE.exists():
            self.paused = True
            logger.warning("Kill switch state restored from previous session — Mira is PAUSED.")
            self.sqlite.log_action("safety", "kill_switch_restored", "paused_from_previous_session")

        # Initialise modules
        await self.pa.initialise()
        await self.trading.initialise()
        await self.social.initialise()
        await self.earning.initialise()
        await self.personal.initialise()

        # Initialise optional modules
        if self.learning:
            try:
                await self.learning.initialise()
                logger.info("LearningAccelerator initialised.")
            except Exception as e:
                logger.warning(f"LearningAccelerator init failed: {e}")

        if self.negotiation and hasattr(self.negotiation, "initialise"):
            try:
                await self.negotiation.initialise()
                logger.info("NegotiationCoach initialised.")
            except Exception as e:
                logger.warning(f"NegotiationCoach init failed: {e}")

        if self.affiliate:
            try:
                await self.affiliate.initialise()
                logger.info("AffiliateTracker initialised.")
            except Exception as e:
                logger.warning(f"AffiliateTracker init failed: {e}")

        if self.computer_use and hasattr(self.computer_use, "initialise"):
            try:
                self.computer_use.initialise()
                logger.info("ComputerUseAgent initialised.")
            except Exception as e:
                logger.warning(f"ComputerUseAgent init failed: {e}")

        # Register scheduled tasks
        self._register_scheduled_tasks()

        # Start Telegram bot
        await self.telegram.start()

        # Log startup
        self.sqlite.log_action(
            module="core",
            action="startup",
            outcome="success",
            details={"config_issues": issues, "brain_online": brain_ok},
        )

        logger.info("Mira is online.")

        # Send startup notification
        try:
            stats = self.sqlite.get_stats()
            scheduled = len(self.scheduler.tasks)
            await self.telegram.send(
                f"Mira is online.\n"
                f"Brain: {'connected' if brain_ok else 'offline'}\n"
                f"Memory: {stats.get('memories', 0)} memories, "
                f"{stats.get('people', 0)} people, "
                f"{self.graph.graph.number_of_nodes()} graph nodes\n"
                f"Scheduled tasks: {scheduled}\n"
                f"Config issues: {len(issues)}"
            )
        except Exception:
            pass

        # Core loop
        try:
            while self.running:
                if not self.paused:
                    await self._tick()
                await asyncio.sleep(Config.TICK_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Mira shutting down gracefully.")
        finally:
            await self.shutdown()

    def _register_scheduled_tasks(self):
        """Register all recurring tasks."""
        # Parse briefing time from config
        try:
            h, m = Config.BRIEFING_TIME.split(":")
            briefing_time = time(int(h), int(m))
        except ValueError:
            briefing_time = time(7, 0)

        # Daily morning briefing
        self.scheduler.add(ScheduledTask(
            name="daily_briefing",
            callback=self._task_daily_briefing,
            schedule_type="daily",
            run_at=briefing_time,
        ))

        # EA health check every 15 minutes
        self.scheduler.add(ScheduledTask(
            name="ea_health_check",
            callback=self._task_ea_health,
            schedule_type="interval",
            interval_seconds=900,
        ))

        # Daily action log at 10pm
        self.scheduler.add(ScheduledTask(
            name="daily_action_log",
            callback=self._task_daily_action_log,
            schedule_type="daily",
            run_at=time(22, 0),
        ))

        # Portfolio snapshot at 8am
        self.scheduler.add(ScheduledTask(
            name="portfolio_snapshot",
            callback=self._task_portfolio_snapshot,
            schedule_type="daily",
            run_at=time(8, 0),
        ))

        # Weekly review on Sundays at 7pm
        self.scheduler.add(ScheduledTask(
            name="weekly_review",
            callback=self._task_weekly_review,
            schedule_type="weekly",
            run_at=time(19, 0),
            days=[6],  # Sunday
        ))

        # Weekly calendar review on Sundays at 6pm
        self.scheduler.add(ScheduledTask(
            name="weekly_calendar_review",
            callback=self._task_calendar_review,
            schedule_type="weekly",
            run_at=time(18, 0),
            days=[6],
        ))

        # Weekly email digest on Sundays at 6pm (alongside calendar review)
        self.scheduler.add(ScheduledTask(
            name="weekly_email_digest",
            callback=self._task_weekly_email_digest,
            schedule_type="weekly",
            run_at=time(18, 0),
            days=[6],  # Sunday
        ))

        # Social media queue processor every 15 minutes
        self.scheduler.add(ScheduledTask(
            name="social_queue_processor",
            callback=self._task_social_queue,
            schedule_type="interval",
            interval_seconds=900,
        ))

        # EOW summary on Fridays at 4pm
        self.scheduler.add(ScheduledTask(
            name="eow_summary",
            callback=self._task_eow_summary,
            schedule_type="weekly",
            run_at=time(16, 0),
            days=[4],  # Friday
        ))

        # Net worth update on Mondays at 8am
        self.scheduler.add(ScheduledTask(
            name="net_worth_update",
            callback=self._task_net_worth,
            schedule_type="weekly",
            run_at=time(8, 0),
            days=[0],  # Monday
        ))

        # Daily backup at 2am
        self.scheduler.add(ScheduledTask(
            name="daily_backup",
            callback=self._task_daily_backup,
            schedule_type="daily",
            run_at=time(2, 0),
        ))

        # Learning review prompts 3x daily (9am, 2pm, 8pm)
        if self.learning:
            for label, hour in [("morning", 9), ("afternoon", 14), ("evening", 20)]:
                self.scheduler.add(ScheduledTask(
                    name=f"learning_review_{label}",
                    callback=self._task_learning_review,
                    schedule_type="daily",
                    run_at=time(hour, 0),
                ))

        # Deadline warnings daily at 8:30am (legal module may not exist yet)
        self.scheduler.add(ScheduledTask(
            name="deadline_warnings",
            callback=self._task_deadline_warnings,
            schedule_type="daily",
            run_at=time(8, 30),
        ))

        # Post-meeting action prompts every 15 minutes
        self.scheduler.add(ScheduledTask(
            name="post_meeting_actions",
            callback=self._task_post_meeting_actions,
            schedule_type="interval",
            interval_seconds=900,
        ))

        # Habit check — gentle nudge at 12pm and 8pm
        for label, hour in [("midday", 12), ("evening", 20)]:
            self.scheduler.add(ScheduledTask(
                name=f"habit_check_{label}",
                callback=self._task_habit_check,
                schedule_type="daily",
                run_at=time(hour, 0),
            ))

        # Presence check — remind to take a break if working too long (every 2 hours)
        self.scheduler.add(ScheduledTask(
            name="presence_check",
            callback=self._task_presence_check,
            schedule_type="interval",
            interval_seconds=7200,
        ))

        # Monthly learning report — 1st of each month at 9am
        self.scheduler.add(ScheduledTask(
            name="monthly_learning_report",
            callback=self._task_monthly_learning_report,
            schedule_type="daily",
            run_at=time(9, 0),
        ))

        # Important dates check — daily at 8:15am
        self.scheduler.add(ScheduledTask(
            name="important_dates_check",
            callback=self._task_important_dates,
            schedule_type="daily",
            run_at=time(8, 15),
        ))

        # Relationship health check — Wednesdays at 10am
        self.scheduler.add(ScheduledTask(
            name="relationship_health",
            callback=self._task_relationship_health,
            schedule_type="weekly",
            run_at=time(10, 0),
            days=[2],  # Wednesday
        ))

        # Email check every 30 minutes
        self.scheduler.add(ScheduledTask(
            name="email_check",
            callback=self._task_email_check,
            schedule_type="interval",
            interval_seconds=1800,
        ))

        logger.info(f"Registered {len(self.scheduler.tasks)} scheduled tasks")

    # ── Scheduled Task Callbacks ─────────────────────────────────────

    async def _task_daily_briefing(self):
        briefing = await self.pa.generate_daily_briefing()
        await self.telegram.send(briefing)
        self.sqlite.log_action("pa", "daily_briefing", "delivered")

    async def _task_ea_health(self):
        await self.trading.check_ea_health()

    async def _task_daily_action_log(self):
        actions = self.sqlite.get_daily_actions()
        if actions:
            summary = f"Daily Action Log — {len(actions)} actions today\n\n"
            for a in actions:
                t = a.get("created_at", "")
                if "T" in str(t):
                    t = str(t).split("T")[1][:5]
                summary += f"  {t} [{a['module']}] {a['action']}\n"
            await self.telegram.send(summary)

    async def _task_portfolio_snapshot(self):
        snapshot = await self.trading.get_portfolio_snapshot()
        self.sqlite.log_action("trading", "portfolio_snapshot", "captured")

    async def _task_weekly_review(self):
        review = await self.patterns.generate_weekly_review()
        await self.telegram.send(f"Weekly Review\n\n{review}")
        self.sqlite.log_action("patterns", "weekly_review", "delivered")

    async def _task_calendar_review(self):
        try:
            review = await self.pa.generate_weekly_calendar_review()
            await self.telegram.send(f"Weekly Calendar Review\n\n{review}")
            self.sqlite.log_action("pa", "calendar_review", "delivered")
        except Exception as e:
            logger.error(f"Calendar review failed: {e}")
            self.sqlite.log_action("pa", "calendar_review", f"failed: {e}")

    async def _task_weekly_email_digest(self):
        digest = await self.pa.generate_weekly_email_digest()
        await self.telegram.send(f"Weekly Email Digest\n\n{digest}")
        self.sqlite.log_action("pa", "weekly_email_digest", "delivered")

    async def _task_social_queue(self):
        await self.social.process_queue()

    async def _task_eow_summary(self):
        summary = await self.pa.generate_eow_summary()
        await self.telegram.send(f"EOW Summary Draft\n\n{summary}")
        self.sqlite.log_action("pa", "eow_summary", "drafted")

    async def _task_net_worth(self):
        update = await self.personal.generate_net_worth_update()
        await self.telegram.send(f"Monday Net Worth Update\n\n{update}")
        self.sqlite.log_action("personal", "net_worth_update", "delivered")

    async def _task_daily_backup(self):
        """Run daily backup of memory databases."""
        backup_dir = Config.DATA_DIR / "backups"
        try:
            result = create_backup(
                data_dir=Config.DATA_DIR,
                backup_dir=backup_dir,
                encrypt=Config.ENCRYPT_AT_REST,
                encryption_key_path=Config.ENCRYPTION_KEY_PATH,
            )
            self.sqlite.log_action(
                "core",
                "daily_backup",
                "success",
                {"path": result["backup_path"], "size_bytes": result["size_bytes"],
                 "files_copied": result["files_copied"]},
            )
            await self.telegram.send(
                f"Daily backup complete.\n"
                f"Files: {result['files_copied']}, Size: {result['size_bytes'] / 1024:.1f} KB"
            )
        except Exception as e:
            logger.error(f"Daily backup failed: {e}")
            self.sqlite.log_action("core", "daily_backup", f"failed: {e}")

    async def _task_learning_review(self):
        """Send spaced-repetition review prompts via Telegram."""
        if self.learning:
            try:
                await self.learning.send_review_prompts()
            except Exception as e:
                logger.error(f"Learning review failed: {e}")

    async def _task_deadline_warnings(self):
        """Check for upcoming legal/contract deadlines."""
        try:
            legal = getattr(self, "legal", None)
            if legal and hasattr(legal, "check_deadline_warnings"):
                warnings = await legal.check_deadline_warnings()
                if warnings:
                    await self.telegram.send(f"Deadline Warnings\n\n{warnings}")
        except Exception as e:
            logger.debug(f"Deadline warning check skipped: {e}")

    async def _task_monthly_learning_report(self):
        """Generate monthly learning report — only on the 1st of each month."""
        if datetime.now().day != 1:
            return
        if not self.learning:
            return
        try:
            report = await self.learning.generate_monthly_report()
            await self.telegram.send(f"Monthly Learning Report\n\n{report}")
            self.sqlite.log_action("learning", "monthly_report", "delivered")
        except Exception as e:
            logger.error(f"Monthly learning report failed: {e}")

    async def _task_important_dates(self):
        """Check for upcoming important dates and send reminders."""
        try:
            upcoming = await self.personal.check_important_dates()
            if upcoming:
                msg = "Upcoming Important Dates\n\n"
                for item in upcoming[:5]:
                    days = item.get("days_until", "?")
                    name = item.get("person_name", "")
                    dtype = item.get("date_type", "").replace("_", " ")
                    label = "TODAY" if days == 0 else f"in {days}d"
                    msg += f"  {name} — {dtype} ({label})\n"
                    if item.get("suggestion"):
                        msg += f"    {item['suggestion']}\n"
                await self.telegram.send(msg)
        except Exception as e:
            logger.debug(f"Important dates check skipped: {e}")

    async def _task_relationship_health(self):
        """Weekly relationship health check — flag contacts needing attention."""
        try:
            flagged = await self.personal.check_relationship_health()
            if flagged:
                msg = f"Relationship Health Check\n\n{len(flagged)} contacts need attention:\n\n"
                for f in flagged[:5]:
                    score = f["health_score"]
                    label = "AT RISK" if score < 30 else "NEEDS ATTENTION"
                    msg += f"[{label}] {f['name']} ({f['relationship_type']})\n"
                    for issue in f["issues"][:2]:
                        msg += f"  - {issue}\n"
                    if f.get("suggestion"):
                        msg += f"  Suggestion: {f['suggestion']}\n"
                    msg += "\n"
                await self.telegram.send(msg[:4000])
        except Exception as e:
            logger.error(f"Relationship health check failed: {e}")

    async def _task_post_meeting_actions(self):
        """Check for recently ended meetings and prompt for action items."""
        try:
            await self.pa.check_post_meeting_actions()
        except Exception as e:
            logger.debug(f"Post-meeting check skipped: {e}")

    async def _task_habit_check(self):
        """Check habits and send gentle nudges for missed ones."""
        try:
            reminders = await self.personal.check_habits()
            if reminders:
                msg = "Habit Check-in\n\n"
                msg += "\n".join(f"- {r}" for r in reminders)
                await self.telegram.send(msg)
                self.sqlite.log_action("personal", "habit_nudge", f"{len(reminders)} reminders sent")
        except Exception as e:
            logger.error(f"Habit check failed: {e}")

    async def _task_presence_check(self):
        """Remind to take a break if actively working for extended periods."""
        try:
            # Check last few hours of actions for continuous activity
            actions = self.sqlite.get_daily_actions()
            if not actions:
                return

            now = datetime.now()
            recent = [a for a in actions if a.get("created_at") and
                      (now - datetime.fromisoformat(str(a["created_at"]))).total_seconds() < 7200]

            if len(recent) >= 8:  # 8+ actions in 2 hours = heavy activity
                await self.telegram.send(
                    "You've been going hard for a while. "
                    "Quick break? Even 5 minutes helps."
                )
                self.sqlite.log_action("personal", "presence_check", "break reminder sent")
        except Exception as e:
            logger.debug(f"Presence check skipped: {e}")

    async def _task_email_check(self):
        """Periodic email check — triage and alert on high-urgency items."""
        try:
            if hasattr(self.pa, "check_email"):
                results = await self.pa.check_email()
                if results:
                    urgent = [e for e in results if isinstance(e, dict) and e.get("urgency", 0) >= 4]
                    if urgent:
                        msg = f"Email Alert — {len(urgent)} urgent\n\n"
                        for e in urgent[:3]:
                            msg += f"  [{e.get('urgency', '?')}] {e.get('subject', 'No subject')[:60]}\n"
                        await self.telegram.send(msg)
                        self.sqlite.log_action("pa", "email_alert", f"{len(urgent)} urgent emails")
        except Exception as e:
            logger.debug(f"Email check skipped: {e}")

    # ── Core Loop ────────────────────────────────────────────────────

    async def _tick(self):
        """Single iteration of the core loop."""
        await self.scheduler.tick()
        await self._check_escalations()
        # Refresh local model status every 60 seconds (12 ticks at 5s interval)
        if not hasattr(self, '_local_check_counter'):
            self._local_check_counter = 0
        self._local_check_counter += 1
        if self._local_check_counter >= 12:
            self._local_check_counter = 0
            try:
                await self.brain.refresh_local_model_status()
            except Exception:
                pass

    async def _check_escalations(self):
        """Re-send unacknowledged notifications after 15 minutes, up to 5 times."""
        now = datetime.now()
        for nid, info in list(self.unacknowledged_notifications.items()):
            elapsed = (now - info["sent_at"]).total_seconds()
            if elapsed >= 900 and info["escalation_count"] < 5:
                info["escalation_count"] += 1
                info["sent_at"] = now
                prefix = f"[ESCALATION #{info['escalation_count']}]"
                try:
                    await self.telegram.send(f"{prefix} {info['message']}")
                except Exception as e:
                    logger.error(f"Failed to send escalation for notification {nid}: {e}")
                if info["escalation_count"] >= 5:
                    logger.warning(f"Max escalations reached for notification {nid}, stopping.")

    def add_notification(self, message: str, module: str = "core") -> str:
        """Add a notification that requires acknowledgement. Returns notification ID."""
        self._notification_counter += 1
        nid = f"n{self._notification_counter}"
        self.unacknowledged_notifications[nid] = {
            "message": message,
            "sent_at": datetime.now(),
            "module": module,
            "escalation_count": 0,
        }
        return nid

    def acknowledge_notification(self, notification_id: str) -> bool:
        """Acknowledge a notification to stop escalation. Returns True if found."""
        if notification_id == "all":
            count = len(self.unacknowledged_notifications)
            self.unacknowledged_notifications.clear()
            logger.info(f"Acknowledged all {count} notifications.")
            return count > 0
        if notification_id in self.unacknowledged_notifications:
            del self.unacknowledged_notifications[notification_id]
            logger.info(f"Acknowledged notification {notification_id}.")
            return True
        return False

    def kill_switch(self):
        """Immediately pause all autonomous actions."""
        self.paused = True
        # Persist kill switch state to survive restarts
        try:
            self.KILL_SWITCH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.KILL_SWITCH_STATE_FILE.write_text(datetime.now().isoformat())
        except Exception as e:
            logger.error(f"Failed to persist kill switch state: {e}")
        self.sqlite.log_action("safety", "kill_switch", "activated")
        logger.warning("KILL SWITCH ACTIVATED — all autonomous actions paused.")
        return "Kill switch activated. Mira is in listen-only mode."

    def resume(self):
        """Resume full autonomous operation."""
        self.paused = False
        # Remove persisted kill switch state
        try:
            if self.KILL_SWITCH_STATE_FILE.exists():
                self.KILL_SWITCH_STATE_FILE.unlink()
        except Exception as e:
            logger.error(f"Failed to remove kill switch state file: {e}")
        self.sqlite.log_action("safety", "resume", "activated")
        logger.info("Autonomous operation resumed.")
        return "Mira is back online. Full capabilities restored."

    def get_status(self) -> str:
        """Get current Mira status."""
        now = datetime.now()
        uptime = now - self.start_time if self.start_time else "Not started"
        mode = "PAUSED (listen-only)" if self.paused else "ACTIVE"
        stats = self.sqlite.get_stats()
        graph_stats = self.graph.get_stats()
        scheduler_status = self.scheduler.get_status()
        costs = self.sqlite.get_api_costs("today")
        daily_actions = self.sqlite.get_daily_actions()

        # Format uptime nicely
        if isinstance(uptime, str):
            uptime_str = uptime
        else:
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes = remainder // 60
            uptime_str = f"{hours}h {minutes}m"

        # Module health check
        modules = {
            "Brain": bool(self.brain and self.brain.client),
            "Memory": bool(self.sqlite),
            "Vector": bool(self.vector),
            "Graph": bool(self.graph),
            "Telegram": bool(self.telegram and self.telegram.app),
            "Computer Use": bool(self.computer_use and self.computer_use.client),
        }
        health = " | ".join(f"{'OK' if v else 'OFF'} {k}" for k, v in modules.items())

        # Last action
        last_action = daily_actions[0] if daily_actions else None
        last_action_str = (
            f"{last_action.get('module', '?')}: {last_action.get('action', '?')[:40]}"
            if last_action else "None today"
        )

        return (
            f"{'PAUSED' if self.paused else 'MIRA ONLINE'}\n"
            f"Uptime: {uptime_str} | Mode: {mode}\n\n"
            f"Modules: {health}\n\n"
            f"Memory:\n"
            f"  {stats.get('memories', 0)} memories | {stats.get('people', 0)} people | "
            f"{stats.get('trades', 0)} trades\n"
            f"  {graph_stats['nodes']} graph nodes | {self.vector.count()} embeddings\n"
            f"  {stats.get('tasks', 0)} tasks | {stats.get('decisions', 0)} decisions\n\n"
            f"Today:\n"
            f"  Actions: {len(daily_actions)}\n"
            f"  API Cost: ${costs['total_cost']:.4f} ({costs['total_calls']} calls)\n"
            f"  Last: {last_action_str}\n\n"
            f"Scheduled: {len(scheduler_status)} tasks\n"
            + "\n".join(
                f"  {s['name']}: runs={s['run_count']}"
                for s in scheduler_status[:10]
            )
        )

    async def process_message(self, text: str, source: str = "telegram") -> str:
        """Process an incoming message — think and respond, store in memory."""
        # ── Intent detection: computer use actions ─────────────────────
        cu_result = await self._try_computer_use_intent(text)
        if cu_result:
            return cu_result

        ingest_result = await self.ingest.ingest_text(text, source=source)
        context = self._build_context(text, ingest_result)
        response = await self.brain.think(text, context=context)

        # Check for learning misconceptions and append correction if found
        if self.learning:
            try:
                correction = await self.learning.check_misconception(text)
                if correction:
                    response += f"\n\n{correction}"
            except Exception as e:
                logger.debug(f"Misconception check skipped: {e}")

        return response

    async def _try_computer_use_intent(self, text: str) -> str | None:
        """Detect if the message is a computer use request and execute it.

        Returns a response string if handled, None if it's a normal message.
        """
        if not self.computer_use or not self.computer_use.client:
            return None
        if self.paused:
            return None

        lower = text.lower().strip()

        # ── Screenshot requests ────────────────────────────────────────
        # "send me a screenshot" = just capture + send (FREE, no AI tokens)
        # "what's on the screen" = capture + send + AI analysis (costs tokens)
        screenshot_triggers = [
            "screenshot", "screen shot", "send me a screenshot",
            "capture the screen", "take a screenshot",
            "show me your screen", "show the screen", "show screen",
            "send me the screen", "grab the screen", "show me the screen",
            "send me a screenshot of", "screenshot of the",
            "send a screenshot", "take a screen", "screen capture",
            "print screen", "snap the screen", "screen grab",
            "show me what's on", "show me whats on",
        ]
        # These ask a question ABOUT the screen — needs Claude Vision ($)
        analysis_triggers = [
            "what's on the screen", "what's on screen",
            "whats on the screen", "what do you see",
            "what can you see on the screen", "what is on the screen",
            "describe the screen", "read the screen",
            "what's happening on the screen", "whats happening on screen",
            "what is happening on", "what are you looking at",
            "what's open right now", "what windows are open",
        ]

        needs_analysis = any(trigger in lower for trigger in analysis_triggers)
        needs_screenshot = needs_analysis or any(trigger in lower for trigger in screenshot_triggers)

        if needs_screenshot:
            path = await self.computer_use.screenshot_to_file()
            if path and self.telegram:
                import os
                try:
                    with open(path, "rb") as photo:
                        await self.telegram.app.bot.send_photo(
                            chat_id=self.telegram.chat_id, photo=photo,
                            caption="Here's what's on the screen right now."
                        )

                    # Only burn tokens on analysis if the user asked a question
                    if needs_analysis:
                        analysis = await self.computer_use.analyse_screen(
                            task="Briefly describe what's visible on screen."
                        )
                        return f"Screenshot sent.\n\n{analysis[:500]}"

                    # Plain screenshot = zero tokens
                    return "Screenshot sent."
                except Exception as e:
                    logger.error(f"Screenshot send failed: {e}")
                    return f"Captured the screen but failed to send: {e}"
                finally:
                    if os.path.exists(path):
                        os.remove(path)
            return "Failed to capture screenshot."

        # ── Simple open-app requests (e.g. "open chrome") ────────────
        open_patterns = [
            "open ", "launch ", "start ", "run ",
        ]
        for pattern in open_patterns:
            if lower.startswith(pattern):
                app_name = text[len(pattern):].strip()
                # Simple app name (<50 chars, no "and"/"then" = just open it)
                if app_name and len(app_name) < 50 and " and " not in app_name.lower():
                    from computer_use.actions import ComputerActions
                    import asyncio as _aio
                    actions = ComputerActions(self.computer_use)
                    try:
                        result = await actions.open_application(app_name)
                        self.sqlite.log_action("computer_use", f"open: {app_name}", "success")
                        # Wait for app to load, then send confirmation screenshot
                        await _aio.sleep(2.0)
                        path = await self.computer_use.screenshot_to_file()
                        if path and self.telegram:
                            import os
                            try:
                                with open(path, "rb") as photo:
                                    await self.telegram.app.bot.send_photo(
                                        chat_id=self.telegram.chat_id, photo=photo,
                                        caption=f"Opened {app_name}."
                                    )
                                return f"Opened {app_name}."
                            finally:
                                if os.path.exists(path):
                                    os.remove(path)
                        return f"Opened {app_name}."
                    except Exception as e:
                        return f"Failed to open {app_name}: {e}"
                # Complex request starting with "open" (e.g. "open MT5 and install the EA")
                # Falls through to AI-driven execution below

        # ── AI-driven computer use (multi-step tasks) ─────────────────
        # Triggers at START of message (direct commands)
        action_start_triggers = [
            "click ", "type ", "close ", "minimize ", "go to ",
            "navigate to ", "search for ", "find the ",
            "switch to ", "drag ", "scroll ",
        ]
        # Triggers ANYWHERE in message (implied computer actions)
        action_contains_triggers = [
            "open ", "launch ", "install ", "download ",
            "on the desktop", "on the screen", "on my computer",
            "on the computer", "on my pc", "on my laptop",
            "on my device", "on the windows", "on this machine",
            "in metatrader", "in mt5", "in mt4", "in chrome",
            "in the browser", "in excel", "in word",
            "right click", "right-click", "double click", "double-click",
            "copy and paste", "drag and drop",
            "press ", "hit ", "ctrl+", "alt+",
        ]

        is_computer_task = (
            any(lower.startswith(t) for t in action_start_triggers)
            or any(t in lower for t in action_contains_triggers)
        )

        if is_computer_task:
            return await self._execute_computer_task(text)

        # ── Fallback: AI classification for ambiguous requests ────────
        # If the message sounds like it wants Mira to DO something on the
        # desktop but didn't match any keywords, use a fast Haiku call to
        # classify it. This catches natural language like "can you check
        # what's happening in MT5" or "go to polymarket and find good bets".
        action_verbs = [
            "check", "look", "see", "show", "get", "grab",
            "put", "move", "set", "change", "update", "fix",
            "write", "read", "send", "save", "delete", "create",
            "install", "uninstall", "configure", "setup",
        ]
        has_action_verb = any(v in lower.split() for v in action_verbs)
        # Only classify if it has an action verb AND is short enough to be a command
        if has_action_verb and len(text.split()) <= 25:
            try:
                classification = await self.brain.think(
                    f"Does this message ask me to perform a physical action on a Windows desktop "
                    f"(click, type, open app, navigate, take screenshot, run command, etc.)? "
                    f"Message: \"{text}\"\n\n"
                    f"Reply with ONLY 'YES' or 'NO'.",
                    tier="fast",
                )
                if classification and classification.strip().upper().startswith("YES"):
                    return await self._execute_computer_task(text)
            except Exception:
                pass  # Classification failed — let it fall through to normal chat

        return None

    async def _execute_computer_task(self, text: str) -> str:
        """Execute a multi-step AI-driven computer use task."""
        try:
            # Notify user we're working on it
            if self.telegram:
                try:
                    await self.telegram.app.bot.send_message(
                        chat_id=self.telegram.chat_id,
                        text="On it. Executing now..."
                    )
                except Exception:
                    pass

            result = await self.computer_use.execute_task(text, max_steps=15)
            status = result.get("status", "unknown")
            summary = ""
            for step in reversed(result.get("steps", [])):
                if step.get("summary"):
                    summary = step["summary"][:500]
                    break

            # Send final screenshot showing what happened
            path = await self.computer_use.screenshot_to_file()
            if path and self.telegram:
                import os
                try:
                    caption = f"Done. {summary[:200]}" if summary else "Task executed."
                    if status != "completed":
                        caption = f"Stopped after {result.get('steps_taken', '?')} steps. {summary[:150]}"
                    with open(path, "rb") as photo:
                        await self.telegram.app.bot.send_photo(
                            chat_id=self.telegram.chat_id, photo=photo,
                            caption=caption
                        )
                finally:
                    if os.path.exists(path):
                        os.remove(path)

            msg = f"Status: {status}"
            if summary:
                msg += f"\n{summary}"
            return msg
        except Exception as e:
            logger.error(f"Computer task failed: {e}")
            return f"Task failed: {e}"

    def _build_context(self, message: str, ingest_result: dict) -> str:
        """Build context from memory for the brain to use."""
        parts = []

        recent = self.sqlite.get_recent_memories(5)
        if recent:
            parts.append("Recent memories:\n" + "\n".join(
                f"- [{m['category']}] {m['content'][:100]}" for m in recent
            ))

        related = self.vector.search(message, n_results=3)
        if related:
            parts.append("Related past context:\n" + "\n".join(
                f"- {m['content'][:100]}" for m in related
            ))

        tasks = self.sqlite.get_pending_tasks()
        if tasks:
            parts.append(f"Pending tasks ({len(tasks)}):\n" + "\n".join(
                f"- [{t['priority']}] {t['title']}" for t in tasks[:5]
            ))

        trades = self.sqlite.get_open_trades()
        if trades:
            parts.append(f"Open trades ({len(trades)}):\n" + "\n".join(
                f"- {t['instrument']} {t['direction']} @ {t['entry_price']}" for t in trades
            ))

        return "\n\n".join(parts) if parts else ""

    async def recall(self, query: str) -> str:
        """Search the second brain by meaning."""
        semantic_results = self.vector.search(query, n_results=5)
        keyword_results = self.sqlite.search_memories(query=query, limit=5)
        graph_nodes = self.graph.find_nodes(label_contains=query)

        parts = []

        if semantic_results:
            parts.append("By meaning:\n" + "\n".join(
                f"- {r['content'][:150]}" for r in semantic_results
            ))

        if keyword_results:
            parts.append("By keyword:\n" + "\n".join(
                f"- [{r['category']}] {r['content'][:150]}" for r in keyword_results
            ))

        if graph_nodes:
            parts.append("Connected concepts:\n" + "\n".join(
                f"- [{n.get('node_type', '?')}] {n.get('label', '?')}" for n in graph_nodes[:5]
            ))

        if not parts:
            return f"Nothing found in memory for: {query}"

        return f"Recall results for '{query}':\n\n" + "\n\n".join(parts)

    async def shutdown(self):
        """Clean shutdown."""
        logger.info("Mira is shutting down...")
        self.running = False

        # Persist kill switch state if active so it survives restart
        if self.paused:
            try:
                self.KILL_SWITCH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
                self.KILL_SWITCH_STATE_FILE.write_text(datetime.now().isoformat())
            except Exception as e:
                logger.error(f"Failed to persist kill switch state on shutdown: {e}")

        self.sqlite.log_action("core", "shutdown", "clean")

        await self.telegram.stop()
        self.sqlite.close()
        self.graph.close()
        logger.info("Mira offline.")


def main():
    mira = Mira()

    loop = asyncio.new_event_loop()

    def signal_handler():
        mira.running = False

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(mira.start())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
