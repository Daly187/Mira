# Mira — Autonomous Digital Twin

## What is this project?
Mira is a fully autonomous AI agent that operates as a digital twin. She trades, posts, earns, remembers, and operates 24/7. Not a chatbot — an extension of the user.

## Tech Stack
- **Agent runtime**: Python 3.11+ (runs on Windows desktop, always-on)
- **AI backbone**: Claude API with 3-tier routing (Haiku/Sonnet/Opus)
- **Memory**: SQLite (structured) + ChromaDB (semantic) + NetworkX (knowledge graph)
- **Interface**: Telegram bot (primary), React dashboard (visual), voice (Whisper + ElevenLabs)
- **Computer use**: Anthropic computer use API for desktop control
- **Dashboard**: React + Vite + Tailwind + FullCalendar, served via FastAPI backend
- **Dev workflow**: Mac edits code, syncs to Windows desktop via Google Drive

## Project Structure
```
Mira/
├── agent/                    # Python agent (runs on Windows desktop)
│   ├── main.py               # Core agent loop + scheduler
│   ├── brain.py              # Claude API with 3-tier model routing
│   ├── telegram_bot.py       # 21 Telegram commands
│   ├── api.py                # FastAPI dashboard backend (25+ endpoints)
│   ├── config.py             # Centralised config from .env
│   ├── scheduler.py          # Recurring task scheduler
│   ├── memory/               # Three-layer memory system
│   │   ├── sqlite_store.py   # 9 tables: memories, people, trades, etc.
│   │   ├── vector_store.py   # ChromaDB semantic search
│   │   └── knowledge_graph.py # NetworkX connected graph
│   ├── capture/              # Input processing
│   │   └── ingest.py         # 4-stage ingestion pipeline
│   ├── modules/              # Feature modules
│   │   ├── pa.py             # Email, calendar, briefings
│   │   ├── trading.py        # MT5, crypto, Polymarket
│   │   ├── social.py         # 6-platform content management
│   │   ├── earning.py        # 5 revenue streams
│   │   ├── personal.py       # Health, finance, travel, family
│   │   ├── patterns.py       # Weekly pattern recognition
│   │   └── whatsapp.py       # WhatsApp monitoring
│   ├── computer_use/         # Desktop automation
│   │   └── agent.py          # Screenshot, click, type
│   └── helpers/              # Utilities
│       ├── encryption.py     # AES-256 at rest
│       ├── voice.py          # STT + TTS
│       └── file_watcher.py   # Auto-restart on code changes
├── dashboard/                # React + Vite web UI
│   └── src/pages/            # Dashboard, Calendar, Memory, People, Trades, Costs, Actions, Settings
├── mobile/                   # React Native Android app (Phase 4)
├── docs/                     # Spec PDF
└── CLAUDE.md                 # This file
```

## Running Locally
```bash
# Agent (on Windows desktop)
cd agent
cp .env.example .env  # Fill in API keys
pip install -r requirements.txt
python main.py

# Dashboard API
cd agent
uvicorn api:app --port 8000

# Dashboard UI
cd dashboard
npm install
npm run dev
```

## Key Patterns
- All AI calls go through `brain.py` with a `tier` parameter ("fast"/"standard"/"deep")
- Every autonomous action gets logged to `action_log` table and notified via Telegram
- Kill switch (`/killswitch`) immediately pauses all autonomous actions
- Settings and autonomy rules stored in SQLite `preferences` table, editable from dashboard
- Memory ingestion flows through `ingest.py` → all 3 memory layers simultaneously

## Build Phases
The project follows 11 sequential phases. Currently built through Phase 3 core + skeletons for all later phases. See `docs/Mira_MVP_Process_Document_v1.pdf` for the full spec.

## Important
- `.env` contains API keys — NEVER commit it
- All personal data encrypted with AES-256 at rest
- Google Drive shared folder syncs code between Mac (dev) and Windows (runtime)
- The user's timezone is Asia/Manila (UTC+8)
