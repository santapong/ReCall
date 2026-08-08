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
        # agent_runs first: it holds an FK to incidents, so any test that logs a step
        # would otherwise break teardown rather than fail on its own merits.
        cur.execute("DELETE FROM agent_runs WHERE incident_id = %s", (incident_id,))
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


def _retrieve(incident_id, *match_ids, confidence="high"):
    """Persist a search result citing match_ids, exactly as the loop does after
    search_incidents. Citations are validated against this, so a test that proposes
    without it is testing a diagnosis the agent could not have grounded."""
    tools.record_retrieval(incident_id, tools.SearchResult(
        query="q", service="billing", confidence=confidence, runbook_ids=["rb-1"],
        matches=[tools.Match(
            id=str(mid), external_id=f"ext-{mid}", title="past incident",
            service="billing", distance=0.2, score=0.8,
        ) for mid in match_ids],
    ))


def test_propose_diagnosis_with_valid_citation_persists(incident):
    _retrieve(incident, incident)
    tools.propose_diagnosis(incident, "webhook pool exhausted", [incident], ["rb-1"])
    row = _working_state(incident)
    assert row[0] == "webhook pool exhausted"


def test_propose_diagnosis_fake_id_raises_and_never_persists(incident):
    _retrieve(incident, incident)
    fake = str(uuid.uuid4())  # valid UUID, no such incident — the AC3 case
    with pytest.raises(LookupError, match="not in this run's search results"):
        tools.propose_diagnosis(incident, "made-up grounding", [fake])
    row = _working_state(incident)
    assert row[0] is None  # nothing persisted


def test_propose_diagnosis_rejects_a_real_but_unretrieved_incident(incident):
    """T4, the provenance half. Validating citations against the whole incidents
    table only proved an ID was real — an incident from another service that the
    agent never retrieved passed just as easily. This is the case that used to slip
    through, and it is the difference between 'the ID exists' and 'the agent could
    only cite what it actually retrieved'."""
    other = tools.insert_incident(
        f"test-{uuid.uuid4()}", "shipping", "unrelated incident", "elsewhere", "sev3",
    )
    try:
        _retrieve(incident, incident)  # the agent retrieved this one, not `other`
        with pytest.raises(LookupError, match="not in this run's search results"):
            tools.propose_diagnosis(incident, "citing something I never saw", [other])
        assert _working_state(incident)[0] is None
    finally:
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM working_state WHERE incident_id = %s", (other,))
            cur.execute("DELETE FROM incidents WHERE id = %s", (other,))


def test_propose_diagnosis_requires_a_search_before_citing(incident):
    """Citing anything at all before calling search_incidents is not groundable."""
    with pytest.raises(LookupError, match="nothing was retrieved"):
        tools.propose_diagnosis(incident, "grounded in thin air", [incident])
    assert _working_state(incident)[0] is None


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
    _retrieve(incident, incident)
    tools.propose_diagnosis(incident, "pool exhausted", [incident], ["rb-1"])
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


def test_run_log_accepts_an_external_id(incident):
    """F1 surfaced this: /status resolves external IDs and /runlog did not, while the
    status page passes one incident_id to both. The demo curls INC-style IDs, so the
    decision-log panel 500'd on camera while the rest of the page rendered fine."""
    tools.log_step(run_id=str(uuid.uuid4()), incident_id=incident, seq=0,
                   step_type="model_turn", name="test-model", outcome="success",
                   latency_ms=1)
    external_id = tools.status_snapshot(incident)["external_id"]

    by_uuid = tools.run_log(incident)
    by_external = tools.run_log(external_id)

    assert len(by_uuid) == 1
    assert by_external == by_uuid


def test_run_log_of_an_unknown_id_is_empty_not_an_error():
    """The page polls this before the incident row exists."""
    assert tools.run_log("NOPE-does-not-exist") == []


# --- T4, runbook half: AC3 is "incident ID **+ runbook step**" ---------------
# docs/01:48 always required both. propose_diagnosis took no runbook parameter, so
# the runbook half lived only in prompts/system.md rule 4 — instructional, not
# structural, exactly the gap T1 closed for write_incident.


def test_runbook_citation_is_validated_and_persisted(incident):
    _retrieve(incident, incident)          # offers runbook_ids=["rb-1"]
    tools.propose_diagnosis(incident, "pool exhausted; drain per rb-1",
                            [incident], ["rb-1"])
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT cited_runbook_ids FROM working_state WHERE incident_id = %s",
                    (incident,))
        assert cur.fetchone()[0] == ["rb-1"]


def test_unretrieved_runbook_is_refused(incident):
    """Same provenance rule as incidents: a runbook the agent never pulled cannot be
    cited, even if it exists."""
    _retrieve(incident, incident)          # only rb-1 was offered
    with pytest.raises(LookupError, match="runbook ids"):
        tools.propose_diagnosis(incident, "citing a runbook I never saw",
                                [incident], ["rb-99"])
    assert _working_state(incident)[0] is None   # nothing persisted


def test_high_confidence_diagnosis_without_a_runbook_is_refused(incident):
    """The half that was missing entirely: a grounded diagnosis citing incidents but
    no runbook step used to pass, contradicting docs/01's AC3."""
    _retrieve(incident, incident)
    with pytest.raises(ValueError, match="cited_runbook_ids is empty"):
        tools.propose_diagnosis(incident, "no runbook step named", [incident], [])
    assert _working_state(incident)[0] is None


def test_honesty_branch_still_needs_neither_citation(incident):
    """AC13 outranks AC3: with nothing close in memory the agent must be able to say
    so and stop, citing nothing at all."""
    tools.record_retrieval(incident, tools.SearchResult(
        query="q", service="billing", confidence="none", matches=[], runbook_ids=[]))
    tools.propose_diagnosis(incident, "no close match in memory; escalating", [], [])
    assert _working_state(incident)[0] == "no close match in memory; escalating"


def test_status_snapshot_exposes_cited_runbooks(incident):
    """The page and the camera read this."""
    _retrieve(incident, incident)
    tools.propose_diagnosis(incident, "d", [incident], ["rb-1"])
    assert tools.status_snapshot(incident)["cited_runbook_ids"] == ["rb-1"]
