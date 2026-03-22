"""
Mira Dashboard API — FastAPI backend serving data to the React dashboard.
Reads from the same SQLite database that the agent writes to.
Accessible via Tailscale from any device.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import Config
from memory.sqlite_store import SQLiteStore

logger = logging.getLogger("mira.api")

app = FastAPI(title="Mira Dashboard API", version="1.0.0")

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
    }


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
        "model_standard": {"type": "str", "default": "claude-sonnet-4-5-20250514", "label": "Standard Model (Sonnet)"},
        "model_deep": {"type": "str", "default": "claude-opus-4-20250514", "label": "Deep Model (Opus)"},
    },
    "polymarket": {
        "polymarket_max_bet": {"type": "float", "default": 50.0, "label": "Max Single Bet ($)"},
        "polymarket_max_exposure": {"type": "float", "default": 500.0, "label": "Max Total Exposure ($)"},
        "polymarket_enabled": {"type": "bool", "default": False, "label": "Polymarket Enabled"},
    },
}


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
