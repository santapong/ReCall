# infra/chaos — index
The AC7 kill rig: a local 3-node CockroachDB cluster (decision D3, docs/08) so the
node-kill take is repeatable — free-tier Cloud has no killable nodes.

| item | what it is | read when |
|---|---|---|
| `docker-compose.yml` | 3 nodes, v25.2.2 pinned, ports 26260-26262/8091 | P4 rehearsal |

## Invariants
- Same CockroachDB version as the dev single-node — rigs never drift.
- `make chaos-up` is the only start path (init + vector-index flag live there).
- The kill is `docker stop recall-crdb-2`; recovery is `docker start` — data
  survives on the named volumes. `make chaos-down` wipes them.
