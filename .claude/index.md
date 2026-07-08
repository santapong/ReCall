# .claude — index
The executable harness: docs/06 (loop, ODD, subagents) and docs/07 (branches, worktrees) turned into machinery Claude Code actually runs.

| item | what it is | fires |
|---|---|---|
| `settings.json` | hook registration + permission allowlist for the loop's commands | always |
| `hooks/session-start.sh` | web bootstrap (`uv sync`) + the Orient step: WORKLOG tail + phase into context | session start |
| `hooks/stop-verify.sh` | "never end a session red" — blocks stop once on a red fast suite | session stop |
| `skills/session-loop/` | the six-step docs/06 loop + ODD disengagement triggers | `/session-loop` |
| `skills/verify/` | ground truth: ruff + pytest + name-the-AC reporting | `/verify` |
| `skills/record/` | WORKLOG line + registration chain + `[ACn]` commit | `/record` |
| `skills/start-work/` | classify branch, create worktree, own venv (docs/07) | `/start-work` |
| `skills/gate-check/` | phase gate + AC scoreboard audit against evidence | `/gate-check` |
| `agents/worker.md` | the docs/06 file-disjoint worker contract | `Task → worker` |

## Invariants
- Skills and hooks implement docs/06–07; if they drift from the docs, fix both in the same commit.
- Hooks stay fast and silent on success — orientation output is the only chatter.
- The Stop hook must never trap a session the environment can't satisfy (missing venv → exit 0).
