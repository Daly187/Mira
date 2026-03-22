#!/bin/bash
# Mira — Start everything with one command
# Usage: ./start.sh [agent|dashboard|api|all]

MIRA_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENT_DIR="$MIRA_DIR/agent"
DASHBOARD_DIR="$MIRA_DIR/dashboard"

start_api() {
    echo "Starting Mira Dashboard API on port 8000..."
    cd "$AGENT_DIR"
    python -m uvicorn api:app --host 0.0.0.0 --port 8000 &
    echo $! > "$MIRA_DIR/.api.pid"
    echo "API PID: $(cat $MIRA_DIR/.api.pid)"
}

start_dashboard() {
    echo "Starting Mira Dashboard on port 3000..."
    cd "$DASHBOARD_DIR"
    npm run dev &
    echo $! > "$MIRA_DIR/.dashboard.pid"
    echo "Dashboard PID: $(cat $MIRA_DIR/.dashboard.pid)"
}

start_agent() {
    echo "Starting Mira Agent..."
    cd "$AGENT_DIR"
    python main.py
}

stop_all() {
    echo "Stopping Mira..."
    [ -f "$MIRA_DIR/.api.pid" ] && kill $(cat "$MIRA_DIR/.api.pid") 2>/dev/null && rm "$MIRA_DIR/.api.pid"
    [ -f "$MIRA_DIR/.dashboard.pid" ] && kill $(cat "$MIRA_DIR/.dashboard.pid") 2>/dev/null && rm "$MIRA_DIR/.dashboard.pid"
    pkill -f "uvicorn api:app" 2>/dev/null
    echo "Stopped."
}

case "${1:-all}" in
    agent)
        start_agent
        ;;
    api)
        start_api
        ;;
    dashboard)
        start_dashboard
        ;;
    stop)
        stop_all
        ;;
    all)
        start_api
        sleep 2
        start_dashboard
        sleep 2
        echo ""
        echo "═══════════════════════════════════════"
        echo "  MIRA is online"
        echo "  Dashboard: http://localhost:3000"
        echo "  API:       http://localhost:8000"
        echo "  Docs:      http://localhost:8000/docs"
        echo "═══════════════════════════════════════"
        echo ""
        echo "Starting agent (Telegram bot)..."
        start_agent
        ;;
    *)
        echo "Usage: ./start.sh [agent|api|dashboard|all|stop]"
        ;;
esac
