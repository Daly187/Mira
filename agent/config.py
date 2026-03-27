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

    # ── Local Model (Optional — on-device via Ollama) ─────────
    LOCAL_MODEL_ENABLED = os.getenv("LOCAL_MODEL_ENABLED", "false").lower() == "true"
    LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:11434")
    LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "phi3:mini")
    LOCAL_MODEL_MAX_TOKENS = int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "1024"))
    LOCAL_MODEL_TIMEOUT = int(os.getenv("LOCAL_MODEL_TIMEOUT", "30"))

    # Cost per 1M tokens (for tracking)
    MODEL_COSTS = {
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
        "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
        "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
        "local": {"input": 0.00, "output": 0.00},
    }

    @classmethod
    def get_model_for_tier(cls, tier: str) -> str:
        """Get model ID for a given tier."""
        if tier == "local":
            return cls.LOCAL_MODEL_NAME
        return {
            "fast": cls.CLAUDE_MODEL_FAST,
            "standard": cls.CLAUDE_MODEL_STANDARD,
            "deep": cls.CLAUDE_MODEL_DEEP,
        }.get(tier, cls.CLAUDE_MODEL_STANDARD)

    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a given API call."""
        # Local models are always free
        if model == cls.LOCAL_MODEL_NAME or model == "local":
            return 0.0
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

    # ── Web Access ────────────────────────────────────────────────
    API_TOKEN = os.getenv("API_TOKEN", "")
    WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
    WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

    @classmethod
    def reload(cls):
        """Re-read all config values from os.environ (call after .env update)."""
        from dotenv import load_dotenv
        load_dotenv(AGENT_DIR / ".env", override=True)

        cls.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        cls.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        cls.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        cls.CLAUDE_MODEL_FAST = os.getenv("CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001")
        cls.CLAUDE_MODEL_STANDARD = os.getenv("CLAUDE_MODEL_STANDARD", "claude-sonnet-4-5-20250514")
        cls.CLAUDE_MODEL_DEEP = os.getenv("CLAUDE_MODEL_DEEP", "claude-opus-4-20250514")
        cls.CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")
        cls.CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
        cls.TICK_INTERVAL = int(os.getenv("TICK_INTERVAL", "5"))
        cls.TIMEZONE = os.getenv("TIMEZONE", "Asia/Manila")
        cls.MAX_DAILY_DRAWDOWN_PCT = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "3.0"))
        cls.MAX_POSITION_SIZE = float(os.getenv("MAX_POSITION_SIZE", "0.1"))
        cls.MAX_TOTAL_EXPOSURE = float(os.getenv("MAX_TOTAL_EXPOSURE", "5.0"))
        cls.BRIEFING_TIME = os.getenv("BRIEFING_TIME", "07:00")
        cls.BRIEFING_TIMEZONE = os.getenv("BRIEFING_TIMEZONE", "Asia/Manila")
        cls.ENCRYPT_AT_REST = os.getenv("ENCRYPT_AT_REST", "true").lower() == "true"
        cls.LOCAL_MODEL_ENABLED = os.getenv("LOCAL_MODEL_ENABLED", "false").lower() == "true"
        cls.LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:11434")
        cls.LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "phi3:mini")
        cls.LOCAL_MODEL_MAX_TOKENS = int(os.getenv("LOCAL_MODEL_MAX_TOKENS", "1024"))
        cls.LOCAL_MODEL_TIMEOUT = int(os.getenv("LOCAL_MODEL_TIMEOUT", "30"))
        cls.API_TOKEN = os.getenv("API_TOKEN", "")
        cls.WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
        cls.WEB_PORT = int(os.getenv("WEB_PORT", "8000"))

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
