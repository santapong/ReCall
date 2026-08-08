# scripts — index
Operator tooling: branch/worktree helpers and the P0 probe. Nothing here runs in Lambda.

| item | what it is | read when |
|---|---|---|
| `wt.sh` | Worktree helper — new/add/ls/rm/prune (docs/07) | Before parallel work |
| `branches_init.sh` | One-time: create + push `dev` and `test` (via `make branches-init`) | Once, after the setup PR merges |
| `probe.sql` | P0 vector probe, throwaway 4-dim table (via `make probe`) | At P0 |
| `probe_runbook.md` | Human-side P0 steps + pre-probe research and decision tree | At P0, before touching the console |
| `probe_bedrock.py` | Prints the embedding model's output dimension | When Bedrock access lands |
| `close.py` | **AC5's trigger** — `close.py <id> "<resolution>"` scrubs, embeds, resolves. The *only* caller of `write_incident` | Filming close→retrieve, or resolving anything |
| `local_e2e.py` | POSTs an alert through the real handler on the credential-free local stack, then prints `/status` and `/runlog` (`make local-e2e`) | Verifying the wiring without AWS |
| `timetravel.sql` | **AC11** — `AS OF SYSTEM TIME` against a *captured* `cluster_logical_timestamp()` | Filming the time-travel shot |

## Invariants
- Scripts never write to the production schema; `probe.sql` cleans up after itself.
- `close.py` is the human half of "you propose; humans dispose". The diagnosis loop cannot reach
  `write_incident` at all, so if nobody runs this, the incident stays open — by design.
- `timetravel.sql` captures a timestamp *before* the run rather than using a relative `'-10m'`,
  which returns zero rows against a two-minute-old incident — live, on camera. Check
  `gc.ttlseconds` on the target tier before filming.
