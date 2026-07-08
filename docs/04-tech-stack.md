# 04 · Tech Stack

Rule inherited from the design pass: boring wins unless a named requirement forces otherwise. Every row states why *for this project* — a pro that would be true of any project doesn't count.

| Layer | Pick | Why (this case) | Rejected | Verify |
|---|---|---|---|---|
| Language | Python 3.12 | Primary language; every hour of learning tax is an hour off the 60 | Go (also fluent, but the AI/embedding ecosystem path is shorter in Python) | — |
| Package mgmt | uv | Already the daily driver; lockfile in repo | pip/poetry | — |
| Database | CockroachDB Cloud (free tier) | Mandated by competition; explicitly hackathon-eligible | — (not a choice) | vector-index cluster setting on fresh cluster — **at probe** |
| Vector search | CockroachDB `VECTOR` + `CREATE VECTOR INDEX` (C-SPANN) | Counts as a required tool; distributed index *is* the differentiation thesis | pgvector-on-Postgres, Pinecone — both would delete the project's reason to exist | `<->` query works on free tier — **at probe** |
| DB driver | psycopg 3 | CockroachDB speaks Postgres wire; psycopg is the boring standard | ORM (SQLAlchemy) — 3 tables, parameterized SQL is simpler and AC4-auditable | pin version at P1 |
| LLM | Claude via **AWS Bedrock**, Converse API | Satisfies AWS requirement with the strongest story; any model is allowed so this is a choice, not a rule | Direct Anthropic API (loses the Bedrock story; Lambda alone still satisfies compliance floor if access lags) | model access approval — **requested at probe** |
| Embeddings | Bedrock Titan Text Embeddings | Same platform, same credential as the LLM; no second vendor | OpenAI/Voyage embeddings — adds a vendor for zero requirement | output dimension → `VECTOR(n)` — **at P1, before seeding** |
| Agent loop | **Custom loop** (boto3, manual tool dispatch, ~50 lines) | Full control of the 4-tool manifest (AC4); confidence branching stays visible (AC13); easiest to debug solo | LangGraph (overkill at 4 tools), Bedrock Agents managed (hides the mechanism the pitch shows), Strands (new dep for a small loop) | — |
| Ingest | Lambda + **Function URL** | One URL, zero gateway config | API Gateway (config surface, no benefit at demo scale) | — |
| Scheduler (stretch only) | EventBridge cron → Lambda | Only if sleep-cycle gate fires Jul 26 | — | — |
| MCP | CockroachDB **managed** MCP server (first-party) | One-click config into Claude Code per official quickstart; counts as required tool | Community MCP wrappers (not what the competition's tooling page points at) | headless auth from a script — **at probe** (see 02, DECISION PENDING) |
| Frontend | Static HTML + vanilla JS | See 03 — 4 h budget, camera is the audience | React/Vite | — |
| Deploy | Makefile: zip + `aws lambda update-function-code` | One function; fewest moving parts | SAM/Terraform (fine tools, config tax unjustified at n=1 function) | — |
| CI | GitHub Actions: pytest on push | Weekly-increment KPI needs green checks, nothing more | — | — |
| Chaos rig | 3-node `cockroach start` via docker-compose (local/EC2) | R1 fallback: free-tier Cloud likely exposes no killable nodes; the kill scene needs nodes you own | killing Cloud infra (probably impossible on serverless tier) | confirm Cloud tier topology — **at probe** |
| Testing | pytest + fixed-seed fixtures | AC2 is a reproducible eval, not a vibe | — | — |
| Lint/format | ruff (lint + format) | One tool, zero config debate | black+flake8 | — |

## Version policy

No version numbers appear in this pack that weren't verified. Pin everything in `uv.lock` at P1 and record the CockroachDB cluster version + Bedrock model IDs in the README the day the probe runs. If a doc and the lockfile disagree, the lockfile is truth.

## The four "verify" flags, gathered

1. Vector index availability / cluster-setting flag on a fresh free-tier cluster → **probe**
2. Headless MCP auth from a script → **probe** (decides Branch A vs B in `02`)
3. Cloud free-tier topology: killable nodes or not → **probe** (decides where the chaos rig lives)
4. Embedding model output dimension → **P1**, before any row is seeded
