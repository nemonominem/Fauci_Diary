#!/bin/bash
# ============================================================
# Tony's Diary Search App — Startup Script
# ============================================================
# Usage:  bash start_search.sh
# Then open:  http://localhost:8765
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Regenerate page_map.json and clean JSON line breaks
echo "Regenerating page map..."
python3 regen_page_map.py

echo "Cleaning JSON line breaks..."
python3 clean_json_breaks.py

# Kill any existing instance
pkill -f "python3 serve.py" 2>/dev/null
sleep 1

# Start server in background
python3 serve.py &
SERVER_PID=$!

# Wait for it to start
sleep 2

# Open in default browser
if command -v open &>/dev/null; then
    open http://localhost:8765
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Tony's Diary Search is running!             ║"
echo "║  URL: http://localhost:8765                   ║"
echo "║  Press Ctrl+C to stop the server.             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

wait $SERVER_PID
