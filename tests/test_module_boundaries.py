"""Module-boundary greps (docs/05): the structural hard rules, asserted.

- SQL writes (INSERT/UPDATE/DELETE) appear only in lambda/tools.py and infra/
- agent.py contains no SQL and no psycopg import
- within lambda/, only db.py imports psycopg; psycopg.connect exists only there

tests/ itself is excluded from the scans (assertions here quote the forbidden
tokens). SQL keywords are matched uppercase, the repo's SQL convention.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAMBDA = ROOT / "lambda"
SQL_WRITE = re.compile(r"\b(INSERT|UPDATE|DELETE)\b")
SKIP_DIRS = {"tests", ".venv", ".git", "__pycache__", "build", "dist", ".worktrees"}


def repo_py_files():
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT)
        if SKIP_DIRS & set(rel.parts):
            continue
        yield rel, path.read_text(encoding="utf-8")


def test_sql_writes_only_in_tools_and_infra():
    allowed = {Path("lambda/tools.py")}
    offenders = [
        str(rel)
        for rel, text in repo_py_files()
        if SQL_WRITE.search(text) and rel not in allowed and rel.parts[0] != "infra"
    ]
    assert not offenders, f"SQL writes outside tools.py/infra/: {offenders}"


def test_agent_has_no_sql_and_no_psycopg():
    text = (LAMBDA / "agent.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import psycopg|from psycopg)", text, re.M), (
        "agent.py imports psycopg"
    )
    assert not SQL_WRITE.search(text), "agent.py contains SQL write keywords"
    assert not re.search(r"\bSELECT\b", text), "agent.py contains SQL"


def test_psycopg_owned_by_db_module():
    for path in sorted(LAMBDA.glob("*.py")):
        if path.name == "db.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import psycopg|from psycopg)", text, re.M), (
            f"lambda/{path.name} imports psycopg — only db.py owns connections"
        )
    for rel, text in repo_py_files():
        if rel == Path("lambda/db.py"):
            continue
        assert "psycopg.connect" not in text, f"{rel} calls psycopg.connect"
