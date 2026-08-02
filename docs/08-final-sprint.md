# 08 · Final Sprint Plan — Aug 2 → Aug 18

*Written 2026-08-02 against repo state at `main` (last commit Jul 8). This file supersedes the **dates** in docs/01's phase table only; every AC, spec, and budget in docs/01–07 stands unchanged. Where this file and docs/01 disagree on dates, this file wins.*

## Reality snapshot

- Repo frozen since Jul 8; P0 never ran. WORKLOG's standing `next:` is still the probe.
- Code = contracted stubs (129 lines in `lambda/`, all `NotImplementedError` with AC-mapped docstrings). Structural tests green. Harness operational.
- Original plan: 60h ceiling, ~48h of build remaining. Calendar remaining: 16 days.
- **Deadline in local time: Aug 18 5:00 pm EDT = Aug 19, 04:00 ICT.** Tuesday night Aug 18 (ICT) is real working time. Target submit: Aug 17 night ICT.
- Stretch (sleep-cycle) is dead by its own Jul 26 gate. Do not revisit.

## Research resolutions — 3 of docs/04's 4 verify-flags answered from documentation (2026-08-02)

### 1 · Vector index flag → CONFIRMED, syntax known
`SET CLUSTER SETTING feature.vector_index.enabled = true;` is the real setting (Cockroach Labs blog, Aug 2025; multiple 2025 sources). C-SPANN shipped v25.2+ as the index engine; prefix columns (`(service, embedding)`) are the documented ownership-scoping pattern — our schema already matches it. A fresh 2026 cluster may have it enabled by default; probe records flag-or-no-flag in docs/02 either way.
Sources: cockroachlabs.com/blog/recommendation-engines-cockroachdb · cockroachlabs.com/blog/cspann-real-time-indexing-billions-vectors · docs.langchain.com/oss/python/integrations/vectorstores/cockroachdb

### 2 · Headless MCP → YES, it works. Branch B chosen anyway.
The official CockroachDB Claude plugin repo documents the managed MCP server (`https://cockroachlabs.cloud/mcp`) with **two** auth paths: OAuth 2.1 PKCE (interactive) and **service-account API key as a Bearer header — explicitly intended for fully autonomous environments**. Read-only by default; write needs `mcp:write` consent. `ccloud` also runs headless: `ccloud auth login --no-redirect` or service-account bearer, every command supports `-o json`.
So Branch A is *viable*. **Decision D2: Branch B regardless** — runtime hot path is `psycopg` with parameterized SQL. Reasons: (a) AC4 auditability — the 4-tool manifest maps to 4 SQL statements we own; (b) no middle service in the node-kill frame — "the database survived" stays a one-hop claim; (c) Zep (arXiv 2501.13956 §appendix) reports choosing predefined queries over LLM-generated ones precisely for schema consistency + hallucination reduction — production precedent for the same architecture. MCP stays the on-camera dev/ops surface (schema, seed inspection, `AS OF SYSTEM TIME` queries via Claude Code) and compliance tool #1.
Flip condition: none for the hackathon. Revisit only post-submission.
Source: github.com/cockroachdb/claude-plugin · cockroachlabs.com/blog/cockroachdb-ai-agents-managed-mcp-server

Claude Code config to paste at P0 (service-account variant):
```json
{ "mcpServers": { "cockroachdb-cloud": {
    "type": "http",
    "url": "https://cockroachlabs.cloud/mcp",
    "headers": { "mcp-cluster-id": "{cluster-id}",
                  "Authorization": "Bearer {service-account-api-key}" } } } }
```

### 3 · Embedding dimension → RESOLVED: `VECTOR(1024)`
Titan Text Embeddings V2, model ID **`amazon.titan-embed-text-v2:0`** (AWS official docs): output 1,024 default, 512/256 optional; 8,192-token input; request body supports `dimensions` and `normalize`. **Always send `"normalize": true`** — unit vectors make L2 (`<->`) and cosine rank identically, so our `<->` queries are metric-safe.
Actions folded into P0/P1: (a) `scripts/probe_bedrock.py` body gains `"dimensions": 1024, "normalize": True`; (b) schema's `DECISION PENDING PROBE` comment resolves to a `-- verified 2026-08-0X: titan-embed-text-v2:0 → 1024` line the day the probe prints it; (c) model ID recorded in README per docs/04 version policy.
Source: docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html (+ model card page with the exact boto3 body)

