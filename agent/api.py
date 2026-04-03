"""
Mira Dashboard API — FastAPI backend serving data to the React dashboard.
Reads from the same SQLite database that the agent writes to.
Accessible via Tailscale from any device.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

try:
    import httpx
except ImportError:
    httpx = None

from config import Config
from memory.sqlite_store import SQLiteStore

logger = logging.getLogger("mira.api")


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Simple Bearer token auth for remote access."""

    EXEMPT_PREFIXES = ("/api/health", "/api/setup/")

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth if no token configured, for non-API routes, or exempt paths
        if not Config.API_TOKEN:
            return await call_next(request)
        if not path.startswith("/api/"):
            return await call_next(request)
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth == f"Bearer {Config.API_TOKEN}":
            return await call_next(request)

        return JSONResponse(status_code=401, content={"error": "Invalid or missing API token"})


app = FastAPI(title="Mira Dashboard API", version="1.0.0")
app.add_middleware(TokenAuthMiddleware)

# Allow dashboard to connect from any origin (Tailscale network)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection (read from same DB as agent)
db = SQLiteStore(Config.MEMORY_DB_PATH)


@app.on_event("startup")
def startup():
    db.initialise()
    _ensure_affiliate_tables()
    logger.info("Dashboard API started")


def _ensure_affiliate_tables():
    """Create affiliate tracking tables if they don't exist."""
    db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS affiliate_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            product_name TEXT NOT NULL,
            affiliate_url TEXT NOT NULL,
            original_url TEXT,
            commission_type TEXT DEFAULT 'percentage',
            commission_rate REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            total_clicks INTEGER DEFAULT 0,
            total_conversions INTEGER DEFAULT 0,
            total_revenue REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS affiliate_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            source_platform TEXT,
            source_post_id TEXT,
            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            converted INTEGER DEFAULT 0,
            revenue_amount REAL DEFAULT 0.0,
            order_id TEXT,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (link_id) REFERENCES affiliate_links(id)
        );

        CREATE INDEX IF NOT EXISTS idx_affiliate_links_platform ON affiliate_links(platform);
        CREATE INDEX IF NOT EXISTS idx_affiliate_links_status ON affiliate_links(status);
        CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_link_id ON affiliate_clicks(link_id);
        CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_clicked ON affiliate_clicks(clicked_at);
        CREATE INDEX IF NOT EXISTS idx_affiliate_clicks_converted ON affiliate_clicks(converted);
    """)
    db.conn.commit()


# ═══════════════════════════════════════════════════════════════
# STATUS & KPIs
# ═══════════════════════════════════════════════════════════════


@app.get("/api/status")
def get_status():
    """Overall Mira status and KPIs."""
    stats = db.get_stats()
    costs = db.get_api_costs("today")
    costs_month = db.get_api_costs("month")
    pending_tasks = db.get_pending_tasks()
    open_trades = db.get_open_trades()

    return {
        "status": "online",
        "memory": stats,
        "open_trades": len(open_trades),
        "pending_tasks": len(pending_tasks),
        "api_cost_today": costs["total_cost"],
        "api_cost_month": costs_month["total_cost"],
        "api_calls_today": costs["total_calls"],
    }


@app.get("/api/kpis")
def get_kpis():
    """Dashboard KPI summary."""
    stats = db.get_stats()
    costs_today = db.get_api_costs("today")
    costs_week = db.get_api_costs("week")
    costs_month = db.get_api_costs("month")
    trades = db.get_trade_history(limit=100)
    actions_today = db.get_daily_actions()

    # Calculate trading P&L
    closed_trades = [t for t in trades if t.get("pnl") is not None]
    total_pnl = sum(t["pnl"] for t in closed_trades)
    win_rate = (
        len([t for t in closed_trades if t["pnl"] > 0]) / len(closed_trades) * 100
        if closed_trades else 0
    )

    return {
        "memory": {
            "total_memories": stats.get("memories", 0),
            "total_people": stats.get("people", 0),
            "total_events": stats.get("events", 0),
            "total_decisions": stats.get("decisions", 0),
        },
        "trading": {
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": len(closed_trades),
            "open_positions": stats.get("trades", 0) - len(closed_trades),
        },
        "api_costs": {
            "today": costs_today["total_cost"],
            "week": costs_week["total_cost"],
            "month": costs_month["total_cost"],
            "calls_today": costs_today["total_calls"],
        },
        "activity": {
            "actions_today": len(actions_today),
            "pending_tasks": stats.get("tasks", 0),
        },
        "email": _get_email_kpis(),
        "habits": _get_habit_kpis(),
    }


def _get_email_kpis() -> dict:
    """Email stats for KPI dashboard."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - __import__('datetime').timedelta(days=7)).isoformat()

        triaged_today = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM action_log WHERE module = 'pa' AND action LIKE '%triage%' AND created_at >= ?",
            (today,),
        ).fetchone()
        triaged_week = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM action_log WHERE module = 'pa' AND action LIKE '%triage%' AND created_at >= ?",
            (week_ago,),
        ).fetchone()
        auto_filed = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM action_log WHERE module = 'pa' AND action LIKE '%auto_filed%' AND created_at >= ?",
            (week_ago,),
        ).fetchone()

        return {
            "triaged_today": dict(triaged_today).get("cnt", 0) if triaged_today else 0,
            "triaged_this_week": dict(triaged_week).get("cnt", 0) if triaged_week else 0,
            "auto_filed_this_week": dict(auto_filed).get("cnt", 0) if auto_filed else 0,
        }
    except Exception:
        return {"triaged_today": 0, "triaged_this_week": 0, "auto_filed_this_week": 0}


