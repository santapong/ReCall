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

Top-level folder indexes (read the folder's `index.md` before working in it): `.claude/` (the executable harness — skills, hooks, worker contract) · `docs/` · `infra/` · `lambda/` · `prompts/` · `scripts/` · `status_page/` · `tests/`.

## Hard rules — never violate

1. **The agent's tool manifest is exactly 4 tools** (`search_incidents`, `get_runbook`, `propose_diagnosis`, `write_incident`). Never add a raw-SQL tool, an execute tool, or a "temporary debug" tool to the manifest. This is AC4 and the pitch depends on it being literally true.
2. **Propose-only.** `tools.py` is the only module that writes to the database. Diagnosis writes go to `working_state` only.
3. **Blameless writes.** Every resolution is scrubbed of names/handles/emails before persisting. A test asserts no survivors.
4. **Confidence honesty.** When retrieval confidence is `none`, the agent says so plainly. It never invents an incident ID (AC3/AC13) — zero fabricated citations across the test set.
5. **Parked stays parked**: region-kill, live Slack ingest, contradiction engine, Agent Skills diagnostics. Do not build these, even if they'd be quick.
6. **Sleep-cycle is dead.** Its Jul 26 gate did not pass on schedule, so it is off the table by its own rule (`docs/08`). Do not revisit before submission.
7. **Behind schedule cuts scope, never the date.** Cut order: UI polish → seed volume → tool breadth. Never cut: chaos demo, write-back, video, on-time submit. Target submit **Aug 17 night ICT**; hard wall **Aug 19, 04:00 ICT** (= Aug 18, 5 pm EDT) — `docs/08`.
8. **Index or it doesn't exist.** Every new folder or subsystem ships an `index.md` (template in `docs/06`) and registers in its parent index — and in this read-order table if it's top-level — in the same commit. Navigate by index; never bulk-load the repo to orient.

## Current state

- Phase: **P0** — the probe (cluster + DDL + one vector query + headless-MCP check + Bedrock access request) gates everything. `make probe` + `scripts/probe_bedrock.py` are ready for it. **Schedule is now `docs/08`: 16 days to the wall; weekends Aug 8–9 and Aug 15–16 carry the load.**
- Repo scaffolded Jul 8 from the handoff pack: layout per `docs/05`, branch/worktree model live in `docs/07` (run `make branches-init` once after the setup PR merges), CI fast suite on PRs, structural tests green (AC4 manifest, module boundaries, retry pattern).
- P1 partially pre-banked (Aug 1): the Orbital corpus, the blameless scrubber, and the 20 AC2 eval pairs already exist — `docs/08`'s "implement `generate.py` (~3 h)" line item is done.
- Open decision markers: **D2 (runtime DB path) is closed — Branch B, psycopg hot path with MCP as the dev/ops surface (`docs/08`).** One marker remains: embedding dimension, expected `1024`, resolved in-file the day `probe_bedrock.py` prints it.
- Source artifacts (charter HTML v1, council report, pitch panel, original design doc) belong in `docs/plans/` — the human drops them in; this pack is the operational consolidation of all four as of Jul 8; where they disagree, this pack wins.

## Commands

Keep this section updated as commands land:

```
uv sync                 # deps — works now
uv run pytest           # structural tests now; AC2 eval joins at P1
uv run ruff check .     # lint — works now (make lint / make fmt)
make probe              # P0: vector probe against your cluster (needs CRDB_CONN_STRING)
make migrate            # apply infra/migrations/*.sql in order
uv run python infra/seed/generate.py   # regenerate corpus + eval fixtures (make seed) — works now
make deploy             # P2 — zip + update Lambda (see 05-code-patterns)
scripts/wt.sh new feature/<slug>       # branch + worktree per docs/07
```

Harness skills (docs/06–07 as machinery, see `.claude/index.md`): `/session-loop` · `/start-work` · `/verify` · `/record` · `/gate-check`. SessionStart hook injects orientation; the Stop hook enforces "never end a session red".

## Definition of done

AC1–AC13 in `docs/01-objective-roadmap.md`. Every PR/commit message names the AC it advances. Submission is done when the Devpost confirmation email exists — not when the code is done.
