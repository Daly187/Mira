"""
Task Scheduler — handles recurring tasks like daily briefings, trading checks, etc.
Runs within the core loop and triggers modules at their scheduled times.
"""

import logging
from datetime import datetime, time
from typing import Callable, Optional

logger = logging.getLogger("mira.scheduler")


class ScheduledTask:
    """A single scheduled task."""

    def __init__(
        self,
        name: str,
        callback: Callable,
        schedule_type: str = "interval",
        interval_seconds: int = 300,
        run_at: time = None,
        days: list[int] = None,
        enabled: bool = True,
    ):
        self.name = name
        self.callback = callback
        self.schedule_type = schedule_type  # "interval" or "daily" or "weekly"
        self.interval_seconds = interval_seconds
        self.run_at = run_at  # For daily/weekly tasks
        self.days = days or list(range(7))  # 0=Monday, 6=Sunday
        self.enabled = enabled
        self.last_run = None
        self.run_count = 0
        self.last_error = None

    def should_run(self) -> bool:
        """Check if this task should run now."""
        if not self.enabled:
            return False

        now = datetime.now()

        if self.schedule_type == "interval":
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds()
            return elapsed >= self.interval_seconds

        elif self.schedule_type == "daily":
            if self.run_at is None:
                return False
            if self.last_run and self.last_run.date() == now.date():
                return False  # Already ran today
            current_time = now.time()
            return current_time >= self.run_at

        elif self.schedule_type == "weekly":
            if self.run_at is None:
                return False
            if now.weekday() not in self.days:
                return False
            if self.last_run and self.last_run.date() == now.date():
                return False
            current_time = now.time()
            return current_time >= self.run_at

        return False


class Scheduler:
    """Manages all scheduled tasks."""

    def __init__(self):
        self.tasks: list[ScheduledTask] = []

    def add(self, task: ScheduledTask):
        """Register a scheduled task."""
        self.tasks.append(task)
        logger.info(f"Scheduled task registered: {task.name} ({task.schedule_type})")

    def remove(self, name: str):
        """Remove a task by name."""
        self.tasks = [t for t in self.tasks if t.name != name]

    async def tick(self):
        """Check all tasks and run any that are due. Called from the core loop."""
        for task in self.tasks:
            if task.should_run():
                try:
                    logger.info(f"Running scheduled task: {task.name}")
                    await task.callback()
                    task.last_run = datetime.now()
                    task.run_count += 1
                    task.last_error = None
                except Exception as e:
                    task.last_error = str(e)
                    logger.error(f"Scheduled task {task.name} failed: {e}")

    def get_status(self) -> list[dict]:
        """Get status of all scheduled tasks."""
        return [
            {
                "name": t.name,
                "type": t.schedule_type,
                "enabled": t.enabled,
                "last_run": t.last_run.isoformat() if t.last_run else "never",
                "run_count": t.run_count,
                "last_error": t.last_error,
            }
            for t in self.tasks
        ]