def _get_habit_kpis() -> dict:
    """Habit stats for KPI dashboard."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        total = db.conn.execute("SELECT COUNT(*) as cnt FROM habits").fetchone()
        done = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM habits WHERE last_completed = ?", (today,)
        ).fetchone()
        best_streak = db.conn.execute(
            "SELECT MAX(streak) as best FROM habits"
        ).fetchone()

        return {
            "total": dict(total).get("cnt", 0) if total else 0,
            "done_today": dict(done).get("cnt", 0) if done else 0,
            "best_streak": dict(best_streak).get("best", 0) if best_streak else 0,
        }
    except Exception:
        return {"total": 0, "done_today": 0, "best_streak": 0}


# ═══════════════════════════════════════════════════════════════
# MEMORY
# ═══════════════════════════════════════════════════════════════


@app.get("/api/memories")
def list_memories(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_importance: Optional[int] = None,
    limit: int = Query(default=50, le=200),
):
    """Search and list memories."""
    return db.search_memories(
        query=query,
        category=category,
        min_importance=min_importance,
        limit=limit,
    )


@app.get("/api/memories/recent")
def recent_memories(limit: int = 20):
    return db.get_recent_memories(limit)


class MemoryCreate(BaseModel):
    content: str
    category: str = "general"
    importance: int = 3
    source: str = "dashboard"
    tags: list = []


@app.post("/api/memories")
def create_memory(memory: MemoryCreate):
    """Manually add a memory from the dashboard."""
    memory_id = db.store_memory(
        content=memory.content,
        category=memory.category,
        importance=memory.importance,
        source=memory.source,
        tags=memory.tags,
    )
    return {"id": memory_id, "status": "stored"}


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    importance: Optional[int] = None


@app.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, update: MemoryUpdate):
    """Update an existing memory."""
    fields = []
    values = []
    if update.content is not None:
        fields.append("content = ?")
        values.append(update.content)
    if update.category is not None:
        fields.append("category = ?")
        values.append(update.category)
    if update.importance is not None:
        fields.append("importance = ?")
        values.append(update.importance)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(memory_id)
    db.conn.execute(f"UPDATE memories SET {', '.join(fields)} WHERE id = ?", values)
    db.conn.commit()
    return {"id": memory_id, "status": "updated"}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    """Delete a memory by ID."""
    db.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    db.conn.commit()
    return {"id": memory_id, "status": "deleted"}


# ═══════════════════════════════════════════════════════════════
# PEOPLE (CRM)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/people")
def list_people():
    return db.get_all_people()


@app.get("/api/people/{name}")
def get_person(name: str):
    person = db.get_person(name)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


class PersonUpdate(BaseModel):
    name: str
    relationship_type: Optional[str] = None
    key_facts: Optional[list] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@app.post("/api/people")
def upsert_person(person: PersonUpdate):
    person_id = db.upsert_person(
        name=person.name,
        relationship_type=person.relationship_type,
        key_facts=person.key_facts,
        email=person.email,
        phone=person.phone,
    )
    return {"id": person_id, "status": "saved"}


@app.delete("/api/people/{person_id}")
def delete_person(person_id: int):
    """Delete a person by ID."""
    db.conn.execute("DELETE FROM people WHERE id = ?", (person_id,))
    db.conn.commit()
    return {"id": person_id, "status": "deleted"}


# ═══════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/tasks")
def list_tasks(module: Optional[str] = None):
    return db.get_pending_tasks(module=module)


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: int = 3
    module: str = "general"
    due_date: Optional[str] = None


@app.post("/api/tasks")
def create_task(task: TaskCreate):
    task_id = db.add_task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        module=task.module,
        due_date=task.due_date,
    )
    return {"id": task_id, "status": "created"}


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: int):
    db.complete_task(task_id)
    return {"status": "completed"}


# ═══════════════════════════════════════════════════════════════
# TRADES
# ═══════════════════════════════════════════════════════════════


@app.get("/api/trades")
def list_trades(limit: int = 50):
    return db.get_trade_history(limit=limit)


@app.get("/api/trades/open")
def open_trades():
    return db.get_open_trades()


class TradeCreate(BaseModel):
    instrument: str
    direction: str
    entry_price: Optional[float] = None
    size: Optional[float] = None
    strategy: Optional[str] = None
    rationale: Optional[str] = None
    platform: str = "mt5"


@app.post("/api/trades")
def create_trade(trade: TradeCreate):
    """Log a new trade from the dashboard."""
    trade_id = db.log_trade(
        instrument=trade.instrument,
        direction=trade.direction,
        entry_price=trade.entry_price,
        size=trade.size,
        strategy=trade.strategy,
        rationale=trade.rationale,
        platform=trade.platform,
    )
    return {"id": trade_id, "status": "logged"}


# ═══════════════════════════════════════════════════════════════
# ACTION LOG
# ═══════════════════════════════════════════════════════════════


@app.get("/api/actions")
def list_actions(date: Optional[str] = None):
    """Get action log for a given day (default: today)."""
    return db.get_daily_actions(date=date)


# ═══════════════════════════════════════════════════════════════
# API COSTS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/costs")
def get_costs(period: str = "today"):
    if period not in ("today", "week", "month", "all"):
        period = "today"
    return db.get_api_costs(period)


# ═══════════════════════════════════════════════════════════════
# SETTINGS & RULES
# ═══════════════════════════════════════════════════════════════

# Settings stored in SQLite preferences table
SETTINGS_SCHEMA = {
    "trading": {
        "max_daily_drawdown_pct": {"type": "float", "default": 3.0, "label": "Max Daily Drawdown %"},
        "max_position_size": {"type": "float", "default": 0.1, "label": "Max Position Size (lots)"},
        "max_total_exposure": {"type": "float", "default": 5.0, "label": "Max Total Exposure %"},
        "trading_paused": {"type": "bool", "default": False, "label": "Trading Paused"},
    },
    "briefing": {
        "briefing_time": {"type": "str", "default": "07:00", "label": "Daily Briefing Time"},
        "briefing_timezone": {"type": "str", "default": "Asia/Manila", "label": "Briefing Timezone"},
    },
    "autonomy": {
        "trading_autonomy": {"type": "str", "default": "full_auto", "label": "Trading Autonomy",
                             "options": ["full_auto", "notify_first", "manual"]},
        "crypto_autonomy": {"type": "str", "default": "full_auto", "label": "Crypto Autonomy",
                            "options": ["full_auto", "notify_first", "manual"]},
        "social_autonomy": {"type": "str", "default": "full_auto", "label": "Social Media Autonomy",
                            "options": ["full_auto", "draft_approve", "manual"]},
        "email_work_autonomy": {"type": "str", "default": "draft_approve", "label": "Work Email Autonomy",
                                "options": ["draft_approve", "ask_first", "manual"]},
        "email_personal_autonomy": {"type": "str", "default": "draft_approve", "label": "Personal Email Autonomy",
                                    "options": ["draft_approve", "ask_first", "manual"]},
        "calendar_autonomy": {"type": "str", "default": "full_auto", "label": "Calendar Autonomy",
                              "options": ["full_auto", "notify_first", "manual"]},
        "whatsapp_general_autonomy": {"type": "str", "default": "draft_approve", "label": "WhatsApp (General) Autonomy",
                                      "options": ["draft_approve", "ask_first", "manual"]},
        "whatsapp_close_autonomy": {"type": "str", "default": "ask_first", "label": "WhatsApp (Close Contacts) Autonomy",
                                    "options": ["ask_first", "manual"]},
    },
    "models": {
        "model_fast": {"type": "str", "default": "claude-haiku-4-5-20251001", "label": "Fast Model (Haiku)"},
        "model_standard": {"type": "str", "default": "claude-sonnet-4-5-20250929", "label": "Standard Model (Sonnet)"},
        "model_deep": {"type": "str", "default": "claude-opus-4-5-20251101", "label": "Deep Model (Opus)"},
    },
    "polymarket": {
        "polymarket_max_bet": {"type": "float", "default": 50.0, "label": "Max Single Bet ($)"},
        "polymarket_max_exposure": {"type": "float", "default": 500.0, "label": "Max Total Exposure ($)"},
        "polymarket_enabled": {"type": "bool", "default": False, "label": "Polymarket Enabled"},
    },
}


# ── ENV KEY SETUP SCHEMA ──────────────────────────────────────
ENV_KEYS_SCHEMA = [
    # Core
    {"key": "ANTHROPIC_API_KEY", "label": "Anthropic API Key", "group": "core", "required": True, "test_service": "anthropic", "help": "Get from console.anthropic.com"},
    {"key": "TELEGRAM_BOT_TOKEN", "label": "Telegram Bot Token", "group": "core", "required": True, "test_service": "telegram_bot", "help": "Create via @BotFather on Telegram"},
    {"key": "TELEGRAM_CHAT_ID", "label": "Telegram Chat ID", "group": "core", "required": True, "test_service": "telegram_chat", "help": "Your numeric Telegram user ID (send /start to @userinfobot)"},
    {"key": "API_TOKEN", "label": "Dashboard API Token", "group": "core", "required": True, "test_service": None, "help": "Secret token for dashboard authentication (any strong string)"},
    # Telegram Userbot
    {"key": "TG_API_ID", "label": "Telegram API ID", "group": "telegram", "required": False, "test_service": "telegram_userbot", "help": "Get from my.telegram.org → API development tools"},
    {"key": "TG_API_HASH", "label": "Telegram API Hash", "group": "telegram", "required": False, "test_service": None, "help": "Get from my.telegram.org → API development tools"},
    {"key": "TG_PHONE", "label": "Telegram Phone Number", "group": "telegram", "required": False, "test_service": None, "help": "Your phone with country code, e.g. +639171234567"},
    {"key": "TG_SYNC_INTERVAL", "label": "Sync Interval (seconds)", "group": "telegram", "required": False, "test_service": None, "help": "How often to sync conversations (default 300 = 5 min)"},
    # Local Model
    {"key": "LOCAL_MODEL_ENABLED", "label": "Enable Local Model", "group": "local_model", "required": False, "test_service": "local_model", "help": "Set to 'true' to use Ollama for simple tasks ($0 cost)"},
    {"key": "LOCAL_MODEL_URL", "label": "Ollama URL", "group": "local_model", "required": False, "test_service": None, "help": "Default: http://localhost:11434"},
    {"key": "LOCAL_MODEL_NAME", "label": "Model Name", "group": "local_model", "required": False, "test_service": None, "help": "e.g. phi3:mini, llama3:8b — run 'ollama list' to see available"},
    # Voice
    {"key": "ELEVENLABS_API_KEY", "label": "ElevenLabs API Key", "group": "voice", "required": False, "test_service": "elevenlabs", "help": "For voice synthesis — elevenlabs.io"},
    {"key": "ELEVENLABS_VOICE_ID", "label": "ElevenLabs Voice ID", "group": "voice", "required": False, "test_service": None, "help": "Voice ID from ElevenLabs dashboard"},
    # Google
    {"key": "GOOGLE_CREDENTIALS_PATH", "label": "Google Credentials Path", "group": "google", "required": False, "test_service": None, "help": "Path to OAuth credentials JSON file"},
    {"key": "PRIORITY_SENDERS", "label": "Priority Email Senders", "group": "google", "required": False, "test_service": None, "help": "Comma-separated emails that bypass work-hours rules"},
    # Security
    {"key": "ENCRYPT_KEY", "label": "Encryption Key", "group": "security", "required": False, "test_service": None, "help": "AES-256 key for data at rest encryption"},
]


def _read_env_file() -> dict:
    """Read .env file into dict."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        example = Path(__file__).parent / ".env.example"
        if example.exists():
            shutil.copy2(example, env_path)
        else:
            env_path.touch()
    values = {}
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_file(updates: dict):
    """Atomically update .env file with new key values."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        example = Path(__file__).parent / ".env.example"
        if example.exists():
            shutil.copy2(example, env_path)
        else:
            env_path.touch()
    existing_lines = []
    with open(env_path, "r") as f:
        existing_lines = f.readlines()
    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")
    tmp_path = env_path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        f.writelines(new_lines)
    os.replace(tmp_path, env_path)
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
        Config.reload()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# SETUP / API KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@app.get("/api/setup/status")
async def get_setup_status():
    """Return configuration status for all env keys (masked values only)."""
    env_values = _read_env_file()
    keys = []
    missing_required = []
    for schema in ENV_KEYS_SCHEMA:
        val = env_values.get(schema["key"], "")
        configured = bool(val and val != "your-key-here" and not val.startswith("your-"))
        masked = f"****{val[-4:]}" if configured and len(val) >= 4 else None
        keys.append({
            "key": schema["key"],
            "label": schema["label"],
            "group": schema["group"],
            "required": schema["required"],
            "configured": configured,
            "masked_value": masked,
            "help": schema["help"],
            "test_service": schema.get("test_service"),
        })
        if schema["required"] and not configured:
            missing_required.append(schema["key"])
    return {
        "keys": keys,
        "setup_complete": len(missing_required) == 0,
        "missing_required": missing_required,
    }


class EnvKeysUpdate(BaseModel):
    keys: dict


@app.post("/api/setup/keys")
async def save_setup_keys(payload: EnvKeysUpdate):
    """Save API keys to .env file. Only allows keys from ENV_KEYS_SCHEMA."""
    allowed_keys = {s["key"] for s in ENV_KEYS_SCHEMA}
    updates = {}
    for key, value in payload.keys.items():
        if key not in allowed_keys:
            continue
        updates[key] = str(value).strip()
    if updates:
        _write_env_file(updates)
        if db:
            db.log_action("setup", f"Updated API keys: {', '.join(updates.keys())}")
    return await get_setup_status()


@app.post("/api/setup/test/{service}")
async def test_setup_service(service: str):
    """Test connectivity for a specific service."""
    env_values = _read_env_file()
    try:
        if service == "anthropic":
            import anthropic as anthropic_lib
            key = env_values.get("ANTHROPIC_API_KEY", "")
            if not key:
                return {"service": service, "status": "error", "message": "API key not configured"}
            client = anthropic_lib.Anthropic(api_key=key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=10,
                messages=[{"role": "user", "content": "Say hi"}],
            )
            return {"service": service, "status": "ok", "message": "Connected to Anthropic API"}

        elif service == "telegram_bot":
            if not httpx:
                return {"service": service, "status": "error", "message": "httpx not installed"}
            token = env_values.get("TELEGRAM_BOT_TOKEN", "")
            if not token:
                return {"service": service, "status": "error", "message": "Bot token not configured"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                data = resp.json()
                if data.get("ok"):
                    return {"service": service, "status": "ok", "message": f"Connected to @{data['result'].get('username', '?')}"}
                return {"service": service, "status": "error", "message": data.get("description", "Unknown error")}

        elif service == "telegram_chat":
            if not httpx:
                return {"service": service, "status": "error", "message": "httpx not installed"}
            token = env_values.get("TELEGRAM_BOT_TOKEN", "")
            chat_id = env_values.get("TELEGRAM_CHAT_ID", "")
            if not token or not chat_id:
                return {"service": service, "status": "error", "message": "Bot token or chat ID not configured"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": "Mira setup test — connection confirmed!"},
                )
                data = resp.json()
                if data.get("ok"):
                    return {"service": service, "status": "ok", "message": "Test message sent to your Telegram"}
                return {"service": service, "status": "error", "message": data.get("description", "Unknown error")}

        elif service == "elevenlabs":
            if not httpx:
                return {"service": service, "status": "error", "message": "httpx not installed"}
            key = env_values.get("ELEVENLABS_API_KEY", "")
            if not key:
                return {"service": service, "status": "error", "message": "API key not configured"}
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
                if resp.status_code == 200:
                    return {"service": service, "status": "ok", "message": "Connected to ElevenLabs"}
                return {"service": service, "status": "error", "message": f"Auth failed (HTTP {resp.status_code})"}

        elif service == "telegram_userbot":
            api_id = env_values.get("TG_API_ID", "")
            api_hash = env_values.get("TG_API_HASH", "")
            phone = env_values.get("TG_PHONE", "")
            if not api_id or not api_hash:
                return {"service": service, "status": "error", "message": "API ID and Hash required — get from my.telegram.org"}
            if not phone:
                return {"service": service, "status": "error", "message": "Phone number not configured"}
            # Check if userbot is connected (if agent is running)
            if hasattr(app.state, "mira") and hasattr(app.state.mira, "userbot"):
                ub = app.state.mira.userbot
                if hasattr(ub, "available") and ub.available:
                    return {"service": service, "status": "ok", "message": "Userbot connected and running"}
            return {"service": service, "status": "ok", "message": f"Keys configured for {phone} — start agent to connect"}

        elif service == "local_model":
            if not httpx:
                return {"service": service, "status": "error", "message": "httpx not installed"}
            enabled = env_values.get("LOCAL_MODEL_ENABLED", "false").lower() == "true"
            if not enabled:
                return {"service": service, "status": "error", "message": "Local model disabled — set LOCAL_MODEL_ENABLED=true"}
            url = env_values.get("LOCAL_MODEL_URL", "http://localhost:11434")
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{url}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m.get("name", "?") for m in data.get("models", [])]
                        if models:
                            return {"service": service, "status": "ok", "message": f"Ollama running — models: {', '.join(models[:5])}"}
                        return {"service": service, "status": "ok", "message": "Ollama running but no models pulled. Run: ollama pull phi3:mini"}
                    return {"service": service, "status": "error", "message": f"Ollama returned HTTP {resp.status_code}"}
            except Exception:
                return {"service": service, "status": "error", "message": f"Cannot reach Ollama at {url} — is it running?"}

        else:
            return {"service": service, "status": "error", "message": f"Unknown service: {service}"}
    except Exception as e:
        return {"service": service, "status": "error", "message": str(e)}


@app.get("/api/settings/schema")
def get_settings_schema():
    """Return the full settings schema with types, defaults, and options."""
    return SETTINGS_SCHEMA


@app.get("/api/settings")
def get_all_settings():
    """Get all current settings values."""
    settings = {}
    for group, fields in SETTINGS_SCHEMA.items():
        settings[group] = {}
        for key, schema in fields.items():
            value = db.get_preference(key)
            if value is None:
                settings[group][key] = schema["default"]
            elif schema["type"] == "float":
                settings[group][key] = float(value)
            elif schema["type"] == "bool":
                settings[group][key] = value.lower() == "true"
            else:
                settings[group][key] = value
    return settings


class SettingUpdate(BaseModel):
    key: str
    value: str


@app.post("/api/settings")
def update_setting(setting: SettingUpdate):
    """Update a single setting."""
    db.set_preference(setting.key, setting.value, confidence=1.0, source="dashboard")
    db.log_action("settings", f"update: {setting.key}", setting.value)
    return {"status": "updated", "key": setting.key, "value": setting.value}


# ═══════════════════════════════════════════════════════════════
# AUTONOMY RULES
# ═══════════════════════════════════════════════════════════════


@app.get("/api/rules")
def get_rules():
    """Get all autonomy rules."""
    rules = {}
    for key, schema in SETTINGS_SCHEMA.get("autonomy", {}).items():
        value = db.get_preference(key)
        rules[key] = {
            "value": value or schema["default"],
            "label": schema["label"],
            "options": schema.get("options", []),
        }
    return rules


@app.post("/api/rules/{rule_key}")
def update_rule(rule_key: str, setting: SettingUpdate):
    """Update a single autonomy rule."""
    if rule_key not in SETTINGS_SCHEMA.get("autonomy", {}):
        raise HTTPException(status_code=404, detail="Rule not found")
    db.set_preference(rule_key, setting.value, confidence=1.0, source="dashboard")
    db.log_action("rules", f"update: {rule_key}", setting.value)
    return {"status": "updated", "rule": rule_key, "value": setting.value}


# ═══════════════════════════════════════════════════════════════
# CALENDAR
# ═══════════════════════════════════════════════════════════════


@app.get("/api/calendar/events")
def get_calendar_events(
    start: Optional[str] = None,
    end: Optional[str] = None,
):
    """Get calendar events — Mira's tasks + user's Google Calendar.
    Returns events formatted for FullCalendar.
    """
    events = []

    # Mira's scheduled tasks
    tasks = db.get_pending_tasks()
    for t in tasks:
        events.append({
            "id": f"task-{t['id']}",
            "title": f"[Mira] {t['title']}",
            "start": t.get("due_date") or t.get("created_at"),
            "className": "mira-event",
            "type": "mira_task",
            "module": t.get("module"),
            "priority": t.get("priority"),
        })

    # Today's actions as timeline markers
    actions = db.get_daily_actions()
    for a in actions:
        if a.get("created_at"):
            events.append({
                "id": f"action-{a['id']}",
                "title": f"{a['module']}: {a['action']}",
                "start": a["created_at"],
                "className": "mira-event",
                "type": "mira_action",
                "display": "list-item",
            })

    # User's Google Calendar events (loaded from cached file if available)
    gcal_path = Path(Config.DATA_DIR) / "gcal_cache.json"
    if gcal_path.exists():
        try:
            gcal_data = json.loads(gcal_path.read_text())
            for evt in gcal_data:
                cal_event = {
                    "id": f"gcal-{evt.get('id', '')}",
                    "title": evt.get("summary", "No title"),
                    "className": "user-event",
                    "type": "google_calendar",
                }
                # Handle all-day vs timed events
                if evt.get("start", {}).get("date"):
                    cal_event["start"] = evt["start"]["date"]
                    cal_event["allDay"] = True
                elif evt.get("start", {}).get("dateTime"):
                    cal_event["start"] = evt["start"]["dateTime"]
                    cal_event["allDay"] = False
                if evt.get("end", {}).get("date"):
                    cal_event["end"] = evt["end"]["date"]
                elif evt.get("end", {}).get("dateTime"):
                    cal_event["end"] = evt["end"]["dateTime"]

                events.append(cal_event)
        except Exception as e:
            logger.error(f"Failed to load gcal cache: {e}")

    return events


@app.post("/api/calendar/events")
def create_calendar_event(req: dict):
    """Create a calendar event as a Mira task with a due date."""
    title = req.get("title", "Untitled Event")
    start = req.get("start")  # ISO datetime string
    event_type = req.get("type", "user_event")
    description = req.get("description", "")

    if not start:
        return {"error": "start is required"}, 400

    task_id = db.add_task(
        title=title,
        description=description,
        priority=req.get("priority", 3),
        module=event_type,
        due_date=start,
    )
    db.log_action("calendar", "event_created", f"Created event: {title}", {"task_id": task_id, "start": start})
    return {
        "id": task_id,
        "title": title,
        "start": start,
        "type": event_type,
        "description": description,
    }


# Mira's recurring schedule (static for display)
MIRA_SCHEDULE = [
    {"time": "07:00", "task": "Morning Briefing", "frequency": "daily"},
    {"time": "08:00", "task": "Portfolio Snapshot", "frequency": "daily"},
    {"time": "every 15min", "task": "EA Health Check", "frequency": "interval"},
    {"time": "every 5min", "task": "Email Poll", "frequency": "interval"},
    {"time": "pre-meeting", "task": "Meeting Brief (30min before)", "frequency": "event"},
    {"time": "post-meeting", "task": "Action Items (1hr after)", "frequency": "event"},
    {"time": "market close", "task": "MT5 Screenshot Report", "frequency": "daily"},
    {"time": "22:00", "task": "Daily Action Log", "frequency": "daily"},
    {"time": "Friday 16:00", "task": "EOW Summary Draft", "frequency": "weekly"},
    {"time": "Sunday 18:00", "task": "Calendar Review", "frequency": "weekly"},
    {"time": "Sunday 19:00", "task": "Weekly Pattern Review", "frequency": "weekly"},
    {"time": "Monday 08:00", "task": "Net Worth Update", "frequency": "weekly"},
]


@app.get("/api/calendar/schedule")
def get_mira_schedule():
    """Get Mira's recurring schedule."""
    return MIRA_SCHEDULE


