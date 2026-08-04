# lambda — index
The one deployed unit: `ingest_handler` plus the agent loop and its 4-tool memory surface. Zipped flat by `make deploy`, so modules import flat (`import tools`) — pytest mirrors this via `pythonpath = ["lambda"]` in pyproject.toml. (The folder name is a Python keyword; flat modules are why that never bites.)

| item | what it is | read when |
|---|---|---|
| `ingest_handler.py` | Entrypoint: POST ingest (pydantic `Alert`, dedupe, invoke) + GET `/status` `/health` `/runlog` (AC1) | Before touching the HTTP surface |
| `agent.py` | Bedrock Converse loop over the manifest; logs every step to `agent_runs`; ZERO SQL here | Before touching agent behavior |
| `tools.py` | The 4-tool contract + all DB writes + non-manifest helpers (ingest, retrieval record, decision log, status reads) | Before touching memory behavior |
| `db.py` | Connections + the retry/reconnect wrapper (AC7) — sole psycopg owner | When adding a query |
| `embed.py` | Text → unit-norm vector; sole Bedrock-embedding surface (D1) | When anything needs a vector |
| `scrub.py` | Blameless-write scrubber (hard rule 3), roster shared with the seed generator | When touching any write path |

## Invariants (tested in tests/test_module_boundaries.py, test_manifest.py)
- `TOOL_MANIFEST` is closed at exactly 4 entries (AC4).
- `tools.py` is the only module with SQL writes; `db.py` the only psycopg importer here.
- `agent.py` never touches SQL or psycopg; it sees four Python functions, nothing else.
- The system prompt loads from `prompts/system.md` at runtime — never inlined.
- The decision log never fails a diagnosis: `tools.log_step` swallows by explicit ADR (asserted by test).
- Runtime DB role is `recall_app` (migration 0003): no DELETE, no DDL, `runbooks` read-only.
