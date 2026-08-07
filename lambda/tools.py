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
from scrub import scrub

# Confidence thresholds (AC13): tuned once in P1 against the seeded corpus, then
# frozen — changing them later requires rerunning the full AC2 eval in the same
# commit (docs/05). NaN = not yet tuned.
#
# `or` not a get() default: an unset key and a key set to "" must behave the same.
# .env.example ships these blank until P1 tuning, and blank env values are normal in
# the Lambda console, so `float("")` would otherwise raise at import — every request
# failing before any of our code runs, with the reason only in CloudWatch.
CONF_HIGH_MAX_DIST = float(os.environ.get("CONFIDENCE_HIGH_MAX_DIST") or "nan")
CONF_NONE_MIN_DIST = float(os.environ.get("CONFIDENCE_NONE_MIN_DIST") or "nan")
DECAY_HALF_LIFE_DAYS = float(os.environ.get("DECAY_HALF_LIFE_DAYS") or "90")

# Titan v2 with normalize:true gives unit vectors, so L2 distance is bounded by 2.
# Used only to map a distance onto the 0..1 score the decay factor multiplies.
MAX_L2_DIST = 2.0

# Upper bound on the model-supplied `k` in search_incidents. Well above AC2's top-3
# question and far below "the whole table".
MAX_SEARCH_K = 20


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


def clamp_k(k) -> int:
    """Bound the model-supplied result count.

    Parameterized SQL makes `k` injection-safe but not sane: k=100000 would pull the
    whole service's history through the LIMIT and then into
    working_state.retrieved_matches as JSONB. Non-integer input raises ValueError,
    which _dispatch already feeds back to the model as a correctable error.
    """
    return max(1, min(int(k), MAX_SEARCH_K))


def search_incidents(query: str, service: str, k: int = 5) -> SearchResult:
    """Embed query → vector search scoped to service → decay re-rank → matches +
    confidence label ('high' | 'low' | 'none', from the fixed thresholds above).

    Decay re-rank happens here in Python, not SQL (docs/02):
    score = (1 - norm_distance) * exp(-age_days / half_life).
    Returns a SearchResult model. AC2, AC13.
    """
    k = clamp_k(k)
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


_INSERT_INCIDENT_SQL = """
    INSERT INTO incidents (external_id, service, title, description, severity)
    VALUES (%(external_id)s, %(service)s, %(title)s, %(description)s, %(severity)s)
    ON CONFLICT (external_id) DO UPDATE SET external_id = excluded.external_id
    RETURNING id
"""

_INSERT_WORKING_STATE_SQL = """
    INSERT INTO working_state (incident_id) VALUES (%(incident_id)s)
    ON CONFLICT (incident_id) DO NOTHING
"""

_RECORD_RETRIEVAL_SQL = """
    INSERT INTO working_state (incident_id, retrieved_matches, confidence, updated_at)
    VALUES (%(incident_id)s, %(matches)s, %(confidence)s, now())
    ON CONFLICT (incident_id) DO UPDATE
        SET retrieved_matches = excluded.retrieved_matches,
            confidence = excluded.confidence,
            updated_at = now()
"""

_CONFIDENCE_SQL = """
    SELECT i.id, ws.confidence, ws.retrieved_matches
    FROM incidents i LEFT JOIN working_state ws ON ws.incident_id = i.id
    WHERE i.id = %(id)s
"""

_PROPOSE_SQL = """
    INSERT INTO working_state (incident_id, proposed_diagnosis, updated_at)
    VALUES (%(incident_id)s, %(diagnosis)s, now())
    ON CONFLICT (incident_id) DO UPDATE
        SET proposed_diagnosis = excluded.proposed_diagnosis, updated_at = now()
"""

_CLOSE_SQL = """
    UPDATE incidents
    SET resolution_summary = %(summary)s, status = 'resolved', resolved_at = now(),
        embedding = %(vec)s::VECTOR, blame_scrubbed = true
    WHERE id = %(id)s
    RETURNING id
"""


_STATUS_SQL = """
    SELECT i.id, i.external_id, i.service, i.title, i.severity, i.status, i.opened_at,
           ws.proposed_diagnosis, ws.confidence, ws.retrieved_matches, ws.updated_at
    FROM incidents i LEFT JOIN working_state ws ON ws.incident_id = i.id
    WHERE i.id::STRING = %(id)s OR i.external_id = %(id)s
"""

