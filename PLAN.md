# PLAN.md — Aug 4 → Aug 18, 2026

*Written 2026-08-04 against `develop` @ the eval-fix + decision-log commits. Supersedes
the **calendar and hour budget** in `docs/08-final-sprint.md`; every AC, spec and exit
criterion in `docs/01–07` stands. Where this file and docs/08 disagree on dates or hours,
this file wins. `SDD.md` does not exist — `docs/02` + `docs/04` + the C4 set are the
design of record.*

---

## Where this actually stands

**Built and green:** 62 tests (43 fast + 19 DB-backed, the latter running locally and in CI
against a real single-node cockroach). The 4-tool manifest, the Converse loop, ingest +
`/status` + `/health` + `/runlog`, the status page, the seed loader, the AC2 harness, the
`agent_runs` decision log, the 3-node chaos rig — plus, executed after this plan was written:
the `recall_app` least-privilege role (review's access-control item), the CI full-suite job,
idempotent migrations, and the real-PIR corpus's credential-free half (10 sourced public
postmortems in `infra/seed/pir_corpus.json`; only its embedding pass still waits on M1).

**Not started:** every line of the live half. No Cloud cluster, no Bedrock access, zero
embeddings written, `CONFIDENCE_HIGH_MAX_DIST` and `CONFIDENCE_NONE_MIN_DIST` still `NaN`.

**The uncomfortable fact:** `credentials` has been the standing `next:` in `WORKLOG.md`
since **Jul 8** — four weeks. Nothing below matters if that stays true for a fifth.

## The arithmetic

| | Hours |
|---|---|
| docs/08's remaining plan (P1 tail 4 + P2 16 + P3 4 + P4 9 + P5 8) | **41** |
| Real capacity: 2 weekends (Aug 8–9, 15–16) ≈ 20h + ~10 weeknights ≈ 12h | **32** |
| Gap, before anything goes wrong | **−9** |

So this plan does not add work on top of docs/08. It **replaces** the tail of it, and the
cut list below is pre-decided rather than improvised at 1 a.m. on the 17th.

**Pre-agreed cuts, in this order** — take them without renegotiating:

1. **AC10** (2 cold viewers) — already optional in docs/01.
2. **AC9** clean-machine timing run — assert the ≤15-min claim in the README, don't test it.
3. **Status-page polish** beyond "renders legibly on camera."
4. **Seed volume 80 → 40** if the embedding pass is slow or Bedrock throttles.

**Never cut:** the refusal shot (M4/shot 2), the node-kill take, the write-back loop, the
video, the Devpost submission.

---

## Milestones

Exit criteria are typed: `test:` a command that passes · `artifact:` a file that exists ·
`signal:` explicit confirmation. No vibes-based done.

### M0 · Credentials — **Aug 4, tonight** · 0.5h

The whole project is downstream of this and it is the only item whose latency is not in
your control.

- Bedrock console: request model access for **Titan Text Embeddings V2**, a **Claude**
  model, and **Amazon Nova** as the fallback. Amazon's own models approve fast; the
  competition rules allow any model, so Nova is a working project rather than no project.
- CockroachDB Cloud: create the cluster in **us-east-1**, paste `CRDB_CONN_STRING` into `.env`.

`signal:` both requests submitted; `test:` `make probe` passes against Cloud (may lag the
Bedrock half). **Demo:** the probe's `<->` query output pasted into WORKLOG.

> **Kill gate:** if Bedrock Claude access is still pending on **Aug 9**, switch the agent
> model to Nova in the same sitting and stop waiting. Record the substitution in the
> README per the docs/04 version policy. Do not spend a second weekend blocked.

### M1 · Memory live — Aug 5–9 · 8h · AC2, AC13

- `make migrate` (0001 + 0002) against the live cluster.
- Embedding pass: `infra/seed/load.py` over the 80-incident corpus + 12 runbooks.
- Resolve the `VECTOR(n)` marker in `schema.sql`/`0001` from what the probe actually
  printed — same commit, both files.
- **Tune `CONFIDENCE_HIGH_MAX_DIST` / `CONFIDENCE_NONE_MIN_DIST` against the real
  distance distribution, then freeze.** This is the highest-uncertainty item in the plan:
  both are `NaN` today and AC13's entire honesty story is downstream of them.
- Run the AC2 eval — **against the repaired eval set.** The old one scored string identity.

`test:` `uv run pytest tests/retrieval_eval.py -s` → ≥18/20 top-3.
**Demo:** the printed hit table. **Tag:** `p1-memory`.

> **This is the first honest reading of retrieval quality this project has ever had.** If
> it comes in at 14/20, that is information, not failure — the fix is threshold tuning and
> query construction, both cheap. If it comes in at 20/20 on the first try, re-read
> `tests/test_eval_independence.py` before believing it.

> **Kill gate:** below 12/20 after one tuning pass → stop tuning, cut the corpus to the 6
> cleanest archetypes per service, and re-pin. A smaller honest benchmark beats a large
> broken one.

### M2 · Agent live — Aug 8–12 · 8h · AC1, AC3, AC4

