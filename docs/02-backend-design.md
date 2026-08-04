# 02 · Backend Design

## Shape

Serverless, one Python package, deliberately not decomposed: **one Lambda** (`ingest_handler`), plus a second (`sleep_cycle_cron`) only if the stretch gate fires. No API gateway layer beyond a Lambda Function URL, no queue, no second data store. Every additional moving part is a part that can fail during the demo.

Architecture is documented as a [C4](https://c4model.com) set in [`docs/diagrams/`](diagrams/) — SVG, no build step. Read them in order; each one zooms into the box the previous one drew.

| | |
|---|---|
| [`c4-context.svg`](diagrams/c4-context.svg) | **L1 · Context** — an on-call engineer and an alerting system on one side, AWS Bedrock on the other |
| [`c4-container.svg`](diagrams/c4-container.svg) | **L2 · Container** — the three deployable pieces: one Lambda, one CockroachDB, one static page |
| [`c4-component.svg`](diagrams/c4-component.svg) | **L3 · Component** — the modules inside the zip and the boundaries `tests/` asserts |

![Recall containers](diagrams/c4-container.svg)

The container view is the one to reach for in review: it shows why "one Lambda" is a decision and not an omission, and it is where the propose-only data path is visible at a glance.

## Runtime DB path — RESOLVED 2026-08-02 · Branch B (decision D2, `docs/08`)

Both branches are viable; the headless-auth question was answered from documentation rather than by the probe. **Branch B is chosen anyway.**

- **Branch A (design as originally written)**: agent tools execute through the managed MCP server's SQL tool. *Verified viable* — the official CockroachDB Claude plugin documents service-account API keys as a Bearer header, explicitly for fully autonomous environments. Not chosen.
- **Branch B — CHOSEN**: runtime hot path = plain Postgres wire protocol via `psycopg` 3, parameterized SQL only, connection string from Cloud Console. The MCP server stays the *development and operations* surface — Claude Code drives schema, seed inspection, and `AS OF SYSTEM TIME` queries through it, on camera — and counts as CockroachDB tool #1 for compliance.

Why B when A works: (a) **AC4 auditability** — the 4-tool manifest maps to 4 SQL statements we own and can show; (b) **no middle service in the node-kill frame** — "the database survived" stays a one-hop claim; (c) production precedent — Zep (arXiv 2501.13956) reports choosing predefined queries over LLM-generated ones for exactly this schema-consistency and hallucination-reduction reason.

**Flip condition: none before submission.** Compliance holds either way (vector index + MCP + ccloud all count). Everything below is branch-agnostic.

## Schema — three memory layers

```sql
-- Episodic memory: every incident, resolved or in-flight
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id STRING UNIQUE,        -- idempotent ingest: same alert twice = same row
    service STRING NOT NULL,
    title STRING NOT NULL,
    description STRING NOT NULL,
    severity STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'open',
    resolution_summary STRING,
    embedding VECTOR(1024),           -- DECISION PENDING PROBE: confirm dim against
                                      -- the actual Bedrock embedding model output
    blame_scrubbed BOOL NOT NULL DEFAULT true,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
CREATE VECTOR INDEX idx_incidents_embedding ON incidents (service, embedding);

-- Semantic memory: runbooks, independent of any one incident
CREATE TABLE runbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service STRING NOT NULL,
    title STRING NOT NULL,
    content STRING NOT NULL,
    embedding VECTOR(1024),
    source_incident_id UUID REFERENCES incidents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE VECTOR INDEX idx_runbooks_embedding ON runbooks (service, embedding);

-- Working memory: what the agent reads/writes mid-incident (AC7's kill test hits this)
CREATE TABLE working_state (
    incident_id UUID PRIMARY KEY REFERENCES incidents(id),
    retrieved_matches JSONB,
    proposed_diagnosis STRING,
    confidence STRING,                -- 'high' | 'low' | 'none' (AC13)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`service` as a prefix column on both vector indexes is a verified CockroachDB pattern: it scopes similarity search per service by default and partitions the index. Retrieval query shape (`<->` = L2 distance, pgvector-compatible):

```sql
SELECT id, title, resolution_summary,
       embedding <-> $2 AS distance
FROM incidents
WHERE service = $1 AND status = 'resolved'
ORDER BY embedding <-> $2
LIMIT 5;
```

**Decay re-rank** happens in Python after fetch: `score = (1 - norm_distance) * exp(-age_days / half_life)`, half-life 90 days. Keep it in code, not SQL — it's tunable and testable there.

Probe note: some mid-2025 sources show vector indexing behind `SET CLUSTER SETTING feature.vector_index.enabled = true`. Check on the fresh cluster; record the answer here.

Pre-probe research (Jul 8, sources in `scripts/probe_runbook.md`): flag confirmed for v25.2+ (C-SPANN, public preview; non-empty tables also need `sql_safe_updates = false` to backfill); **Basic-tier vector-index support is at risk** — test `CREATE VECTOR INDEX` first and use the runbook's fallback tree if blocked; managed MCP documents service-account API keys for headless auth (Branch A becomes possible; Branch B stays the recommended demo shape). Both `DECISION PENDING PROBE` markers remain open until the live cluster answers.

Probe result — **self-hosted** (Aug 4, local single-node v25.2.2, `~/.local/bin/cockroach`, insecure dev node, store `~/.local/share/recall-crdb`): `CREATE VECTOR INDEX` fails until `SET CLUSTER SETTING feature.vector_index.enabled = true`, then the full probe (DDL + index + 5 rows + `<->` top-3) passes → **flag required, works once set**. Any self-hosted rig (including the AC7 3-node chaos rig) must set this flag at cluster init. The **Cloud Basic-tier** answer is still open — runbook step A on cockroachlabs.cloud remains human-side, and the embedding-dimension `DECISION PENDING PROBE` marker stays open until the Bedrock probe answers (the runtime-DB-path marker was resolved 2026-08-02 as Branch B).

## The 4-tool contract (AC4 — this list is closed)

```
search_incidents(query: str, service: str, k: int = 5) -> SearchResult
    Embed query → vector search scoped to service → decay re-rank →
    return matches + confidence label.
    confidence: 'high' | 'low' | 'none' from fixed distance thresholds,
    tuned empirically against the seeded corpus in P1 (AC13).

    SearchResult also carries runbook_ids for the searched service (added
    2026-08-02): without it the agent has no legal way to learn a runbook id,
    and AC3 requires citing a runbook step. This is a field on a return model,
    not a fifth tool — the manifest stays closed at 4.

get_runbook(runbook_id: str) -> Runbook
    Read-only fetch by ID. No search.

propose_diagnosis(incident_id: str, diagnosis: str,
                  cited_incident_ids: list[str]) -> None
    Writes working_state ONLY. cited_incident_ids must be non-empty
    unless confidence == 'none' (AC3). IDs are validated against the DB
    before write — an unknown ID raises, never persists.

write_incident(incident_id: str, resolution_summary: str) -> None
    Close path. Runs the blameless scrub before persisting, then embeds
    the resolution so the very next similar alert can retrieve it (AC5).
```

The agent's system prompt (versioned in `prompts/`) hard-requires: state the confidence label before proposing anything; when `none`, say plainly that no close match exists and stop.

## Data flow → AC mapping

1. Alert POSTs to Function URL → dedupe on `external_id` → insert `incidents` + `working_state`, invoke agent — **AC1**
2. Agent → `search_incidents` — **AC2, AC13**
3. Agent → `propose_diagnosis` with validated citations — **AC3, AC4**
4. Status page polls `working_state` — surface only
5. Close → `write_incident` → scrub → embed → persist — **AC5**, and the next similar alert finds it

## Seed data spec (P1)

- Fictional SaaS **Orbital**, six services: `api-gateway`, `auth`, `billing`, `search`, `notifications`, `db-cluster`.
- ~80 synthetic postmortems, generated by script (`infra/seed/generate.py`), deterministic (fixed RNG seed) so AC2 is reproducible.
- 20 of them are designed pairs: a "historical" incident plus a test alert crafted to match it — that's the AC2 eval set, expected IDs pinned in a fixture.
- Every seeded resolution passes the blameless scrub (generator never emits names).

## Error handling

- **CockroachDB serialization conflicts (SQLSTATE 40001)**: retry with exponential backoff, max 3. Expected under serializable isolation; not an error to surface.
- **Bedrock throttling**: same backoff pattern, max 3, then fail the run visibly — never silently degrade to a cached answer.
- **Embedding failure**: fail the ingest loudly. No fallback to keyword search; a silent quality downgrade would poison AC2.

## Env vars

`CRDB_CONN_STRING` · `BEDROCK_MODEL_ID` · `BEDROCK_EMBED_MODEL_ID` · `AWS_REGION` · `CONFIDENCE_HIGH_MAX_DIST` · `CONFIDENCE_NONE_MIN_DIST` · `DECAY_HALF_LIFE_DAYS` (default 90). `.env.example` committed; secrets never.
