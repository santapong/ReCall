"""End-to-end smoke test of the whole ingest path, credential-free.

POSTs an alert through the real handler against a real cluster, using the explicit
local backends (EMBED_BACKEND=local, BEDROCK_BACKEND=local). Everything between the
HTTP event and the database is production code: pydantic validation, insert_incident,
the Converse loop, tool dispatch, citation validation, the agent_runs decision log,
and the /status and /runlog read paths.

What it proves: the wiring works and the invariants hold. What it does NOT prove:
anything about model or retrieval quality — see lambda/embed.py.

    export CRDB_CONN_STRING=postgresql://root@localhost:26257/defaultdb?sslmode=disable
    EMBED_BACKEND=local BEDROCK_BACKEND=local \
        uv run python scripts/local_e2e.py
"""

import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))

import ingest_handler  # noqa: E402
import tools  # noqa: E402


def main() -> int:
    for name in ("EMBED_BACKEND", "BEDROCK_BACKEND"):
        if os.environ.get(name, "").strip().lower() != "local":
            print(f"set {name}=local — this script is the credential-free path")
            return 2
    if not os.environ.get("CRDB_CONN_STRING"):
        print("set CRDB_CONN_STRING (docs/08 P0 step 2)")
        return 2

    alert = {
        "external_id": f"LOCAL-{uuid.uuid4().hex[:8]}",
        "service": "billing",
        "title": "payment webhooks timing out",
        "description": "p99 webhook latency above 30s, retries climbing",
        "severity": "sev2",
    }
    print(f"POST {alert['external_id']} ({alert['service']})")
    response = ingest_handler.handler({"body": json.dumps(alert)}, None)
    print(f"  status  {response['statusCode']}")
    if response["statusCode"] != 200:
        print(f"  body    {response['body']}")
        return 1

    body = json.loads(response["body"])
    incident_id = body["incident_id"]
    print(f"  answer  {body['response'][:100]}")

    snapshot = tools.status_snapshot(incident_id)
    print(f"\nGET /status  confidence={snapshot['confidence']!r}")
    print(f"  diagnosis  {(snapshot['proposed_diagnosis'] or '(none)')[:80]}")
    cited = (snapshot.get("retrieved_matches") or {}).get("matches") or []
    print(f"  retrieved  {len(cited)} matches")

    steps = tools.run_log(incident_id)
    print(f"\nGET /runlog  {len(steps)} steps")
    for step in steps:
        print(f"  {step['seq']:>2}  {step['step_type']:<11}{step['name']:<22}"
              f"{step['outcome']:<8}{step['latency_ms']:>5}ms")

    ok = bool(steps) and snapshot["confidence"] is not None
    print("\nOK — the loop ran, the decision log filled, the read paths answered."
          if ok else "\nFAILED — see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
