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

import hashlib
import json
import math
import os
import random
import re
import sys
import time

import boto3
from botocore.exceptions import ClientError

EMBED_MODEL_ID = os.environ.get("BEDROCK_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")

# The one place the dimension lives. The probe prints the real number; if it is not
# 1024, this constant and the VECTOR(n) markers in infra/ move together in one commit.
EMBED_DIM = int(os.environ.get("EMBED_DIM") or "1024")

THROTTLE_CODES = ("ThrottlingException", "TooManyRequestsException")

# "local" selects the credential-free stand-in in local_embed(). Anything else —
# including unset, empty, or a typo — selects real Bedrock. Never inferred from a
# missing credential: a silent quality downgrade would poison AC2 without anyone
# noticing, which is the failure this module's docstring exists to prevent.
EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "").strip().lower()

_client = None
_warned_local = False


def _warn_local_backend() -> None:
    """Say it once per process, on stderr, unmissably. A run whose numbers came from
    the stand-in must never be mistaken for a run against Titan."""
    global _warned_local
    if not _warned_local:
        _warned_local = True
        print(
            "WARNING: EMBED_BACKEND=local — vectors come from the lexical stand-in, "
            "not Bedrock. Retrieval scores and tuned thresholds from this run are "
            "provisional and do not transfer to Titan (lambda/embed.py).",
            file=sys.stderr, flush=True,
        )


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


def local_embed(text: str) -> list[float]:
    """A deterministic, dependency-free stand-in for Titan. NOT a fallback.

    Reached only when EMBED_BACKEND=local is set explicitly (see `embed` below). It
    exists so the whole system — migrate, seed load, threshold tuning, the agent loop,
    the status page — is runnable while Bedrock model access is pending, instead of
    the entire project sitting behind one approval queue.

    Mechanism: the hashing trick. Lowercased word tokens are hashed into EMBED_DIM
    buckets, counted, and L2-normalized, so the output is a unit vector of the real
    dimension and `<->` stays metric-safe. Same text always gives the same vector, so
    corpus and query embed consistently.

    What it is NOT: semantic. Two documents that describe the same failure in
    different words are near-orthogonal here, where Titan would place them close
    together. Concretely:

      * Retrieval quality measured on this backend is a LEXICAL overlap score, not a
        reading of the memory system. It is especially misleading for AC2, whose eval
        set was deliberately rewritten (tests/test_eval_independence.py) so that
        shared surface tokens could not carry the benchmark.
      * Confidence thresholds tuned here do not transfer. The distance distribution is
        a different shape; both bands must be re-tuned against Titan before AC13's
        honesty branch means anything.
      * Nothing filmed for the video may run on it.

    blake2b, not hash(): PYTHONHASHSEED randomizes str hashing per process, which
    would make a corpus embedded in one run unmatchable by a query in the next.
    """
    counts: dict[int, float] = {}
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest, "big") % EMBED_DIM
        counts[bucket] = counts.get(bucket, 0.0) + 1.0

    vector = [0.0] * EMBED_DIM
    norm = math.sqrt(sum(v * v for v in counts.values()))
    if norm == 0:  # tokenizer found nothing usable (punctuation only)
        raise ValueError(f"refusing to embed text with no tokens: {text[:40]!r}")
    for bucket, value in counts.items():
        vector[bucket] = value / norm
    return vector


def embed(text: str) -> list[float]:
    """Text → unit-norm embedding. Raises on anything unexpected; never returns partial."""
    if not text or not text.strip():
        raise ValueError("refusing to embed empty text — the caller has a bug")

    # Opt-in by exact value, never by absence. A missing credential must fail loudly
    # rather than silently downgrade quality — see this module's docstring. The
    # warning is deliberately repeated per process start, not once per import.
    if EMBED_BACKEND == "local":
        _warn_local_backend()
        return local_embed(text)

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