# ═══════════════════════════════════════════════════════════════
# MODULES STATUS
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# KILL SWITCH
# ═══════════════════════════════════════════════════════════════


@app.post("/api/killswitch")
def activate_killswitch():
    """Activate kill switch — pause ALL autonomous actions."""
    db.set_preference("kill_switch_active", "true", confidence=1.0, source="dashboard")
    db.log_action("safety", "kill_switch_activated", "All autonomous actions paused")
    return {"status": "activated", "kill_switch_active": True}


@app.post("/api/resume")
def deactivate_killswitch():
    """Deactivate kill switch — resume autonomous actions."""
    db.set_preference("kill_switch_active", "false", confidence=1.0, source="dashboard")
    db.log_action("safety", "kill_switch_deactivated", "Autonomous actions resumed")
    return {"status": "deactivated", "kill_switch_active": False}


@app.get("/api/killswitch/status")
def get_killswitch_status():
    """Get current kill switch state."""
    value = db.get_preference("kill_switch_active")
    active = value is not None and value.lower() == "true"
    return {"kill_switch_active": active}


# ═══════════════════════════════════════════════════════════════
# SOCIAL
# ═══════════════════════════════════════════════════════════════


@app.get("/api/social/stats")
async def get_social_stats():
    """Get social media engagement stats from content_queue and action_log."""
    try:
        from datetime import timedelta
        now = datetime.now()
        week_ago = (now - timedelta(days=7)).isoformat()
        month_ago = (now - timedelta(days=30)).isoformat()

        posts_week = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM content_queue WHERE status = 'posted' AND posted_at >= ?",
            (week_ago,),
        ).fetchone()
        posts_month = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM content_queue WHERE status = 'posted' AND posted_at >= ?",
            (month_ago,),
        ).fetchone()
        queued = db.conn.execute(
            "SELECT COUNT(*) as cnt FROM content_queue WHERE status = 'queued'"
        ).fetchone()
        by_platform = db.conn.execute(
            "SELECT platform, COUNT(*) as cnt FROM content_queue WHERE status = 'posted' AND posted_at >= ? GROUP BY platform",
            (month_ago,),
        ).fetchall()

        return {
            "posts_this_week": dict(posts_week).get("cnt", 0) if posts_week else 0,
            "posts_this_month": dict(posts_month).get("cnt", 0) if posts_month else 0,
            "queued": dict(queued).get("cnt", 0) if queued else 0,
            "platform_breakdown": {dict(r)["platform"]: dict(r)["cnt"] for r in by_platform},
        }
    except Exception:
        return {"posts_this_week": 0, "posts_this_month": 0, "queued": 0, "platform_breakdown": {}}


