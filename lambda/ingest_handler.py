"""Lambda entrypoint — thin by design: parse, dedupe, invoke agent (docs/02).

Flow (AC1): alert JSON POSTs to the Function URL → validate → dedupe on
external_id (same alert twice = same row, tools.insert_incident is idempotent)
→ insert incidents + working_state via tools.py helpers → run_agent. Embedding
failure fails the ingest loudly; no keyword-search fallback (docs/02 error
handling).
"""

import base64
import json
import os

from pydantic import BaseModel, Field, ValidationError

import tools
from agent import run_agent


class Alert(BaseModel):
    """The one payload that crosses the network boundary (docs/05: pydantic at
    every process/network boundary)."""

    external_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: str = Field(min_length=1)


def _response(status: int, body: dict) -> dict:
    # CORS is not optional here: the status page is a static file served from
    # file:// or GitHub Pages, so without this header the browser blocks every read
    # of the Function URL and the primary on-camera surface shows "waiting for
    # incident…" forever. Reads are public by design for the demo (see README).
    return {"statusCode": status,
            "headers": {"Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"},
            "body": json.dumps(body)}


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    if http.get("method") == "GET":
        path = http.get("path", "")
        if path.endswith("/health"):
            return _response(200, tools.health())
        incident_id = (event.get("queryStringParameters") or {}).get("incident_id", "")
        if path.endswith("/status"):
            snapshot = tools.status_snapshot(incident_id) if incident_id else None
            if snapshot is None:
                return _response(404, {"error": f"no incident {incident_id!r}"})
            return _response(200, snapshot)
        if path.endswith("/runlog"):
            # The replayable decision log (migration 0002). Read-only, non-manifest —
            # observability, not memory: every step the agent took, in execution order.
            if not incident_id:
                return _response(400, {"error": "incident_id is required"})
            return _response(200, {"incident_id": incident_id,
                                   "steps": tools.run_log(incident_id)})
        return _response(404, {"error": "unknown path"})

    # POST spends Bedrock tokens on an unauthenticated public URL, so it takes a
    # shared secret when one is configured. Deliberately POST-only: the status page
    # must keep reading /status and /runlog without one. Absent env var = open, which
    # is what local development and the test suite run with. This bounds casual abuse
    # of the URL; it is not an identity system, and the README says so.
    expected = os.environ.get("RECALL_INGEST_TOKEN")
    if expected:
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
        if headers.get("x-recall-token") != expected:
            return _response(401, {"error": "missing or invalid x-recall-token"})

    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        alert = Alert.model_validate_json(raw)
    except ValidationError as exc:
        return _response(400, {"error": "invalid alert payload", "detail": exc.errors()})

    # Loud to the caller, not only to CloudWatch. Unhandled, a DB blip or a Bedrock
    # error surfaces as a bare 502 from the Function URL with the real reason buried
    # in logs — the worst possible failure mode mid-demo. Still loud: 500, with the
    # exception type and message in the body.
    try:
        incident_id = tools.insert_incident(
            alert.external_id, alert.service, alert.title, alert.description, alert.severity,
        )
        # AC12: ?memory=off runs the same alert through the same model with the memory
        # tools withheld. It is a real second arm, not a display toggle.
        memory_on = (event.get("queryStringParameters") or {}).get("memory") != "off"
        diagnosis = run_agent(incident_id, alert.service, alert.title, alert.description,
                              memory=memory_on)
    except Exception as exc:
        return _response(500, {"error": "diagnosis failed",
                               "detail": f"{type(exc).__name__}: {exc}"})
    return _response(200, {"incident_id": incident_id, "response": diagnosis})
