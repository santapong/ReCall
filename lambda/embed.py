"""The ONLY module that turns text into vectors. Nothing else calls Bedrock for embeddings.

Why its own module and not part of tools.py: the P1 seed loader (infra/seed/) has to
embed 92 documents without importing the DB-write surface, and agent.py's Converse
client at P2 is a different Bedrock concern. One embedding surface, three callers.

Decision D1 (docs/08), pending only the probe's printed confirmation:
- model `amazon.titan-embed-text-v2:0`, 1024 dimensions
- `normalize: true` on every single call — unit vectors make L2 (`<->`) and cosine
  rank identically, which is what makes the `<->` queries in tools.py metric-safe.
  Embedding one corpus normalized and one query unnormalized would silently skew
  every distance, so normalization is not a per-call option here. It is the contract.

Failures are loud (docs/05): a failed embedding fails the ingest. There is no keyword
fallback — a silent quality downgrade would poison AC2 without anyone noticing.
"""

import json
import os
import random
import time

import boto3
from botocore.exceptions import ClientError

EMBED_MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

# The one place the dimension lives. The probe prints the real number; if it is not
# 1024, this constant and the VECTOR(n) markers in infra/ move together in one commit.
EMBED_DIM = int(os.environ.get("EMBED_DIM") or "1024")

THROTTLE_CODES = ("ThrottlingException", "TooManyRequestsException")

_client = None


def get_client():
    """Lazy so importing this module needs no AWS credentials (tests import it)."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION"))
    return _client


def with_throttle_retry(fn, *, max_attempts=5, base_delay=1.0):
    """docs/05 retry shape, Bedrock's half: same silent-retry / loud-failure contract
    as db.with_retry, matching on the throttling error codes instead of SQLSTATE.

    Deliberately slower than db.with_retry's 3 x 0.2s. That shape totals ~0.6s of
    backoff, which is the right order for a CockroachDB serialization conflict and
    the wrong one for Bedrock: real account-level throttling clears in seconds, and
    this wraps every Converse turn plus all 92 seed embeddings. 5 x 1.0s gives ~15s
    of total patience before failing loudly.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code not in THROTTLE_CODES or attempt == max_attempts:
                raise
            time.sleep(base_delay * 2 ** (attempt - 1) + random.uniform(0, 0.1))
    raise AssertionError("unreachable: loop either returns or raises")


def embed(text: str) -> list[float]:
    """Text → unit-norm embedding. Raises on anything unexpected; never returns partial."""
    if not text or not text.strip():
        raise ValueError("refusing to embed empty text — the caller has a bug")

    body = json.dumps({"inputText": text, "dimensions": EMBED_DIM, "normalize": True})

    def _call():
        resp = get_client().invoke_model(modelId=EMBED_MODEL_ID, body=body)
        return json.loads(resp["body"].read())

    payload = with_throttle_retry(_call)
    vector = payload.get("embedding")
    if not isinstance(vector, list):
        raise RuntimeError(f"Bedrock returned no embedding for model {EMBED_MODEL_ID}")
    if len(vector) != EMBED_DIM:
        raise RuntimeError(
            f"embedding dimension {len(vector)} != EMBED_DIM {EMBED_DIM} — the schema's "
            "VECTOR(n) and this constant have drifted apart; fix both in one commit"
        )
    return vector


def to_vector_literal(vector: list[float]) -> str:
    """Render a vector for the wire as a bound parameter (cast `%s::VECTOR` at the
    call site). Still parameterized — the value never reaches SQL by f-string."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
