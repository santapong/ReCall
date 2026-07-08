#!/bin/bash
# SessionStart hook — bootstrap + the docs/06 "Orient" step, automated.
# Web sessions: install deps so pytest/ruff work from the first turn.
# All sessions: inject orientation (WORKLOG tail + phase) into context.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  uv sync --quiet
fi

echo "== Recall orientation (docs/06 session loop: orient in <=3 further reads) =="
echo "-- WORKLOG tail (newest first):"
sed -n '2,4p' WORKLOG.md 2>/dev/null || echo "   (no WORKLOG yet)"
echo "-- Phase:"
grep -m1 -E '^- Phase:' CLAUDE.md 2>/dev/null || echo "   (see docs/01 phase table)"
echo "-- Loop: /session-loop to work · /start-work for a new branch+worktree · /verify before every commit · /record to close out."
