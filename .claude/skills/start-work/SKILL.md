---
name: start-work
description: Start a new Recall work unit on the right branch per docs/07 — classify it (feat/fix/test/docs/chore/experiment/hotfix), name the AC, create the branch + worktree with scripts/wt.sh, set up its venv. Use when beginning any new feature, fix, test, doc change, experiment, or emergency.
---

# Start work (docs/07 branch + worktree flow)

1. **Classify the task.** One question decides it: *what would a reader of the
   history call this change?*

   | Type | Base | Merges into | Use for |
   |---|---|---|---|
   | `feat/<slug>` | `develop` | `develop` | new capability advancing an AC |
   | `fix/<slug>` | `develop` | `develop` | bugfix |
   | `test/<slug>` | `develop` | `develop` | test-only work: eval harnesses, fixtures, CI rigs |
   | `docs/<slug>` | `develop` | `develop` | documentation, diagrams, changelog — no code |
   | `chore/<slug>` | `develop` | `develop` | tooling, dependencies, CI config, repo governance |
   | `experiment/<slug>` | anything | **never** | probes/spikes — findings go to WORKLOG/docs, branch deleted |
   | `release/<name>` | `develop` | `main` (tagged), then back into `develop` | release candidate: full suite, AC2 eval, chaos rehearsal |
   | `hotfix/<slug>` | `main` | `main` (tagged), then back into `develop` | demo-day emergency |

   `main` is release-only and never receives a direct commit.

2. **Name it** — kebab-case, phase prefix when useful: `feat/p1-seed-corpus`.
   Know the AC before creating the branch; a task with no AC that isn't upkeep
   gets questioned first (docs/06).

3. **Create branch + worktree:**

   ```bash
   scripts/wt.sh new feat/p1-seed-corpus            # base defaults to develop
   cd ../<repo>.worktrees/feat-p1-seed-corpus
   uv sync                                          # every worktree owns its venv
   # copy .env in ONLY if this task needs the DB
   ```

   In a remote/CI session already parked on its own `claude/*` branch, skip the
   worktree and work in place — the branch *naming and flow* still follow docs/07
   (PR into `develop`).

4. **Finish** — push (`git push -u origin <branch>`), PR into `develop`
   (hotfix → `main`) with the AC in the title; after merge:
   `scripts/wt.sh rm <branch> && git branch -d <branch>`.
