#!/bin/bash
# Section 11 AI Coach — Session Start Hook
# Installs Python dependencies for sync.py

set -euo pipefail

# Only run full setup in remote Claude Code environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "🚴 Intervals ICU Coach — setting up environment..."

pip install --quiet requests

echo "✅ Dependencies ready"
