"""AC2's integrity guard: the eval set must not be solvable by string overlap.

Regression origin (2026-08-04). The generator paired each eval alert with its target
incident by reusing `arch["title"]` for both, so all 20 alert titles were byte-identical
to their target's title (similarity 1.00, 20/20). `tools.search_incidents` embeds
`title + "\\n" + description`, so the query literally contained the target document's
title. AC2 would have scored 20/20 on lexical identity and reported it as semantic
retrieval — a benchmark that cannot fail measures nothing, and the README points judges
straight at it.

The sharp test is not "are the strings different" — it is **can the target be singled
out of its own search space by string match alone**. Search is service-scoped, so the
search space for an alert is the other incidents of that same service. If the alert
title shares a token with the target that no sibling incident has, that token is a
free answer key and retrieval never has to understand anything.

These tests read the committed fixtures, so they fail whether the generator or the
JSON drifts. They are pure — no DB, no Bedrock — and run in the fast suite.
"""

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = json.loads((REPO / "infra/seed/corpus.json").read_text())
PAIRS = json.loads((REPO / "tests/fixtures/eval_pairs.json").read_text())

# Coarse ceiling. Two honest descriptions of the same failure share some vocabulary;
# 0.60 catches copies and near-copies without demanding artificial divergence.
MAX_TITLE_SIMILARITY = 0.60

# Words that carry no diagnostic information, so sharing them proves nothing. Service
# names are here for the same reason: search is already scoped to the service, so
# "gateway" cannot discriminate between two api-gateway incidents.
STOPWORDS = frozenset("""
a an and are as at be been below by during for from has have in into is it its of on
one only or over per since the their then there this to under up upon versus via was
were what when where which while with without
after above across again against all also any because before being between both each
few further here how more most no nor not now other out own same so some such than
that these those through too very
api gateway auth billing search notifications db cluster orbital service services
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    """Content tokens: lowercase alphanumerics, stopwords and 1-char noise removed."""
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS}


def _by_service() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for inc in CORPUS["incidents"]:
        out.setdefault(inc["service"], []).append(inc)
    return out


def test_alert_title_is_never_a_copy_of_the_target_title():
    """The original bug, stated as an assertion. Reports every offender at once."""
    by_id = {i["external_id"]: i for i in CORPUS["incidents"]}
    offenders = []
    for pair in PAIRS:
        alert_title = pair["alert"]["title"]
        target_title = by_id[pair["expected_incident_external_id"]]["title"]
        ratio = SequenceMatcher(None, alert_title.lower(), target_title.lower()).ratio()
        if ratio > MAX_TITLE_SIMILARITY:
            offenders.append(
                f"  {pair['alert']['external_id']} ~ "
                f"{pair['expected_incident_external_id']} ({ratio:.2f})\n"
                f"    alert : {alert_title}\n"
                f"    target: {target_title}"
            )
    assert not offenders, (
        f"{len(offenders)}/{len(PAIRS)} alert titles exceed similarity "
        f"{MAX_TITLE_SIMILARITY} against their target:\n" + "\n".join(offenders)
    )


def test_no_alert_title_token_uniquely_identifies_its_target():
    """The real guard: no free answer key inside the service-scoped search space.

    A token shared by the alert title and the target title, and by NO other incident
    in that service, would let plain string matching win without semantics.
    """
    by_id = {i["external_id"]: i for i in CORPUS["incidents"]}
    per_service = _by_service()
    offenders = []

    for pair in PAIRS:
        target = by_id[pair["expected_incident_external_id"]]
        shared = _tokens(pair["alert"]["title"]) & _tokens(target["title"])
        siblings = [
            i for i in per_service[target["service"]]
            if i["external_id"] != target["external_id"]
        ]
        for token in sorted(shared):
            if not any(token in _tokens(s["title"]) for s in siblings):
                offenders.append(
                    f"  {pair['alert']['external_id']} → "
                    f"{target['external_id']}: {token!r} appears in the alert title and "
                    f"in no other {target['service']} incident title"
                )

    assert not offenders, (
        "alert titles leak a unique lexical key to their target:\n" + "\n".join(offenders)
    )


def test_alert_description_is_a_paraphrase_not_a_copy():
    """symptom_b carries the retrieval signal; it must still not be symptom_a."""
    by_id = {i["external_id"]: i for i in CORPUS["incidents"]}
    for pair in PAIRS:
        target = by_id[pair["expected_incident_external_id"]]
        alert_desc = pair["alert"]["description"]
        assert alert_desc != target["description"]
        ratio = SequenceMatcher(None, alert_desc.lower(), target["description"].lower()).ratio()
        assert ratio < 0.85, (
            f"{pair['alert']['external_id']} description is a near-copy "
            f"({ratio:.2f}) of {target['external_id']}"
        )


def test_alert_still_shares_real_meaning_with_its_target():
    """The opposite failure mode: scrubbing the titles so hard the pair stops being a
    pair. Alert and target must still overlap somewhere across title + description —
    otherwise the benchmark is unfair rather than merely easy."""
    by_id = {i["external_id"]: i for i in CORPUS["incidents"]}
    for pair in PAIRS:
        target = by_id[pair["expected_incident_external_id"]]
        alert = _tokens(pair["alert"]["title"] + " " + pair["alert"]["description"])
        inc = _tokens(target["title"] + " " + target["description"])
        assert len(alert & inc) >= 2, (
            f"{pair['alert']['external_id']} and {target['external_id']} share "
            f"{sorted(alert & inc)} — too little common ground to be a valid pair"
        )
