# docs — index
The operational design pack: consolidated truth for why, what, and how. Where a doc and reality disagree, fix the doc in the same commit (docs/05 clause).

| item | what it is | read when |
|---|---|---|
| `01-objective-roadmap.md` | Objective, phases + gates, AC1–AC13, parked list | First, always |
| `02-backend-design.md` | Schema, 4-tool contract, data flow, seed spec | Before any backend code |
| `03-frontend-design.md` | The one status page | Only at P3 (Aug 13–14) |
| `04-tech-stack.md` | Every pick + why, the four verify flags | Before adding any dependency |
| `05-code-patterns.md` | Repo layout, module boundaries, testing, cadence | Before first commit |
| `06-claude-code-harness.md` | Session loop, doc policy, ODD, subagents | Every session |
| `07-branching-worktrees.md` | Branch roles, merge flow, worktree layout + helper | Before creating any branch/worktree |
| `08-final-sprint.md` | Aug 2→18 compressed schedule, closed decisions D1–D4, shot list | Every session until submission |
| `plans/` | Source artifacts (read-only history) | Only to settle a "where did this come from" |

## Invariants
- The read-order table in CLAUDE.md mirrors this folder — update both in the same commit.
- Numbered docs are operational truth; `plans/` is history and never edited.
- `08` supersedes `01`'s **dates** only. Every AC, spec, and budget in `01`–`07` stands unchanged.
