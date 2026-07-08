#!/usr/bin/env bash
# One-time bootstrap after the setup PR merges to main (docs/07):
# creates the long-lived dev and test branches from origin/main and pushes them.
set -euo pipefail

git fetch origin main

for b in dev test; do
  if git ls-remote --exit-code --heads origin "$b" >/dev/null 2>&1; then
    echo "origin/$b already exists — skipping"
    continue
  fi
  if git show-ref --verify --quiet "refs/heads/$b"; then
    echo "local branch '$b' already exists; refusing to guess — push it yourself if it is correct" >&2
    exit 1
  fi
  git branch --no-track "$b" origin/main
  git push -u origin "$b"
  echo "created + pushed $b (from origin/main)"
done

cat <<'EOF'
done. Recommended one-time GitHub settings (manual):
  - protect main and test: require a PR + green checks
  - dev: require green checks
EOF
