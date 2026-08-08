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


# Which arm each POST ran (AC12). Module-level so _wire keeps its two-value return
# and the existing callers stay unchanged.
memory_flags: list[bool] = []


def _wire(monkeypatch):
    inserted, ran = [], []
    memory_flags.clear()

    def fake_insert(external_id, service, title, description, severity):
        inserted.append(external_id)
        return "inc-uuid"

    def fake_run(incident_id, service, title, description, *, memory=True):
        ran.append(incident_id)
        memory_flags.append(memory)
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


def test_get_runlog_routes_to_decision_log(monkeypatch):
    steps = [{"seq": 0, "step_type": "model_turn", "name": "claude", "outcome": "success",
              "latency_ms": 812, "input_tokens": 900, "output_tokens": 40,
              "confidence": None, "detail": None,
              "created_at": "2026-08-04T00:00:00+00:00"}]
    monkeypatch.setattr(tools, "run_log", lambda iid: steps if iid == "inc-1" else [])

    resp = ingest_handler.handler(_get_event("/runlog", {"incident_id": "inc-1"}), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"incident_id": "inc-1", "steps": steps}

    # An incident with no run yet is an empty log, not a 404 — the page polls this.
    empty = ingest_handler.handler(_get_event("/runlog", {"incident_id": "inc-2"}), None)
    assert empty["statusCode"] == 200 and json.loads(empty["body"])["steps"] == []

    assert ingest_handler.handler(_get_event("/runlog"), None)["statusCode"] == 400


def test_get_health_routes_to_health(monkeypatch):
    monkeypatch.setattr(tools, "health", lambda: {"incidents": 92})
    resp = ingest_handler.handler(_get_event("/health"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"]) == {"incidents": 92}


# --- B4: the status page is a browser, and browsers enforce CORS -------------


def test_every_response_carries_the_cors_header(monkeypatch):
    """Without this the status page — served from file:// or GitHub Pages — can never
    read the Function URL, and the primary on-camera surface shows 'waiting for
    incident…' forever. Asserted on an error path too: a 404 the page cannot read is
    indistinguishable from a page that never loaded (see F3)."""
    _wire(monkeypatch)
    monkeypatch.setattr(tools, "health", lambda: {"incidents": 92})

    for resp in (
        ingest_handler.handler({"body": json.dumps(ALERT)}, None),      # 200 POST
        ingest_handler.handler({}, None),                                # 400
        ingest_handler.handler(_get_event("/health"), None),             # 200 GET
        ingest_handler.handler(_get_event("/nope"), None),               # 404
    ):
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"


# --- B6: the POST branch fails loudly to the caller, not only to CloudWatch --


def test_agent_failure_is_a_500_with_a_reason_not_an_uncaught_502(monkeypatch):
    """run_agent and insert_incident had no try/except, so a DB blip or a Bedrock
    error propagated out of handler and the Function URL returned a bare 502 with the
    real reason buried in logs — the worst failure mode to hit mid-demo."""
    _wire(monkeypatch)

    def boom(*a, **kw):
        raise RuntimeError("thresholds untuned")

    monkeypatch.setattr(ingest_handler, "run_agent", boom)
    resp = ingest_handler.handler({"body": json.dumps(ALERT)}, None)

    assert resp["statusCode"] == 500
    body = json.loads(resp["body"])
    assert body["error"] == "diagnosis failed"
    assert "RuntimeError" in body["detail"] and "thresholds untuned" in body["detail"]


def test_insert_failure_is_also_handled(monkeypatch):
    _wire(monkeypatch)

    def boom(*a, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr(tools, "insert_incident", boom)
    resp = ingest_handler.handler({"body": json.dumps(ALERT)}, None)

    assert resp["statusCode"] == 500
    assert "connection refused" in json.loads(resp["body"])["detail"]


# --- C5: shared-secret ingest, POST only -------------------------------------


def test_ingest_token_is_required_when_configured(monkeypatch):
    inserted, ran = _wire(monkeypatch)
    monkeypatch.setenv("RECALL_INGEST_TOKEN", "s3cret")

    denied = ingest_handler.handler({"body": json.dumps(ALERT)}, None)
    assert denied["statusCode"] == 401
    assert inserted == [] and ran == []  # no DB touch, no Bedrock spend

    wrong = ingest_handler.handler(
        {"body": json.dumps(ALERT), "headers": {"x-recall-token": "nope"}}, None)
    assert wrong["statusCode"] == 401

    ok = ingest_handler.handler(
        {"body": json.dumps(ALERT), "headers": {"X-Recall-Token": "s3cret"}}, None)
    assert ok["statusCode"] == 200  # header match is case-insensitive


def test_reads_stay_open_when_the_token_is_configured(monkeypatch):
    """POST-only by design — the status page has no way to hold a secret, and reads
    are public for the demo (named in the README)."""
    monkeypatch.setenv("RECALL_INGEST_TOKEN", "s3cret")
    monkeypatch.setattr(tools, "health", lambda: {"incidents": 92})
    monkeypatch.setattr(tools, "run_log", lambda iid: [])

    assert ingest_handler.handler(_get_event("/health"), None)["statusCode"] == 200
    assert ingest_handler.handler(
        _get_event("/runlog", {"incident_id": "inc-1"}), None)["statusCode"] == 200


def test_no_token_configured_means_open(monkeypatch):
    _wire(monkeypatch)
    monkeypatch.delenv("RECALL_INGEST_TOKEN", raising=False)
    assert ingest_handler.handler({"body": json.dumps(ALERT)}, None)["statusCode"] == 200


def test_memory_off_query_param_selects_the_amnesia_arm(monkeypatch):
    """AC12 reaches the loop as a real parameter, not a CSS class in the browser."""
    _wire(monkeypatch)
    ingest_handler.handler(
        {"body": json.dumps(ALERT), "queryStringParameters": {"memory": "off"}}, None)
    assert memory_flags == [False]


def test_memory_defaults_on(monkeypatch):
    """Anything other than exactly "off" — including absent — runs the grounded arm."""
    _wire(monkeypatch)
    ingest_handler.handler({"body": json.dumps(ALERT)}, None)
    ingest_handler.handler(
        {"body": json.dumps(ALERT), "queryStringParameters": {"memory": "on"}}, None)
    assert memory_flags == [True, True]
