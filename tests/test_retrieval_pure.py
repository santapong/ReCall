"""AC13 + AC2's ranking maths, as pure functions — no DB, no Bedrock.

The DB-backed halves of search_incidents/get_runbook are covered by the real-cluster
AC2 eval (retrieval_eval.py, post-probe); mocked-DB tests are banned (docs/05). What
is testable without a cluster is exactly what this file covers: the decay curve, the
confidence branch, and the vector wire format.
"""

import math
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

import db
import tools
from embed import to_vector_literal

NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def test_identical_vector_scores_higher_than_distant_one():
    near = tools.decay_score(0.1, NOW, now=NOW)
    far = tools.decay_score(1.4, NOW, now=NOW)
    assert near > far


def test_decay_halves_the_score_at_one_half_life():
    fresh = tools.decay_score(0.2, NOW, now=NOW, half_life_days=90)
    aged = tools.decay_score(0.2, NOW - timedelta(days=90), now=NOW, half_life_days=90)
    assert aged == pytest.approx(fresh * math.exp(-1), rel=1e-9)


def test_recent_weaker_match_can_outrank_stale_stronger_one():
    """The point of the decay re-rank: last week's near-miss beats last year's twin."""
    stale_twin = tools.decay_score(0.15, NOW - timedelta(days=400), now=NOW)
    recent_near = tools.decay_score(0.45, NOW - timedelta(days=3), now=NOW)
    assert recent_near > stale_twin


def test_unresolved_incident_scores_on_similarity_alone():
    assert tools.decay_score(0.5, None, now=NOW) == pytest.approx(1.0 - 0.5 / 2.0)


def test_naive_datetimes_are_treated_as_utc_not_crashed():
    naive = tools.decay_score(0.3, NOW.replace(tzinfo=None), now=NOW)
    aware = tools.decay_score(0.3, NOW, now=NOW)
    assert naive == pytest.approx(aware)


def _tuned(monkeypatch, high=0.35, none=0.85):
    monkeypatch.setattr(tools, "CONF_HIGH_MAX_DIST", high)
    monkeypatch.setattr(tools, "CONF_NONE_MIN_DIST", none)


def test_confidence_bands(monkeypatch):
    _tuned(monkeypatch)
    assert tools.confidence_label(0.10) == "high"
    assert tools.confidence_label(0.35) == "high"  # boundary is inclusive
    assert tools.confidence_label(0.50) == "low"
    assert tools.confidence_label(0.90) == "none"


def test_no_matches_is_none_not_low(monkeypatch):
    """AC13: an empty index must say 'none', never a shrug that reads as a weak hit."""
    _tuned(monkeypatch)
    assert tools.confidence_label(None) == "none"


def test_untuned_thresholds_raise_instead_of_guessing():
    """NaN comparisons are silently False — that would label everything 'low' and
    quietly break the one criterion that says the agent never bluffs."""
    assert math.isnan(tools.CONF_HIGH_MAX_DIST), "thresholds are tuned in P1, not before"
    with pytest.raises(RuntimeError, match="untuned"):
        tools.confidence_label(0.2)


def test_vector_literal_round_trips_as_a_bound_parameter():
    literal = to_vector_literal([0.5, -0.25, 0.0])
    assert literal.startswith("[") and literal.endswith("]")
    assert [float(x) for x in literal[1:-1].split(",")] == [0.5, -0.25, 0.0]


def test_broken_connection_is_retried_and_reconnected(monkeypatch):
    """AC7: a node dying mid-diagnosis surfaces as OperationalError, not a
    serialization failure. The in-flight answer still has to land."""
    monkeypatch.setattr("time.sleep", lambda _s: None)
    closed = {"n": 0}
    monkeypatch.setattr(db, "close_conn", lambda: closed.__setitem__("n", closed["n"] + 1))
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise psycopg.OperationalError("connection to node lost")
        return "diagnosis landed"

    assert db.with_retry(flaky, max_attempts=3, base_delay=0.001) == "diagnosis landed"
    assert closed["n"] == 1, "the dead connection must be dropped before retrying"
