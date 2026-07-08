---
name: gate-check
description: Audit Recall's phase gate and acceptance criteria — compare docs/01's exit criterion and AC1–AC13 against repo reality, list unresolved DECISION PENDING markers, apply the cut order if behind schedule. Use weekly, before promotions/tags, or when asked "where are we?".
---

# Gate check (docs/01 made auditable)

1. **Locate** — current phase + exit criterion from the `docs/01` phase table;
   today's date against the window.
2. **Evidence, not vibes** — run `/verify`; then check the gate's specific
   artifacts exist and run (e.g. P0: probe output recorded; P1: seeded corpus +
   eval ≥18/20; P2: `curl` → diagnosis with a real citation).
3. **AC sweep** — for each of AC1–AC13, mark: proven (name the test/artifact),
   in progress, or not started. Never claim an AC without its evidence.
4. **Markers** — `grep -rn "DECISION PENDING" docs/ infra/` — list what's still
   open and what input unblocks each.
5. **Schedule check** — behind? Apply hard rule 7's cut order: UI polish → seed
   volume (80→30) → tool breadth. NEVER cut: chaos demo, write-back, video,
   Aug 15 submit. A gate may slip ≤4 days (KPI); more means cut scope today.
6. **Output** — a short status block: phase, gate verdict (pass/at-risk/fail),
   AC scoreboard, open markers, and the ONE next gate-advancing task (which
   becomes the WORKLOG `next:` clause).
