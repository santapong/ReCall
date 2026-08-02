# Changelog

All notable changes to Recall are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project is pre-release and
unversioned until submission, so changes are grouped by date under **Unreleased**.

Phase tags (`w1`…`w6` on `main`) mark runnable increments per `docs/07`; a phase gate exits when
its tag exists. Commit messages name the acceptance criterion they advance — the `[ACn]` markers
below are those criteria, defined in [`docs/01-objective-roadmap.md`](docs/01-objective-roadmap.md).

## [Unreleased]

### 2026-08-02 — architecture diagrams, sprint plan, memory core

#### Added
- **C4 architecture diagrams** in `docs/diagrams/` — Context, Container and Component levels as
  hand-authored SVG. No build step and no diagram-as-code toolchain; presentation attributes rather
  than CSS-in-SVG so the files rasterise correctly for slides and the video. Embedded in the README
  and `docs/02`, replacing the previous Mermaid flowcharts.
- **`docs/08-final-sprint.md`** — the Aug 2 → 18 compressed schedule, closing decisions D1–D4 and
  fixing the video shot list. Supersedes the dates in `docs/01`'s phase table; every acceptance
  criterion, budget and exit criterion there is unchanged.
- **`lambda/embed.py`** — the sole Bedrock embedding surface. Titan V2 at 1024 dimensions with
  `normalize=true` on every call, so the corpus and the queries can never be normalised differently.
  Throttle retry mirrors the database retry contract; a failed embedding fails loudly rather than
  falling back to keyword search. [AC2]
- **`search_incidents` and `get_runbook`** are implemented: service-scoped `<->` vector query,
  decay re-rank in Python, and an explicit confidence label. Pydantic models (`Match`,
  `SearchResult`, `Runbook`) at the boundary. [AC2][AC13]
- **`db.get_conn`** — cached module-level connection; warm-container reuse is what keeps ingest
  under the 5-second budget. [AC1]
- `SearchResult.runbook_ids` — without it the agent had no legal way to learn a runbook ID, and
  citing a runbook step is required. A field on a return model, not a fifth tool. [AC3]
- 10 pure-function tests covering the decay curve, the confidence bands and reconnect behaviour
  (`tests/test_retrieval_pure.py`). Suite: 16 → 26. [AC13]
- This changelog.

#### Changed
- **`db.with_retry` now reconnects on a dropped connection.** A killed node surfaces as
  `psycopg.OperationalError`, not `SerializationFailure`, so the original pattern would have retried
  nothing and let the in-flight diagnosis die during the node-kill demo. `docs/05` amended with the
  reasoning in the same commit. [AC7]
- **Decision D2 — runtime database path resolved to Branch B**: `psycopg` on the hot path with
  parameterised SQL; the managed MCP server stays the development and operations surface and counts
  as CockroachDB tool #1. Branch A was verified viable (service-account bearer auth) and rejected
  anyway — it costs tool-manifest auditability and puts a middle service in the node-kill frame.
  No flip before submission. [AC4]
- `scripts/probe_bedrock.py` sends `dimensions: 1024` and `normalize: true`, and prints the vector's
  L2 norm so unit length is verified rather than assumed (decision D1).
- Hard rule 6 struck: the sleep-cycle stretch goal is dead by its own Jul 26 gate.
- Hard rule 8 amended: asset-only folders (`docs/diagrams/`) are described by their parent index
  rather than carrying a stub `index.md`.
- README refreshed — C4 diagrams, the real Aug 2–18 calendar, and honest per-phase status.

### 2026-08-01 — memory substrate

#### Added
- **Deterministic Orbital corpus** (`infra/seed/generate.py`): 80 synthetic postmortems across six
  services, 12 runbooks, and 20 designed alert pairs whose expected IDs are pinned in
  `tests/fixtures/eval_pairs.json`. Fixed RNG seed and a fixed time anchor, so regeneration
  reproduces the committed files byte-for-byte. [AC2]
- **Blameless scrubber** (`lambda/scrub.py`) with a name roster shared with the generator, so the
  zero-survivors test cannot be fooled by a name the generator knows and the scrubber doesn't.
- `scripts/probe_runbook.md` — the P0 probe as an ordered human runbook with a decision tree for the
  free-tier vector-index risk. [AC8]

### 2026-07-08 — scaffold

#### Added
- Repository scaffolded from the handoff pack: layout per `docs/05`, the seven-document design pack,
  and an `index.md` in every folder.
- Branch and worktree model (`docs/07`, `scripts/wt.sh`, `make branches-init`):
  `feature/* → dev → test → main`.
- CI fast suite on pull requests, with structural tests green from the first commit — the closed
  4-tool manifest [AC4], module boundaries, and the retry pattern.
- Claude Code harness (`.claude/`): five skills, a SessionStart orientation hook, a Stop
  never-end-red hook, and the worker agent contract — `docs/06` and `docs/07` as executable
  machinery rather than prose.
- Judge-facing README v1: badges, the three-memory-layer table, and the why-CockroachDB table.
  [AC6][AC9]
- MIT licence.