_HEALTH_SQL = "SELECT count(*) FROM incidents"


def status_snapshot(incident_id: str) -> dict | None:
    """Read path for the status page (docs/03): one incident + its working memory.
    Non-manifest — the camera reads this, not the agent. Accepts internal or
    external ID so the demo can curl INC-style IDs."""

    def _fetch():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_STATUS_SQL, {"id": incident_id})
            return cur.fetchone()

    row = db.with_retry(_fetch)
    if row is None:
        return None
    return {
        "incident_id": str(row[0]), "external_id": row[1], "service": row[2],
        "title": row[3], "severity": row[4], "status": row[5],
        "opened_at": row[6].isoformat() if row[6] else None,
        "proposed_diagnosis": row[7], "confidence": row[8],
        "retrieved_matches": row[9],
        "updated_at": row[10].isoformat() if row[10] else None,
    }


def health() -> dict:
    """Row count for the node-kill segment's /health endpoint (docs/03)."""

    def _fetch():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_HEALTH_SQL)
            return cur.fetchone()[0]

    return {"incidents": int(db.with_retry(_fetch))}


def insert_incident(external_id: str, service: str, title: str, description: str,
                    severity: str) -> str:
    """Ingest-side write (non-manifest — the agent never sees this; AC4 stays at 4).

    Idempotent on external_id (AC1): the same alert twice returns the same row. Also
    seeds the working_state row so the agent loop always has one to update.
    """
    params = {"external_id": external_id, "service": service, "title": title,
              "description": description, "severity": severity}

    def _write():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_INSERT_INCIDENT_SQL, params)
            incident_id = str(cur.fetchone()[0])
            cur.execute(_INSERT_WORKING_STATE_SQL, {"incident_id": incident_id})
        return incident_id

    return db.with_retry(_write)


def record_retrieval(incident_id: str, result: SearchResult) -> None:
    """Persist what the agent retrieved (non-manifest — called by the loop, not the
    model). working_state.confidence written here is what lets propose_diagnosis
    enforce AC3's cite-or-be-none rule, and AC11's time-travel query reads this row.
    """
    params = {
        "incident_id": incident_id,
        "matches": result.model_dump_json(include={"matches", "runbook_ids"}),
        "confidence": result.confidence,
    }
    def _write():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_RECORD_RETRIEVAL_SQL, params)

    db.with_retry(_write)


_LOG_STEP_SQL = """
    INSERT INTO agent_runs (run_id, incident_id, seq, step_type, name, outcome,
                            latency_ms, input_tokens, output_tokens, confidence, detail)
    VALUES (%(run_id)s, %(incident_id)s, %(seq)s, %(step_type)s, %(name)s, %(outcome)s,
            %(latency_ms)s, %(input_tokens)s, %(output_tokens)s, %(confidence)s,
            %(detail)s)
    ON CONFLICT (run_id, seq) DO NOTHING
"""

MAX_DETAIL_CHARS = 500


def log_step(*, run_id: str, incident_id: str, seq: int, step_type: str, name: str,
             outcome: str, latency_ms: int, input_tokens: int | None = None,
             output_tokens: int | None = None, confidence: str | None = None,
             detail: str | None = None) -> None:
    """Append one step to the replayable decision log (non-manifest — the loop calls
    this, never the model). Schema and rationale: infra/migrations/0002.

    **Deliberate exception to docs/05's "failures are loud".** Every other write in this
    module raises; this one swallows and prints. Telemetry that can fail a diagnosis is
    worse than no telemetry — an unreachable agent_runs table must never take down the
    incident response it is describing. Best-effort by design; the print keeps the drop
    visible in CloudWatch instead of silent.

    ADR — decision: best-effort logging. Alternatives: raise (couples availability of
    diagnosis to availability of observability), buffer-and-flush (state lost on a
    Lambda freeze). Flip condition: if the decision log ever becomes a compliance record
    rather than a debugging aid, it must become a loud write inside the same transaction
    as the step it describes.
    """
    params = {
        "run_id": run_id, "incident_id": incident_id, "seq": seq,
        "step_type": step_type, "name": name, "outcome": outcome,
        "latency_ms": int(latency_ms), "input_tokens": input_tokens,
        "output_tokens": output_tokens, "confidence": confidence,
        "detail": detail[:MAX_DETAIL_CHARS] if detail else None,
    }

    def _write():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_LOG_STEP_SQL, params)

    try:
        db.with_retry(_write)
    except Exception as exc:  # noqa: BLE001 — see the docstring; this is the whole point
        print(f"agent_runs log dropped (run={run_id} seq={seq}): {exc!r}")


