"""The ONLY module that owns connections. Nothing else calls psycopg.connect.

CockroachDB speaks the Postgres wire protocol; runtime path is psycopg 3 per
docs/02 Branch B — decision D2, closed 2026-08-02, no flip before submission.
"""

import os
import random
import time

import psycopg

RETRYABLE = ("40001",)  # CRDB serialization conflict — expected under serializable isolation

# AC7: when a node dies mid-diagnosis the in-flight answer must still land. A dropped
# connection surfaces as OperationalError, not SerializationFailure, so retrying only
# on 40001 would fail the one demo we are not allowed to cut. The cached connection is
# discarded and reopened on the next attempt — CockroachDB routes us to a live node.
RECONNECTABLE = (psycopg.OperationalError, psycopg.InterfaceError)

_conn = None


def with_retry(fn, *, max_attempts=3, base_delay=0.2):
    """docs/05 error-handling pattern: retries are silent, failures are loud,
    nothing degrades quietly. Same shape is reused for Bedrock ThrottlingException
    in embed.with_throttle_retry (and agent.py at P2)."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except psycopg.errors.SerializationFailure:
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))
        except RECONNECTABLE:
            close_conn()  # force a fresh connection to a surviving node (AC7)
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))


def get_conn():
    """Open (or reuse) the connection from CRDB_CONN_STRING. Sole psycopg.connect site.

    Module-level reuse is deliberate: a warm Lambda container keeps the connection
    across invocations, which is what keeps AC1 under 5 s.
    """
    global _conn
    if _conn is None or _conn.closed:
        conn_string = os.environ.get("CRDB_CONN_STRING")
        if not conn_string:
            raise RuntimeError(
                "CRDB_CONN_STRING is unset — copy .env.example to .env and paste the "
                "cluster connection string (docs/08 P0 step 2)"
            )
        _conn = psycopg.connect(conn_string, autocommit=True, application_name="recall")
    return _conn


def close_conn():
    """Drop the cached connection. Called on a broken link, and by tests."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:  # noqa: BLE001 — closing a dead socket must never mask the real error
            pass
        _conn = None
