# infra/chaos — index
The AC7 kill rig: a local 3-node CockroachDB cluster (decision D3, docs/08) so the
node-kill take is repeatable — free-tier Cloud has no killable nodes.

| item | what it is | read when |
|---|---|---|
| `docker-compose.yml` | 3 nodes, v25.2.2 pinned, ports 26260-26262/8091 | P4 rehearsal |

## Invariants
- Same CockroachDB version as the dev single-node — rigs never drift.
- `make chaos-up` is the only start path (init + vector-index flag live there).
- **Connect with the multi-host string** (`make chaos-conn`), and **kill `recall-crdb-1`** — the
  node the connection is actually on. Recovery is `docker start`; data survives on the named
  volumes, and `make chaos-down` wipes them.
- Why both halves matter (corrected 2026-08-08): the rig used to print a *single-host* string for
  crdb-1 while the documented kill was crdb-2, so the connection never broke, `db.with_retry`'s
  reconnect arm — the thing AC7 exists to demonstrate — never fired, and the take proved nothing.
  Killing crdb-1 against a single-host string breaks it permanently instead, with no failover
  host. Multi-host **and** kill-the-node-you-are-on is the only combination that exercises the code.
