# 09 · Demo Script — v1 (P3 deliverable, target ≤ 3:00)

*Shot order from docs/08. Read aloud at marked pace: ~2:35, buffer to 3:00. Every
shot names the AC it proves. Rehearse against the local rig before recording; the
video is cut in this order.*

## Cold open — 0:00–0:25 · AC1, AC3

**Screen:** terminal left, status page right (clock at 00:00).

> This is Recall — an on-call agent that remembers every incident your team ever
> had. An alert just fired at Orbital, our fictional SaaS.
> *(curl the alert)* Within seconds: the agent searched three years of incident
> memory, found the closest past incidents, and proposed a diagnosis — citing
> INC-1187 by ID and the exact runbook step that fixed it last time. Not a
> hallucination: that ID is a real row, and the agent is incapable of inventing
> one — cited IDs are validated against the database before anything persists.

## Amnesia A/B — 0:25–0:55 · AC12

**Screen:** split — `?memory=off` left, normal right, same alert.

> Same alert, side by side. On the left, the same model with no memory: generic
> advice — check the logs, restart the service. On the right, with memory: the
> specific root cause from the last time this exact failure happened, and the
> runbook step that resolved it. The difference isn't the model. It's the memory.

## Node kill — 0:55–1:30 · AC7

**Screen:** status page full, clock ticking; terminal overlay for the kill.

> That memory lives in CockroachDB. Watch what happens when it fails mid-thought.
> A diagnosis is in flight — and I'm killing a database node. Now.
> *(docker stop recall-crdb-2 — clock keeps ticking)*
> The clock never stopped. The diagnosis lands. Row counts before and after:
> identical. The incident memory survived the kind of outage it exists to
> diagnose — that's not a backup restoring, that's the database not going down.

## Time travel — 1:30–1:50 · AC11

**Screen:** terminal, `AS OF SYSTEM TIME` query via the MCP dev surface.

> Every diagnosis is auditable in time. What did memory believe at 02:14, before
> the fix? One query — `AS OF SYSTEM TIME` — and there it is: the working state
> exactly as the agent saw it, mid-incident. Blameless postmortems get receipts.

## Close → retrieve — 1:50–2:10 · AC5

**Screen:** terminal close, then second alert fires; memory panel updates.

> The on-call closes the incident with what actually fixed it. That resolution is
> scrubbed of names, embedded, and written back. Next similar alert — *(fire it)*
> — the incident we just closed is now the top match. Every resolved incident
> makes the next one faster. That's the loop.

## Why CockroachDB — 2:10–2:25 · AC6

**Screen:** README memory-layer diagram + why-CockroachDB table.

> Three memory layers — episodic, semantic, working — three tables, one database:
> distributed vector search for retrieval, survival by consensus for the outage,
> time travel for the audit. No bolt-on vector store, no second system to fail.

## Outro — 2:25–2:35

**Screen:** repo page.

> Recall: institutional incident memory, durable and agent-native. MIT licensed,
> repo's open, README gets a stranger running in fifteen minutes. Thanks.

---

## Filming notes

- The elapsed clock must be visibly ticking in every status-page shot — it is the
  proof the takes are live (docs/03).
- The kill take: rehearse until one clean take; assert row counts on camera with
  a prepared `SELECT count(*)` in shell history.
- AC10 check: after the first full cut, show two cold viewers; both must state
  what it does and why CockroachDB, unprompted.
