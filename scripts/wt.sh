#!/usr/bin/env bash
# Worktree helper — the interface described in docs/07-branching-worktrees.md.
# Worktrees live as siblings of the repo: ../<repo>.worktrees/<branch-with-dashes>
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
REPO="$(basename "$ROOT")"
WT_ROOT="$(dirname "$ROOT")/${REPO}.worktrees"

usage() {
  cat <<EOF
usage: scripts/wt.sh <command>

  new <branch> [base]   create branch off [base] (default: develop, else main) + worktree
  add <branch>          worktree for an existing branch (e.g. develop, main)
  ls                    list worktrees
  rm <branch>           remove the branch's worktree (the branch survives)
  prune                 drop stale worktree registrations
EOF
  exit 1
}

dir_for() { printf '%s/%s\n' "$WT_ROOT" "${1//\//-}"; }

default_base() {
  if git show-ref --verify --quiet refs/heads/develop; then echo develop
  elif git ls-remote --exit-code --heads origin develop >/dev/null 2>&1; then echo origin/develop
  else echo main
  fi
}

post_create() {
  cat <<EOF
worktree ready: $1
next:
  cd $1
  uv sync          # every worktree gets its own venv
  # copy .env in only if this task needs the DB
EOF
}

cmd="${1:-}"; [ -n "$cmd" ] || usage
case "$cmd" in
  new)
    branch="${2:?usage: wt.sh new <branch> [base]}"
    base="${3:-$(default_base)}"
    dir="$(dir_for "$branch")"
    mkdir -p "$WT_ROOT"
    git worktree add -b "$branch" "$dir" "$base"
    post_create "$dir"
    ;;
  add)
    branch="${2:?usage: wt.sh add <branch>}"
    dir="$(dir_for "$branch")"
    mkdir -p "$WT_ROOT"
    if ! git show-ref --verify --quiet "refs/heads/$branch"; then
      git fetch origin "$branch"
      git branch --track "$branch" "origin/$branch"
    fi
    git worktree add "$dir" "$branch"
    post_create "$dir"
    ;;
  ls)
    git worktree list
    ;;
  rm)
    branch="${2:?usage: wt.sh rm <branch>}"
    dir="$(dir_for "$branch")"
    git worktree remove "$dir"
    echo "removed $dir (branch '$branch' still exists — 'git branch -d $branch' when merged)"
    ;;
  prune)
    git worktree prune -v
    ;;
  *)
    usage
    ;;
esac
