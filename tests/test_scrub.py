"""Hard rule 3: blameless writes — zero survivors (docs/05 scrub pattern).

Every seeded resolution plus 20 adversarial strings go through scrub();
no email, @handle, or roster name survives.
"""

import json
import re
from pathlib import Path

from scrub import NAME_LIST, REDACTED, scrub

CORPUS = json.loads((Path(__file__).resolve().parents[1] / "infra/seed/corpus.json").read_text())

ADVERSARIAL = [
    "Alice Nakamura restarted the pods at 02:14.",
    "paged ben ortiz who rolled back the deploy",
    "root cause found by Chidi (see thread)",
    "DANA PETROV confirmed the fix in prod",
    "elena.vasquez@orbital.dev approved the change",
    "escalated to farid.haddad+oncall@orbital.dev",
    "thanks @grace.lindqvist for the quick rollback",
    "cc @hiro_tanaka on the postmortem",
    "Ingrid Sørensen owns the follow-up items",
    "jonas said the cache was cold — jonas.weber@orbital.dev",
    "Kavya Raman and Liam Doyle traced the leak together",
    "handoff from mai to noor at shift change",
    "Otis restarted node 3; Priya verified row counts",
    "contact priya.shah@orbital.dev or @otis-brennan",
    "reviewed-by: Ben; approved-by: Alice",
    "the fix (thanks HIRO!) shipped in v2.3.1",
    "Grace's dashboard caught it first",
    "ping @Liam or email mai.pham@orbital.dev",
    "NOOR RAHIMI + jonas debugged the planner regression",
    "postmortem doc by kavya@orbital.dev, reviewed by Dana",
]

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_.-]+")
_NAME_TOKENS = {n.lower() for n in NAME_LIST}


def _survivors(text: str) -> list[str]:
    out = _EMAIL.findall(text.replace(REDACTED, "")) + _HANDLE.findall(
        text.replace(REDACTED, "")
    )
    out += [w for w in re.findall(r"[A-Za-zÀ-ÿ]+", text) if w.lower() in _NAME_TOKENS]
    return out


def test_adversarial_strings_have_zero_survivors():
    assert len(ADVERSARIAL) == 20
    for s in ADVERSARIAL:
        assert not _survivors(scrub(s)), f"survivor in: {scrub(s)!r}"


def test_every_seeded_text_is_blameless_by_construction():
    for inc in CORPUS["incidents"]:
        for field in ("title", "description", "resolution_summary"):
            assert scrub(inc[field]) == inc[field], f"{inc['external_id']}.{field}"
    for rb in CORPUS["runbooks"]:
        assert scrub(rb["content"]) == rb["content"], rb["external_id"]


def test_scrub_is_idempotent():
    for s in ADVERSARIAL:
        once = scrub(s)
        assert scrub(once) == once
