"""Lambda entrypoint — thin by design: parse, dedupe, invoke agent (docs/02).

Flow (AC1): alert JSON POSTs to the Function URL → validate → dedupe on
external_id (same alert twice = same row, tools.insert_incident is idempotent)
→ insert incidents + working_state via tools.py helpers → run_agent. Embedding
failure fails the ingest loudly; no keyword-search fallback (docs/02 error
handling).
"""

import base64
import json

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
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body)}


def handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    if http.get("method") == "GET":
        path = http.get("path", "")
        if path.endswith("/health"):
            return _response(200, tools.health())
        if path.endswith("/status"):
            incident_id = (event.get("queryStringParameters") or {}).get("incident_id", "")
            snapshot = tools.status_snapshot(incident_id) if incident_id else None
            if snapshot is None:
                return _response(404, {"error": f"no incident {incident_id!r}"})
            return _response(200, snapshot)
        return _response(404, {"error": "unknown path"})

    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        alert = Alert.model_validate_json(raw)
    except ValidationError as exc:
        return _response(400, {"error": "invalid alert payload", "detail": exc.errors()})

    incident_id = tools.insert_incident(
        alert.external_id, alert.service, alert.title, alert.description, alert.severity,
    )
    diagnosis = run_agent(incident_id, alert.service, alert.title, alert.description)
    return _response(200, {"incident_id": incident_id, "response": diagnosis})
