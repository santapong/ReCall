---
name: session-loop
description: Drive one full Recall working session per docs/06 — orient, plan ONE gate-advancing task naming its AC, build the smallest end-to-end slice, verify, record, commit tagged [ACn]. Use at the start of every working session or when unsure what to do next.
---

# Session loop (executable form of docs/06)

Run the six steps in order. Do not skip Verify or Record.

1. **Orient** — the SessionStart hook already injected the WORKLOG tail and phase.
   Spend at most 3 more reads: the current phase's row in `docs/01`, the ONE doc
   this task needs (CLAUDE.md read-order table), the files you'll edit. If
   orienting takes more reads than that, the indexes failed — fix the index in
   the same commit as the work.
2. **Plan** — one gate-advancing task. Name the AC it moves, in ≤5 lines. A task
   that advances no AC and isn't index/worklog upkeep gets questioned before it
   gets built. If the task needs its own branch, run `/start-work` first.
3. **Build** — smallest end-to-end slice. Output goes to disk, not the transcript.
4. **Verify** — run `/verify`. Red means fix now; never proceed red.
5. **Record** — run `/record` (WORKLOG line with the `next:` handoff clause,
   index registration if structure changed).
6. **Commit** — `type(scope): subject [ACn]`. Never end a session red.

## Disengagement (ODD — stop, don't push through)

If any trigger below fires: write the open question as a WORKLOG line, end the
turn. This is a harness success, not a failure.

- Collides with a CLAUDE.md hard rule (1–8)
- Resolving a `DECISION PENDING` marker without probe data from the human
- New or paid AWS resources not named in `docs/04` — anything that could bill
- Schema changes beyond what the current AC requires
- Work that adds hours beyond the current phase budget (docs/01 table)
- Anything on the parked list · git history rewrites or force-push
