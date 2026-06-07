#!/usr/bin/env bash
# deploy.sh — rsync the add-on to HA (when SSH is available)
# Usage: ./deploy.sh [ha-host]
set -euo pipefail

HA_HOST="${1:-ha-green}"
ADDON_DEST="/addons/claude_bridge"

echo "→ Deploying to ${HA_HOST}:${ADDON_DEST}"
ssh "${HA_HOST}" "mkdir -p ${ADDON_DEST}"

rsync -avz --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' --exclude '.git' \
  "$(dirname "$0")/claude_bridge/" "${HA_HOST}:${ADDON_DEST}/"

echo "→ Done. Rebuild: ssh ${HA_HOST} 'ha addons rebuild local_claude_bridge'"
echo "→ Logs:    ssh ${HA_HOST} 'ha addons logs local_claude_bridge'"