_RUN_LOG_SQL = """
    SELECT seq, step_type, name, outcome, latency_ms, input_tokens, output_tokens,
           confidence, detail, created_at
    FROM agent_runs
    WHERE incident_id = %(id)s
    ORDER BY run_id, seq
"""


def run_log(incident_id: str) -> list[dict]:
    """Read path for the decision log (non-manifest — the status page and the camera
    read this, not the agent). Replays every step of every run for one incident, in
    execution order. Pairs with AS OF SYSTEM TIME: working_state says what memory
    believed at 02:14, this says what the agent did to get there and what it cost."""

    def _fetch():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_RUN_LOG_SQL, {"id": incident_id})
            return cur.fetchall()

    return [
        {"seq": r[0], "step_type": r[1], "name": r[2], "outcome": r[3],
         "latency_ms": r[4], "input_tokens": r[5], "output_tokens": r[6],
         "confidence": r[7], "detail": r[8],
         "created_at": r[9].isoformat() if r[9] else None}
        for r in db.with_retry(_fetch)
    ]


def propose_diagnosis(incident_id: str, diagnosis: str, cited_incident_ids: list[str]) -> None:
    """Write working_state ONLY. cited_incident_ids must be non-empty unless
    confidence == 'none' (AC3). Every ID is validated before the write — an ID the
    agent did not actually retrieve raises and never persists.

    Citations are checked for *provenance*, not mere existence. Validating against
    the whole incidents table (`WHERE id = ANY(...)`) only proves an ID is real, so
    any incident in the corpus passed — including one from a different service the
    agent never saw. Checking against this run's own retrieved_matches turns "the ID
    exists" into "the agent could only cite what it actually retrieved", which is
    the claim AC3 is worth making.
    """

    def _check():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_CONFIDENCE_SQL, {"id": incident_id})
            row = cur.fetchone()
            if row is None:
                raise LookupError(f"no incident with id {incident_id!r}")
            confidence = row[1]
            retrieved = row[2] or {}
            if cited_incident_ids:
                # record_retrieval persists what search_incidents returned — the loop
                # writes it, not the model, so it cannot be forged from inside the
                # conversation.
                known = {str(m.get("id")) for m in (retrieved.get("matches") or [])}
                if not known:
                    raise LookupError(
                        "diagnosis cites incidents but nothing was retrieved for this "
                        "run — call search_incidents before proposing (AC3)"
                    )
                unknown = [c for c in cited_incident_ids if c not in known]
                if unknown:
                    raise LookupError(
                        f"diagnosis cites incident ids {unknown} that were not in this "
                        "run's search results — refusing to persist a citation the "
                        "agent did not retrieve (AC3)"
                    )
            elif confidence != "none":
                raise ValueError(
                    "cited_incident_ids is empty but confidence is "
                    f"{confidence!r} — a diagnosis without citations is only legal "
                    "on the honesty branch (AC3/AC13)"
                )
            cur.execute(_PROPOSE_SQL, {"incident_id": incident_id, "diagnosis": diagnosis})

    db.with_retry(_check)


def write_incident(incident_id: str, resolution_summary: str) -> None:
    """Close path: blameless scrub (lambda/scrub.py) → embed the resolution →
    persist, so the very next similar alert can retrieve it (AC5).
    """
    scrubbed = scrub(resolution_summary)
    vector = to_vector_literal(embed(scrubbed))  # embed outside the retry: not a DB error

    def _write():
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(_CLOSE_SQL, {"summary": scrubbed, "vec": vector, "id": incident_id})
            if cur.fetchone() is None:
                raise LookupError(f"no incident with id {incident_id!r}")

    db.with_retry(_write)


# AC4: the closed manifest. tests/test_manifest.py asserts exactly these 4 names.
TOOL_MANIFEST = {
    "search_incidents": search_incidents,
    "get_runbook": get_runbook,
    "propose_diagnosis": propose_diagnosis,
    "write_incident": write_incident,
}
