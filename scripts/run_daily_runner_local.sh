#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHATBOT_DIR="$ROOT_DIR/chatbot"
LOG_FILE="$ROOT_DIR/logs/daily_runner.log"

mkdir -p "$(dirname "$LOG_FILE")"

ONLY_ENABLED="${ONLY_ENABLED:-1}"
FORCE="${FORCE:-0}"
LIMIT="${LIMIT:-200}"
BOOTSTRAP_ENABLE_N="${BOOTSTRAP_ENABLE_N:-0}"
ASSISTANT_ID="${ASSISTANT_ID:-graph_daily_runner}"
LANGGRAPH_API_URL="${LANGGRAPH_API_URL:-http://localhost:2024}"

{
  echo
  echo "===== $(date -u +"%Y-%m-%dT%H:%M:%SZ") daily_runner start ====="
  echo "ONLY_ENABLED=$ONLY_ENABLED FORCE=$FORCE LIMIT=$LIMIT BOOTSTRAP_ENABLE_N=$BOOTSTRAP_ENABLE_N ASSISTANT_ID=$ASSISTANT_ID LANGGRAPH_API_URL=$LANGGRAPH_API_URL"
} | tee -a "$LOG_FILE"

cd "$CHATBOT_DIR"
set -a
source ../.env
export LANGGRAPH_API_URL
set +a

../.venv/bin/python - <<'PY' 2>&1 | tee -a "$LOG_FILE"
import asyncio
import os
import logging
from cron.daily_runner import run_daily

def _b(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default

async def main():
    logging.basicConfig(level=logging.INFO)
    result = await run_daily(
        only_enabled=_b("ONLY_ENABLED", True),
        force=_b("FORCE", False),
        limit=_i("LIMIT", 200),
        bootstrap_enable_n=_i("BOOTSTRAP_ENABLE_N", 0),
        assistant_id=os.getenv("ASSISTANT_ID", "graph_daily_runner"),
    )
    print("RESULT:", result)

asyncio.run(main())
PY

echo "===== $(date -u +"%Y-%m-%dT%H:%M:%SZ") daily_runner end =====" | tee -a "$LOG_FILE"
