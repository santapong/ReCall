"""AC2 substrate: the corpus is deterministic, pinned, and pair-aligned.

The committed corpus.json / eval_pairs.json must be exactly what the generator
produces — if this fails, someone changed the generator (or the RNG seed)
without regenerating, and the pinned AC2 expectations are no longer trustworthy.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "infra" / "seed"))
from generate import SERVICES, build_corpus  # noqa: E402

CORPUS_FILE = json.loads((REPO / "infra/seed/corpus.json").read_text())
PAIRS_FILE = json.loads((REPO / "tests/fixtures/eval_pairs.json").read_text())


def test_generator_is_deterministic():
    assert build_corpus() == build_corpus()


def test_committed_files_match_generator_output():
    built = build_corpus()
    assert {"incidents": built["incidents"], "runbooks": built["runbooks"]} == CORPUS_FILE
    assert built["eval_pairs"] == PAIRS_FILE


def test_corpus_shape():
    incidents = CORPUS_FILE["incidents"]
    assert len(incidents) == 80
    assert len(PAIRS_FILE) == 20
    assert {i["service"] for i in incidents} == set(SERVICES)
    per_service_runbooks = {s: 0 for s in SERVICES}
    for rb in CORPUS_FILE["runbooks"]:
        per_service_runbooks[rb["service"]] += 1
    assert all(n == 2 for n in per_service_runbooks.values())
    assert len({i["external_id"] for i in incidents}) == 80  # unique ids


def test_eval_pairs_are_aligned_paraphrases():
    by_id = {i["external_id"]: i for i in CORPUS_FILE["incidents"]}
    for pair in PAIRS_FILE:
        target = by_id[pair["expected_incident_external_id"]]  # KeyError = broken pin
        alert = pair["alert"]
        assert alert["service"] == target["service"]
        assert target["status"] == "resolved"
        assert target["is_eval_target"] is True
        # paraphrase, not copy — retrieval must work on meaning
        assert alert["description"] != target["description"]


def test_eval_targets_use_distinct_archetypes_within_service():
    seen = set()
    for pair in PAIRS_FILE:
        key = (pair["alert"]["service"], pair["archetype"])
        assert key not in seen, f"duplicate eval archetype {key}"
        seen.add(key)
