<div align="center">

# Recall

### An on-call agent that cannot invent an incident. <br/>Not because the prompt forbids it — because the write path refuses it.

[![CI](https://github.com/santapong/ReCall/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/santapong/ReCall/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![uv](https://img.shields.io/badge/deps-uv-261230?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-P2%20·%20built%2C%20awaiting%20cloud%20creds-e6a53f)](docs/08-final-sprint.md)

**CockroachDB × AWS hackathon entry** · built solo, in the open · submission target **Aug 17, 2026**

[The problem](#the-problem) ·
[The guarantee](#the-guarantee--structural-not-instructional) ·
[Who it's for](#who-its-for) ·
[How it works](#how-it-works) ·
[Architecture](#architecture) ·
[Memory design](#memory-design--three-layers) ·
[What we don't claim](#what-we-dont-claim) ·
[Why CockroachDB](#why-cockroachdb) ·
[Quickstart](#quickstart) ·
[Roadmap](#roadmap)

</div>

---

> **Status — Aug 4.** All application code is built and tested: the 4-tool memory surface
> (read *and* write sides), the Bedrock Converse loop, ingest + status + runlog endpoints, the
> status page, the seed loader, the AC2 eval harness, the `agent_runs` decision log, a corpus of
> 10 real public postmortems, and a rehearsed 3-node kill rig. What has not yet happened is the
> first *live* run — cloud credentials (CockroachDB Cloud + Bedrock) are the remaining gate.
> 102 tests green, the DB-backed ones running in CI against a real single-node CockroachDB (now on PRs too, so the invariants below are enforced where they break). Changes are logged in [`CHANGELOG.md`](CHANGELOG.md).

## The problem

An LLM asked to diagnose a production incident will always produce an answer. That is the problem.

The largest published study of the failure mode — [1,675 agent runs across five models on
OpenRCA](https://arxiv.org/abs/2602.09937) (Feb 2026) — found the two dominant failure modes are
**hallucinated data interpretation** and **incomplete exploration**, and that they *"persist across
all models regardless of capability tier."* Its conclusion is the uncomfortable one: **"prompt
engineering alone cannot resolve the dominant pitfalls."** Grafana's incident-agent team reached the
same place from the opposite direction — *["structural enforcement beats instructions. Harness gates
outperform 'you MUST' in
prompts."](https://medium.com/grafana-labs/inside-the-harness-how-grafana-assistant-investigates-incidents-9a982b8ff01d)*

At 2 a.m. this is not an abstraction. A confident, ungrounded root cause sends the on-call engineer
down a wrong path, and it is *more* expensive than no answer at all, because it is credible.

Underneath it sits the ordinary rot: tribal knowledge lives in senior engineers' heads and dies in
unread postmortems. The same failure takes four hours to root-cause twice. Diagnosis speed is really
a function of who answers the page. The knowledge isn't missing — it's unreachable at the moment it
matters, so the model fills the gap with fluent invention.

**Recall's answer is not a better prompt.** The agent gets exactly four tools and no escape hatches;
every incident ID it cites is checked against the database *before* the write; an uncited diagnosis
is legal only on the branch where the agent has already said "I don't know." The honesty is a
property of the code path, not of the model's good behaviour on the day.

## The guarantee — structural, not instructional

Four invariants. None of them are honour-system, and each fails CI if broken — including on
pull requests, where the full DB-backed suite runs against a real cluster.

| Invariant | Enforced by | Fails how |
|---|---|---|
| **The agent cannot cite an incident it did not retrieve** | `propose_diagnosis` validates every `cited_incident_ids` entry against *this run's own* `working_state.retrieved_matches` — persisted by the loop, not the model, so it cannot be forged from inside the conversation | `LookupError` — the write never happens; the error goes back to the model in-band so it can correct itself, and lands in `agent_runs` as an `error` row |
| **The agent cannot bluff when memory is empty** | `search_incidents` returns a confidence label from frozen distance thresholds; an empty `cited_incident_ids` is accepted *only* when confidence is `none` | `ValueError` — a diagnosis with no citations on a `high`/`low` branch is refused, not logged and shipped |
| **The agent cannot reach anything but memory** | `TOOL_MANIFEST` is closed at four tools — no raw SQL, no execute, no shell | [`tests/test_manifest.py`](tests/test_manifest.py) fails on a fifth tool; [`tests/test_module_boundaries.py`](tests/test_module_boundaries.py) fails if `agent.py` imports psycopg or contains SQL |
| **The agent cannot close an incident** | `write_incident` is filtered out of the `toolConfig` the diagnosis loop sends, so the model is never offered it, and `_dispatch` refuses it outright if a spec ever drifts back in | `ValueError` back to the model, an `error` row in `agent_runs`, and no write. [`tests/test_agent_loop.py`](tests/test_agent_loop.py) asserts the tool is absent from every Converse call |

The manifest is, deliberately, **propose-only**: Recall never executes a fix. It writes a
diagnosis into working memory and stops. That is structural, not a prompt instruction — the
diagnosis loop is not given the write tool at all, and the close path
([`scripts/close.py`](scripts/close.py)) is a human-run script with no path from the model to it.

This is the part that is hard to retrofit. Adding memory to an agent is a weekend; making its
answers structurally refuse to exceed their evidence is the thing that decides whether an on-call
engineer trusts it at 2 a.m.

### Access control — the database enforces it too

The same posture holds one layer down. The Lambda connects as a dedicated `recall_app` role
([`infra/migrations/0003_app_role.sql`](infra/migrations/0003_app_role.sql)) that can read memory,
write incidents and working state, and append to the decision log — and nothing else: **no DELETE
on any table, no DDL, and no write access to `runbooks`** (semantic memory changes only through the
seed/ops path, never through the agent's runtime). So even if every application-level guard failed
at once, the blast radius of a compromised agent session is bounded by the database's own grants —
it could not drop a table, erase history, or rewrite a runbook.

The grants are exercised, not asserted: [`tests/test_app_role.py`](tests/test_app_role.py) opens a
real connection *as* `recall_app` and proves each property. Writing it is what found the two holes
that made the paragraph above untrue until now — the role had no `CONNECT`/`USAGE` and so could
never have connected at all, and it inherited `CREATE` from the `public` pseudo-role, so "no DDL"
was false.

### What we don't harden, and why

The demo's ingress is deliberately thin, and it is better to name that than to let a Production
Readiness reviewer find it:

- **Reads are public by design.** `GET /status` and `/runlog` are unauthenticated so the status
  page — a static file with no backend — can poll them on camera. Anyone with the Function URL can
  read every incident and every decision trace. The corpus is synthetic; a real deployment would
  put this behind the same auth as the rest of the on-call tooling.
- **Ingest is a shared secret in a plaintext env var**, not Secrets Manager or SigV4. It bounds
  casual abuse of a URL that spends Bedrock tokens; it is not an identity system.
- **Blast radius is capped by reserved concurrency** (5), set by `make deploy-config`, so a loop or
  a scraper cannot run up an unbounded bill.
- **No WAF, no per-IP rate limit, no request signing.** Out of scope for a hackathon entry with a
  public demo URL and a fixed spend ceiling.

## Who it's for

- **On-call engineers** — the diagnosis reaches them seconds after the page, grounded in what
  actually fixed this failure before, with an honest confidence label instead of a confident guess.
- **SRE and platform teams** — institutional memory stops depending on who happens to still be on
  the team; the blameless scrubber keeps names out of the record by construction.
- **Engineering leaders** — postmortems become an asset with compounding returns rather than
  write-only documents, and `AS OF SYSTEM TIME` gives audits exactly what memory believed
  mid-incident.

## How it works

<p align="center"><img src="docs/diagrams/c4-context.svg" alt="C4 Level 1 — system context: an on-call engineer and an alerting system interact with Recall, which depends on AWS Bedrock" width="100%"></p>

1. An alert POSTs to a Lambda Function URL; ingest is idempotent (same alert twice = same incident).
2. The agent embeds the alert and searches CockroachDB's **distributed vector index** for the closest
   past incidents at the fictional SaaS "Orbital" — scoped per service, decay-ranked so fresh
   incidents outrank stale ones.
3. It proposes a diagnosis **grounded in a real past resolution**, citing real incident IDs and a real
   runbook step — or, when nothing is close enough, says so plainly instead of guessing. An invented
   ID doesn't just violate the prompt; the write path rejects it before it can persist.
4. On close, the resolution is scrubbed of names and written back — so the *very next* similar alert
   retrieves it.
5. Every step of that run is appended to `agent_runs`, in order, with latency and token cost — so the
   diagnosis can be replayed after the fact instead of taken on faith.

**Signature demo:** hand the agent an alert nothing in memory matches. It states `confidence: none`,
says so plainly, and stops — no citation, no guess, no fluent invention. Then force a fabricated
incident ID into the write path and watch it bounce, on camera, into the decision log as an `error`
row. The node-kill take follows: kill a database node mid-diagnosis, the in-flight answer completes,
row counts stay identical, the incident clock never stops.

## Architecture

Documented as a [C4](https://c4model.com) set — hand-authored SVG in [`docs/diagrams/`](docs/diagrams),
no build step and no diagram toolchain to install. Each level zooms into the box the previous one drew.

### Containers — the three deployable pieces

<p align="center"><img src="docs/diagrams/c4-container.svg" alt="C4 Level 2 — containers: one AWS Lambda, one CockroachDB cluster, one static status page polling the Lambda" width="100%"></p>

One Lambda, one database, one static page. That's the whole system, and the sparseness is a decision:
every additional moving part is a part that can fail during a live demo. The status page polls the
Lambda's read-only `GET /status`; its `GET /health` row count is what's on camera during the node kill.

### Components — the boundaries the test suite enforces

<p align="center"><img src="docs/diagrams/c4-component.svg" alt="C4 Level 3 — components inside the Lambda: ingest_handler, agent, tools, db, embed, scrub, and the enforced boundaries between them" width="100%"></p>

The amber boxes are the invariants the pitch rests on, and none of them are honour-system: `agent.py`
importing psycopg, an `INSERT` outside `tools.py`, or a fifth tool in the manifest each fail
[`tests/test_module_boundaries.py`](tests/test_module_boundaries.py) and
[`tests/test_manifest.py`](tests/test_manifest.py) in CI.

There is deliberately no L4 code-level diagram — the code *is* the L4, and a diagram duplicating it
would rot the first time someone renamed a function.

## Memory design — three layers

| Layer | Table | What it holds | Written by |
|---|---|---|---|
| **Episodic** | `incidents` | Every incident ever, resolved or in-flight, with embeddings | ingest + close path |
| **Semantic** | `runbooks` | Distilled how-to knowledge, independent of any one incident | seed loader |
| **Working** | `working_state` | What the agent believes about the *active* incident — retrieved matches, proposed diagnosis, confidence | the agent loop |

Schema: [`infra/schema.sql`](infra/schema.sql). Retrieval is a service-scoped `<->` vector query with a
decay re-rank in Python (`score = (1 − norm_distance) · exp(−age_days / half_life)`), so the ranking
is tunable and unit-testable.

### And one table that isn't memory

`agent_runs` is the **replayable decision log** ([`0002`](infra/migrations/0002_agent_runs.sql)): one
row per step of a run — model turn or tool call — in execution order, with latency, token counts,
outcome, and the confidence label that was live at the time. `ORDER BY run_id, seq` replays the exact
interleaving the loop executed. Read it with `GET /runlog?incident_id=…`.

The three memory tables say what the agent *believed*. This one says what it *did*, what it cost, and
where it was refused — a rejected citation is an `error` row, which makes it the most interesting
line in the log. Logging is best-effort by explicit decision: telemetry that can fail a diagnosis is
worse than no telemetry, so `tools.log_step` swallows and prints rather than raising. The ADR and its
flip condition are in the docstring; a test asserts a diagnosis survives an unreachable log.

## The agent's contract

The whole surface, four tools, no escape hatches. The guarantees are [above](#the-guarantee--structural-not-instructional);
this is what each one does.

| Tool | Does | Guarantee |
|---|---|---|
| `search_incidents` | vector search + decay re-rank | returns an explicit confidence label: `high` / `low` / `none` |
| `get_runbook` | fetch one runbook by ID | read-only, no search — IDs come from search results only |
| `propose_diagnosis` | record the diagnosis | writes *working memory only*; cited IDs validated against the DB — an unknown ID raises, never persists |
| `write_incident` | close + write back the fix | blameless scrub first: names, @handles, emails never persist |

## What we don't claim

Three things a skeptical reader should have already thought, answered plainly. Pretending they
aren't there is how a demo stops being credible.

**"Similar past incidents" is not a new feature.** incident.io, PagerDuty, ServiceNow, Atlassian and
Rootly all ship it, and [Azure's SRE Agent](https://learn.microsoft.com/en-us/azure/sre-agent/memory)
went GA in April 2026 with a near-identical three-source memory design. Recall is not claiming to
have invented incident memory. It is claiming that *what the agent is structurally prevented from
doing with that memory* is the part that decides whether it gets trusted — and that part is
consistently the thing that gets bolted on last.

**Vector search is a contested choice.** incident.io, who run this at real scale,
[evaluated embeddings and moved away from them](https://www.zenml.io/llmops-database/ai-powered-incident-response-system-with-multi-agent-investigation)
for text similarity plus LLM reranking, because *"vector embeddings presented significant debugging
challenges."* That critique is correct and it is the reason retrieval here is observable by
construction: `decay_score` is a pure function with an injectable clock and unit tests, raw distances
ride on every `Match`, every retrieval is persisted to `working_state`, and `AS OF SYSTEM TIME` can
replay what was retrieved at any past instant. If a rank looks wrong you can read exactly why. That
is the debuggability they said embeddings cost them.

**"Your incident memory dies with your infrastructure" is weaker than it sounds.** The principle is
canonical — the Google SRE Book warns against
[depending on the software you are trying to fix](https://sre.google/sre-book/managing-incidents/) —
and Atlassian's April 2022 outage took Jira, Confluence, Opsgenie *and* Statuspage from 775 customers
at once. But most teams' postmortems live in third-party SaaS in a different failure domain: during
the AWS us-east-1 outage of Oct 2025, [incident.io stayed up](https://incident.io/blog/service-disruption-october-20th-2025)
and customers kept their incident history. The honest version of the claim is **correlation and
concentration** — your prod and your tooling in the same region, or your wiki and your on-call tool
behind one vendor — not co-location. The node-kill demo proves survivability under node loss. It
does not prove that everyone's current setup is broken.

## Why CockroachDB

| The system needs | CockroachDB delivers |
|---|---|
| Semantic search over incidents | Native `VECTOR` type + distributed vector index (C-SPANN), scoped per service by a prefix column |
| "What did memory believe at 02:14?" | `AS OF SYSTEM TIME` time-travel reads over `working_state` and `agent_runs` |
| A boring, auditable data path | Postgres wire protocol — plain parameterized SQL via psycopg 3, no ORM. Four tools map to four statements you can read |
| Memory that survives node loss mid-diagnosis | Distributed, replicated SQL — kill 1 of 3 nodes, zero committed rows lost (rig rehearsed: [`infra/chaos/`](infra/chaos/index.md)) |

One database for episodic memory, semantic memory, working state, the decision log, *and* the vector
index. The alternative shape — Postgres plus a vector store plus a metrics backend — is three systems
to keep consistent and three things that can fail mid-incident.

## Tech stack

| Layer | Pick | Why |
|---|---|---|
| Agent | Claude on **AWS Bedrock** (Converse API), custom loop in [`lambda/agent.py`](lambda/agent.py) | full control of the 4-tool manifest; confidence branching stays visible; invented IDs bounce off the write path |
| Embeddings | Bedrock Titan V2, 1024-d, `normalize:true` always | same platform, same credential, no second vendor; unit vectors keep `<->` metric-safe |
| Ingest | **AWS Lambda** + Function URL (POST ingest, GET `/status` · `/health` · `/runlog`) | one URL, zero gateway config, fewest moving parts on demo day |
| Database | **CockroachDB** + distributed vector index | memory, decision log and vector index in one system — see table above |
| Frontend | one static HTML page, vanilla JS ([`status_page/`](status_page/index.md)) | the audience is a camera; build risk ≈ 0 |
| Tooling | Python 3.12 · uv · psycopg 3 · pydantic · pytest · ruff | boring wins; every pick documented in [`docs/04`](docs/04-tech-stack.md) |

## Quickstart

```bash
git clone https://github.com/santapong/ReCall.git && cd ReCall
uv sync                      # deps — uv provisions Python 3.12 itself
uv run pytest                # fast suite; DB-backed tests skip without a cluster
make help                    # every workflow: probe, migrate, seed, chaos-up, deploy…
```

With any CockroachDB — Cloud free tier or a local single-node
(`cockroach start-single-node --insecure`) — set `CRDB_CONN_STRING`
(`cp .env.example .env`), then:

```bash
make probe                   # DDL + 5 rows + one `<->` vector query, then cleans up
make migrate                 # apply infra/migrations/*.sql in order (0001 schema, 0002 decision log)
uv run pytest                # now 102 green — the DB-backed tests run for real
```

The AC7 resilience rig (needs Docker):

```bash
make chaos-up                # 3-node local cluster, vector index flag enabled
docker stop recall-crdb-2    # the kill — survivors keep serving
make chaos-down              # stop and wipe
```

## Roadmap

Gate-exited phases. The 13 acceptance criteria live in
[`docs/01-objective-roadmap.md`](docs/01-objective-roadmap.md); the live calendar is
[`docs/08-final-sprint.md`](docs/08-final-sprint.md); the video script is
[`docs/09-demo-script.md`](docs/09-demo-script.md).

| Phase | Window | Exit criterion | |
|---|---|---|---|
| **P0 · Probe** | Aug 2–4 | live cluster + vector query + Bedrock access requested | 🟡 local probe passed (flag-then-works); Cloud half awaits credentials |
| **P1 · Memory foundation** | Aug 3–7 | planted incident retrieved top-3 from CLI; 80-postmortem corpus | 🟡 code + loader + eval harness done; embedding pass awaits Bedrock |
| **P2 · Agent loop** | Aug 8–12 | `curl` an alert → diagnosis citing a real incident + runbook | 🟡 loop, prompt, handler built + offline-tested; first live run awaits credentials |
| **P3 · Surface** | Aug 13–14 | live status page; demo script ≤3 min | 🟡 page + script v1 built; goes live with the Lambda |
| **P4 · Resilience** | Aug 15–16 | node-kill rehearsal recorded, zero row loss verified | 🟡 rig built, kill rehearsed mechanically; recorded take remains |
| **P5 · Ship** | Aug 17–18 | video ≤3:00 up; Devpost submission confirmed | ⚪ |

**After the hackathon** — deliberately parked until submission ([`docs/01`](docs/01-objective-roadmap.md)
scope discipline): nightly memory consolidation (episodic → semantic), live Slack ingest,
region-level chaos, Agent Skills diagnostics. The parked list is the feature backlog, not a graveyard.

## Development

The repo is built to be driven by both a human and coding agents — conventions are executable where
possible.

- **Branching** ([`docs/07`](docs/07-branching-worktrees.md)): `feat/* → develop → release/* → main`,
  where `main` is release-only and every merge into it is tagged (`w1`…`w6`, the runnable-increment
  KPI). Short-lived branches are named for intent — `feat/` `fix/` `test/` `docs/` `chore/`
  `experiment/` `hotfix/` — so the history reads honestly. Parallel work happens in **git worktrees**
  (`scripts/wt.sh new feat/<slug>`), one branch = one folder = one venv.
- **Enforced boundaries**: `agent.py` contains zero SQL; `tools.py` is the only module that writes;
  the 4-tool manifest is exactly 4 — all asserted by [`tests/`](tests/index.md), not by review vibes.
- **Testing**: pytest is ground truth. The retrieval eval is a reproducible 20-alert benchmark with
  pinned expected IDs — ≥18/20 top-3 or the gate doesn't exit. DB tests run against a real
  single-node CockroachDB; mocked-DB tests are banned.
- **The benchmark is guarded against itself.** Until Aug 4 every eval alert title was byte-identical
  to its target incident's title, so AC2 was scoring string identity and calling it retrieval —
  a benchmark that cannot fail. [`tests/test_eval_independence.py`](tests/test_eval_independence.py)
  now asserts the sharper property: no token shared between an alert and its target may be *unique*
  to that target within the service-scoped search space, so the answer can never be lexically free.
- **Docs**: [`CLAUDE.md`](CLAUDE.md) is the agent-facing index with eight hard rules; every folder
  ships an `index.md`. Navigate by index — never bulk-load the repo to orient.
- **Commits** name the acceptance criterion they advance: `feat(tools): decay re-rank [AC2]`.

## License

[MIT](LICENSE) © 2026 [Santapong Sondhi](https://github.com/santapong)

<div align="center"><sub>Built for the CockroachDB × AWS hackathon — an agentic-memory reference
implementation for on-call engineering.</sub></div>
