"""The ONLY module that owns connections. Nothing else calls psycopg.connect.

CockroachDB speaks the Postgres wire protocol; runtime path is psycopg 3 per
docs/02 Branch B — decision D2, closed 2026-08-02, no flip before submission.
"""

import random
import time

import psycopg

RETRYABLE = ("40001",)  # CRDB serialization conflict — expected under serializable isolation


def with_retry(fn, *, max_attempts=3, base_delay=0.2):
    """docs/05 error-handling pattern: retries are silent, failures are loud,
    nothing degrades quietly. Same shape is reused for Bedrock ThrottlingException
    in agent.py at P2."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except psycopg.errors.SerializationFailure:
            if attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))


def get_conn():
    """Open (or reuse) the connection from CRDB_CONN_STRING. Sole psycopg.connect site."""
    raise NotImplementedError("P1 — wired when the first real query lands")
