# lambda — index
The one deployed unit: `ingest_handler` plus the agent loop and its 4-tool memory surface. Zipped flat by `make deploy`, so modules import flat (`import tools`) — pytest mirrors this via `pythonpath = ["lambda"]` in pyproject.toml. (The folder name is a Python keyword; flat modules are why that never bites.)

| item | what it is | read when |
|---|---|---|
| `ingest_handler.py` | Entrypoint: POST ingest (pydantic `Alert`, dedupe, invoke) + GET `/status` `/health` `/runlog` (AC1) | Before touching the HTTP surface |
| `agent.py` | Bedrock Converse loop over the manifest; logs every step to `agent_runs`; ZERO SQL here | Before touching agent behavior |
| `tools.py` | The 4-tool contract + all DB writes + non-manifest helpers (ingest, retrieval record, decision log, status reads) | Before touching memory behavior |
| `db.py` | Connections + the retry/reconnect wrapper (AC7) — sole psycopg owner | When adding a query |
| `embed.py` | Text → unit-norm vector; sole Bedrock-embedding surface (D1), plus the opt-in local stand-in | When anything needs a vector |
| `scrub.py` | Blameless-write scrubber (hard rule 3), roster shared with the seed generator; `SAFE_PHRASES` protects operational vocabulary | When touching any write path |

## Invariants (tested in tests/test_module_boundaries.py, test_manifest.py, test_agent_loop.py)
- `TOOL_MANIFEST` is closed at exactly 4 entries (AC4).
- `tools.py` is the only module with SQL writes; `db.py` the only psycopg importer here.
- `agent.py` never touches SQL or psycopg; it sees four Python functions, nothing else.
- The system prompt loads from `prompts/system.md` at runtime — never inlined.
- The decision log never fails a diagnosis: `tools.log_step` swallows by explicit ADR (asserted by test).
- Runtime DB role is `recall_app` (migration 0003): no DELETE, no DDL, `runbooks` read-only, and no
  `CREATE` — the `public` pseudo-role's default grant is revoked. Proven by `tests/test_app_role.py`,
  which connects *as* the role rather than asserting it in prose.
- **Propose-only is structural.** `write_incident` is filtered out of the `toolConfig` the diagnosis
  loop sends (`DIAGNOSIS_TOOL_SPECS`), and `_dispatch` refuses it outright. The manifest still holds
  four tools — AC4 counts the manifest, not what one loop is offered. Close path: `scripts/close.py`.
- **Citations are provenance-checked, not existence-checked.** `propose_diagnosis` validates both
  `cited_incident_ids` and `cited_runbook_ids` against *this run's* `working_state.retrieved_matches`,
  which the loop persists — so the model cannot cite anything it did not actually retrieve (AC3, both
  halves per docs/01:48).

## The two local backends (M0')
Explicit opt-in only, by exact value — never inferred from a missing credential, because a silent
quality downgrade would poison AC2 without anyone noticing (see `embed.py`'s docstring).

- `EMBED_BACKEND=local` → `embed.local_embed`, a deterministic hashing-trick vectorizer (blake2b, so
  it survives `PYTHONHASHSEED`). **Lexical, not semantic**: scores and tuned thresholds from it do
  not transfer to Titan.
- `BEDROCK_BACKEND=local` → `agent.local_converse`, a scripted walk of the prompt's contract.
- Both announce themselves: stderr warning, `local-scripted` in the decision log, `PROVISIONAL` on
  the AC2 table. Nothing filmed may run on either.
