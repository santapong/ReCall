# lambda — index
The one deployed unit: `ingest_handler` plus the agent loop and its 4-tool memory surface. Zipped flat by `make deploy`, so modules import flat (`import tools`) — pytest mirrors this via `pythonpath = ["lambda"]` in pyproject.toml. (The folder name is a Python keyword; flat modules are why that never bites.)

| item | what it is | read when |
|---|---|---|
| `ingest_handler.py` | Entrypoint; thin — parse, dedupe, invoke agent (AC1) | P2 |
| `agent.py` | Bedrock Converse loop; ZERO SQL here | P2 |
| `tools.py` | The 4-tool contract + all DB writes | Before touching memory behavior |
| `db.py` | Connections + the retry wrapper — sole psycopg owner | When adding a query |
| `scrub.py` | Blameless-write scrubber (hard rule 3) | P1 |

## Invariants (tested in tests/test_module_boundaries.py, test_manifest.py)
- `TOOL_MANIFEST` is closed at exactly 4 entries (AC4).
- `tools.py` is the only module with SQL writes; `db.py` the only psycopg importer here.
- `agent.py` never touches SQL or psycopg; it sees four Python functions, nothing else.
- The system prompt loads from `prompts/system.md` at runtime — never inlined.
