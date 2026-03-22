"""
Seed test data into Mira's database so the dashboard looks populated.
Run once: python seed_data.py
"""

import random
from datetime import datetime, timedelta
from memory.sqlite_store import SQLiteStore
from config import Config

Config.ensure_dirs()
db = SQLiteStore(Config.MEMORY_DB_PATH)
db.initialise()

print("Seeding Mira database with test data...")

# ── Memories ─────────────────────────────────────────────────────
memories = [
    ("David mentioned Q2 targets are aggressive — need to revisit Manila headcount", "work", 4),
    ("Spoke to Andrew about the Tacloban site expansion timeline", "work", 4),
    ("BTC looking strong above 68k, watching for a pullback to 65k to add", "trading", 3),
    ("Mom's birthday is April 15 — need to sort gift and shipping to SA", "personal", 5),
    ("New compliance deadline for Mexico payroll: May 30", "work", 5),
    ("Interesting thread on CT about Solana DePIN projects", "trading", 2),
    ("Gym session — legs day, felt good. Sleep was 7.2 hours last night", "health", 2),
    ("F1 Melbourne GP this weekend — Verstappen looking dominant again", "personal", 1),
    ("DalyKraken dual investment settled — 4.2% return on ETH position", "trading", 3),
    ("Meeting with vendor in Cebu rescheduled to next Thursday", "work", 3),
    ("Had a great idea about automating the EOW summary with Granola + Gmail", "work", 4),
    ("Noticed I trade worse on Thursday afternoons — energy dip pattern?", "trading", 4),
    ("WhatsApp group discussing team offsite options for June", "work", 2),
    ("Read article on Claude computer use — could automate MT5 monitoring", "learning", 3),
    ("Polymarket: US election odds seem mispriced given latest polling", "trading", 4),
    ("Called the plumber about the kitchen sink — coming Saturday morning", "personal", 2),
    ("Boldr Canada compliance audit results came back clean", "work", 4),
    ("Sleep quality dropped last 3 days — correlated with late trading sessions", "health", 3),
    ("New LinkedIn post about BPO automation got 2.4k impressions", "social", 3),
    ("Need to review vendor contract renewal for Manila cleaning service", "work", 3),
]

for content, category, importance in memories:
    days_ago = random.randint(0, 14)
    db.store_memory(
        content=content,
        category=category,
        importance=importance,
        source=random.choice(["telegram", "phone", "watch", "email"]),
        tags=[category],
    )

# ── People ───────────────────────────────────────────────────────
people = [
    ("David", "work", "david@boldr.com", ["CEO of Boldr", "Based in US", "Weekly 1:1 on Mondays"]),
    ("Andrew", "work", "andrew@boldr.com", ["COO", "Focuses on operations", "Needs EOW summary"]),
    ("Mom", "family", None, ["Lives in South Africa", "Birthday April 15", "Prefers WhatsApp calls"]),
    ("James", "personal", None, ["Friend from SA", "Also trades crypto", "F1 fan"]),
    ("Maria", "work", "maria@boldr.com", ["HR lead Manila", "Handles compliance PH"]),
    ("Carlos", "work", "carlos@boldr.com", ["Mexico site lead", "Payroll compliance contact"]),
    ("Sarah", "work", "sarah@boldr.com", ["Finance team", "Handles vendor payments"]),
    ("Alex", "personal", None, ["Met at crypto meetup Manila", "Solana developer"]),
]

for name, rel_type, email, facts in people:
    db.upsert_person(name=name, relationship_type=rel_type, email=email, key_facts=facts)

# ── Trades ───────────────────────────────────────────────────────
trades = [
    ("EURUSD", "buy", 1.0842, 1.0891, 0.1, 49.0, "trend_following", "Bullish engulfing on H4"),
    ("GBPJPY", "sell", 191.45, 190.82, 0.05, 31.5, "mean_reversion", "Overbought RSI on daily"),
    ("XAUUSD", "buy", 2341.50, 2318.20, 0.1, -23.3, "breakout", "Failed breakout above resistance"),
    ("USDJPY", "sell", 151.80, 151.22, 0.1, 58.0, "trend_following", "Intervention risk trade"),
    ("EURUSD", "buy", 1.0910, None, 0.1, None, "trend_following", "Continuation of uptrend"),
    ("BTCUSD", "buy", 67500.0, 69200.0, 0.01, 17.0, "dca", "Weekly DCA buy"),
    ("ETHBTC", "buy", 0.0485, 0.0462, 0.5, -11.5, "mean_reversion", "ETH/BTC ratio bounce play"),
]

