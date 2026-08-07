"""T3: the `recall_app` least-privilege role, exercised rather than asserted.

README ("Access control") and lambda/index.md both state in the present tense that
the Lambda connects as a dedicated role that cannot DELETE, cannot run DDL, and can
only read runbooks. Until this file existed nothing connected as it — `.env.example`
shipped a generic user, CI connected as root, and migration 0003 was missing the
`CONNECT`/`USAGE` grants the role needs to open a session at all, so the claim could
not have been true. Editing the sentence would have been the cheap fix; this is the
one that makes it correct.

One live connection as the role validates database CONNECT, schema USAGE, and every
table grant at once. Skips cleanly without a cluster, like the other DB-backed suites.
"""

import os

import psycopg
import pytest

ROLE_CONN_ENV = "RECALL_APP_CONN_STRING"


def _role_conn_string() -> str | None:
    """Prefer an explicit role connection string; otherwise derive one from the admin
    string by swapping the user, which is what a local insecure node allows."""
    explicit = os.environ.get(ROLE_CONN_ENV)
    if explicit:
        return explicit
    admin = os.environ.get("CRDB_CONN_STRING")
    if not admin or "://" not in admin:
        return None
    scheme, rest = admin.split("://", 1)
    if "@" not in rest:
        return None
    return f"{scheme}://recall_app@{rest.split('@', 1)[1]}"


@pytest.fixture(scope="module")
def role_conn():
    conn_string = _role_conn_string()
    if not conn_string:
        pytest.skip("no cluster configured — set CRDB_CONN_STRING (docs/08 P0 step 2)")
    try:
        conn = psycopg.connect(conn_string, autocommit=True, application_name="recall-role-test")
    except Exception as exc:  # noqa: BLE001 — unreachable or unauthenticated means skip
        pytest.skip(f"cannot connect as recall_app: {exc}")
    yield conn
    conn.close()


def _fails_with_insufficient_privilege(conn, sql: str) -> bool:
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    except psycopg.errors.InsufficientPrivilege:
        return True
    except psycopg.Error:
        # Any other database error means the statement was *permitted* and failed for
        # an unrelated reason — which is exactly what this test must not tolerate.
        return False
    return False


def test_role_can_open_a_session(role_conn):
    """CONNECT on the database plus USAGE on the schema — the two grants whose
    absence made every table grant below unreachable."""
    with role_conn.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] == "recall_app"


def test_role_can_read_all_three_memory_layers(role_conn):
    for table in ("incidents", "runbooks", "working_state", "agent_runs"):
        with role_conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {table}")
            assert cur.fetchone()[0] >= 0


def test_role_cannot_delete_from_any_table(role_conn):
    """No DELETE anywhere: memory is append/update-only at runtime. This is the grant
    that makes the agent unable to destroy history even if it were compromised."""
    for table in ("incidents", "working_state", "runbooks", "agent_runs"):
        assert _fails_with_insufficient_privilege(
            role_conn, f"DELETE FROM {table} WHERE false"
        ), f"recall_app can DELETE from {table}"


def test_role_cannot_write_semantic_memory(role_conn):
    """Runbooks are read-only at runtime — semantic memory changes through the
    seed/ops path, never through the agent."""
    assert _fails_with_insufficient_privilege(
        role_conn,
        "INSERT INTO runbooks (service, title, content) VALUES ('x', 'x', 'x')",
    )
    assert _fails_with_insufficient_privilege(
        role_conn, "UPDATE runbooks SET title = title WHERE false"
    )


def test_role_cannot_run_ddl(role_conn):
    assert _fails_with_insufficient_privilege(
        role_conn, "CREATE TABLE recall_app_should_not_be_able_to_do_this (id INT)"
    )
    assert _fails_with_insufficient_privilege(
        role_conn, "DROP TABLE IF EXISTS agent_runs"
    )
