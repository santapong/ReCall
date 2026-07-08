# 01 · Objective & Roadmap

*Consolidates charter v1 (Jul 7) + council refinements (Jul 8) + pitch panel (Jul 8). Where the charter HTML and this file disagree, this file wins.*

## Objective — one line, in our control

Submit a complete, judged-ready entry by **Aug 15, 5 pm EDT** (72 h early) that passes all acceptance criteria and every hard requirement, within ≤60 build hours. Winning is upside, not the objective — no one controls judges.

## Vision

Tribal on-call knowledge lives in senior engineers' heads and rots in unread postmortems. Recall makes institutional incident memory durable, queryable, and agent-native — every resolved incident makes the next one faster. And because that memory lives in CockroachDB, it survives the very outages it's helping diagnose.

## Why (three reasons, one honest note)

- **Judging fit**: sponsor names incident diagnosis as a target use case; the node-kill demo hits Memory Design + Production Readiness in one recorded moment.
- **Career**: first real AWS reps, a public agentic-memory reference repo for the LLM/RAG-for-B2B-SaaS niche.
- **Real problem**: on-call knowledge evaporates on turnover — universal, sayable in 15 seconds.
- Honest base rate: most hackathon codebases die post-event. The durable payoff is skills + portfolio + placement odds. This is not a startup.

## Competition hard requirements (from official rules + resources page)

- ≥2 CockroachDB tools. Ours: **managed MCP server + distributed vector index**, with ccloud CLI in setup scripts as a free third. (Agent Skills also counts per the resources page — parked.)
- ≥1 AWS service. Ours: **Bedrock + Lambda**. Lambda alone already satisfies the floor if Bedrock access lags — any AWS service counts, any model allowed.
- Public repo, OSI license (MIT), live demo URL, video ≤3:00.
- CockroachDB Cloud free tier is explicitly hackathon-eligible.

## Phases — gate-exited, dates fixed

| Dates | Phase | Exit criterion | Hours |
|---|---|---|---|
| → Jul 8 | **P0 · Probe** | MCP config working in Claude Code; DDL + 5 rows + one `<->` query succeed on a live cluster; headless-MCP auth answered; Bedrock model access requested | 1 |
| Jul 8–12 | **P1 · Memory foundation** | Scripted query returns the planted incident in top-3, from CLI. Schema, ~80 seeded postmortems, embeddings, both vector indexes. Must land before Jul 13 | 10 |
| Jul 13–26 | **P2 · Agent loop** | `curl` an alert → diagnosis citing a real incident ID + runbook step; write-back row visible. **Jul 13–17 is a reduced-capacity week (external commitments) — scheduled light by design** | 16 |
| Jul 27–Aug 2 | **P3 · Surface** | Status page shows live incident + memory hits; demo script v1 reads ≤3 min. Budget cut 8 h → 4 h to fund the stretch goal | 4 |
| Aug 3–9 | **P4 · Resilience** | Node-kill rehearsal recorded, zero committed-row loss verified; stranger-ready README with the "why CockroachDB" table | 9 |
| Aug 10–15 | **P5 · Ship** | Video ≤3:00 uploaded; Devpost confirmation email exists. Aug 16–18 = untouched buffer | 8 |

**Stretch (gated): sleep-cycle** — nightly EventBridge→Lambda job that distills incident clusters into new runbooks (episodic→semantic consolidation). Enters P3 week **only if** G0–G2 all passed on schedule at the Jul 26 checkpoint. Must read via `AS OF SYSTEM TIME` to count. Self-funds (+5 h) via the P3 cut: 59 − 4 + 5 = 60 h, exactly at ceiling.

## Acceptance criteria — definition of done

| AC | Criterion | Test |
|---|---|---|
| AC1 | POST alert JSON → working-memory incident row + agent run starts, <5 s | curl + row visible |
| AC2 | Planted match in top-3 for ≥18 of 20 scripted alerts | pytest over seeded corpus |
| AC3 | Every diagnosis cites ≥1 real incident ID + ≥1 runbook step; **zero invented IDs** | cited IDs verified against DB |
| AC4 | Tool manifest = memory read/write only, exactly 4 tools | manifest inspection |
| AC5 | Close incident A → next similar alert retrieves A | on camera |
| AC6 | Three memory layers named + mapped to schema in README | README diagram |
| AC7 | Kill 1 of 3 nodes mid-diagnosis → in-flight answer completes, row counts identical | recorded rehearsal + count assertion |
| AC8 | Compliance checklist: 2+ CRDB tools, 1+ AWS, public repo, MIT, demo URL, video ≤3:00 | submission checklist |
| AC9 | Stranger clones repo → running ≤15 min from README alone | clean-machine run in P4 |
| AC10 | 2 cold viewers state what it does + why CockroachDB, unprompted | 2/2 after one watch |
| AC11 | Time-travel demoed: "what did memory believe at 02:14" via `AS OF SYSTEM TIME` | in video |
| AC12 | Amnesia A/B in video: same alert, memory off vs on, side by side | in video |
| AC13 | Explicit low-confidence branch: `confidence='none'` → agent says so, never guesses | threshold test + prompt audit |

## KPIs

Ship by Aug 15 (binary, the one that matters) · 6/6 gates, ≤4-day slip each · runnable increment every week (tagged commit or demo GIF) · ≥90% top-3 retrieval on the 20-alert set · 1 recorded zero-loss node-kill · capacity guardrails hold every week.

## Scope discipline

**Cut order when behind**: UI polish → seed volume (80→30) → tool breadth. **Never cut**: chaos demo, write-back, video, Aug 15 submit.

**Parked — do not build**: region-kill, live Slack ingest (simulate with pasted transcripts instead), contradiction engine, Agent Skills diagnostics (~3–4 h, on-theme, still parked).
