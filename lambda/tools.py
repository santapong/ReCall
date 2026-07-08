"""The agent's entire memory surface, and the ONLY module that writes to the DB.

Hard rules (CLAUDE.md 1–2, enforced by tests/):
- TOOL_MANIFEST is closed at exactly these 4 entries (AC4). No raw-SQL tool, no
  execute tool, no "temporary debug" tool — ever.
- Diagnosis writes touch working_state only; write_incident is the sole close path.
- Ingest-side writes (insert incident + working_state on alert) also live in this
  module as non-manifest helpers when P2 lands — the manifest is the agent-facing
  registry, not the whole module.

All SQL is parameterized; f-string SQL is a rejected commit (docs/05).
"""

import os

# Confidence thresholds (AC13): tuned once in P1 against the seeded corpus, then
# frozen — changing them later requires rerunning the full AC2 eval in the same
# commit (docs/05). NaN = not yet tuned.
CONF_HIGH_MAX_DIST = float(os.environ.get("CONFIDENCE_HIGH_MAX_DIST", "nan"))
CONF_NONE_MIN_DIST = float(os.environ.get("CONFIDENCE_NONE_MIN_DIST", "nan"))
DECAY_HALF_LIFE_DAYS = float(os.environ.get("DECAY_HALF_LIFE_DAYS", "90"))


def search_incidents(query: str, service: str, k: int = 5):
    """Embed query → vector search scoped to service → decay re-rank → matches +
    confidence label ('high' | 'low' | 'none', from the fixed thresholds above).

    Decay re-rank happens here in Python, not SQL (docs/02):
    score = (1 - norm_distance) * exp(-age_days / half_life).
    Returns a SearchResult model. AC2, AC13.
    """
    raise NotImplementedError("P1 — memory foundation (docs/01 phase table)")


def get_runbook(runbook_id: str):
    """Read-only fetch by ID. No search. Returns a Runbook model."""
    raise NotImplementedError("P1 — memory foundation (docs/01 phase table)")


def propose_diagnosis(incident_id: str, diagnosis: str, cited_incident_ids: list[str]) -> None:
    """Write working_state ONLY. cited_incident_ids must be non-empty unless
    confidence == 'none' (AC3). Every ID is validated against the DB before the
    write — an unknown ID raises and never persists.
    """
    raise NotImplementedError("P2 — agent loop (docs/01 phase table)")


def write_incident(incident_id: str, resolution_summary: str) -> None:
    """Close path: blameless scrub (lambda/scrub.py) → embed the resolution →
    persist, so the very next similar alert can retrieve it (AC5).
    """
    raise NotImplementedError("P2 — agent loop (docs/01 phase table)")


# AC4: the closed manifest. tests/test_manifest.py asserts exactly these 4 names.
TOOL_MANIFEST = {
    "search_incidents": search_incidents,
    "get_runbook": get_runbook,
    "propose_diagnosis": propose_diagnosis,
    "write_incident": write_incident,
}
