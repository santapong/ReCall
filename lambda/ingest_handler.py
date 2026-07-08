"""Lambda entrypoint — thin by design: parse, dedupe, invoke agent (docs/02).

Flow (AC1): alert JSON POSTs to the Function URL → validate → dedupe on
external_id (same alert twice = same row) → insert incidents + working_state via
tools.py helpers → run_agent(incident_id). Embedding failure fails the ingest
loudly; no keyword-search fallback (docs/02 error handling).
"""


def handler(event, context):
    raise NotImplementedError("P2 — agent loop (docs/01 phase table)")
