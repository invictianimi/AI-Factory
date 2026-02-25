#!/bin/bash
# AI Factory Tri-Sync: Local <-> Transport <-> GitHub <-> Google Drive
set -euo pipefail

FACTORY_DIR="/home/aifactory/AI-Factory"
TRANSPORT_DIR="/mnt/transport/AI-Factory"
GDRIVE_REMOTE="gdrive:AI-Factory"
LOG_FILE="$FACTORY_DIR/logs/sync.log"

mkdir -p "$FACTORY_DIR/logs"
echo "[$(date -Iseconds)] Sync started" >> "$LOG_FILE"

# 1. Git: commit and push any local changes
cd "$FACTORY_DIR"
git add -A 2>/dev/null
git diff --cached --quiet || git commit -m "auto-sync: $(date +%Y%m%d-%H%M%S)" 2>/dev/null
git push origin main 2>/dev/null || echo "[$(date -Iseconds)] Git push skipped (no remote or conflict)" >> "$LOG_FILE"

# 2. Transport share: sync bidirectional (local is source of truth)
if mountpoint -q /mnt/transport 2>/dev/null; then
    rsync -av --delete --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
        "$FACTORY_DIR/" "$TRANSPORT_DIR/" 2>/dev/null
    echo "[$(date -Iseconds)] Transport share synced" >> "$LOG_FILE"
else
    echo "[$(date -Iseconds)] Transport share not mounted, skipping" >> "$LOG_FILE"
fi

# 3. Google Drive: sync key files (not the full repo — just outputs, logs, dashboards)
rclone sync "$FACTORY_DIR/outputs/" "$GDRIVE_REMOTE/outputs/" 2>/dev/null
rclone sync "$FACTORY_DIR/logs/" "$GDRIVE_REMOTE/logs/" 2>/dev/null
rclone sync "$FACTORY_DIR/docs/" "$GDRIVE_REMOTE/docs/" 2>/dev/null
rclone copy "$FACTORY_DIR/CLAUDE.md" "$GDRIVE_REMOTE/" 2>/dev/null
echo "[$(date -Iseconds)] Google Drive synced" >> "$LOG_FILE"

echo "[$(date -Iseconds)] Sync complete" >> "$LOG_FILE"
