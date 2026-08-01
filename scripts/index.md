# scripts — index
Operator tooling: branch/worktree helpers and the P0 probe. Nothing here runs in Lambda.

| item | what it is | read when |
|---|---|---|
| `wt.sh` | Worktree helper — new/add/ls/rm/prune (docs/07) | Before parallel work |
| `branches_init.sh` | One-time: create + push `dev` and `test` (via `make branches-init`) | Once, after the setup PR merges |
| `probe.sql` | P0 vector probe, throwaway 4-dim table (via `make probe`) | At P0 |
| `probe_runbook.md` | Human-side P0 steps + pre-probe research and decision tree | At P0, before touching the console |
| `probe_bedrock.py` | Prints the embedding model's output dimension | When Bedrock access lands |

## Invariants
- Scripts never write to the production schema; `probe.sql` cleans up after itself.
