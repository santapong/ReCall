"""The one retry wrapper (docs/05): silent retries, loud exhaustion."""

import psycopg
import pytest

import db


def test_retries_serialization_failure_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise psycopg.errors.SerializationFailure()
        return 42

    assert db.with_retry(flaky, max_attempts=3, base_delay=0.001) == 42
    assert calls["n"] == 3


def test_raises_loudly_after_max_attempts(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)

    def always_fails():
        raise psycopg.errors.SerializationFailure()

    with pytest.raises(psycopg.errors.SerializationFailure):
        db.with_retry(always_fails, max_attempts=3, base_delay=0.001)


def test_other_errors_are_not_retried():
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        db.with_retry(boom)
    assert calls["n"] == 1
