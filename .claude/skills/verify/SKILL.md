---
name: verify
description: Ground-truth verification for Recall — ruff plus the pytest fast suite (AC4 manifest, module boundaries, retry pattern; AC evals as they land). Run before every commit and before ending any session. pytest green is the definition of done, not the transcript saying "done".
---

# Verify (docs/06: the verifier is ground truth)

```bash
uv run ruff check .
uv run pytest -q
```

Then:

1. **Any red → stop and fix now.** If truly blocked, record the exact failure and
   open question as a WORKLOG line — but never commit red, never end a session red.
2. **Name what was proven.** Report which AC-mapped tests ran (see
   `tests/index.md` for the map: AC4 manifest, module boundaries, retry; AC2
   retrieval eval from P1; AC3 citation validation from P2).
3. **DB-backed tests (P1+)** need a real database — a local single-node
   `cockroach start-single-node` or the cluster in `CRDB_CONN_STRING`. Mocked-DB
   tests are banned (docs/05); if the DB isn't reachable, say so plainly rather
   than skipping silently.
4. **Touched behavior, not just code?** Exercise it end-to-end once (e.g.
   `make probe` for schema work, a real `curl` for the ingest path at P2) —
   tests first, but the demo runs on the real path.
