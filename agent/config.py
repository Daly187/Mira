"""
Mira Configuration — centralised settings loaded from .env and config files.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from agent directory
AGENT_DIR = Path(__file__).parent
load_dotenv(AGENT_DIR / ".env")


class Config:
    """All Mira configuration in one place."""

    # ── Paths ────────────────────────────────────────────────────────
    AGENT_DIR = AGENT_DIR
    DATA_DIR = AGENT_DIR / "data"
    LOG_DIR = AGENT_DIR / "logs"
    MEMORY_DB_PATH = DATA_DIR / "memory.db"
    CHROMA_DIR = DATA_DIR / "chroma_data"
    KNOWLEDGE_GRAPH_PATH = DATA_DIR / "knowledge_graph.db"
    ENCRYPTION_KEY_PATH = DATA_DIR / "encryption.key"

    # ── API Keys ─────────────────────────────────────────────────────
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # ── Claude API — Tiered Models ───────────────────────────────────
    # Fast (Haiku): JSON extraction, classification, simple parsing — cheapest
    CLAUDE_MODEL_FAST = os.getenv("CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001")
    # Standard (Sonnet): Conversation, analysis, drafting — balanced
    CLAUDE_MODEL_STANDARD = os.getenv("CLAUDE_MODEL_STANDARD", "claude-sonnet-4-5-20250514")
    # Deep (Opus): Research, decision briefs, complex reasoning — best quality
    CLAUDE_MODEL_DEEP = os.getenv("CLAUDE_MODEL_DEEP", "claude-opus-4-20250514")
    # Default model (backwards compat)
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")
    CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))

    # Cost per 1M tokens (for tracking)
    MODEL_COSTS = {
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
        "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
        "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    }

    @classmethod
    def get_model_for_tier(cls, tier: str) -> str:
        """Get model ID for a given tier."""
        return {
            "fast": cls.CLAUDE_MODEL_FAST,
            "standard": cls.CLAUDE_MODEL_STANDARD,
            "deep": cls.CLAUDE_MODEL_DEEP,
        }.get(tier, cls.CLAUDE_MODEL_STANDARD)

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given API call."""
        costs = cls.MODEL_COSTS.get(model, {"input": 3.00, "output": 15.00})
        return (input_tokens * costs["input"] / 1_000_000) + (output_tokens * costs["output"] / 1_000_000)

    # ── Agent Behaviour ──────────────────────────────────────────────
    TICK_INTERVAL = int(os.getenv("TICK_INTERVAL", "5"))  # seconds between loop ticks
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Manila")

    # ── Trading Risk Limits ──────────────────────────────────────────
    MAX_DAILY_DRAWDOWN_PCT = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "3.0"))
    MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "0.1"))  # lots
    MAX_TOTAL_EXPOSURE = float(os.getenv("MAX_TOTAL_EXPOSURE", "5.0"))  # % of account

    # ── Daily Briefing ───────────────────────────────────────────────
    BRIEFING_TIME = os.getenv("BRIEFING_TIME", "07:00")  # Manila time
    BRIEFING_TIMEZONE = os.getenv("BRIEFING_TIMEZONE", "Asia/Manila")

    # ── Notification Format ──────────────────────────────────────────
    NOTIFICATION_FORMAT = "[{module}] {action} | {outcome}"

    # ── Privacy ──────────────────────────────────────────────────────
    ENCRYPT_AT_REST = os.getenv("ENCRYPT_AT_REST", "true").lower() == "true"

    @classmethod
    def ensure_dirs(cls):
        """Create required directories if they don't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate(cls) -> list[str]:
        """Check for missing critical config. Returns list of issues."""
        issues = []
        if not cls.ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY not set")
        if not cls.TELEGRAM_BOT_TOKEN:
            issues.append("TELEGRAM_BOT_TOKEN not set")
        return issues
