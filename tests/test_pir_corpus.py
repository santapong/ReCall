"""Guards for the real-PIR track (review 2026-08-04, Real-World Impact).

The pinned AC2 eval set must be untouched by this corpus: every PIR incident lives
in its own 'public' service, which no eval alert targets — service-scoped search
means the two tracks cannot contaminate each other. Summaries must be blameless
and loader-shaped like the Orbital corpus.
"""

import json
from datetime import datetime
from pathlib import Path

from scrub import scrub

SEED = Path(__file__).resolve().parent.parent / "infra" / "seed"
PIR = json.loads((SEED / "pir_corpus.json").read_text(encoding="utf-8"))
PAIRS = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "eval_pairs.json").read_text()
)

REQUIRED = ("external_id", "service", "title", "description", "severity", "status",
            "resolution_summary", "opened_at", "resolved_at")


def test_shape_matches_the_loader_contract():
    incidents = PIR["incidents"]
    assert len(incidents) >= 10, "review target: 10-15 real PIRs"
    for inc in incidents:
        for key in REQUIRED:
            assert inc.get(key), f"{inc.get('external_id')}: missing {key}"
        assert inc["status"] == "resolved"
        opened = datetime.fromisoformat(inc["opened_at"])
        resolved = datetime.fromisoformat(inc["resolved_at"])
        assert resolved > opened, f"{inc['external_id']}: resolved before opened"
        assert "Source: " in inc["resolution_summary"], (
            f"{inc['external_id']}: a real PIR must cite its source"
        )


def test_external_ids_unique_and_pir_prefixed():
    ids = [i["external_id"] for i in PIR["incidents"]]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("PIR-") for i in ids)


def test_isolated_in_its_own_service():
    assert {i["service"] for i in PIR["incidents"]} == {"public"}
    eval_services = {p["alert"]["service"] for p in PAIRS}
    assert "public" not in eval_services, (
        "an eval alert targets the PIR service — the tracks must stay isolated (AC2)"
    )


def test_summaries_are_blameless():
    for inc in PIR["incidents"]:
        for field in ("title", "description", "resolution_summary"):
            text = inc[field]
            assert scrub(text) == text, (
                f"{inc['external_id']}.{field} changed under scrub — "
                "names/handles/emails must never be in a PIR summary"
            )
