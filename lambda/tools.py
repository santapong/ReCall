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

import math
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

import db
from embed import embed, to_vector_literal

# Confidence thresholds (AC13): tuned once in P1 against the seeded corpus, then
# frozen — changing them later requires rerunning the full AC2 eval in the same
# commit (docs/05). NaN = not yet tuned.
CONF_HIGH_MAX_DIST = float(os.environ.get("CONFIDENCE_HIGH_MAX_DIST", "nan"))
CONF_NONE_MIN_DIST = float(os.environ.get("CONFIDENCE_NONE_MIN_DIST", "nan"))
DECAY_HALF_LIFE_DAYS = float(os.environ.get("DECAY_HALF_LIFE_DAYS", "90"))

# Titan v2 with normalize:true gives unit vectors, so L2 distance is bounded by 2.
# Used only to map a distance onto the 0..1 score the decay factor multiplies.
MAX_L2_DIST = 2.0


class Match(BaseModel):
    """One retrieved past incident. `id` is what the agent is allowed to cite (AC3)."""

    id: str
    external_id: str
    title: str
    resolution_summary: str | None = None
    service: str
    resolved_at: datetime | None = None
    distance: float = Field(description="raw L2 distance from the query vector")
    score: float = Field(description="decay-re-ranked relevance, higher is better")


class SearchResult(BaseModel):
    """What search_incidents hands back. `confidence` drives AC13's honesty branch."""

    query: str
    service: str
    confidence: str  # 'high' | 'low' | 'none'
    matches: list[Match]
    runbook_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Runbooks for this service, so the agent can call get_runbook without a "
            "search tool it is not allowed to have (AC4 keeps the manifest at 4)."
        ),
    )


class Runbook(BaseModel):
    id: str
    service: str
    title: str
    content: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def decay_score(distance: float, resolved_at: datetime | None, *, now: datetime | None = None,
                half_life_days: float | None = None) -> float:
    """docs/02: score = (1 - norm_distance) * exp(-age_days / half_life).

    Pure function of its arguments — `now` is injectable so the AC2 eval and the unit
    tests stay deterministic. An unresolved incident has no age to decay and scores on
    similarity alone; it is filtered out of search anyway, this is belt and braces.
    """
    half_life = DECAY_HALF_LIFE_DAYS if half_life_days is None else half_life_days
    similarity = 1.0 - (distance / MAX_L2_DIST)
    if resolved_at is None:
        return similarity
    reference = now or _now()
    if resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=timezone.utc)
    age_days = max((reference - resolved_at).total_seconds() / 86400.0, 0.0)
    return similarity * math.exp(-age_days / half_life)


def confidence_label(best_distance: float | None) -> str:
    """AC13's honesty branch, from the frozen thresholds. Fails loudly when untuned:
    NaN comparisons are silently False, which would label everything 'low' and quietly
    poison the one criterion that says the agent never bluffs."""
    if math.isnan(CONF_HIGH_MAX_DIST) or math.isnan(CONF_NONE_MIN_DIST):
        raise RuntimeError(
            "confidence thresholds are untuned — set CONFIDENCE_HIGH_MAX_DIST and "
            "CONFIDENCE_NONE_MIN_DIST (tuned once in P1 against the seeded corpus, "
            "docs/05). Refusing to guess a confidence label."
        )
    if best_distance is None or best_distance >= CONF_NONE_MIN_DIST:
        return "none"
    if best_distance <= CONF_HIGH_MAX_DIST:
        return "high"
    return "low"


_SEARCH_SQL = """
    SELECT id, external_id, service, title, resolution_summary, resolved_at,
           embedding <-> %(vec)s::VECTOR AS distance
    FROM incidents
    WHERE service = %(service)s AND status = 'resolved' AND embedding IS NOT NULL
    ORDER BY embedding <-> %(vec)s::VECTOR
    LIMIT %(k)s
"""

_RUNBOOK_IDS_SQL = "SELECT id FROM runbooks WHERE service = %(service)s ORDER BY title"

_RUNBOOK_SQL = "SELECT id, service, title, content FROM runbooks WHERE id = %(id)s"


def search_incidents(query: str, service: str, k: int = 5) -> SearchResult:
    """Embed query → vector search scoped to service → decay re-rank → matches +
    confidence label ('high' | 'low' | 'none', from the fixed thresholds above).

    Decay re-rank happens here in Python, not SQL (docs/02):
    score = (1 - norm_distance) * exp(-age_days / half_life).
    Returns a SearchResult model. AC2, AC13.
    """
    vector = to_vector_literal(embed(query))
    params = {"vec": vector, "service": service, "k": k}

    def _fetch():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_SEARCH_SQL, params)
            rows = cur.fetchall()
            cur.execute(_RUNBOOK_IDS_SQL, {"service": service})
            runbook_ids = [str(r[0]) for r in cur.fetchall()]
        return rows, runbook_ids

    rows, runbook_ids = db.with_retry(_fetch)

    now = _now()
    matches = [
        Match(
            id=str(row[0]),
            external_id=row[1],
            service=row[2],
            title=row[3],
            resolution_summary=row[4],
            resolved_at=row[5],
            distance=float(row[6]),
            score=decay_score(float(row[6]), row[5], now=now),
        )
        for row in rows
    ]
    # Rank by decayed score; confidence stays a function of raw distance, because
    # "how close is the nearest memory" must not be flattered by recency.
    matches.sort(key=lambda m: m.score, reverse=True)
    best_distance = min((m.distance for m in matches), default=None)

    return SearchResult(
        query=query,
        service=service,
        confidence=confidence_label(best_distance),
        matches=matches,
        runbook_ids=runbook_ids,
    )


def get_runbook(runbook_id: str) -> Runbook:
    """Read-only fetch by ID. No search. Returns a Runbook model."""

    def _fetch():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_RUNBOOK_SQL, {"id": runbook_id})
            return cur.fetchone()

    row = db.with_retry(_fetch)
    if row is None:
        raise LookupError(f"no runbook with id {runbook_id!r}")
    return Runbook(id=str(row[0]), service=row[1], title=row[2], content=row[3])


def propose_diagnosis(incident_id: str, diagnosis: str, cited_incident_ids: list[str]) -> None:
    """Write working_state ONLY. cited_incident_ids must be non-empty unless
    confidence == 'none' (AC3). Every ID is validated against the DB before the
    write — an unknown ID raises and never persists.
    """
    raise NotImplementedError("P2 — agent loop (docs/08 schedule)")


def write_incident(incident_id: str, resolution_summary: str) -> None:
    """Close path: blameless scrub (lambda/scrub.py) → embed the resolution →
    persist, so the very next similar alert can retrieve it (AC5).
    """
    raise NotImplementedError("P2 — agent loop (docs/08 schedule)")


# AC4: the closed manifest. tests/test_manifest.py asserts exactly these 4 names.
TOOL_MANIFEST = {
    "search_incidents": search_incidents,
    "get_runbook": get_runbook,
    "propose_diagnosis": propose_diagnosis,
    "write_incident": write_incident,
}
