"""Bedrock Converse loop — custom, small by design (docs/04).

ZERO SQL in this file, no psycopg import, ever (docs/05 module boundary — a test
greps for it). This module sees the functions in tools.TOOL_MANIFEST (plus the
loop-side record_retrieval and log_step helpers) and nothing else. The system prompt
is loaded from prompts/system.md at runtime, never inlined — prompt changes must be
diffable.

Every step the loop takes is appended to the agent_runs decision log via
tools.log_step: one row per model turn and per tool call, in execution order, with
latency, tokens, and outcome. Logging is best-effort and can never fail a diagnosis —
see the ADR in tools.log_step.
"""

import json
import os
import time
import uuid
from pathlib import Path

import boto3

import tools
from embed import with_throttle_retry

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
MAX_TURNS = 12

# Repo layout: lambda/../prompts/. Deployed zip (flat, make deploy): ./prompts/.
_PROMPT_CANDIDATES = (
    Path(__file__).resolve().parent / "prompts" / "system.md",
    Path(__file__).resolve().parent.parent / "prompts" / "system.md",
)

# Converse toolSpec for the closed manifest (AC4). Names must match TOOL_MANIFEST
# exactly — tests/test_manifest.py asserts both sides.
TOOL_SPECS = [
    {"toolSpec": {
        "name": "search_incidents",
        "description": "Vector-search past incidents for this service; returns matches, "
                       "a confidence label, and the service's runbook_ids.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "query": {"type": "string"},
            "service": {"type": "string"},
            "k": {"type": "integer", "default": 5},
        }, "required": ["query", "service"]}}}},
    {"toolSpec": {
        "name": "get_runbook",
        "description": "Fetch one runbook by ID (IDs come from search results only).",
        "inputSchema": {"json": {"type": "object", "properties": {
            "runbook_id": {"type": "string"},
        }, "required": ["runbook_id"]}}}},
    {"toolSpec": {
        "name": "propose_diagnosis",
        "description": "Record the proposed diagnosis for the active incident, citing "
                       "real incident IDs from the search results.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "incident_id": {"type": "string"},
            "diagnosis": {"type": "string"},
            "cited_incident_ids": {"type": "array", "items": {"type": "string"}},
        }, "required": ["incident_id", "diagnosis", "cited_incident_ids"]}}}},
    {"toolSpec": {
        "name": "write_incident",
        "description": "Close path only: persist the human-confirmed resolution. "
                       "Never called during diagnosis.",
        "inputSchema": {"json": {"type": "object", "properties": {
            "incident_id": {"type": "string"},
            "resolution_summary": {"type": "string"},
        }, "required": ["incident_id", "resolution_summary"]}}}},
]

# The manifest is propose-only *structurally*, not by instruction (README "The
# guarantee"). `write_incident` is a real, irreversible write — it sets
# status='resolved' and overwrites the embedding future retrievals match against —
# so a model that called it mid-diagnosis could fabricate a resolution and poison
# memory. A sentence in prompts/system.md is not an enforcement mechanism, so the
# diagnosis loop never sees the tool at all, and _dispatch refuses it a second time
# in case a spec ever drifts back in. The close path is scripts/close.py, human-run.
CLOSE_PATH_TOOLS = frozenset({"write_incident"})
DIAGNOSIS_TOOL_SPECS = [s for s in TOOL_SPECS
                        if s["toolSpec"]["name"] not in CLOSE_PATH_TOOLS]

_client = None


