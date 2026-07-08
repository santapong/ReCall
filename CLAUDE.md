# Recall — On-call Incident Copilot

> An on-call agent that remembers every incident your team ever had — and whose memory survives the very outages it's diagnosing.

CockroachDB × AWS hackathon entry. Deadline **Aug 18, 2026, 5 pm EDT** (= Aug 19, 04:00 ICT) — internal ship date **Aug 15**. Solo build, ≤60 h total budget.

## What this is

Alert fires → Lambda ingests → agent (Claude on AWS Bedrock) searches CockroachDB's distributed vector index for the closest past incidents at the fictional SaaS "Orbital" → proposes a diagnosis grounded in a real past resolution, citing real incident IDs → on close, writes the fix back so the next similar alert retrieves it. Signature demo: kill a database node mid-diagnosis, live on camera, zero rows lost.

## Read order

| File | Answers | Read when |
|---|---|---|
| `docs/01-objective-roadmap.md` | Why this exists, phases + dates, acceptance criteria, what's parked | First, always |
| `docs/02-backend-design.md` | Schema, agent loop, tool contract, data flow, seed data spec | Before any backend code |
| `docs/03-frontend-design.md` | The one status page: layout, tokens, endpoint | Only at P3 (Jul 27+) |
| `docs/04-tech-stack.md` | Every pick, why, rejected alternatives, what to verify | Before adding any dependency |
| `docs/05-code-patterns.md` | Module rules, error handling, testing, commit cadence | Before first commit |
| `docs/06-claude-code-harness.md` | How to work: session loop, doc policy, ODD, subagents | Every session, before coding |
| `docs/07-branching-worktrees.md` | Branch roles, merge flow, worktree layout + helper | Before creating any branch or worktree |

Top-level folder indexes (read the folder's `index.md` before working in it): `docs/` · `infra/` · `lambda/` · `prompts/` · `scripts/` · `status_page/` · `tests/`.

## Hard rules — never violate

1. **The agent's tool manifest is exactly 4 tools** (`search_incidents`, `get_runbook`, `propose_diagnosis`, `write_incident`). Never add a raw-SQL tool, an execute tool, or a "temporary debug" tool to the manifest. This is AC4 and the pitch depends on it being literally true.
2. **Propose-only.** `tools.py` is the only module that writes to the database. Diagnosis writes go to `working_state` only.
3. **Blameless writes.** Every resolution is scrubbed of names/handles/emails before persisting. A test asserts no survivors.
4. **Confidence honesty.** When retrieval confidence is `none`, the agent says so plainly. It never invents an incident ID (AC3/AC13) — zero fabricated citations across the test set.
5. **Parked stays parked**: region-kill, live Slack ingest, contradiction engine, Agent Skills diagnostics. Do not build these, even if they'd be quick.
6. **Sleep-cycle is gated.** Build only if the Jul 26 checkpoint passed on schedule, and only reading via `AS OF SYSTEM TIME` — otherwise it doesn't count as the differentiator it exists to be.
7. **Behind schedule cuts scope, never the date.** Cut order: UI polish → seed volume → tool breadth. Never cut: chaos demo, write-back, video, Aug 15 submit.
8. **Index or it doesn't exist.** Every new folder or subsystem ships an `index.md` (template in `docs/06`) and registers in its parent index — and in this read-order table if it's top-level — in the same commit. Navigate by index; never bulk-load the repo to orient.

## Current state

- Phase: **P0** — the probe (cluster + DDL + one vector query + headless-MCP check + Bedrock access request) gates everything. `make probe` + `scripts/probe_bedrock.py` are ready for it.
- Repo scaffolded Jul 8 from the handoff pack: layout per `docs/05`, branch/worktree model live in `docs/07` (run `make branches-init` once after the setup PR merges), CI fast suite on PRs, structural tests green (AC4 manifest, module boundaries, retry pattern).
- Open decision markers: search for `DECISION PENDING PROBE` across docs — two exist (runtime DB path, embedding dimension). Resolve them in-file the day the probe answers them.
- Source artifacts (charter HTML v1, council report, pitch panel, original design doc) belong in `docs/plans/` — the human drops them in; this pack is the operational consolidation of all four as of Jul 8; where they disagree, this pack wins.

## Commands

Keep this section updated as commands land:

```
uv sync                 # deps — works now
uv run pytest           # structural tests now; AC2 eval joins at P1
uv run ruff check .     # lint — works now (make lint / make fmt)
make probe              # P0: vector probe against your cluster (needs CRDB_CONN_STRING)
make migrate            # apply infra/migrations/*.sql in order
uv run python infra/seed/generate.py   # P1 — stub until the corpus lands (make seed)
make deploy             # P2 — zip + update Lambda (see 05-code-patterns)
scripts/wt.sh new feature/<slug>       # branch + worktree per docs/07
```

## Definition of done

AC1–AC13 in `docs/01-objective-roadmap.md`. Every PR/commit message names the AC it advances. Submission is done when the Devpost confirmation email exists — not when the code is done.
