#!/bin/bash
# AI Factory — Pipeline Runner
# Runs the full pipeline: collect → triage → dedup → analysis → editorial → compliance → publish
# Usage: ./scripts/run-pipeline.sh [standard|deep-dive|friday]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_TYPE="${1:-standard}"
LOG_FILE="$REPO_ROOT/logs/pipeline-run.log"

# Load environment
if [ -f "$REPO_ROOT/.env" ]; then
  export $(grep -v '^#' "$REPO_ROOT/.env" | xargs)
fi

export HF_HOME="$REPO_ROOT/.hf_cache"
export PYTHONPATH="$REPO_ROOT:$REPO_ROOT/projects/the-llm-report"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline starting: $RUN_TYPE" | tee -a "$LOG_FILE"

source "$REPO_ROOT/.venv/bin/activate"

# Ensure LiteLLM proxy is running (budget enforcement + model routing)
if ! curl -s --max-time 2 "http://localhost:4000/v1/models" > /dev/null 2>&1; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LiteLLM proxy not responding — starting..." | tee -a "$LOG_FILE"
  systemctl --user start litellm-factory.service 2>/dev/null || \
    bash "$REPO_ROOT/scripts/start-litellm.sh" --wait
  # Wait up to 15s for proxy to be ready
  for i in $(seq 1 15); do
    if curl -s --max-time 1 "http://localhost:4000/v1/models" > /dev/null 2>&1; then
      echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LiteLLM proxy ready" | tee -a "$LOG_FILE"
      break
    fi
    sleep 1
  done
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] LiteLLM proxy OK" | tee -a "$LOG_FILE"
fi

python3 "$REPO_ROOT/projects/the-llm-report/pipeline/run_pipeline.py" "$RUN_TYPE" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline completed with exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
exit $EXIT_CODE
