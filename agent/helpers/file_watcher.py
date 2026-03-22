"""
File Watcher — monitors the agent/ directory for .py file changes and auto-restarts.
Used on the Windows desktop to pick up code changes synced from Mac via Google Drive.

Uses the watchdog library for efficient filesystem event monitoring (no polling).
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger("mira.file_watcher")

# Directories and patterns to ignore
IGNORE_DIRS = {"__pycache__", "data", "logs", ".git", "node_modules", ".venv", "venv"}
IGNORE_EXTENSIONS = {".pyc", ".pyo", ".pyd"}


class _ChangeHandler(FileSystemEventHandler):
    """Watchdog handler that filters events and forwards relevant .py changes."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def _should_ignore(self, path: str) -> bool:
        """Return True if this path should be ignored."""
        p = Path(path)

        # Ignore non-.py files
        if p.suffix not in (".py",):
            return True

        # Ignore compiled Python files
        if p.suffix in IGNORE_EXTENSIONS:
            return True

        # Ignore files inside excluded directories
        parts = p.parts
        for ignore_dir in IGNORE_DIRS:
            if ignore_dir in parts:
                return True

        return False

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if not self._should_ignore(event.src_path):
            self._callback(event)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if not self._should_ignore(event.src_path):
            self._callback(event)


class FileWatcher:
    """
    Watches the agent/ directory for .py file changes using watchdog.
    On change, debounces for a short period then triggers a restart.
    """

    def __init__(self, watch_dir: str | Path, restart_command: str = "python main.py"):
        self.watch_dir = Path(watch_dir).resolve()
        self.restart_command = restart_command
        self._observer: Observer | None = None
        self._process: subprocess.Popen | None = None
        self._debounce_timer: threading.Timer | None = None
        self._debounce_seconds = 2.0
        self._lock = threading.Lock()
        self._running = False
        self._last_changed_files: list[str] = []

    def start(self):
        """Begin watching in a background thread. Non-blocking."""
        if self._running:
            logger.warning("File watcher already running")
            return

        handler = _ChangeHandler(self._on_change)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_dir), recursive=True)
        self._observer.daemon = True
        self._observer.start()
        self._running = True

        file_count = sum(1 for _ in self.watch_dir.rglob("*.py")
                         if not any(d in _.parts for d in IGNORE_DIRS))
        logger.info(
            f"File watcher started — monitoring {file_count} .py files in {self.watch_dir}"
        )

    def stop(self):
        """Stop watching and clean up."""
        self._running = False

        # Cancel any pending debounce timer
        with self._lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        # Stop the observer
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        # Kill managed subprocess if any
        self._kill_process()

        logger.info("File watcher stopped")

    def set_process(self, process: subprocess.Popen):
        """Register the managed subprocess (main.py) so the watcher can restart it."""
        self._process = process

    def _on_change(self, event: FileSystemEvent):
        """Handle a file change event. Debounces rapid successive changes."""
        rel_path = os.path.relpath(event.src_path, self.watch_dir)
        event_type = event.event_type.upper()
        logger.info(f"Change detected: {event_type} {rel_path}")

        with self._lock:
            self._last_changed_files.append(rel_path)

            # Reset the debounce timer — wait for burst of saves to finish
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self._debounce_seconds, self._restart
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _kill_process(self):
        """Terminate the managed subprocess."""
        if self._process is None:
            return
        if self._process.poll() is not None:
            # Already exited
            return

        logger.info(f"Killing process PID {self._process.pid}")
        try:
            # On Windows, terminate() sends TerminateProcess.
            # On Unix, send SIGTERM first, then SIGKILL if it doesn't die.
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Process did not terminate, sending SIGKILL")
                self._process.kill()
                self._process.wait(timeout=3)
        except Exception as e:
            logger.error(f"Error killing process: {e}")

    def _restart(self):
        """Kill the current process and start a new one."""
        with self._lock:
            changed = self._last_changed_files.copy()
            self._last_changed_files.clear()
            self._debounce_timer = None

        logger.info(f"Restarting after {len(changed)} file change(s):")
        for f in changed:
            logger.info(f"  - {f}")

        # Kill current process
        self._kill_process()

        # Start a new process
        try:
            cmd_parts = self.restart_command.split()

            # If the command starts with "python", replace with the current interpreter
            # so we use the correct venv Python on both Windows and Mac.
            if cmd_parts[0] in ("python", "python3"):
                cmd_parts[0] = sys.executable

            logger.info(f"Starting: {' '.join(cmd_parts)}")
            self._process = subprocess.Popen(
                cmd_parts,
                cwd=str(self.watch_dir),
                # Inherit stdin/stdout/stderr so logs are visible
            )
            logger.info(f"Process started with PID {self._process.pid}")
        except Exception as e:
            logger.error(f"Failed to start process: {e}")


# ---------------------------------------------------------------------------
# Standalone usage: python -m helpers.file_watcher
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [FileWatcher] %(message)s",
        datefmt="%H:%M:%S",
    )

    agent_dir = Path(__file__).parent.parent  # agent/
    watcher = FileWatcher(agent_dir, restart_command="python main.py")

    # Start main.py first
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(agent_dir),
    )
    watcher.set_process(proc)
    watcher.start()

    logger.info("Press Ctrl+C to stop")

    try:
        while True:
            # If main.py crashes on its own (not via watcher restart), log it
            if proc.poll() is not None and watcher._process is proc:
                logger.warning(f"main.py exited with code {proc.returncode}")
                break
            # Keep reference in sync
            proc = watcher._process or proc
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted — shutting down")
    finally:
        watcher.stop()
