# 06 · Claude Code — Harness & Loop

The model is not the system. The **harness** — Claude Code plus this repo's conventions — decides what context loads, what state persists, and what "done" means. This file is the harness spec. Read it at session start, every session.

## Verified mechanics this repo relies on

Checked against official Claude Code docs, Jul 8 2026:

- Root `CLAUDE.md` auto-loads at every session start. It is the only file guaranteed in context — which is why it's an index with hard rules, not a manual.
- Nested `CLAUDE.md` files in subdirectories are discovered **on demand** when working in that subtree — native progressive disclosure.
- `@path/to/file.md` imports pull files into context lazily.
- Guidance consensus: keep the root file lean (≲200 lines); split detail into pointed-to docs.

This repo uses those mechanics deliberately: **one** root CLAUDE.md holds all hard rules (rules fragmented across nested files drift); `index.md` files carry navigation; imports stay unused unless a doc proves it earns permanent context.

## Documentation policy — navigate, don't inhale

*Adapted from the LLM-wiki pattern: overviews + indexes so the agent orients in O(depth), not O(repo).*

1. **Root has two overviews, different audiences.** `CLAUDE.md` = agent-facing index + hard rules (exists). `README.md` = judge-facing overview (built in P4; AC6, AC9 live there). Both mandatory.
2. **Every non-trivial folder ships `index.md`**: what this folder is, a contents table, its invariants. Template below. Under ~40 lines — an index that scrolls is a doc pretending to be an index.
3. **Registration chain, same commit.** New folder or subsystem → its `index.md` → parent index updated → CLAUDE.md read-order updated if it's a top-level concern. A folder without registration is the same severity as a red test: the build convention is broken.
4. **Load discipline.** Session start: CLAUDE.md (auto) → `WORKLOG.md` tail → current phase line in `01` → the ONE doc the task needs → the files you'll edit. If orienting took more than ~5 reads, the indexes failed — fix the index in the same commit as the work.

`index.md` template:

```markdown
# <folder> — index
One sentence: what this folder is and why it exists.

| item | what it is | read when |
|---|---|---|
| ... | ... | ... |

## Invariants
- Rules that apply to everything in this folder (e.g. "only tools.py writes").
```

## The session loop

1. **Orient** — ≤3 reads beyond the auto-loaded CLAUDE.md: WORKLOG tail, phase gate in `01`, the task's doc.
2. **Plan** — one gate-advancing task. Name the AC it moves. ≤5 lines. A task that advances no AC and isn't index/worklog upkeep gets questioned before it gets built.
3. **Build** — smallest end-to-end slice. Output goes to disk, not to the transcript.
4. **Verify** — `uv run pytest`; the named AC test if it exists; the module-boundary grep test always.
5. **Record** — one WORKLOG line; update indexes if structure changed; resolve a `DECISION PENDING` marker only if the human supplied the answer.
6. **Commit** — message tagged `[ACn]`. Never end a session red. The WORKLOG line's final clause is the next session's first task — the filesystem is the only memory that survives the session, so the handoff lives there or nowhere.

`WORKLOG.md` — root of repo, newest first, one line per session, cap ~30 lines (archive overflow to `docs/plans/worklog-archive.md`):

```markdown
# WORKLOG — newest first
- 2026-07-09 · P1 · seed generator + fixtures done, eval at 19/20 · next: tune CONF thresholds
- 2026-07-08 · P0 · probe: vector idx OK no flag, headless MCP = no → Branch B locked · next: schema.sql
```

## ODD — what runs autonomous, what disengages

**Autonomous zone** (no human touch needed): implementing within the locked design; writing tests; refactors that respect module boundaries; docs/index/worklog upkeep; regenerating seed data; the local chaos rig; `make deploy` to the existing function.

**Disengagement triggers** — stop, write the open question as a WORKLOG line, end the turn:

- Anything colliding with CLAUDE.md hard rules 1–8
- Resolving a `DECISION PENDING` marker without probe data from the human
- Creating new or paid AWS resources not named in `04` — anything that could produce a bill
- Schema changes beyond what the current AC requires
- Work that adds hours beyond the current phase budget
- Anything on the parked list
- Git history rewrites or force-push

North star is **tasks-per-human-touch** — maximize autonomous progress — but a disengagement on a real trigger is a success of the harness, not a failure of the agent. The triggers exist because they mark exactly where being wrong is expensive.

## Subagents — the exception, not the default

Working economics for this project: a single agent runs ≈4× chat-baseline token cost; multi-agent setups ≈15×; peer-to-peer agent chatter adds an O(n²) re-read tax. Therefore:

- **Orchestrator → worker only.** No lateral agent communication, ever.
- **Spawn only for genuinely file-disjoint parallel units** — e.g., seed generator ∥ eval fixtures ∥ status-page skeleton. If two workers would touch the same file, it's one task.
- **Worker contract**: role brief injected at spawn (point to the exact doc sections it needs — not "read the docs"); writes real output to disk; returns ≤100 words plus file paths; never reads a sibling's transcript. The orchestrator integrates from disk only.
- Default remains one loop. At 60-hour solo scale, most parallelism is fake parallelism with real coordination cost.

## The verifier is ground truth

`pytest` green is the definition of done — not the transcript saying "done." AC tests are the gates. `make deploy` is the only deploy path. If the Makefile can't do it, demo day can't either.
