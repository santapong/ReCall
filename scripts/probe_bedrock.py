"""P0/P1 probe: confirm Bedrock embedding access and print the output dimension.

The dimension resolves the `VECTOR(1024)` DECISION PENDING PROBE marker in
docs/02 and infra/schema.sql — update both the day this runs.

Run:  uv run python scripts/probe_bedrock.py [model_id]
Env:  AWS_REGION (and AWS credentials), optional BEDROCK_EMBED_MODEL_ID.
"""

import json
import os
import sys

import boto3


def main() -> int:
    model_id = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get(
        "BEDROCK_EMBED_MODEL_ID"
    )
    if not model_id:
        print(
            "no model id: pass one as argv[1] or set BEDROCK_EMBED_MODEL_ID.\n"
            "Check the exact Titan Text Embeddings id in the Bedrock console "
            "(docs/04 version policy: record verified ids only).",
            file=sys.stderr,
        )
        return 2

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))
    resp = client.invoke_model(
        modelId=model_id,
        body=json.dumps({"inputText": "payment webhooks timing out"}),
    )
    embedding = json.loads(resp["body"].read())["embedding"]
    print(f"model {model_id} -> dimension {len(embedding)}")
    print(
        "now: set VECTOR(n) in infra/schema.sql + infra/migrations/0001_init.sql, "
        "resolve the marker in docs/02, and record the model id in the README."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
