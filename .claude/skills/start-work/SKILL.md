---
name: start-work
description: Start a new Recall work unit on the right branch per docs/07 — classify it (feature/fix/spike/hotfix), name the AC, create the branch + worktree with scripts/wt.sh, set up its venv. Use when beginning any new feature, fix, experiment, or emergency.
---

# Start work (docs/07 branch + worktree flow)

1. **Classify the task:**

   | Type | Base | Merges into | Use for |
   |---|---|---|---|
   | `feature/<slug>` | `dev` | `dev` | new capability advancing an AC |
   | `fix/<slug>` | `dev` | `dev` | bugfix |
   | `spike/<slug>` | anything | **never** | probes/experiments — findings go to WORKLOG/docs, branch deleted |
   | `hotfix/<slug>` | `main` | `main`, then back into `test` + `dev` | demo-day emergency |

2. **Name it** — kebab-case, phase prefix when useful: `feature/p1-seed-corpus`.
   Know the AC before creating the branch; a task with no AC that isn't upkeep
   gets questioned first (docs/06).

3. **Create branch + worktree:**

   ```bash
   scripts/wt.sh new feature/p1-seed-corpus        # base defaults to dev
   cd ../<repo>.worktrees/feature-p1-seed-corpus
   uv sync                                          # every worktree owns its venv
   # copy .env in ONLY if this task needs the DB
   ```

   In a remote/CI session already parked on its own `claude/*` branch, skip the
   worktree and work in place — the branch *naming and flow* still follow docs/07
   (PR into `dev`).

4. **Finish** — push (`git push -u origin <branch>`), PR into `dev` (hotfix →
   `main`) with the AC in the title; after merge:
   `scripts/wt.sh rm <branch> && git branch -d <branch>`.
