#!/usr/bin/env bash
# ==============================================================================
# Standalone Runner for Football Analysis FastAPI Backend
# Runs FastAPI on http://localhost:8000 with auto-reload and CORS support.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Check Python virtual environment
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Virtual environment not found at $VENV_PYTHON. Using system python3..."
    PYTHON_CMD="python3"
else
    PYTHON_CMD="$VENV_PYTHON"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

echo "===================================================================="
echo " Starting Football Analysis Backend API on http://$HOST:$PORT"
echo " Docs available at: http://localhost:$PORT/docs"
echo " OpenAPI JSON at:   http://localhost:$PORT/openapi.json"
echo "===================================================================="

export PYTHONPATH="$PROJECT_ROOT/src:${PYTHONPATH:-}"

# Check if port is already in use and warn
if lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Warning: Port $PORT is currently in use. Existing process may be active."
    echo "To kill the existing process, run: kill \$(lsof -t -i:$PORT)"
fi

exec "$PYTHON_CMD" -m uvicorn football_analysis.api.app:app \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --reload-dir "$PROJECT_ROOT/src/football_analysis"