- `make deploy`; create the Function URL; set env vars (model IDs, thresholds, conn string).
- `curl` all 20 alerts end-to-end. Assert AC1 latency < 5s and **zero invented IDs**.
- Confirm `agent_runs` fills: `GET /runlog?incident_id=…` returns an ordered step list
  with real latencies and token counts.

`test:` 20/20 alerts return a diagnosis citing a real incident ID + runbook step, no
`LookupError` reaching the caller. **Demo:** one curl → one grounded answer. **Tag:** `p2-agent`.

### M3 · The de-risking artifact — Aug 12 · 1.5h · AC13, AC3

**Build this before the polish, not after.** It is the falsifiable test of the claim the
entire repositioned pitch rests on.

Two live cases, scripted and repeatable:

1. An alert with **no** near neighbour in the corpus → `confidence: none` → the agent says
   so and stops, `cited_incident_ids` empty, `propose_diagnosis` not called with citations.
2. `propose_diagnosis` called with a **fabricated UUID** → `LookupError`, nothing persisted,
   an `error` row in `agent_runs`.

`artifact:` `scripts/demo_refusal.sh` that runs both and prints the outcomes.
`test:` case 1 produces zero cited IDs; case 2 leaves `working_state.proposed_diagnosis`
unchanged.

> **What forces a redesign:** if case 1 does not reliably produce `confidence: none` —
> i.e. the thresholds can't separate "genuinely novel" from "weak match" on real
> distances — then AC13's honesty branch is decorative and the pitch's lead claim is
> half-true. Response: widen `CONF_NONE_MIN_DIST` until a hand-built novel alert lands
> there consistently, and say in the README that the band is tuned conservatively.
> Do **not** ship shot 2 of the video against a branch that only fires sometimes.

### M4 · Resilience + surface — Aug 13–16 · 8h · AC5, AC7, AC11, AC12

- Migrate + seed a subset into the 3-node docker rig.
- **Shot 2 (the refusal)** — record until clean. Highest-value 27 seconds in the video.
- Node-kill take: in-flight diagnosis, `docker stop recall-crdb-2`, row counts identical.
- `AS OF SYSTEM TIME` on `working_state`, then `/runlog` — both on camera.
- Close → retrieve take. Amnesia A/B (`?memory=off`).
- **One CockroachDB MCP query on camera** — five seconds, removes Stage One ambiguity.

`artifact:` clean takes for shots 1–7 of `docs/09`. **Demo:** the rough cut.

### M5 · Ship — Aug 17–18 · 6h · AC8, AC6

- Cut to ≤3:00. Upload public (YouTube/Vimeo).
- Devpost: repo URL, **functional demo URL**, video, CockroachDB tools list (distributed
  vector index + managed MCP + ccloud), AWS list (Bedrock + Lambda), text description.
- Confirmation email screenshot → `docs/plans/`.

`artifact:` Devpost confirmation email. **Hard wall:** Aug 18, 5:00 pm ET = **Aug 19,
04:00 ICT**. Target submit: **Aug 17 night ICT**, 24h of real buffer.

---

## Critical path

```
M0 credentials → M1 embeddings + thresholds → M2 live agent → M3 refusal proof → M4 takes → M5 cut + submit
```

Everything else is slack. Specifically parallelizable, do while blocked: README/Devpost
copy, the demo-script read-throughs, status-page polish, `scripts/demo_refusal.sh` written
against stubs.

**The single longest pole is M0's Bedrock approval, and it is the one thing you cannot
work around by staying up later.**

## Risk register

| Risk | Observable trigger | Mitigation |
|---|---|---|
| **Bedrock Claude access lags** | No approval by Aug 9 | Switch to Nova, same sitting. Rules allow any model. Record the substitution in the README |
| **Thresholds can't separate `none` from `low`** | M3 case 1 fires inconsistently across 5 runs | Widen `CONF_NONE_MIN_DIST` conservatively and say so in the README. If still unstable, shot 2 leads with the fabricated-ID case only — that one is deterministic |
| **A weekend disappears** | Aug 8–9 lost to life | M2 spills to Aug 13–14 nights; take cuts 1–3 immediately, not on the 16th |

## Kill criteria, per gate

- **M0, Aug 9:** no Bedrock Claude → Nova, no debate.
- **M1, Aug 10:** AC2 below 12/20 after one tuning pass → shrink the corpus, re-pin, move on.
- **M2, Aug 13:** no live end-to-end curl → cut the status page entirely and film against
  terminal output. The page is not load-bearing for any AC.
- **M4, Aug 16 night:** fewer than 5 clean takes → cut shots 3 and 6, ship a 2:10 video.
  A short honest video beats a missed deadline.

## First physical action — 25 minutes, tonight

1. AWS console → Bedrock → Model access → request **Titan Text Embeddings V2**, a
   **Claude** model, and **Amazon Nova**. (~10 min)
2. cockroachlabs.cloud → create cluster, **us-east-1** → copy connection string →
   `cp .env.example .env`, paste. (~10 min)
3. `make probe`. Paste the output into `WORKLOG.md` with tonight's date. (~5 min)

If step 3 fails on the vector-index flag, run
`SET CLUSTER SETTING feature.vector_index.enabled = true;` and retry — record which of the
two happened, per `docs/02`.
