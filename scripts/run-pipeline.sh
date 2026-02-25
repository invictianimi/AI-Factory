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

python3 "$REPO_ROOT/projects/the-llm-report/pipeline/run_pipeline.py" "$RUN_TYPE" 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Pipeline completed with exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
exit $EXIT_CODE