# ═══════════════════════════════════════════════════════════════
# EARNINGS
# ═══════════════════════════════════════════════════════════════


EARNING_MODULES = [
    {
        "id": "polymarket",
        "name": "Polymarket Alpha Engine",
        "potential_min": 500,
        "potential_max": 5000,
        "phase": 7,
        "status": "pending",
        "description": "Prediction market research and autonomous betting",
    },
    {
        "id": "content",
        "name": "Content Monetisation",
        "potential_min": 200,
        "potential_max": 5000,
        "phase": 9,
        "status": "pending",
        "description": "YouTube AdSense, TikTok, Instagram, affiliate links",
    },
    {
        "id": "consulting",
        "name": "Consulting Pipeline",
        "potential_min": 2000,
        "potential_max": 10000,
        "phase": 9,
        "status": "pending",
        "description": "BPO operations, finance systems, AI automation consulting",
    },
    {
        "id": "freelance",
        "name": "Freelance Agent",
        "potential_min": 500,
        "potential_max": 3000,
        "phase": 8,
        "status": "pending",
        "description": "Upwork, Fiverr, Freelancer, PeoplePerHour",
    },
    {
        "id": "digital_products",
        "name": "Digital Product Store",
        "potential_min": 100,
        "potential_max": 2000,
        "phase": 8,
        "status": "pending",
        "description": "Trading guides, Excel templates, finance dashboards on Gumroad/Etsy",
    },
    {
        "id": "newsletter",
        "name": "Paid Newsletter",
        "potential_min": 200,
        "potential_max": 2000,
        "phase": 11,
        "status": "pending",
        "description": "Weekly premium insights newsletter",
    },
]


