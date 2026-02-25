#!/bin/bash
# AI Factory — LiteLLM Proxy Startup Script
# Starts the LiteLLM proxy if not already running.
# Usage: ./scripts/start-litellm.sh [--wait]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LITELLM_PORT=4000
LITELLM_PID_FILE="/tmp/litellm-factory.pid"
LITELLM_LOG="$REPO_ROOT/logs/litellm.log"

# Load environment
if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  source "$REPO_ROOT/.env"
  set +a
fi

# Check if already running
if curl -s --max-time 2 "http://localhost:$LITELLM_PORT/health" > /dev/null 2>&1; then
  echo "[litellm] Proxy already running on port $LITELLM_PORT"
  exit 0
fi

echo "[litellm] Starting LiteLLM proxy on port $LITELLM_PORT..."

source "$REPO_ROOT/.venv/bin/activate"

nohup litellm \
  --config "$REPO_ROOT/orchestrator/config/litellm_config.yaml" \
  --port $LITELLM_PORT \
  >> "$LITELLM_LOG" 2>&1 &

echo $! > "$LITELLM_PID_FILE"
echo "[litellm] Proxy started (PID $!)"

# Wait for ready (up to 15s)
if [ "${1}" = "--wait" ]; then
  echo "[litellm] Waiting for proxy to be ready..."
  for i in $(seq 1 15); do
    if curl -s --max-time 1 "http://localhost:$LITELLM_PORT/health" > /dev/null 2>&1; then
      echo "[litellm] Proxy ready after ${i}s"
      exit 0
    fi
    sleep 1
  done
  echo "[litellm] WARNING: Proxy may not be ready yet — continuing anyway"
fi
