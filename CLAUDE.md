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
| `docs/03-frontend-design.md` | The one status page: layout, tokens, endpoint | Only at P3 (Aug 13–14) |
| `docs/04-tech-stack.md` | Every pick, why, rejected alternatives, what to verify | Before adding any dependency |
| `docs/05-code-patterns.md` | Module rules, error handling, testing, commit cadence | Before first commit |
| `docs/06-claude-code-harness.md` | How to work: session loop, doc policy, ODD, subagents | Every session, before coding |
| `docs/07-branching-worktrees.md` | Branch roles, merge flow, worktree layout + helper | Before creating any branch or worktree |
| `docs/08-final-sprint.md` | The live schedule (Aug 2→18), closed decisions D1–D4, video shot list | Every session until submission — **supersedes `01`'s dates** |
| `docs/09-demo-script.md` | The ≤3:00 video script, shot by shot, AC-mapped | At P3+, before filming |

Top-level folder indexes (read the folder's `index.md` before working in it): `.claude/` (the executable harness — skills, hooks, worker contract) · `docs/` · `infra/` · `lambda/` · `prompts/` · `scripts/` · `status_page/` · `tests/`.

## Hard rules — never violate

1. **The agent's tool manifest is exactly 4 tools** (`search_incidents`, `get_runbook`, `propose_diagnosis`, `write_incident`). Never add a raw-SQL tool, an execute tool, or a "temporary debug" tool to the manifest. This is AC4 and the pitch depends on it being literally true.
2. **Propose-only.** `tools.py` is the only module that writes to the database. Diagnosis writes go to `working_state` only.
3. **Blameless writes.** Every resolution is scrubbed of names/handles/emails before persisting. A test asserts no survivors.
4. **Confidence honesty.** When retrieval confidence is `none`, the agent says so plainly. It never invents an incident ID (AC3/AC13) — zero fabricated citations across the test set.
5. **Parked stays parked**: region-kill, live Slack ingest, contradiction engine, Agent Skills diagnostics. Do not build these, even if they'd be quick.
6. **Sleep-cycle is dead.** Its Jul 26 gate did not pass on schedule, so it is off the table by its own rule (`docs/08`). Do not revisit before submission.
7. **Behind schedule cuts scope, never the date.** Cut order: UI polish → seed volume → tool breadth. Never cut: chaos demo, write-back, video, on-time submit. Target submit **Aug 17 night ICT**; hard wall **Aug 19, 04:00 ICT** (= Aug 18, 5 pm EDT) — `docs/08`.
8. **Index or it doesn't exist.** Every new folder or subsystem ships an `index.md` (template in `docs/06`) and registers in its parent index — and in this read-order table if it's top-level — in the same commit. Navigate by index; never bulk-load the repo to orient. *Amended 2026-08-02*: **asset-only folders** (`docs/diagrams/` — SVG and nothing else) carry no `index.md`; the parent index describes every file instead. The rule's purpose is that nothing is undiscoverable, and a one-format asset folder is better served by one table upstream than by a stub file inside it.

## Current state (2026-08-04)

- **All application code is built and offline-verified; cloud credentials are the only gate.** The 4-tool surface (read + write), the Converse loop, ingest + `GET /status`/`/health`, the status page, the seed loader (`infra/seed/load.py`), the AC2 eval harness, the `agent_runs` decision log (+ `GET /runlog`), the AC7 chaos rig (`infra/chaos/`, kill rehearsed), the `recall_app` least-privilege role, and the 10-PIR real-postmortem corpus (`infra/seed/pir_corpus.json`, service `public`, AC2-isolated) all exist. Suite: 102 green (CI runs the full DB-backed suite on PRs and develop/release pushes); DB-backed tests run against a real local single-node (v25.2.2, user-space install; probe answer: vector index = flag-then-works, recorded in `docs/02`).
- Still awaiting the human: CockroachDB Cloud cluster + MCP service-account key, AWS keys + Bedrock model-access grant (`scripts/probe_runbook.md` steps A–C). Then, in order: Cloud probe/migrate → `probe_bedrock.py` → `load.py` → tune the two thresholds → AC2 eval → `make deploy` → live end-to-end.
- One open decision marker: embedding dimension, expected `1024`, resolved in-file the day `probe_bedrock.py` prints it. D1–D4 are otherwise closed (`docs/08`).
- Source artifacts (charter HTML v1, council report, pitch panel, original design doc) belong in `docs/plans/` — the human drops them in; where they disagree with this pack, this pack wins.

## Commands

Keep this section updated as commands land:

```
uv sync                 # deps
uv run pytest           # 102 tests; DB-backed ones need CRDB_CONN_STRING (local node)
uv run ruff check .     # lint (make lint / make fmt)
make probe              # vector probe against your cluster (needs CRDB_CONN_STRING)
make migrate            # apply infra/migrations/*.sql in order
uv run python infra/seed/generate.py   # regenerate corpus + eval fixtures (make seed)
uv run python infra/seed/load.py       # embed + upsert the corpus (needs Bedrock creds)
uv run pytest tests/test_retrieval_eval.py -s   # AC2 eval — runs once corpus is embedded
make chaos-up / chaos-down             # AC7 3-node kill rig (Docker)
make deploy             # bundle deps + prompts + code, update the Lambda
scripts/wt.sh new feat/<slug>          # branch + worktree per docs/07 (base: develop)
```

Harness skills (docs/06–07 as machinery, see `.claude/index.md`): `/session-loop` · `/start-work` · `/verify` · `/record` · `/gate-check`. SessionStart hook injects orientation; the Stop hook enforces "never end a session red".

## Definition of done

AC1–AC13 in `docs/01-objective-roadmap.md`. Every PR/commit message names the AC it advances, and every change a reader would notice gets a `CHANGELOG.md` entry in the same commit — the changelog is the outward-facing history, `WORKLOG.md` is the session log; they are not the same file and neither replaces the other. Submission is done when the Devpost confirmation email exists — not when the code is done.
