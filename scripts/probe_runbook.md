# P0 probe runbook — human steps, in order

*Written Jul 8 from pre-probe research (sources at bottom). This container has no cloud
credentials and its egress policy blocks the cockroach binary, so the live probe runs on
your machine. Every `DECISION PENDING PROBE` marker is resolved only by what the real
cluster says — expectations below are research, not results.*

## What research already says (verify, don't trust)

| Probe question | Expected answer (Jul 2026 research) | Confidence |
|---|---|---|
| Vector index available? | Yes since v25.2 (C-SPANN, public preview) — gated by `SET CLUSTER SETTING feature.vector_index.enabled = true`; non-empty tables also need `SET sql_safe_updates = false` to backfill | high |
| Works on the **free (Basic) tier**? | **At risk** — serverless pods have documented limitations with vector-index in-memory structures; `CREATE VECTOR INDEX` may be restricted. Test this FIRST. | low |
| Headless MCP auth? | Yes per docs — managed MCP server supports **service-account API keys** ("fully autonomous environments") plus OAuth 2.1 PKCE for interactive; console generates the config snippet | medium |
| Embedding dimension | Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`): 256/512/1024, **default 1024** — schema's `VECTOR(1024)` is the expected fit, confirmed at P1 by `scripts/probe_bedrock.py` | high |
| Killable nodes on free tier? | No (multi-tenant serverless) — chaos rig stays self-hosted 3-node as docs/04 planned | high |

## A · Cluster + vector probe (~15 min)

1. cockroachlabs.cloud → create a **Basic** cluster (free tier; hackathon-eligible).
2. Grab the connection string (Connect → General connection string).
3. In this repo:
   ```bash
   cp .env.example .env         # paste CRDB_CONN_STRING
   export CRDB_CONN_STRING='postgresql://...'
   make probe
   ```
4. Decision tree:
   - `CREATE VECTOR INDEX` **succeeds** → record "no flag needed" in docs/02.
   - Fails with a feature/flag error → `psql "$CRDB_CONN_STRING" -c "SET CLUSTER SETTING feature.vector_index.enabled = true;"` then `make probe` again → record "flag required, settable on Basic".
   - Flag **rejected on Basic** (serverless blocks the setting) or index unsupported →
     record it, then pick the fallback: (a) self-hosted 3-node rig as the primary DB —
     it already exists in the plan for AC7's kill demo and *strengthens* it, or
     (b) Standard-tier trial credits if compliance review confirms eligibility.
     Either way the vector-index differentiator survives; only the hosting moves.
5. Also record: cluster's CockroachDB version (`SELECT version();`) → README + docs/04.

## B · Managed MCP, headless (~10 min)

1. Cloud Console → the cluster's **MCP** page → copy the generated config snippet.
2. Interactive check: `claude mcp add --transport http <name> <url>` → `/mcp` → OAuth →
   ask Claude Code to list tables. Record: works / not.
3. Headless check (the Branch A/B decider): create a **service-account API key** in the
   console, then hit the MCP endpoint from a script/curl with that key. Record: works / not.
   - Note: even if headless works, docs/02's Branch B (psycopg runtime + MCP as the
     dev/ops surface on camera) stays the recommended demo shape — cleaner kill story.

## C · Bedrock access request (~5 min, do today — approval can lag)

1. AWS console → **Bedrock → Model access** (region `us-east-1`): request
   **Anthropic Claude** (the current default text model) and
   **Amazon Titan Text Embeddings V2**.
2. When granted (P1): `AWS_REGION=us-east-1 uv run python scripts/probe_bedrock.py amazon.titan-embed-text-v2:0`
   → prints the real dimension → resolve the `VECTOR(1024)` markers.

## D · Report back (what unblocks the markers)

Tell the agent (or edit in-file yourself) these four answers:

1. Vector index on Basic: works / flag-then-works / unsupported (+ fallback chosen)
2. Cluster version string
3. MCP: interactive OK? headless service-account OK? → resolves docs/02 "Runtime DB path"
4. Bedrock: access granted? embed dimension → resolves `VECTOR(1024)` markers (P1)

P0 exits (docs/01) when A + B are answered and C is *requested*.

## Sources (Jul 8, 2026)

- Vector indexes + flag: cockroachlabs.com/docs/v25.2/vector-indexes.html · cockroachlabs.com/blog/cockroachdb-252-performance-vector-indexing
- Serverless vector-index limits: cockroachlabs.com/blog/distributed-vector-indexing-cockroachdb · blog.bytebytego.com/p/how-cockroachdb-built-vector-indexing
- Managed MCP (OAuth + service-account keys): cockroachlabs.com/blog/cockroachdb-ai-agents-managed-mcp-server
- Titan V2 dims/model id: docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html