### 4 · Free-tier topology → still probe-time
Unchanged: assume no killable Cloud nodes; chaos rig = local `docker-compose` 3-node cluster per docs/04 R1. Probe confirms and records.

## Decisions closed today (Rule B8)

| # | Decision | Call | Flip |
|---|---|---|---|
| D1 | `VECTOR(n)` | **1024**, `normalize:true` everywhere | probe prints a different length (won't) |
| D2 | Runtime DB path | **Branch B** — psycopg hot path, MCP as dev/ops + compliance | none pre-submission |
| D3 | Chaos rig | local 3-node docker-compose | probe finds killable Cloud nodes (still prefer local — repeatable takes) |
| D4 | Agent model | Pick a Claude model in the Bedrock console at P0; prefer the fastest/cheapest Claude that passes AC3 in P2; **record the verified ID in README, never in docs from memory** (docs/04 policy) | diagnosis quality fails AC3 in P2 → step up one tier |

## Compressed schedule

Weekends carry the load: **Aug 8–9 and Aug 15–16 are the two big blocks (~10h each).** Weeknights ≈ 1–1.5h.

| Dates (ICT) | Phase | Budget | Exit test | ACs |
|---|---|---|---|---|
| **Aug 2 (today)** | P0 · Probe | 1h | `make probe` returns *payment webhooks timing out* first; MCP tools listed in Claude Code; Bedrock access requested; WORKLOG entry | — |
| Aug 3–7 | P1 · Memory | 10h | `uv run pytest tests/test_retrieval_eval.py` → ≥18/20 top-3; planted incident retrieved from CLI | AC2, AC13 |
| Aug 8–12 | P2 · Agent loop | 16h | `curl` alert → diagnosis citing real incident ID + runbook step; `working_state` row visible; zero invented IDs across the 20-alert set | AC1, AC3, AC4, AC13 |
| Aug 13–14 | P3 · Surface | 4h | status page shows live incident + memory hits; demo script reads ≤3:00 | — |
| Aug 15–16 | P4 · Resilience | 9h | recorded node-kill: in-flight diagnosis completes, row counts identical before/after; `AS OF SYSTEM TIME` query on camera; close→retrieve take | AC5, AC7, AC9, AC11 |
| Aug 17–18 | P5 · Ship | 8h | video ≤3:00 uploaded; Devpost confirmation email exists | AC8, AC10, AC12 |

## Task breakdown

### P0 — today, one sitting (~60–90 min)
1. Cluster: console or `ccloud cluster create serverless recall us-east-1 --cloud AWS -o json`. Region **us-east-1** (Titan V2 + Bedrock both live there).
2. `export CRDB_CONN_STRING=…` (from console / `ccloud cluster connection-string`).
3. `make probe`. If `CREATE VECTOR INDEX` fails → run the cluster setting, retry, **record which** in docs/02.
4. Managed MCP: create service-account API key → paste config block above into Claude Code → `/mcp` shows tools. One read query on camera-quality later; today just prove auth.
5. Bedrock console: enable model access — Titan Text Embeddings V2 (Amazon models usually instant) + chosen Claude model (may queue — this is why it's step 5 today, not next week).
6. When granted: `uv run python scripts/probe_bedrock.py amazon.titan-embed-text-v2:0` → prints 1024 → update `schema.sql`, `0001_init.sql`, docs/02 marker, README model IDs — same commit.
7. WORKLOG entry, newest-first.

### P1 — memory foundation (10h)
- `make migrate` against the live cluster (0001_init).
- Implement `infra/seed/generate.py` per docs/02 spec: 6 services, ~80 postmortems, 20 designed alert-pairs, fixed `RNG_SEED`, scrub-shared name list. (~3h)
- Embedding pass: batch Titan calls (`normalize:true`), write vectors. Budget note: 80 docs ≈ trivial token cost. (~1.5h)
- `tools.search_incidents`: embed → `<->` query (service-scoped, resolved-only) → decay re-rank in Python → confidence label. `tools.get_runbook`. (~2.5h)
- Tune `CONF_HIGH_MAX_DIST` / `CONF_NONE_MIN_DIST` against the corpus; freeze; AC2 eval as pytest fixture with pinned expected IDs. (~2h)
- Tag `p1-memory` when 18/20 green. (~1h slack)

### P2 — agent loop (16h)
- `ingest_handler`: Function URL event → dedupe on `external_id` → insert incident + working_state → `run_agent`. (~2h)
- `agent.py`: Bedrock Converse loop, manual dispatch over `TOOL_MANIFEST`, ThrottlingException retry via `with_retry`, hard stop states: diagnosis proposed / confidence-none stated. Target ~50 lines; ZERO SQL (test greps). (~4h)
- `propose_diagnosis` (validate cited IDs against DB, working_state only) + `write_incident` (scrub → embed → persist) + `scrub.py` name list. (~3h)
- `prompts/system.md`: confidence-first contract, cite-or-stop, AC13 language. (~1h)
- Lambda deploy path: `make deploy` + psycopg bundling into the zip (the P2 wiring the Makefile comment promises), Function URL created, env vars set. (~3h)
- End-to-end: `curl` all 20 alerts, assert AC1 latency + AC3 zero-invented-IDs. Tag `p2-agent`. (~3h)

### P3 — surface (4h)
- `status_page/`: static HTML + vanilla JS polling `working_state` (read path: tiny Lambda GET or direct — keep to the 4h, camera is the audience).
- Demo script v1 written and read aloud ≤3:00.

### P4 — resilience (9h)
- docker-compose 3-node local cluster; migrate + seed subset into it for the kill scene.
- Rehearse: alert in-flight → `docker stop` node 2 → diagnosis completes → `SELECT count(*)` before/after identical. Record until one clean take. (AC7)
- `AS OF SYSTEM TIME '-10m'` working_state query on camera (AC11).
- Close incident A → fire similar alert → A retrieved, on camera (AC5).
- README stranger pass: clean-machine clone → running ≤15 min (AC9, best-effort if time bites).

### P5 — ship (8h)
- Record remaining shots, cut to ≤3:00, upload.
- Devpost form: repo URL, demo URL, video, CRDB tools list (vector index + managed MCP + ccloud), AWS list (Bedrock + Lambda).
- Confirmation email screenshot into `docs/plans/`. Done.

## Video shot list (cut order)

1. Cold open: alert curls in, agent diagnoses citing an incident ID — 25s (AC1/AC3)
2. Amnesia A/B: same alert, memory off vs on, split screen — 30s (AC12)
3. Node-kill: diagnosis in flight, node dies, answer lands, counts match — 35s (AC7)
4. Time-travel: "what did memory believe at 02:14" `AS OF SYSTEM TIME` — 20s (AC11)
5. Close→retrieve: resolve A, next alert finds A — 20s (AC5)
6. Memory-layer diagram + why-CockroachDB table from README — 15s (AC6)
7. Outro: repo, one-line vision — 10s. Total ≈ 2:35, buffer to 3:00.

## Risks

| Risk | Likelihood | Response |
|---|---|---|
| Claude-on-Bedrock access approval lags | med | Titan usually instant → P1 unblocked regardless; agent floor holds with **any** Bedrock model (rules allow any); Lambda alone already satisfies AWS compliance — docs/01 |
| Free-tier vector index gated/unavailable | low | Flag documented above; worst case: dedicated trial cluster or local compose for dev + Cloud for demo data path |
| Weekend Aug 8–9 lost (life) | med | P2 spills into Aug 13–14 nights; P3 collapses to 2h (page is polling JSON — cuttable to near-zero); AC10 already optional |
| Thai-hours deadline confusion | — | Submit target Aug 17 night ICT; hard wall Aug 19 04:00 ICT. Calendar entry now. |
| Scope creep (new ideas mid-sprint) | known pattern | This file is the scope. New ideas → one WORKLOG line, post-Aug-18 list. |

## Working agreement
Every session ends with a WORKLOG line (newest-first, `next:` named). Weekly runnable increment = git tag. Thresholds frozen once tuned (docs/05). This plan is not edited after Aug 3 except to strike completed phases.
