"""Embed + load the Orbital corpus into the cluster (P1: `uv run python infra/seed/load.py`).

Reads corpus.json (deterministic, committed — regenerate via `make seed` only),
embeds every incident resolution and runbook through the one embedding surface
(lambda/embed.py, normalize:true always), and upserts by external_id/title so the
load is re-runnable. Needs CRDB_CONN_STRING + AWS creds with Bedrock access; fails
loudly without them (docs/05 — no silent degrade, no keyword fallback).

Writes here are legal: infra/ shares the write allowance with lambda/tools.py
(tests/test_module_boundaries.py).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lambda"))

import db  # noqa: E402
from embed import embed, to_vector_literal  # noqa: E402

CORPUS = Path(__file__).resolve().parent / "corpus.json"
# Real public post-incident reports (review 2026-08-04): one extra service ('public'),
# one demo shot, AC2's pinned set untouched. Loaded after the Orbital corpus.
PIR_CORPUS = Path(__file__).resolve().parent / "pir_corpus.json"

_INCIDENT_SQL = """
    INSERT INTO incidents (external_id, service, title, description, severity, status,
                           resolution_summary, embedding, opened_at, resolved_at)
    VALUES (%(external_id)s, %(service)s, %(title)s, %(description)s, %(severity)s,
            %(status)s, %(resolution_summary)s, %(embedding)s::VECTOR,
            %(opened_at)s, %(resolved_at)s)
    ON CONFLICT (external_id) DO UPDATE SET
        service = excluded.service, title = excluded.title,
        description = excluded.description, severity = excluded.severity,
        status = excluded.status, resolution_summary = excluded.resolution_summary,
        embedding = excluded.embedding, opened_at = excluded.opened_at,
        resolved_at = excluded.resolved_at
"""

# Runbooks have no natural key in the schema; (service, title) is unique in the
# generated corpus, so delete-then-insert keeps the load re-runnable.
_RUNBOOK_DELETE_SQL = "DELETE FROM runbooks WHERE service = %(service)s AND title = %(title)s"
_RUNBOOK_SQL = """
    INSERT INTO runbooks (service, title, content, embedding)
    VALUES (%(service)s, %(title)s, %(content)s, %(embedding)s::VECTOR)
"""


def embed_incident_text(incident: dict) -> str:
    """What goes into the vector: title + description + resolution — the same
    surface an alert query is matched against (docs/02 seed spec)."""
    parts = [incident["title"], incident["description"], incident.get("resolution_summary") or ""]
    return "\n".join(p for p in parts if p)


def _execute(sql: str, params: dict) -> None:
    """Run one statement under the retry arm, acquiring the connection and cursor
    *inside* the retried callable.

    This is load-bearing, not style. db.with_retry handles a dropped link by calling
    close_conn() and retrying — but a connection or cursor captured beforehand is
    already dead by then, so the retry re-executed against a closed cursor and could
    never succeed. One transient drop killed the whole 92-document pass mid-Bedrock-
    spend, which is exactly the situation the retry exists to survive.
    """
    def run():
        with db.get_conn().cursor() as cur:
            cur.execute(sql, params)

    db.with_retry(run)


def load_corpus(path: Path) -> None:
    corpus = json.loads(path.read_text(encoding="utf-8"))

    incidents = corpus["incidents"]
    for n, incident in enumerate(incidents, 1):
        vector = to_vector_literal(embed(embed_incident_text(incident)))
        params = {k: incident.get(k) for k in (
            "external_id", "service", "title", "description", "severity",
            "status", "resolution_summary", "opened_at", "resolved_at",
        )}
        params["embedding"] = vector
        _execute(_INCIDENT_SQL, params)
        print(f"\r  incidents {n}/{len(incidents)}", end="", flush=True)
    print()

    runbooks = corpus["runbooks"]
    for n, runbook in enumerate(runbooks, 1):
        vector = to_vector_literal(embed(f"{runbook['title']}\n{runbook['content']}"))
        params = {"service": runbook["service"], "title": runbook["title"],
                  "content": runbook["content"], "embedding": vector}
        _execute(_RUNBOOK_DELETE_SQL, params)
        _execute(_RUNBOOK_SQL, params)
        print(f"\r  runbooks {n}/{len(runbooks)}", end="", flush=True)
    print()


def main() -> None:
    print(f"== {CORPUS.name}")
    load_corpus(CORPUS)
    if PIR_CORPUS.exists():
        print(f"== {PIR_CORPUS.name}")
        load_corpus(PIR_CORPUS)
    print("load complete — run the AC2 eval next: uv run pytest tests/test_retrieval_eval.py -s")


if __name__ == "__main__":
    main()
