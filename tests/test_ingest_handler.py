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


def _get_event(path, params=None):
    return {"requestContext": {"http": {"method": "GET", "path": path}},
            "queryStringParameters": params or {}}


def test_get_status_routes_to_snapshot(monkeypatch):
    monkeypatch.setattr(tools, "status_snapshot",
                        lambda iid: {"incident_id": iid} if iid == "inc-1" else None)
    ok = ingest_handler.handler(_get_event("/status", {"incident_id": "inc-1"}), None)
    assert ok["statusCode"] == 200
    missing = ingest_handler.handler(_get_event("/status", {"incident_id": "nope"}), None)
    assert missing["statusCode"] == 404
    no_param = ingest_handler.handler(_get_event("/status"), None)
    assert no_param["statusCode"] == 404


def test_get_health_routes_to_health(monkeypatch):
    monkeypatch.setattr(tools, "health", lambda: {"incidents": 92})
    resp = ingest_handler.handler(_get_event("/health"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"incidents": 92}
