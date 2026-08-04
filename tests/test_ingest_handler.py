"""AC1 mechanics, offline: the entrypoint validates, inserts via tools helpers,
invokes the agent, and rejects garbage with a 400 — thin, per docs/02."""

import base64
import json

import ingest_handler
import tools


ALERT = {
    "external_id": "alert-42", "service": "billing",
    "title": "payment webhooks timing out", "description": "p99 > 30s",
    "severity": "sev2",
}


def _wire(monkeypatch):
    inserted, ran = [], []

    def fake_insert(external_id, service, title, description, severity):
        inserted.append(external_id)
        return "inc-uuid"

    def fake_run(incident_id, service, title, description):
        ran.append(incident_id)
        return "confidence high: diagnosis"

    monkeypatch.setattr(tools, "insert_incident", fake_insert)
    monkeypatch.setattr(ingest_handler, "run_agent", fake_run)
    return inserted, ran


def test_valid_alert_inserts_and_runs_agent(monkeypatch):
    inserted, ran = _wire(monkeypatch)
    resp = ingest_handler.handler({"body": json.dumps(ALERT)}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["incident_id"] == "inc-uuid"
    assert inserted == ["alert-42"] and ran == ["inc-uuid"]


def test_base64_body_is_decoded(monkeypatch):
    _wire(monkeypatch)
    raw = base64.b64encode(json.dumps(ALERT).encode()).decode()
    resp = ingest_handler.handler({"body": raw, "isBase64Encoded": True}, None)
    assert resp["statusCode"] == 200


def test_invalid_payload_is_400_and_never_touches_the_db(monkeypatch):
    inserted, ran = _wire(monkeypatch)
    resp = ingest_handler.handler({"body": json.dumps({"service": "billing"})}, None)
    assert resp["statusCode"] == 400
    assert inserted == [] and ran == []


def test_empty_body_is_400(monkeypatch):
    _wire(monkeypatch)
    resp = ingest_handler.handler({}, None)
    assert resp["statusCode"] == 400
