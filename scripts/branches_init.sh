#!/usr/bin/env bash
# One-time bootstrap (docs/07): creates the long-lived `develop` branch from
# origin/main and pushes it. `main` is release-only; day-to-day work happens on
# short-lived prefixed branches (feat/ fix/ test/ docs/ chore/ experiment/), and
# release candidates are cut as release/<name> only when one is needed.
set -euo pipefail

git fetch origin main

b=develop
if git ls-remote --exit-code --heads origin "$b" >/dev/null 2>&1; then
  echo "origin/$b already exists — nothing to do"
elif git show-ref --verify --quiet "refs/heads/$b"; then
  echo "local branch '$b' already exists; refusing to guess — push it yourself if it is correct" >&2
  exit 1
else
  git branch --no-track "$b" origin/main
  git push -u origin "$b"
  echo "created + pushed $b (from origin/main)"
fi

cat <<'EOF'
done. Recommended one-time GitHub settings (manual):
  - protect main: require a PR + green checks (main is release-only and always tagged)
  - develop: require green checks
  - set develop as the default base branch for new pull requests
EOF
