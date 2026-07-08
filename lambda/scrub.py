"""Blameless-write scrubber (CLAUDE.md hard rule 3).

One function: scrub(text) -> str. Strips emails, @handles, and known-name
patterns from the seeded corpus's name list — the generator
(infra/seed/generate.py) and this module share that list so the test is
airtight: every seeded resolution + 20 adversarial strings, zero survivors.
"""


def scrub(text: str) -> str:
    raise NotImplementedError("P1 — lands with the seed corpus (docs/05 scrub pattern)")
