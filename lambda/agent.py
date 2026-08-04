"""Bedrock Converse loop — custom, small by design (docs/04).

ZERO SQL in this file, no psycopg import, ever (docs/05 module boundary — a test
greps for it). This module sees the functions in tools.TOOL_MANIFEST (plus the
loop-side record_retrieval helper) and nothing else. The system prompt is loaded
from prompts/system.md at runtime, never inlined — prompt changes must be diffable.
"""

import json
import os
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


def _dispatch(name: str, args: dict, incident_id: str):
    """One tool call: manifest lookup → run → (json result | error text back to the
    model). Tool validation errors (an invented ID, an illegal uncited diagnosis)
    return as errors so the model can correct itself — the DB write never happened
    (AC3). Anything else is a real bug and raises loudly."""
    fn = tools.TOOL_MANIFEST[name]
    try:
        result = fn(**args)
    except (LookupError, ValueError) as exc:
        return {"status": "error", "content": [{"text": str(exc)}]}
    if name == "search_incidents":
        # The loop, not the model, persists what was retrieved — AC11 reads this.
        tools.record_retrieval(incident_id, result)
    payload = result.model_dump_json() if hasattr(result, "model_dump_json") else "ok"
    return {"status": "success", "content": [{"json": json.loads(payload) if payload != "ok" else {"ok": True}}]}


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

    for _ in range(MAX_TURNS):
        resp = with_throttle_retry(lambda: get_client().converse(
            modelId=MODEL_ID, system=system, messages=messages,
            toolConfig={"tools": TOOL_SPECS},
        ))
        message = resp["output"]["message"]
        messages.append(message)
        tool_uses = [c["toolUse"] for c in message["content"] if "toolUse" in c]

        if not tool_uses:
            # Hard stop states: diagnosis already recorded, or the honesty branch /
            # final statement. Either way the model's text is the answer.
            return "".join(c.get("text", "") for c in message["content"]).strip()

        results = []
        for use in tool_uses:
            outcome = _dispatch(use["name"], use["input"], incident_id)
            if use["name"] == "propose_diagnosis" and outcome["status"] == "success":
                proposed = True
            results.append({"toolResult": {"toolUseId": use["toolUseId"], **outcome}})
        messages.append({"role": "user", "content": results})

        if proposed:
            # Diagnosis persisted — one closing turn for the model to summarize.
            final = with_throttle_retry(lambda: get_client().converse(
                modelId=MODEL_ID, system=system, messages=messages,
                toolConfig={"tools": TOOL_SPECS},
            ))["output"]["message"]
            return "".join(c.get("text", "") for c in final["content"]).strip()

    raise RuntimeError(
        f"agent exceeded {MAX_TURNS} turns without proposing or stopping — refusing "
        "to spin silently (docs/05: failures are loud)"
    )
