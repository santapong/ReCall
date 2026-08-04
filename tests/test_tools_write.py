"""AC3 (citation validation: a fake ID raises, never persists) + AC5 substrate
(write-back close path: scrub → embed → persist) + AC1 substrate (idempotent ingest).

Runs against a real local single-node cockroach (docs/05: mocked-DB tests are banned);
skips cleanly when CRDB_CONN_STRING is unset or the node is down. Only the embedding
is stubbed — Bedrock is not the SQL path, and the stub returns a deterministic
unit-norm vector of the real EMBED_DIM.
"""

import os
import uuid

import pytest

import db
import embed as embed_mod
import tools

pytestmark = pytest.mark.usefixtures("_live_db")


@pytest.fixture(scope="module")
def _live_db():
    if not os.environ.get("CRDB_CONN_STRING"):
        pytest.skip("CRDB_CONN_STRING unset — DB-backed tests need the local node")
    try:
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001 — any connect failure means skip, not fail
        pytest.skip(f"local cockroach not reachable: {exc}")
    yield
    db.close_conn()


@pytest.fixture(autouse=True)
def _stub_embed(monkeypatch):
    """Deterministic unit vector; first component 1.0, rest 0. Real dim, real literal."""
    fake = [1.0] + [0.0] * (embed_mod.EMBED_DIM - 1)
    monkeypatch.setattr(tools, "embed", lambda text: fake)


@pytest.fixture
def incident():
    """A fresh open incident + working_state row, deleted on teardown."""
    external_id = f"test-{uuid.uuid4()}"
    incident_id = tools.insert_incident(
        external_id, "billing", "payment webhooks timing out",
        "p99 webhook latency above 30s", "sev2",
    )
    yield incident_id
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM working_state WHERE incident_id = %s", (incident_id,))
        cur.execute("DELETE FROM incidents WHERE id = %s", (incident_id,))


def _working_state(incident_id):
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT proposed_diagnosis, confidence, retrieved_matches"
            " FROM working_state WHERE incident_id = %s",
            (incident_id,),
        )
        return cur.fetchone()


def test_insert_incident_is_idempotent(incident):
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT external_id FROM incidents WHERE id = %s", (incident,))
        external_id = cur.fetchone()[0]
    again = tools.insert_incident(external_id, "billing", "dup", "dup", "sev2")
    assert again == incident  # same alert twice = same row (AC1)


def test_propose_diagnosis_with_valid_citation_persists(incident):
    tools.propose_diagnosis(incident, "webhook pool exhausted", [incident])
    row = _working_state(incident)
    assert row[0] == "webhook pool exhausted"


def test_propose_diagnosis_fake_id_raises_and_never_persists(incident):
    fake = str(uuid.uuid4())  # valid UUID, no such incident — the AC3 case
    with pytest.raises(LookupError, match="invented citation"):
        tools.propose_diagnosis(incident, "made-up grounding", [fake])
    row = _working_state(incident)
    assert row[0] is None  # nothing persisted


def test_propose_diagnosis_unknown_incident_raises():
    with pytest.raises(LookupError, match="no incident"):
        tools.propose_diagnosis(str(uuid.uuid4()), "orphan diagnosis", [])


def test_empty_citations_require_confidence_none(incident):
    with pytest.raises(ValueError, match="honesty branch"):
        tools.propose_diagnosis(incident, "uncited guess", [])


def test_empty_citations_allowed_on_honesty_branch(incident):
    result = tools.SearchResult(
        query="q", service="billing", confidence="none", matches=[], runbook_ids=[],
    )
    tools.record_retrieval(incident, result)
    tools.propose_diagnosis(incident, "no close match in memory; escalating", [])
    row = _working_state(incident)
    assert row[0] == "no close match in memory; escalating"
    assert row[1] == "none"
    assert row[2] is not None


def test_write_incident_scrubs_resolves_and_embeds(incident):
    tools.write_incident(incident, "Fixed by Alice Nakamura, ping @alice or alice@orbital.dev")
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT resolution_summary, status, resolved_at, embedding IS NOT NULL,"
            " blame_scrubbed FROM incidents WHERE id = %s",
            (incident,),
        )
        summary, status, resolved_at, has_embedding, blame_scrubbed = cur.fetchone()
    assert "Alice" not in summary and "@alice" not in summary and "alice@" not in summary
    assert status == "resolved" and resolved_at is not None
    assert has_embedding and blame_scrubbed


def test_status_snapshot_reads_incident_and_working_state(incident):
    tools.record_retrieval(incident, tools.SearchResult(
        query="q", service="billing", confidence="high", matches=[], runbook_ids=[]))
    tools.propose_diagnosis(incident, "pool exhausted", [incident])
    snap = tools.status_snapshot(incident)
    assert snap["incident_id"] == incident
    assert snap["proposed_diagnosis"] == "pool exhausted"
    assert snap["confidence"] == "high"
    # External-ID lookup works too (the demo curls INC-style IDs):
    assert tools.status_snapshot(snap["external_id"])["incident_id"] == incident


def test_status_snapshot_unknown_returns_none():
    assert tools.status_snapshot(str(uuid.uuid4())) is None


def test_health_counts_incidents(incident):
    assert tools.health()["incidents"] >= 1


def test_write_incident_unknown_id_raises():
    with pytest.raises(LookupError, match="no incident"):
        tools.write_incident(str(uuid.uuid4()), "resolution for a ghost")