@app.get("/api/earnings")
def get_earnings():
    """Return earning module status and tracked revenue."""
    # Check if any revenue has been logged
    modules = []
    for mod in EARNING_MODULES:
        # Look for tracked revenue in action_log
        revenue_rows = db.conn.execute(
            """SELECT COALESCE(SUM(CAST(outcome AS REAL)), 0) as total
               FROM action_log
               WHERE module = ? AND action = 'revenue'
               AND created_at >= DATE('now', 'start of month')""",
            (f"earning_{mod['id']}",),
        ).fetchone()
        current_month = revenue_rows["total"] if revenue_rows else 0.0

        modules.append({
            **mod,
            "current_month_earnings": round(current_month, 2),
        })

    total_min = sum(m["potential_min"] for m in EARNING_MODULES)
    total_max = sum(m["potential_max"] for m in EARNING_MODULES)
    total_current = sum(m["current_month_earnings"] for m in modules)

    return {
        "modules": modules,
        "total_potential_min": total_min,
        "total_potential_max": total_max,
        "total_current_month": round(total_current, 2),
    }


# ═══════════════════════════════════════════════════════════════
# MODULES STATUS
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# AFFILIATES
# ═══════════════════════════════════════════════════════════════


class AffiliateCreate(BaseModel):
    platform: str
    product_name: str
    affiliate_url: str
    original_url: Optional[str] = None
    commission_type: str = "percentage"
    commission_rate: float = 0.0


@app.get("/api/affiliates")
def list_affiliates():
    """List all registered affiliate links with stats."""
    rows = db.conn.execute(
        """SELECT * FROM affiliate_links
           ORDER BY total_revenue DESC, total_clicks DESC"""
    ).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/affiliates")