def get_client():
    """Lazy so importing this module needs no AWS credentials (tests inject a fake)."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))
    return _client


def load_system_prompt() -> str:
    """The runtime prompt is everything below the `---` separator in system.md;
    above it is versioning prose for humans."""
    path = next((p for p in _PROMPT_CANDIDATES if p.exists()), None)
    if path is None:
        raise FileNotFoundError("prompts/system.md missing — the prompt ships with the code")
    text = path.read_text(encoding="utf-8")
    _, sep, body = text.partition("\n---\n")
    return body.strip() if sep else text.strip()


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class _RunLog:
    """Step sequencer for one agent run. Owns the run_id and the seq counter so the
    loop body stays readable and the ordering can't drift. Writes go through
    tools.log_step — this class holds no SQL and no connection."""

    def __init__(self, incident_id: str):
        self.run_id = str(uuid.uuid4())
        self.incident_id = incident_id
        self.seq = 0

    def step(self, step_type: str, name: str, outcome: str, latency_ms: int, **extra):
        tools.log_step(
            run_id=self.run_id, incident_id=self.incident_id, seq=self.seq,
            step_type=step_type, name=name, outcome=outcome, latency_ms=latency_ms,
            **extra,
        )
        self.seq += 1


def _dispatch(name: str, args: dict, incident_id: str, log: "_RunLog"):
    """One tool call: manifest lookup → run → (json result | error text back to the
    model). Tool validation errors (an invented ID, an illegal uncited diagnosis)
    return as errors so the model can correct itself — the DB write never happened
    (AC3). Anything else is a real bug and raises loudly.

    Both outcomes are logged: a rejected citation is the most interesting row in the
    decision log, because it is the enforcement working."""
    started = time.perf_counter()
    try:
        if name in CLOSE_PATH_TOOLS:
            raise ValueError(f"{name} is not available during diagnosis — it is the "
                             "close path, run by a human after resolution")
        # Inside the try on purpose: an unknown tool name is a KeyError, which the
        # model can correct itself from. Outside, it escaped as a 502.
        fn = tools.TOOL_MANIFEST[name]
        result = fn(**args)
    except (LookupError, ValueError, TypeError) as exc:
        log.step("tool_call", name, "error", _ms(started), detail=str(exc))
        return {"status": "error", "content": [{"text": str(exc)}]}
    confidence = getattr(result, "confidence", None)
    log.step("tool_call", name, "success", _ms(started), confidence=confidence)
    if name == "search_incidents":
        # The loop, not the model, persists what was retrieved — AC11 reads this.
        tools.record_retrieval(incident_id, result)
    payload = result.model_dump_json() if hasattr(result, "model_dump_json") else "ok"
    return {"status": "success", "content": [{"json": json.loads(payload) if payload != "ok" else {"ok": True}}]}


def _converse(system, messages, log: "_RunLog"):
    """One Bedrock turn, timed and logged. Token counts come from the Converse
    response's usage block — cost is an NFR, so it is recorded, not estimated."""
    started = time.perf_counter()
    resp = with_throttle_retry(lambda: get_client().converse(
        modelId=MODEL_ID, system=system, messages=messages,
        toolConfig={"tools": DIAGNOSIS_TOOL_SPECS},
    ))
    usage = resp.get("usage") or {}
    log.step("model_turn", MODEL_ID, "success", _ms(started),
             input_tokens=usage.get("inputTokens"),
             output_tokens=usage.get("outputTokens"))
    return resp


def run_agent(incident_id: str, service: str, title: str, description: str) -> str:
    """Drive Claude on Bedrock over the 4-tool manifest until it proposes a
    diagnosis (AC3) or states confidence 'none' plainly and stops (AC13).
    Returns the model's final text. Bedrock throttling gets the with_retry shape;
    after max attempts the run fails visibly — never a silent degrade (docs/02).
    """
    if not MODEL_ID:
        raise RuntimeError("BEDROCK_MODEL_ID is unset — record the verified ID per docs/04")
    system = [{"text": load_system_prompt()}]
    messages = [{"role": "user", "content": [{"text": json.dumps({
        "incident_id": incident_id, "service": service,
        "title": title, "description": description,
    })}]}]
    proposed = False
    log = _RunLog(incident_id)

    # One turn is reserved for the closing summary that follows a successful
    # propose_diagnosis, so MAX_TURNS is the real ceiling on Converse calls rather
    # than one below it. Previously a run that proposed on the last iteration made
    # MAX_TURNS + 1 calls, putting both the documented cost and latency ceilings a
    # full turn under the truth.
    for _ in range(MAX_TURNS - 1):
        message = _converse(system, messages, log)["output"]["message"]
        messages.append(message)
        tool_uses = [c["toolUse"] for c in message["content"] if "toolUse" in c]

        if not tool_uses:
            # Hard stop states: diagnosis already recorded, or the honesty branch /
            # final statement. Either way the model's text is the answer.
            return "".join(c.get("text", "") for c in message["content"]).strip()

        results = []
        for use in tool_uses:
            outcome = _dispatch(use["name"], use["input"], incident_id, log)
            if use["name"] == "propose_diagnosis" and outcome["status"] == "success":
                proposed = True
            results.append({"toolResult": {"toolUseId": use["toolUseId"], **outcome}})
        messages.append({"role": "user", "content": results})

        if proposed:
            # Diagnosis persisted — one closing turn for the model to summarize.
            final = _converse(system, messages, log)["output"]["message"]
            return "".join(c.get("text", "") for c in final["content"]).strip()

    raise RuntimeError(
        f"agent exceeded {MAX_TURNS} turns without proposing or stopping — refusing "
        "to spin silently (docs/05: failures are loud)"
    )
