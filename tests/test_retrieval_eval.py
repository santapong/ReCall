"""AC2 — the retrieval eval: 20 scripted alerts, planted match in top-3 for >= 18.

Runs against the live, seeded, embedded cluster (needs CRDB_CONN_STRING, Bedrock
creds, and the tuned confidence thresholds). Skips — loudly, with the reason — when
the substrate isn't there, so the fast suite stays green pre-P1. Prints the full
hit table; the passing table's screenshot goes in the README (docs/05).

Run with: uv run pytest tests/retrieval_eval.py -s
"""

import json
import os
from pathlib import Path

import pytest

import db
import tools

PAIRS = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "eval_pairs.json").read_text()
)
TOP_K = 3
PASS_FLOOR = 18


@pytest.fixture(scope="module")
def _substrate():
    if not os.environ.get("CRDB_CONN_STRING"):
        pytest.skip("CRDB_CONN_STRING unset")
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE")):
        pytest.skip("no AWS credentials — search embeds the query via Bedrock")
    try:
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM incidents WHERE embedding IS NOT NULL")
            embedded = cur.fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"cluster not reachable: {exc}")
    if embedded < len(PAIRS):
        pytest.skip(f"only {embedded} embedded incidents — run infra/seed/load.py first")
    yield
    db.close_conn()


def test_planted_match_in_top3_for_at_least_18_of_20(_substrate):
    assert len(PAIRS) == 20, "eval set drifted — AC2 is defined over exactly 20 alerts"
    hits = 0
    rows = []
    for pair in PAIRS:
        alert = pair["alert"]
        result = tools.search_incidents(
            f"{alert['title']}\n{alert['description']}", alert["service"], k=TOP_K,
        )
        top = [m.external_id for m in result.matches[:TOP_K]]
        hit = pair["expected_incident_external_id"] in top
        hits += hit
        rows.append((alert["external_id"], pair["expected_incident_external_id"],
                     "HIT " if hit else "MISS", result.confidence, ", ".join(top)))

    print(f"\n{'alert':<12}{'expected':<12}{'':<6}{'conf':<6}top-{TOP_K}")
    for row in rows:
        print(f"{row[0]:<12}{row[1]:<12}{row[2]:<6}{row[3]:<6}{row[4]}")
    print(f"\n{hits}/{len(PAIRS)} planted matches in top-{TOP_K} (floor: {PASS_FLOOR})")

    assert hits >= PASS_FLOOR, f"AC2 fails: {hits}/{len(PAIRS)} < {PASS_FLOOR}"
