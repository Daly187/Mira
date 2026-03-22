#!/usr/bin/env python3
"""
start_with_watcher.py — Launch main.py with automatic restart on code changes.

Usage:
    python start_with_watcher.py

This script:
  1. Starts main.py as a subprocess
  2. Watches the agent/ directory for .py file changes (via watchdog)
  3. On change, waits 2 seconds (debounce), then restarts main.py
  4. Handles Ctrl+C gracefully

Designed for the Mac -> Google Drive -> Windows dev workflow:
edit on Mac, syncs to Windows, agent auto-restarts.
"""

import logging
import signal
import subprocess
import sys
import time
from pathlib import Path

# Ensure agent/ is on sys.path so imports work
AGENT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(AGENT_DIR))

from helpers.file_watcher import FileWatcher

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mira.launcher")


def main():
    logger.info("=" * 60)
    logger.info("  Mira Agent Launcher with File Watcher")
    logger.info("=" * 60)
    logger.info(f"Agent directory : {AGENT_DIR}")
    logger.info(f"Python          : {sys.executable}")
    logger.info("")

    # Create the watcher
    watcher = FileWatcher(
        watch_dir=AGENT_DIR,
        restart_command=f"{sys.executable} main.py",
    )

    # Start main.py
    logger.info("Starting main.py ...")
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(AGENT_DIR),
    )
    logger.info(f"main.py running as PID {process.pid}")

    # Hand the process to the watcher so it can kill/restart it
    watcher.set_process(process)

    # Start watching for file changes
    watcher.start()

    # ── Graceful shutdown on Ctrl+C / SIGTERM ─────────────────────────

    shutdown_requested = False

    def _handle_signal(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            # Second signal — force exit
            logger.warning("Forced exit")
            sys.exit(1)
        shutdown_requested = True
        logger.info("Shutdown signal received — cleaning up ...")

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Main loop: keep running until shutdown ────────────────────────

    try:
        while not shutdown_requested:
            # Check if the managed process died on its own
            current = watcher._process
            if current is not None and current.poll() is not None:
                code = current.returncode
                if code != 0:
                    logger.warning(
                        f"main.py exited with code {code} — "
                        f"waiting for file change to restart ..."
                    )
                else:
                    logger.info("main.py exited cleanly (code 0)")
                    break
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # ── Cleanup ───────────────────────────────────────────────────────

    logger.info("Stopping file watcher ...")
    watcher.stop()
    logger.info("Goodbye.")


if __name__ == "__main__":
    main()
