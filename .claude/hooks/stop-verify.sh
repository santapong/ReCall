#!/bin/bash
# Stop hook — docs/06: "Never end a session red." If the fast suite fails, block
# the stop once with the failure tail so it gets fixed or recorded in WORKLOG.
# Deliberately silent and permissive when the environment isn't bootstrapped —
# a doc-only session must never be trapped by missing deps.
set -uo pipefail

input="$(cat || true)"
# stop_hook_active=true means we already blocked once this cycle — let it through.
if printf '%s' "$input" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || exit 0
command -v uv >/dev/null 2>&1 || exit 0
[ -d .venv ] || exit 0

out="$(uv run --no-sync pytest -q 2>&1)" && exit 0

{
  echo "Fast suite is RED — docs/06 hard line: never end a session red."
  echo "Fix it now, or record the failure and the open question as a WORKLOG line, then stop."
  echo "--- pytest tail ---"
  printf '%s\n' "$out" | tail -n 15
} >&2
exit 2
