---
name: record
description: Close out a Recall work unit — append the one-line WORKLOG entry with the "next:" handoff clause, keep the registration chain intact (index.md updates), and commit tagged [ACn]. The filesystem is the only memory that survives the session; the handoff lives there or nowhere.
---

# Record (docs/06 steps 5–6)

1. **WORKLOG line** — prepend under the header of `WORKLOG.md`, newest first:

   ```
   - YYYY-MM-DD · P<phase> · <what landed, past tense, one line> · next: <the next session's first task>
   ```

   The `next:` clause is mandatory — it is the next session's Plan step.
   Cap ~30 lines: move overflow to `docs/plans/worklog-archive.md` (create it on
   first overflow and register it in `docs/plans/index.md`).

2. **Registration chain (hard rule 8)** — if structure changed in this work
   unit: new/changed folder gets its `index.md`, parent index updated, CLAUDE.md
   read-order/folder line updated if top-level. Same commit as the work.

3. **Markers** — resolve a `DECISION PENDING` marker only if the human supplied
   the answer this session; record the resolution in the marked file itself.

4. **Commit** — `type(scope): subject [ACn]` (e.g.
   `feat(tools): decay re-rank in search_incidents [AC2]`). Pure doc/index
   upkeep may tag the AC it supports or `[docs]`. Run `/verify` first if
   anything executable changed since the last verify.
