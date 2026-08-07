# 05 · Code Patterns

Conventions Claude Code follows on every commit. When a pattern here conflicts with a habit, the pattern wins; when reality proves a pattern wrong, change the pattern *in this file* in the same commit.

## Repo layout

```
recall/
├── CLAUDE.md
├── WORKLOG.md                # one line per session, newest first (see docs/06)
├── docs/                     # this pack — has its own index.md
│   └── plans/                # charter/council/pitch exports (read-only history)
├── infra/                    # index.md required
│   ├── schema.sql            # DDL — the single source of schema truth
│   └── seed/generate.py      # deterministic Orbital corpus
├── lambda/                   # index.md required — invariants live there
│   ├── ingest_handler.py     # entrypoint; thin — parse, dedupe, invoke agent
│   ├── agent.py              # Bedrock Converse loop; ZERO SQL in this file
│   ├── tools.py              # the ONLY module that writes to the DB
│   ├── db.py                 # the ONLY module that owns connections
│   ├── embed.py              # the ONLY module that calls Bedrock for embeddings
│   └── scrub.py              # blameless-write scrubber
├── prompts/
│   └── system.md             # agent system prompt, versioned like code
├── status_page/index.html    # the whole frontend
├── tests/                    # index.md maps test file → AC
├── Makefile
└── .env.example
```

## Module boundaries (enforced by review, asserted by tests where possible)

- `agent.py` contains no SQL and no psycopg import. It sees four Python functions and nothing else.
- `tools.py` is the sole DB-write surface. A test greps the codebase: `INSERT|UPDATE|DELETE` appear only in `tools.py` and `infra/`.
- `db.py` owns the connection/pool and the retry wrapper. Nothing else calls `psycopg.connect`.
- `embed.py` owns the Bedrock embedding call and the `EMBED_DIM` constant. Nothing else embeds — the seed loader and `tools.py` share one surface, so the corpus and the queries can never be normalized differently.
- `prompts/system.md` is loaded at runtime, never inlined — prompt changes must be diffable.

## SQL

Parameterized always; f-string SQL is a rejected commit. No ORM. Schema changes are numbered `.sql` files applied by `make migrate`; `schema.sql` stays the canonical full DDL.

## Types

Pydantic v2 models at every boundary that crosses a process or the network: `Alert`, `Match`, `SearchResult`, `Diagnosis`, `Runbook`. Plain dataclasses fine for internals. A tool returns a model or raises — never a dict.

## Error handling

One retry wrapper, used everywhere it applies:

```python
RETRYABLE = ("40001",)  # CRDB serialization conflict — expected under serializable isolation
RECONNECTABLE = (psycopg.OperationalError, psycopg.InterfaceError)  # AC7: a node died

def with_retry(fn, *, max_attempts=3, base_delay=0.2):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except psycopg.errors.SerializationFailure:
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))
        except RECONNECTABLE:
            close_conn()  # drop the dead socket; the next attempt lands on a live node
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))
```

**Amended 2026-08-02**: the original snippet retried serialization failures only. A killed node surfaces as `OperationalError`, not `SerializationFailure`, so AC7's "in-flight answer completes" would have failed on the one demo that is never cut. The reconnect arm is why the node-kill take works.

Same shape for Bedrock `ThrottlingException` (`embed.with_throttle_retry`, matching on error code). Rules: retries are silent, failures are loud, and nothing ever degrades quietly — a failed embedding fails the ingest; it never falls back to keyword search (that would silently poison AC2).

## The scrub pattern (AC hard rule 3)

`scrub.py` exposes one function: `scrub(text) -> str`. Strips emails, @handles, and known-name patterns from the seeded corpus's name list. Test: run every seeded resolution + 20 adversarial strings through it, assert zero survivors. The generator and the scrubber share the name list so the test is airtight.

## Confidence thresholds (AC13)

Constants in one place (`tools.py` top), loaded from env with defaults, tuned once in P1 against the seeded corpus and then frozen:

```python
CONF_HIGH_MAX_DIST = float(os.environ.get("CONFIDENCE_HIGH_MAX_DIST", ...))  # tune P1
CONF_NONE_MIN_DIST = float(os.environ.get("CONFIDENCE_NONE_MIN_DIST", ...))  # tune P1
```

Changing them after P1 requires rerunning the full AC2 eval in the same commit.

## Testing

- `pytest`; fixtures load the deterministic corpus (fixed RNG seed committed).
- `tests/test_retrieval_eval.py` **is** AC2: 20 alerts, expected IDs pinned, asserts ≥18 top-3 hits and prints the full hit table — the table screenshot goes in the README.
- `tests/test_manifest.py` **is** AC4: asserts the tool registry has exactly 4 entries with the exact names.
- Citation validation test **is** AC3: feed a diagnosis citing a fake ID, assert it raises.
- No mocked-DB unit tests for SQL paths — run against a local single-node `cockroach` in CI. Mocks lie about serialization behavior.

## Cadence & commits

- Weekly tag (`w1`…`w6`) — each tag runs end-to-end at whatever depth exists. This is the runnable-increment KPI.
- Commit messages name the AC they advance: `feat(tools): decay re-rank in search_incidents [AC2]`.
- `make deploy` is the only deploy path. If it isn't in the Makefile, it doesn't happen on demo day.

## What Claude Code should refuse to do

Add a fifth tool "temporarily." Inline SQL in `agent.py` "just for debugging." Add a framework "since we might need it." Build anything on the parked list. Skip the scrub "because it's seed data." Create a folder without its `index.md` and registration (docs/06 policy). The answer to each is the same: the constraint *is* the feature — every one of these maps to an acceptance criterion or a pitch claim that must stay literally true.
