# 09 · Demo Script — v2 (P3 deliverable, target ≤ 3:00)

*Read aloud at marked pace: ~2:45, buffer to 3:00. Every shot names the AC it proves.
Rehearse against the local rig before recording; the video is cut in this order.*

> **v2 changed the cut order (2026-08-04).** v1 led with the node kill and buried the
> refusal in a subordinate clause of the cold open. That aimed the whole video at one of
> five equally-weighted judging criteria. The differentiator — that the agent is
> *structurally* incapable of inventing a citation — now gets its own beat at 0:28, and
> the node kill is demoted from thesis to one proven failure mode. Nothing was cut from
> the build; only the ordering changed.

## Cut order

| # | Shot | Window | Proves |
|---|---|---|---|
| 1 | Cold open — the grounded answer | 0:00–0:28 | AC1, AC3 |
| 2 | **The refusal** | 0:28–0:55 | AC13, AC3 |
| 3 | Amnesia A/B | 0:55–1:18 | AC12 |
| 4 | Node kill | 1:18–1:48 | AC7 |
| 5 | Close → retrieve | 1:48–2:08 | AC5 |
| 6 | Time travel + decision log | 2:08–2:32 | AC11 |
| 7 | Outro over the memory-layer card | 2:32–2:45 | AC6 |

---

## 1 · Cold open — 0:00–0:28 · AC1, AC3

**Screen:** terminal left, status page right (clock at 00:00).

> Every LLM you point at a production incident will give you an answer. That's the
> problem — at 2 a.m. a confident wrong root cause is worse than no answer, because you
> believe it.
> This is Recall. *(curl the alert)* An alert just fired at Orbital. Within seconds: it
> searched three years of incident memory, found the closest past incidents, and proposed
> a diagnosis citing INC-1187 by ID and the runbook step that fixed it last time.
> That ID is a real row. Here's why it has to be.

**Note:** land on the cited ID visible on the status page. Don't explain the mechanism
yet — shot 2 is the explanation.

## 2 · The refusal — 0:28–0:55 · AC13, AC3

**Screen:** terminal, two commands back to back. This is the shot the video is built around.

> Two things this agent cannot do.
> *(fire an alert nothing in memory matches)* One: it can't bluff. No close match —
> confidence `none` — so it says exactly that and stops. No citation, no guess.
> *(force a fabricated incident ID into the write path)* Two: it can't invent. That
> incident ID doesn't exist, and the write path rejects it before anything persists.
> Not a prompt saying "please don't hallucinate" — a database check that has to pass.
> The rejection is right there in the decision log, as an error row.

**Filming notes**

- Two takes stitched: `curl` the novel alert, then the forced-ID case.
- Stage the forced-ID case by calling `propose_diagnosis` directly with a made-up UUID —
  show the `LookupError` text on screen. Do **not** fake it; run it live.
- End on `GET /runlog` output with the `error` row highlighted. That row is the proof.

## 3 · Amnesia A/B — 0:55–1:18 · AC12

**Screen:** split — `?memory=off` left, normal right, same alert.

> Same alert, same model, side by side. Left, no memory: check the logs, restart the
> service. Right, with memory: the actual root cause from the last time this exact
> failure happened, and the step that resolved it. The difference isn't the model.

**Staging (changed 2026-08-08):** fire *two* alerts — one `POST ?memory=off`, one without —
then open each incident on the page. The flag now reaches the loop: `run_agent(memory=False)`
withholds the tools entirely, and `record_ungrounded_answer` persists the result as
`confidence='none'` with no matches. Both panes are therefore real runs read from the same
schema. It was previously a CSS toggle that blanked a panel, which would have filmed as an
A/B while actually comparing the page against itself; the left pane's line is now an output,
not a script direction.

## 4 · Node kill — 1:18–1:48 · AC7

**Screen:** status page full, clock ticking; terminal overlay for the kill.

> Memory this thing depends on had better not go down with the system it's diagnosing.
> A diagnosis is in flight — and I'm killing a database node. Now.
> *(docker stop recall-crdb-1 — clock keeps ticking)*
> The clock never stopped. The answer lands. Row counts before and after: identical.
> That's not a backup restoring. That's the database not going down.

**Note:** the claim is scoped deliberately — *survives node loss*, not *everyone else's
setup is broken*. The README's "What we don't claim" section says the same in writing.

**Setup (corrected 2026-08-08):** export the **multi-host** connection string first
(`make chaos-conn`) and kill **crdb-1**, the node the connection is actually on. The rig
previously printed a single-host string for crdb-1 while the script killed crdb-2, so the
connection never broke, `db.with_retry`'s reconnect arm never fired, and the shot proved
nothing. Killing crdb-1 against a single-host string breaks it permanently instead — hence
all three hosts.

## 5 · Close → retrieve — 1:48–2:08 · AC5

**Screen:** terminal close, then second alert fires; memory panel updates.

> The on-call closes it with what actually fixed it. Scrubbed of names, embedded, written
> back. Next similar alert — *(fire it)* — the incident we just closed is the top match.
> Every resolved incident makes the next one faster.

**The close command (added 2026-08-08):** `uv run python scripts/close.py <id> "<resolution>"`.
This is the *only* caller of `write_incident` — the diagnosis loop is not offered the tool at
all, so "you propose, humans dispose" is enforced by there being no path from the model to
this command. Rehearsed locally: a resolution closed this way came back as the top match at
distance 0.87 against a corpus whose next-best was 1.24.

## 6 · Time travel + decision log — 2:08–2:32 · AC11

**Screen:** terminal, `AS OF SYSTEM TIME` query via the MCP dev surface, then `/runlog`.

**The query (added 2026-08-08):** `scripts/timetravel.sql`. Run step 1 to capture
`cluster_logical_timestamp()` **before** firing the alert, and read at that captured value —
*not* at a relative `AS OF SYSTEM TIME '-10m'`, which returns zero rows against a
two-minute-old incident, live, on camera. Check `gc.ttlseconds` on the tier first. Rehearsed:
0 decision-log steps at the captured moment, 7 now.

> Every diagnosis is auditable twice over. What did memory *believe* at 02:14?
> One `AS OF SYSTEM TIME` query — the working state exactly as the agent saw it,
> mid-incident. And what did it *do* to get there? *(GET /runlog)* Every step in order:
> which tool, how long, how many tokens, what got refused. Blameless postmortems with
> receipts.

## 7 · Outro — 2:32–2:45 · AC6

**Screen:** README memory-layer table + why-CockroachDB table, then the repo page.

> Three memory layers, one decision log, one database — episodic, semantic, working,
> plus distributed vector search, time travel, and survival by consensus. No bolt-on
> vector store, no second system to fail. MIT, repo's open, README gets a stranger
> running in fifteen minutes.

---

## Filming notes

- The elapsed clock must be visibly ticking in every status-page shot — it is the proof
  the takes are live (docs/03).
- **Shot 2 is the one to reshoot until it's clean.** If time runs out, shots 3 and 6 are
  the cuttable ones; 1, 2, 4 and 5 are not.
- The kill take: rehearse until one clean take; assert row counts on camera with a
  prepared `SELECT count(*)` in shell history.
- Put **one CockroachDB MCP query on camera** during shot 6 — the managed MCP server is a
  claimed competition tool and Stage One is pass/fail on tools being meaningfully used.
  A visible query costs five seconds and removes the ambiguity.
- AC10 check: after the first full cut, show two cold viewers; both must state what it
  does and why CockroachDB, unprompted. If they say "it remembers past incidents" but not
  "it refuses to make things up", shot 2 didn't land — recut it.