def create_affiliate(link: AffiliateCreate):
    """Register a new affiliate link."""
    cursor = db.conn.execute(
        """INSERT INTO affiliate_links
           (platform, product_name, affiliate_url, original_url,
            commission_type, commission_rate)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            link.platform,
            link.product_name,
            link.affiliate_url,
            link.original_url,
            link.commission_type,
            link.commission_rate,
        ),
    )
    db.conn.commit()
    link_id = cursor.lastrowid
    db.log_action(
        "affiliate",
        "register_link",
        f"Registered {link.product_name} on {link.platform}",
        {"link_id": link_id, "platform": link.platform},
    )
    return {"id": link_id, "status": "registered"}


@app.get("/api/affiliates/report")
def get_affiliate_report():
    """Weekly affiliate revenue report."""
    from datetime import timedelta

    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()

    clicks_row = db.conn.execute(
        "SELECT COUNT(*) as total_clicks FROM affiliate_clicks WHERE clicked_at >= ?",
        (seven_days_ago,),
    ).fetchone()

    conv_row = db.conn.execute(
        """SELECT COUNT(*) as total_conversions,
                  COALESCE(SUM(revenue_amount), 0) as total_revenue
           FROM affiliate_clicks
           WHERE clicked_at >= ? AND converted = 1""",
        (seven_days_ago,),
    ).fetchone()

    platform_rows = db.conn.execute(
        """SELECT al.platform,
                  COUNT(ac.id) as clicks,
                  SUM(CASE WHEN ac.converted = 1 THEN 1 ELSE 0 END) as conversions,
                  COALESCE(SUM(ac.revenue_amount), 0) as revenue
           FROM affiliate_clicks ac
           JOIN affiliate_links al ON ac.link_id = al.id
           WHERE ac.clicked_at >= ?
           GROUP BY al.platform
           ORDER BY revenue DESC""",
        (seven_days_ago,),
    ).fetchall()

    link_rows = db.conn.execute(
        """SELECT al.id, al.product_name, al.platform,
                  COUNT(ac.id) as clicks,
                  SUM(CASE WHEN ac.converted = 1 THEN 1 ELSE 0 END) as conversions,
                  COALESCE(SUM(ac.revenue_amount), 0) as revenue
           FROM affiliate_clicks ac
           JOIN affiliate_links al ON ac.link_id = al.id
           WHERE ac.clicked_at >= ?
           GROUP BY al.id
           ORDER BY revenue DESC
           LIMIT 10""",
        (seven_days_ago,),
    ).fetchall()

    total_clicks = clicks_row["total_clicks"] if clicks_row else 0
    total_conversions = conv_row["total_conversions"] if conv_row else 0
    total_revenue = conv_row["total_revenue"] if conv_row else 0.0
    conversion_rate = (
        (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
    )

    return {
        "period": "last_7_days",
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "total_revenue": round(total_revenue, 2),
        "conversion_rate": round(conversion_rate, 2),
        "by_platform": [dict(r) for r in platform_rows],
        "top_links": [dict(r) for r in link_rows],
    }


# ═══════════════════════════════════════════════════════════════
# MODULES STATUS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/modules")
def get_modules():
    """Status of all Mira modules."""
    return {
        "telegram": {"status": "active", "phase": 2},
        "memory": {"status": "active", "phase": 3},
        "brain": {"status": "active", "phase": 3},
        "computer_use": {"status": "pending", "phase": 5},
        "pa": {"status": "pending", "phase": 6},
        "trading": {"status": "pending", "phase": 7},
        "social": {"status": "pending", "phase": 8},
        "pattern_recognition": {"status": "pending", "phase": 9},
        "personal": {"status": "pending", "phase": 10},
        "dashboard": {"status": "active", "phase": 11},
        "voice": {"status": "pending", "phase": 11},
        "earning": {
            "freelance": {"status": "pending", "phase": 8},
            "content_monetisation": {"status": "pending", "phase": 9},
            "polymarket": {"status": "pending", "phase": 7},
            "digital_products": {"status": "pending", "phase": 8},
            "consulting": {"status": "pending", "phase": 9},
        },
    }


# ═══════════════════════════════════════════════════════════════
# HABITS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/habits")
async def get_habits():
    """Get all habits with stats."""
    try:
        rows = db.conn.execute("SELECT * FROM habits ORDER BY category, name").fetchall()
        habits = []
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        for row in rows:
            h = dict(row)
            # Check if done today
            done_today = db.conn.execute(
                "SELECT id FROM habit_log WHERE habit_id = ? AND completed_at = ?",
                (h["id"], today),
            ).fetchone()
            h["done_today"] = bool(done_today)

            # Completions last 7 days
            from datetime import timedelta
            seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            h["completions_7d"] = db.conn.execute(
                "SELECT COUNT(*) as cnt FROM habit_log WHERE habit_id = ? AND completed_at >= ?",
                (h["id"], seven_days_ago),
            ).fetchone()["cnt"]

            habits.append(h)
        return habits
    except Exception as e:
        return []


@app.post("/api/habits")
async def create_habit(request: Request):
    """Create a new habit."""
    try:
        body = await request.json()
        name = body.get("name", "").strip().lower()
        frequency = body.get("target_frequency", "daily")
        category = body.get("category", "general")
        if not name:
            raise HTTPException(status_code=400, detail="Habit name is required")
        # Check for duplicate
        existing = db.conn.execute(
            "SELECT id FROM habits WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"Habit '{name}' already exists")
        cursor = db.conn.execute(
            "INSERT INTO habits (name, target_frequency, category) VALUES (?, ?, ?)",
            (name, frequency, category),
        )
        db.conn.commit()
        return {"status": "created", "id": cursor.lastrowid, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/habits/{habit_id}")
async def delete_habit(habit_id: int):
    """Delete a habit and its log entries."""
    try:
        existing = db.conn.execute("SELECT id FROM habits WHERE id = ?", (habit_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Habit not found")
        db.conn.execute("DELETE FROM habit_log WHERE habit_id = ?", (habit_id,))
        db.conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
        db.conn.commit()
        return {"status": "deleted", "id": habit_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/habits/{habit_name}/log")
async def log_habit(habit_name: str):
    """Log a habit as done today."""
    try:
        row = db.conn.execute(
            "SELECT * FROM habits WHERE name = ? COLLATE NOCASE", (habit_name,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Habit '{habit_name}' not found")

        today = datetime.now().strftime("%Y-%m-%d")
        already = db.conn.execute(
            "SELECT id FROM habit_log WHERE habit_id = ? AND completed_at = ?",
            (row["id"], today),
        ).fetchone()
        if already:
            return {"status": "already_logged", "streak": row["streak"]}

        db.conn.execute(
            "INSERT INTO habit_log (habit_id, completed_at) VALUES (?, ?)",
            (row["id"], today),
        )
        # Simple streak increment
        new_streak = (row["streak"] or 0) + 1
        db.conn.execute(
            "UPDATE habits SET streak = ?, last_completed = ? WHERE id = ?",
            (new_streak, today, row["id"]),
        )
        db.conn.commit()
        return {"status": "logged", "streak": new_streak}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# RELATIONSHIPS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/relationships/health")
async def get_relationship_health():
    """Get people flagged for relationship attention."""
    try:
        rows = db.conn.execute(
            """SELECT name, relationship_type, last_interaction, conversation_count,
                      relationship_health, commitments
               FROM people
               WHERE relationship_health IN ('needs_attention', 'at_risk')
               ORDER BY last_interaction ASC"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════
# SCHEDULE
# ═══════════════════════════════════════════════════════════════


@app.get("/api/schedule")
async def get_schedule():
    """Get all scheduled tasks — static definitions + last execution times."""
    # Static task definitions (mirrors main.py scheduler registration)
    task_defs = [
        {"name": "daily_briefing", "schedule": "Daily 7:00am", "module": "pa", "description": "Morning briefing via Telegram"},
        {"name": "ea_health", "schedule": "Every 15 min", "module": "trading", "description": "Check MT5 EA health"},
        {"name": "daily_action_log", "schedule": "Daily 10:00pm", "module": "core", "description": "Send daily action summary"},
        {"name": "portfolio_snapshot", "schedule": "Daily 8:00am", "module": "trading", "description": "Capture portfolio state"},
        {"name": "weekly_review", "schedule": "Sunday 7:00pm", "module": "patterns", "description": "Weekly pattern analysis"},
        {"name": "calendar_review", "schedule": "Sunday 6:00pm", "module": "pa", "description": "Next week calendar review"},
        {"name": "weekly_email_digest", "schedule": "Sunday 6:00pm", "module": "pa", "description": "Low-priority email digest"},
        {"name": "social_queue", "schedule": "Every 4 hours", "module": "social", "description": "Process content posting queue"},
        {"name": "eow_summary", "schedule": "Friday 5:00pm", "module": "pa", "description": "End-of-week Boldr summary"},
        {"name": "net_worth", "schedule": "Monday 8:30am", "module": "personal", "description": "Net worth snapshot update"},
        {"name": "daily_backup", "schedule": "Daily 3:00am", "module": "core", "description": "Backup memory databases"},
        {"name": "learning_review", "schedule": "Daily 12:00pm", "module": "learning", "description": "Spaced repetition prompts"},
        {"name": "deadline_warnings", "schedule": "Daily 9:00am", "module": "pa", "description": "Legal/compliance deadlines"},
        {"name": "habit_check", "schedule": "Daily 12:00pm & 8:00pm", "module": "personal", "description": "Habit completion reminders"},
        {"name": "presence_check", "schedule": "Every 2 hours", "module": "personal", "description": "Break reminder after long work"},
        {"name": "email_check", "schedule": "Every 30 min", "module": "pa", "description": "Gmail polling and triage"},
        {"name": "post_meeting_actions", "schedule": "Every 15 min", "module": "pa", "description": "Post-meeting action prompts"},
        {"name": "relationship_health", "schedule": "Wednesday 10:00am", "module": "personal", "description": "Flag neglected relationships"},
        {"name": "monthly_learning_report", "schedule": "1st of month 9:00am", "module": "learning", "description": "Monthly learning summary"},
        {"name": "important_dates", "schedule": "Daily 8:15am", "module": "personal", "description": "Birthday/anniversary reminders"},
        {"name": "competitive_intelligence", "schedule": "Monday 9:00am", "module": "personal", "description": "Weekly competitor scan"},
        {"name": "compliance_check", "schedule": "Daily 9:00am", "module": "pa", "description": "Compliance deadline tracker"},
    ]

    # Enrich with last execution time from action_log
    try:
        for task in task_defs:
            name = task["name"]
            row = db.conn.execute(
                """SELECT created_at, outcome FROM action_log
                   WHERE action LIKE ? OR action LIKE ?
                   ORDER BY created_at DESC LIMIT 1""",
                (f"%{name}%", f"%{name.replace('_', ' ')}%"),
            ).fetchone()
            if row:
                r = dict(row)
                task["last_run"] = r.get("created_at")
                task["last_outcome"] = r.get("outcome", "")[:100]
            else:
                task["last_run"] = None
                task["last_outcome"] = "Never run"
    except Exception:
        pass

    return task_defs


# ═══════════════════════════════════════════════════════════════
# COMPLIANCE
# ═══════════════════════════════════════════════════════════════


@app.get("/api/compliance/deadlines")
async def get_compliance_deadlines():
    """Get compliance deadlines from preferences."""
    try:
        raw = db.get_preference("compliance_deadlines")
        if not raw:
            return []
        import json as _json
        deadlines = _json.loads(raw)
        if not isinstance(deadlines, list):
            return []

        from datetime import datetime as _dt
        now = _dt.now()
        for dl in deadlines:
            try:
                due = _dt.fromisoformat(dl.get("due_date", ""))
                dl["days_until"] = (due - now).days
                dl["alert_level"] = (
                    "critical" if dl["days_until"] <= 1
                    else "high" if dl["days_until"] <= 7
                    else "medium" if dl["days_until"] <= 30
                    else "low"
                )
            except (ValueError, TypeError):
                dl["days_until"] = None
                dl["alert_level"] = "unknown"
        return sorted(deadlines, key=lambda x: x.get("days_until") or 9999)
    except Exception:
        return []


@app.post("/api/compliance/deadlines")
async def save_compliance_deadline(request: Request):
    """Add or update a compliance deadline."""
    try:
        body = await request.json()
        import json as _json

        raw = db.get_preference("compliance_deadlines")
        deadlines = _json.loads(raw) if raw else []

        deadlines.append({
            "name": body.get("name", ""),
            "due_date": body.get("due_date", ""),
            "jurisdiction": body.get("jurisdiction", ""),
            "category": body.get("category", "compliance"),
        })

        db.set_preference("compliance_deadlines", _json.dumps(deadlines))
        return {"status": "saved", "total": len(deadlines)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# DECISIONS
# ═══════════════════════════════════════════════════════════════


@app.get("/api/decisions")
async def get_decisions(limit: int = Query(50)):
    """Get recent decisions with scores."""
    try:
        rows = db.conn.execute(
            "SELECT * FROM decisions ORDER BY decided_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


@app.post("/api/decisions")
async def create_decision(request: Request):
    """Log a new decision."""
    try:
        body = await request.json()
        decision_text = body.get("decision", "").strip()
        if not decision_text:
            raise HTTPException(status_code=400, detail="Decision text is required")
        context = body.get("context", "")
        reasoning = body.get("reasoning", "")
        domain = body.get("domain", "general")
        alternatives = body.get("alternatives_considered", "[]")
        if isinstance(alternatives, list):
            import json as _json
            alternatives = _json.dumps(alternatives)
        cursor = db.conn.execute(
            """INSERT INTO decisions (decision, context, reasoning, domain, alternatives_considered)
               VALUES (?, ?, ?, ?, ?)""",
            (decision_text, context, reasoning, domain, alternatives),
        )
        db.conn.commit()
        return {"status": "created", "id": cursor.lastrowid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/decisions/{decision_id}/score")
async def score_decision(decision_id: int, request: Request):
    """Score a past decision."""
    try:
        body = await request.json()
        outcome = body.get("outcome", "")
        score = body.get("score", 5)
        db.score_decision(decision_id, outcome, score)
        return {"status": "scored", "id": decision_id, "score": score}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# TELEGRAM CONTACTS — Autonomous conversation whitelist
# ═══════════════════════════════════════════════════════════════


@app.get("/api/telegram/contacts")
async def get_telegram_contacts():
    """Get all Telegram contacts with autonomy settings."""
    return db.get_all_telegram_contacts()


@app.post("/api/telegram/contacts")
async def upsert_telegram_contact(request: Request):
    """Create or update a Telegram contact."""
    body = await request.json()
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    cid = db.upsert_telegram_contact(
        name=name,
        telegram_user_id=body.get("telegram_user_id"),
        telegram_username=body.get("telegram_username"),
        autonomy_level=body.get("autonomy_level"),
        relationship_type=body.get("relationship_type"),
        communication_style=body.get("communication_style"),
        key_facts=body.get("key_facts"),
        metadata=body.get("metadata"),
    )
    return {"status": "ok", "id": cid, "name": name}


@app.get("/api/telegram/contacts/{name}")
async def get_telegram_contact(name: str):
    """Look up a specific Telegram contact."""
    contact = db.get_telegram_contact(name=name)
    if not contact:
        raise HTTPException(status_code=404, detail=f"Contact '{name}' not found")
    return contact


@app.delete("/api/telegram/contacts/{contact_id}")
async def delete_telegram_contact(contact_id: int):
    """Delete a Telegram contact."""
    deleted = db.delete_telegram_contact(contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted", "id": contact_id}


@app.get("/api/telegram/contacts/{contact_id}/messages")
async def get_contact_messages(contact_id: int, limit: int = Query(default=50)):
    """Get message history for a Telegram contact."""
    return db.get_telegram_history(contact_id, limit=limit)


@app.get("/api/telegram/reviews")
async def get_pending_reviews():
    """Get all messages pending owner review."""
    return db.get_pending_reviews()


@app.post("/api/telegram/contacts/{contact_id}/send")
async def send_telegram_message(contact_id: int, request: Request):
    """Send a message to a contact via the userbot, or schedule it for later."""
    body = await request.json()
    text = body.get("text", "").strip()
    schedule_at = body.get("schedule_at")

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    contact = db.get_telegram_contact(name=None, telegram_user_id=None)
    # Look up by ID directly
    row = db.conn.execute("SELECT * FROM telegram_contacts WHERE id = ?", (contact_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact = dict(row)

    if schedule_at:
        sid = db.save_scheduled_message(contact_id, text, schedule_at, reason="manual")
        return {"status": "scheduled", "scheduled_id": sid}

    # Send immediately via userbot
    if not hasattr(app.state, "mira") or not app.state.mira:
        raise HTTPException(status_code=503, detail="Agent not running")

    userbot = getattr(app.state.mira, "userbot", None)
    if not userbot or not userbot.available:
        raise HTTPException(status_code=503, detail="Userbot not connected. Configure TG_API_ID/TG_API_HASH in .env")

    contact_name = contact.get("telegram_username") or contact.get("name")
    result = await userbot.send_message(contact_name, text)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to send message")

    msg_id = db.save_telegram_message(
        contact_id, "assistant", text, source="userbot",
        telegram_message_id=result.get("message_id"),
    )
    db.log_action("telegram", "message_sent", f"to {contact['name']}", {"text": text[:200]})

    return {"status": "sent", "message_id": msg_id}


@app.post("/api/telegram/contacts/{contact_id}/read")
async def mark_contact_read(contact_id: int):
    """Mark all messages from a contact as read."""
    row = db.conn.execute("SELECT * FROM telegram_contacts WHERE id = ?", (contact_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact = dict(row)

    # Mark read via userbot if available
    if hasattr(app.state, "mira") and app.state.mira:
        userbot = getattr(app.state.mira, "userbot", None)
        if userbot and userbot.available:
            name = contact.get("telegram_username") or contact.get("name")
            await userbot.mark_read(name)

    return {"status": "ok"}


@app.get("/api/telegram/unread")
async def get_unread_counts():
    """Get unread message counts from the userbot."""
    if not hasattr(app.state, "mira") or not app.state.mira:
        return []

    userbot = getattr(app.state.mira, "userbot", None)
    if not userbot or not userbot.available:
        return []

    dialogs = await userbot.get_unread_dialogs()

    # Match unread dialogs to known contacts
    contacts = db.get_all_telegram_contacts()
    contact_map = {}
    for c in contacts:
        contact_map[c["name"].lower()] = c
        if c.get("telegram_username"):
            contact_map[c["telegram_username"].lower().lstrip("@")] = c

    results = []
    for d in dialogs:
        matched = contact_map.get(d["name"].lower()) or contact_map.get(d["username"].lower())
        if matched:
            results.append({
                "contact_id": matched["id"],
                "name": matched["name"],
                "unread_count": d["unread_count"],
                "last_message": d["last_message"],
            })

    return results


@app.get("/api/telegram/scheduled")
async def get_scheduled_messages(contact_id: int = Query(default=None),
                                  status: str = Query(default=None)):
    """Get scheduled messages with optional filters."""
    return db.get_scheduled_messages(contact_id=contact_id, status=status)


@app.post("/api/telegram/scheduled")
async def create_scheduled_message(request: Request):
    """Create a scheduled message for future delivery."""
    body = await request.json()
    contact_id = body.get("contact_id")
    content = body.get("content", "").strip()
    send_at = body.get("send_at")
    reason = body.get("reason", "manual")

    if not contact_id or not content or not send_at:
        raise HTTPException(status_code=400, detail="contact_id, content, and send_at are required")

    sid = db.save_scheduled_message(contact_id, content, send_at, reason)
    return {"status": "ok", "id": sid}


@app.delete("/api/telegram/scheduled/{message_id}")
async def cancel_scheduled(message_id: int):
    """Cancel a pending scheduled message."""
    cancelled = db.cancel_scheduled_message(message_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Message not found or already sent")
    return {"status": "cancelled", "id": message_id}


@app.post("/api/telegram/sync")
async def trigger_sync():
    """Trigger an immediate conversation sync from userbot."""
    if not hasattr(app.state, "mira") or not app.state.mira:
        raise HTTPException(status_code=503, detail="Agent not running")

    userbot = getattr(app.state.mira, "userbot", None)
    if not userbot or not userbot.available:
        raise HTTPException(status_code=503, detail="Userbot not connected")

    # Sync all contacts
    contacts = db.get_all_telegram_contacts()
    synced = 0
    for contact in contacts:
        name = contact.get("telegram_username") or contact.get("name")
        messages = await userbot.get_recent_messages(name, limit=20)
        for msg in messages:
            db.save_telegram_message(
                contact["id"], msg["role"], msg["content"],
                source="userbot", telegram_message_id=msg.get("id"),
            )
        db.update_contact_synced(contact["id"])
        synced += 1

    return {"status": "ok", "contacts_synced": synced}


# ═══════════════════════════════════════════════════════════════
# SOUL SETTINGS — Per-relationship communication rules
# ═══════════════════════════════════════════════════════════════


@app.get("/api/soul/settings")
async def get_all_soul_settings():
    """Get all soul settings (communication rules per relationship type)."""
    settings = db.get_all_soul_settings()
    if not settings:
        # Return default presets so the UI has something to show
        defaults = [
            {"relationship_type": "friend", "tone": "casual", "formality": 2, "humor_level": 4,
             "emoji_usage": "moderate", "response_length": "short", "proactive_outreach": 1,
             "escalation_keywords": "[]", "custom_instructions": "", "enabled": 1},
            {"relationship_type": "colleague", "tone": "professional", "formality": 3, "humor_level": 2,
             "emoji_usage": "minimal", "response_length": "medium", "proactive_outreach": 0,
             "escalation_keywords": "[]", "custom_instructions": "", "enabled": 1},
            {"relationship_type": "family", "tone": "warm", "formality": 1, "humor_level": 4,
             "emoji_usage": "moderate", "response_length": "medium", "proactive_outreach": 1,
             "escalation_keywords": "[]", "custom_instructions": "", "enabled": 1},
            {"relationship_type": "client", "tone": "professional", "formality": 4, "humor_level": 1,
             "emoji_usage": "none", "response_length": "detailed", "proactive_outreach": 0,
             "escalation_keywords": '["deadline", "budget", "contract", "payment"]',
             "custom_instructions": "Always be courteous and solution-oriented.", "enabled": 1},
        ]
        # Seed defaults into DB
        for d in defaults:
            db.upsert_soul_setting(**d)
        return db.get_all_soul_settings()
    return settings


@app.get("/api/soul/settings/{relationship_type}")
async def get_soul_setting(relationship_type: str):
    """Get soul settings for a specific relationship type."""
    setting = db.get_soul_setting(relationship_type)
    if not setting:
        raise HTTPException(status_code=404, detail=f"No soul settings for '{relationship_type}'")
    return setting


@app.post("/api/soul/settings")
async def upsert_soul_setting(request: Request):
    """Create or update soul settings for a relationship type."""
    body = await request.json()
    rel_type = body.get("relationship_type")
    if not rel_type:
        raise HTTPException(status_code=400, detail="relationship_type is required")

    sid = db.upsert_soul_setting(
        relationship_type=rel_type,
        tone=body.get("tone"),
        formality=body.get("formality"),
        humor_level=body.get("humor_level"),
        emoji_usage=body.get("emoji_usage"),
        response_length=body.get("response_length"),
        proactive_outreach=body.get("proactive_outreach"),
        escalation_keywords=body.get("escalation_keywords"),
        custom_instructions=body.get("custom_instructions"),
        enabled=body.get("enabled"),
    )
    return {"status": "ok", "id": sid, "relationship_type": rel_type}


@app.delete("/api/soul/settings/{relationship_type}")
async def delete_soul_setting(relationship_type: str):
    """Delete soul settings for a relationship type."""
    deleted = db.delete_soul_setting(relationship_type)
    if not deleted:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"status": "deleted", "relationship_type": relationship_type}


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET — Real-time dashboard updates
# ═══════════════════════════════════════════════════════════════

_ws_clients: set[WebSocket] = set()


async def broadcast_event(event_type: str, data: dict = None):
    """Broadcast an event to all connected WebSocket clients.

    Call this from anywhere in the agent to push real-time updates:
        from api import broadcast_event
        await broadcast_event("action", {"module": "trading", "action": "trade_opened"})
    """
    if not _ws_clients:
        return
    payload = json.dumps({"type": event_type, "data": data or {}, "ts": datetime.now().isoformat()})
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients -= dead


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for real-time dashboard updates.

    Clients connect and receive JSON events:
    - {"type": "action", "data": {...}} — new action logged
    - {"type": "memory", "data": {...}} — new memory stored
    - {"type": "trade", "data": {...}} — trade opened/closed
    - {"type": "status", "data": {...}} — status change
    - {"type": "ping"} — keepalive (every 30s)
    """
    # Auth check: token as query param or first message
    token = websocket.query_params.get("token", "")
    if Config.API_TOKEN and token != Config.API_TOKEN:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(_ws_clients)} total)")

    try:
        import asyncio
        while True:
            # Send keepalive ping every 30 seconds
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Client can send "ping" to get a "pong"
                if msg.strip().lower() == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        _ws_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(_ws_clients)} total)")


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK (no auth required)
# ═══════════════════════════════════════════════════════════════


@app.get("/api/health")
async def health():
    """Health check endpoint — no auth required."""
    return {
        "status": "ok",
        "version": "1.0",
        "auth_required": bool(Config.API_TOKEN),
        "websocket": "/ws",
        "ws_clients": len(_ws_clients),
    }


# ═══════════════════════════════════════════════════════════════
# STATIC FILE SERVING (Dashboard)
# Must be LAST — catch-all route for SPA
# ═══════════════════════════════════════════════════════════════

STATIC_DIR = Config.AGENT_DIR / "static"

if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    # Serve built assets (JS/CSS bundles)
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        """Serve the React dashboard. SPA catch-all for client-side routing."""
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