for inst, direction, entry, exit_p, size, pnl, strategy, rationale in trades:
    trade_id = db.log_trade(
        instrument=inst, direction=direction, entry_price=entry,
        size=size, strategy=strategy, rationale=rationale, platform="mt5"
    )
    if exit_p and pnl is not None:
        db.close_trade(trade_id, exit_price=exit_p, pnl=pnl)

# ── Decisions ────────────────────────────────────────────────────
decisions = [
    ("Increased DCA frequency on BTC from weekly to twice weekly", "Market showing accumulation pattern at support", "trading"),
    ("Declined vendor contract renewal with ABC Cleaning", "Found cheaper alternative with better reviews", "work"),
    ("Moved daily briefing time from 6am to 7am", "Was consistently skipping 6am briefing — 7am better aligned with routine", "personal"),
]

for decision, reasoning, domain in decisions:
    db.log_decision(decision=decision, reasoning=reasoning, domain=domain)

# ── Tasks ────────────────────────────────────────────────────────
tasks = [
    ("Review Mexico payroll compliance docs", 2, "work"),
    ("Sort Mom's birthday gift", 3, "personal"),
    ("Analyse Polymarket US election odds", 3, "trading"),
    ("Draft LinkedIn post about AI in BPO", 4, "social"),
    ("Review vendor contract renewal", 3, "work"),
    ("Update MT5 EA settings for Asian session", 2, "trading"),
]

for title, priority, module in tasks:
    db.add_task(title=title, priority=priority, module=module)

# ── Action Log ───────────────────────────────────────────────────
actions = [
    ("core", "startup", "success"),
    ("memory", "ingest", "stored 5 memories"),
    ("trading", "ea_health_check", "all EAs running"),
    ("pa", "daily_briefing", "delivered"),
    ("pa", "email_triage", "3 emails processed"),
    ("trading", "portfolio_snapshot", "captured"),
    ("memory", "ingest", "stored conversation"),
    ("social", "queue_linkedin", "post drafted"),
    ("trading", "risk_check", "within limits"),
    ("pa", "meeting_brief", "generated for 2pm call"),
]

for module, action, outcome in actions:
    db.log_action(module, action, outcome)

# ── API Usage (cost tracking) ────────────────────────────────────
api_calls = [
    ("claude-haiku-4-5-20251001", "fast", "entity_extraction", 450, 180, 0.0008),
    ("claude-haiku-4-5-20251001", "fast", "entity_extraction", 520, 210, 0.0009),
    ("claude-haiku-4-5-20251001", "fast", "email_triage", 380, 150, 0.0007),
    ("claude-haiku-4-5-20251001", "fast", "entity_extraction", 490, 195, 0.0008),
    ("claude-haiku-4-5-20251001", "fast", "whatsapp_classify", 280, 120, 0.0005),
    ("claude-sonnet-4-5-20250514", "standard", "conversation", 1200, 850, 0.016),
    ("claude-sonnet-4-5-20250514", "standard", "conversation", 980, 620, 0.013),
    ("claude-sonnet-4-5-20250514", "standard", "daily_briefing", 2100, 1400, 0.027),
    ("claude-sonnet-4-5-20250514", "standard", "draft_reply", 800, 450, 0.009),
    ("claude-sonnet-4-5-20250514", "standard", "analysis", 1500, 900, 0.018),
    ("claude-opus-4-20250514", "deep", "deep_research", 3200, 2800, 0.258),
    ("claude-opus-4-20250514", "deep", "polymarket_analysis", 2800, 1900, 0.185),
]

for model, tier, task_type, input_tok, output_tok, cost in api_calls:
    db.log_api_usage(model, tier, task_type, input_tok, output_tok, cost)

# ── Preferences ──────────────────────────────────────────────────
db.set_preference("max_daily_drawdown_pct", "3.0", 1.0, "config")
db.set_preference("briefing_time", "07:00", 1.0, "config")
db.set_preference("trading_paused", "false", 1.0, "config")
db.set_preference("polymarket_enabled", "false", 1.0, "config")

stats = db.get_stats()
print(f"Seeded: {stats}")
print("Done!")
db.close()
