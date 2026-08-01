"""Deterministic Orbital corpus generator (docs/02 seed spec) — AC2's substrate.

- 80 synthetic postmortems across the 6 Orbital services, plus 12 runbooks.
- 20 designed pairs: a historical incident + a fresh alert that paraphrases its
  symptoms (variant-B phrasing, same parameters) — the AC2 eval set, expected
  external_ids pinned in tests/fixtures/eval_pairs.json.
- Fully deterministic: fixed RNG seed, fixed time anchor (never datetime.now()).
  Regenerating must reproduce the committed files byte-for-byte (tested).
- Blameless by construction: templates contain no people; scrub.NAME_LIST is
  imported as the shared roster and a test asserts zero survivors either way.

Run: make seed   (writes infra/seed/corpus.json + tests/fixtures/eval_pairs.json)
"""

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "lambda"))
from scrub import NAME_LIST, scrub  # noqa: E402  (path set up just above)

RNG_SEED = 20260818  # fixed forever once P1 lands — AC2 depends on it
ANCHOR = datetime(2026, 7, 1, tzinfo=timezone.utc)  # deterministic "now"

SERVICES = ("api-gateway", "auth", "billing", "search", "notifications", "db-cluster")

REGIONS = ("us-east-1", "eu-west-1", "ap-southeast-1")
DEPS = ("payments-api", "ledger", "profile-svc", "catalog", "smtp-relay", "kms")

# Five archetypes per service. symptom_a seeds the historical incident;
# symptom_b is the paraphrase used for the paired eval alert (same parameters,
# different wording — retrieval must work on meaning, not string overlap).
ARCHETYPES = {
    "api-gateway": [
        {
            "key": "upstream-timeout",
            "title": "Gateway 5xx spike — upstream timeouts to {dep}",
            "symptom_a": "p99 latency above {ms} ms and 5xx rate at {pct}% in {region}; "
            "upstream connections to {dep} time out and retries amplify load.",
            "symptom_b": "edge error rate around {pct}% in {region}; calls to {dep} hang "
            "past {ms} ms then fail, retry traffic is stacking up.",
            "cause": "Connection pool to {dep} exhausted after a deploy halved pool size.",
            "steps": "roll back the pool-size change; raise max connections to {n}0; "
            "drain and restart gateway pods in {region}; watch p99 for 15 minutes.",
        },
        {
            "key": "rate-limiter",
            "title": "Legitimate traffic throttled — rate limiter misconfigured",
            "symptom_a": "429s at {pct}% for authenticated users in {region} after config "
            "push; abuse dashboard shows no attack traffic.",
            "symptom_b": "large customers report requests rejected with 429 in {region}; "
            "roughly {pct}% of valid calls throttled since the last config change.",
            "cause": "Per-IP limit applied to shared NAT ranges by a config typo.",
            "steps": "revert limiter config; exempt known NAT ranges; add config lint "
            "rule; backfill request credits for affected accounts.",
        },
        {
            "key": "cert-expiry",
            "title": "TLS handshake failures at the edge — certificate expired",
            "symptom_a": "handshake failures climbing to {pct}% in {region}; clients "
            "report certificate-expired errors on api.orbital.dev.",
            "symptom_b": "customers in {region} see TLS errors; monitoring shows expired "
            "leaf certificate on the edge, failure rate near {pct}%.",
            "cause": "Automated renewal job lost its DNS challenge permission.",
            "steps": "issue certificate manually; restore renewal job credentials; add "
            "expiry alert at 21 days; verify full chain on all edge nodes.",
        },
        {
            "key": "route-drift",
            "title": "Elevated 404s after canary — route table drift",
            "symptom_a": "404 rate up {pct}% on /v2 endpoints in {region} after canary "
            "promotion; old routes missing from the generated table.",
            "symptom_b": "spike of not-found responses on v2 paths in {region}; canary "
            "rollout appears to have dropped legacy route entries, {pct}% of calls affected.",
            "cause": "Route generator ran against a stale service registry snapshot.",
            "steps": "re-run route generation from live registry; promote corrected "
            "table; add route-count diff check to canary gate.",
        },
        {
            "key": "ws-leak",
            "title": "Memory climb on gateway nodes — websocket connections never closed",
            "symptom_a": "gateway RSS grows {pct}% per hour; websocket count monotonic; "
            "nodes in {region} OOM-restart roughly every {n} hours.",
            "symptom_b": "gateway pods in {region} restarting on OOM about every {n} "
            "hours; open websocket connections only ever increase, memory up {pct}%/h.",
            "cause": "Idle-timeout handler dropped by a refactor, sockets leak.",
            "steps": "deploy idle-timeout fix; force-close sockets idle beyond 10 min; "
            "add websocket-count alert; verify memory plateau over {n} hours.",
        },
    ],
    "auth": [
        {
            "key": "refresh-loop",
            "title": "Token refresh loop — clients hammering /token",
            "symptom_a": "/token QPS up {pct}%; same clients refresh every {n} seconds; "
            "access tokens rejected immediately after issue in {region}.",
            "symptom_b": "auth traffic storm in {region}: clients stuck refreshing every "
            "{n}s because fresh access tokens are rejected, load up {pct}%.",
            "cause": "Token audience claim changed while validators kept the old value.",
            "steps": "roll back issuer audience change; purge bad tokens; coordinate "
            "validator config with issuer release; add audience contract test.",
        },
        {
            "key": "bcrypt-cost",
            "title": "Login latency breach — password hash cost misconfigured",
            "symptom_a": "login p99 at {ms} ms in {region} after security patch; CPU "
            "saturated on auth pods; no traffic increase.",
            "symptom_b": "sign-in takes seconds for users in {region}; auth CPU pegged "
            "since the patch, p99 around {ms} ms with flat traffic.",
            "cause": "Patch bumped bcrypt cost factor from 10 to 14 in one env only.",
            "steps": "set cost factor back to 10; scale auth pool to {n} pods while "
            "backlog drains; add latency budget test to the patch pipeline.",
        },
        {
            "key": "session-evict",
            "title": "Users logged out en masse — session store eviction",
            "symptom_a": "active sessions dropped {pct}% in minutes; session store memory "
            "ceiling hit and LRU evicted live sessions in {region}.",
            "symptom_b": "support flood: everyone in {region} logged out around the same "
            "time; session count fell {pct}% as the store evicted under memory pressure.",
            "cause": "Session TTL doubled without resizing the store.",
            "steps": "raise store memory to {n} GB; restore TTL; move eviction policy to "
            "expire-only; page on 80% store memory.",
        },
        {
            "key": "oidc-outage",
            "title": "Third-party OIDC provider outage — social logins failing",
            "symptom_a": "social login success below {pct}%; provider status page red; "
            "password logins unaffected in {region}.",
            "symptom_b": "google/github sign-ins failing for {region} users, success "
            "rate {pct}%; provider reports an incident; direct logins fine.",
            "cause": "Upstream identity provider outage; no local fallback messaging.",
            "steps": "enable provider-outage banner; extend session lifetimes {n} hours "
            "during outage; add provider health probe to status page.",
        },
        {
            "key": "clock-skew",
            "title": "JWT rejections — node clock skew beyond tolerance",
            "symptom_a": "token-not-yet-valid errors at {pct}% on two nodes in {region}; "
            "ntp drift near {n} seconds.",
            "symptom_b": "sporadic 401s in {region}: validators reject fresh JWTs as "
            "not-yet-valid, {pct}% of requests; two hosts show {n}s clock drift.",
            "cause": "NTP daemon dead on two hosts after base image update.",
            "steps": "restart and pin ntp service; raise skew tolerance to 30 s; alert "
            "on drift over 5 s; rebuild affected hosts.",
        },
    ],
    "billing": [
        {
            "key": "webhook-timeout",
            "title": "Payment webhooks timing out — provider retries piling up",
            "symptom_a": "webhook processing p99 at {ms} ms; provider retry queue depth "
            "{n}00 and rising; duplicate delivery warnings in {region}.",
            "symptom_b": "payment provider callbacks in {region} exceed {ms} ms and time "
            "out; retries queue up past {n}00, duplicates appearing.",
            "cause": "Webhook handler took a synchronous dependency on the ledger; ledger "
            "connection pool exhausted under load.",
            "steps": "roll back the pool-size change on ledger; make webhook ack async; "
            "drain retry queue; verify duplicate suppression on replay.",
        },
        {
            "key": "invoice-stuck",
            "title": "Nightly invoice job stalled — lock contention",
            "symptom_a": "invoice batch at {pct}% after {n} hours; lock waits dominate; "
            "no invoices issued for {region} accounts since midnight.",
            "symptom_b": "billing run for {region} frozen around {pct}% complete for {n} "
            "hours; database lock contention between batch and API writes.",
            "cause": "Batch job and API wrote the same account rows in opposite order.",
            "steps": "kill and restart batch with account-id ordering; chunk commits to "
            "500 rows; schedule batch off-peak; add job progress alert at 2 h.",
        },
        {
            "key": "decline-spike",
            "title": "Card declines spiking — PSP degradation",
            "symptom_a": "decline rate {pct}% versus 4% baseline in {region}; PSP latency "
            "{ms} ms; declines cluster on one card network.",
            "symptom_b": "checkout failures up in {region}: {pct}% of charges declined, "
            "concentrated on a single network; PSP responding around {ms} ms.",
            "cause": "Payment service provider incident on one card network route.",
            "steps": "fail over to secondary PSP for the affected network; queue and "
            "auto-retry declined charges after recovery; notify affected merchants.",
        },
        {
            "key": "double-charge",
            "title": "Duplicate charges reported — idempotency key regression",
            "symptom_a": "{n} duplicate-charge reports in {region}; charge attempts show "
            "same cart charged twice within {ms} ms; idempotency table misses rising.",
            "symptom_b": "customers in {region} charged twice for one checkout; about {n} "
            "cases, second charge lands within {ms} ms; dedupe lookups missing.",
            "cause": "Idempotency key derivation changed, old retries no longer matched.",
            "steps": "restore previous key derivation; refund duplicates via script; "
            "backfill key mapping for in-flight retries; add dual-read during migrations.",
        },
        {
            "key": "rounding-drift",
            "title": "Ledger imbalance — currency rounding drift",
            "symptom_a": "end-of-day ledger off by {n} cents per 10k transactions in "
            "{region}; drift began after FX precision change.",
            "symptom_b": "reconciliation failing in {region}: small per-batch imbalance, "
            "roughly {n} cents per 10k rows, since the FX precision deploy.",
            "cause": "Mixed bankers-rounding and truncation across two code paths.",
            "steps": "standardize on bankers rounding in the shared money lib; replay "
            "affected batches; add reconciliation invariant test to CI.",
        },
    ],
    "search": [
        {
            "key": "index-lag",
            "title": "Search results stale — indexing pipeline lag",
            "symptom_a": "index lag {n} minutes versus 2-minute SLO; new listings absent "
            "from results in {region}; consumer group rebalancing repeatedly.",
            "symptom_b": "fresh content not searchable for ~{n} minutes in {region}; "
            "ingestion consumers stuck rebalancing, lag far over SLO.",
            "cause": "Indexer poll loop exceeded max-poll-interval on oversized batches.",
            "steps": "cap batch size at {n}00 docs; raise max poll interval; replay "
            "backlog; alert on lag over 5 minutes.",
        },
        {
            "key": "shard-hotspot",
            "title": "Query latency uneven — shard hotspot",
            "symptom_a": "one shard at {pct}% CPU while others idle; p99 {ms} ms for "
            "queries hitting tenant prefix in {region}.",
            "symptom_b": "search slow for a subset of tenants in {region}, p99 near {ms} "
            "ms; a single shard runs hot at {pct}% CPU.",
            "cause": "Routing key concentrated one large tenant on a single shard.",
            "steps": "split hot tenant across {n} shards with composite routing; warm "
            "replicas before cutover; add per-shard CPU skew alert.",
        },
        {
            "key": "planner-regression",
            "title": "Faceted queries slow — planner regression after upgrade",
            "symptom_a": "facet-heavy queries p99 {ms} ms post-upgrade in {region}; plans "
            "switched to full scans on the category field.",
            "symptom_b": "filters with facets crawling in {region} since the upgrade, "
            "around {ms} ms p99; execution plans show scans instead of index use.",
            "cause": "Engine upgrade changed cost model; stats not rebuilt.",
            "steps": "rebuild field statistics; pin planner hints on top {n} facet "
            "queries; add plan-diff check to upgrade runbook.",
        },
        {
            "key": "synonym-relevance",
            "title": "Relevance complaints — synonym pack overreach",
            "symptom_a": "click-through on top-3 results down {pct}% in {region} after "
            "synonym deploy; unrelated products matching brand terms.",
            "symptom_b": "search quality regressed in {region}: top results off-topic "
            "for brand queries, CTR down {pct}% since the new synonym pack.",
            "cause": "Overbroad synonym expansion mapped brand names to generic terms.",
            "steps": "roll back synonym pack; add offline relevance eval gate with {n}00 "
            "golden queries; re-ship curated pack behind experiment flag.",
        },
        {
            "key": "agg-oom",
            "title": "Search nodes OOM — unbounded aggregation queries",
            "symptom_a": "two data nodes OOM in {region}; heap dumps show {n} GB "
            "aggregation buckets from an analytics client.",
            "symptom_b": "repeated out-of-memory crashes on search data nodes in "
            "{region}; giant bucket aggregations (~{n} GB) traced to one API client.",
            "cause": "No circuit breaker on bucket count for scripted aggregations.",
            "steps": "set max-buckets circuit breaker; move analytics client to async "
            "export API; add per-client resource quota; restart affected nodes.",
        },
    ],
    "notifications": [
        {
            "key": "email-backlog",
            "title": "Email delivery delayed — queue backlog",
            "symptom_a": "outbound email queue depth {n}k and climbing; oldest message "
            "{ms} minutes; SMTP relay 4xx deferrals at {pct}% in {region}.",
            "symptom_b": "emails arriving very late for {region} users; backlog around "
            "{n}k messages, relay deferring {pct}% with temporary errors.",
            "cause": "Relay IP reputation dip caused throttling; retries compounded.",
            "steps": "warm up secondary relay IPs; shed marketing traffic; drain backlog "
            "oldest-first; add deferral-rate alert at 5%.",
        },
        {
            "key": "apns-cert",
            "title": "iOS pushes failing — APNs certificate expired",
            "symptom_a": "APNs rejects at {pct}% with certificate errors; android "
            "delivery normal; started at certificate expiry timestamp in {region}.",
            "symptom_b": "push notifications dead on iOS for {region}, rejection rate "
            "{pct}%; android unaffected; provider cites expired credentials.",
            "cause": "APNs auth key rotated in staging but not production.",
            "steps": "deploy renewed APNs key; replay failed pushes from the last {n} "
            "hours; move key rotation to shared automation with expiry alerts.",
        },
        {
            "key": "template-error",
            "title": "Blank notifications sent — template rendering errors",
            "symptom_a": "render error rate {pct}% after template deploy; users in "
            "{region} receive empty bodies; error logs show missing variable.",
            "symptom_b": "customers in {region} getting blank alerts; roughly {pct}% of "
            "renders throw missing-variable since the template release.",
            "cause": "Template referenced a field removed from the event schema.",
            "steps": "roll back template pack; add schema-template contract check to CI; "
            "re-send affected notifications with corrected template.",
        },
        {
            "key": "provider-limit",
            "title": "SMS delivery throttled — provider rate limit hit",
            "symptom_a": "SMS provider 429s at {pct}%; OTP delivery p99 {ms} s in "
            "{region}; volume spike from a marketing campaign.",
            "symptom_b": "one-time codes slow or missing in {region}; provider "
            "throttling {pct}% of sends after campaign traffic, p99 near {ms} s.",
            "cause": "Campaign and transactional SMS shared one rate-limited account.",
            "steps": "split transactional sends to a dedicated account; pause campaign; "
            "prioritize OTP queue; add provider quota headroom alert.",
        },
        {
            "key": "retry-storm",
            "title": "Duplicate notifications — retry storm after timeout tune",
            "symptom_a": "duplicate sends {pct}% after client timeout lowered to {ms} "
            "ms; delivery service completes late, callers retry in {region}.",
            "symptom_b": "users in {region} getting the same alert 2-3 times; timeout "
            "now {ms} ms causes premature retries, duplicate rate {pct}%.",
            "cause": "Client timeout below service p99; no idempotency on send API.",
            "steps": "raise client timeout above p99; add idempotency keys to send API; "
            "dedupe window {n} minutes server-side.",
        },
    ],
    "db-cluster": [
        {
            "key": "serialization-spike",
            "title": "Transaction retries spiking — serialization conflicts",
            "symptom_a": "SQLSTATE 40001 retry rate {pct}% on orders workload in "
            "{region}; p99 commit {ms} ms; contention on a counter row.",
            "symptom_b": "application logs full of serialization failures in {region}, "
            "about {pct}% of transactions; commits stretch to {ms} ms under contention.",
            "cause": "New feature incremented a single global counter row per order.",
            "steps": "shard the counter into {n} buckets; keep client retry with "
            "backoff; add contention dashboard; verify 40001 rate under 1%.",
        },
        {
            "key": "hot-range",
            "title": "Single range saturated — sequential key hotspot",
            "symptom_a": "one range at {pct}% CPU with sequential inserts in {region}; "
            "write p99 {ms} ms; neighbors idle.",
            "symptom_b": "writes slow cluster-wide from one hot range in {region}, p99 "
            "{ms} ms; timestamp-ordered keys hammer a single node at {pct}% CPU.",
            "cause": "Monotonic key prefix concentrated writes on one range.",
            "steps": "switch to hash-sharded index with {n} buckets; pre-split ranges; "
            "confirm load spreads across nodes.",
        },
        {
            "key": "disk-pressure",
            "title": "Node disk pressure — compactions falling behind",
            "symptom_a": "node storage at {pct}%; compaction backlog {n} GB; write "
            "stalls of {ms} ms appearing in {region}.",
            "symptom_b": "intermittent write stalls (~{ms} ms) in {region}; one node "
            "near {pct}% disk with {n} GB of pending compactions.",
            "cause": "TTL job deleted heavily, tombstones outpaced compaction.",
            "steps": "throttle TTL deletes; raise compaction concurrency; add disk "
            "headroom alert at 70%; verify stall count returns to zero.",
        },
        {
            "key": "backup-io",
            "title": "Nightly backup saturating IO — foreground latency breach",
            "symptom_a": "backup window overlaps peak; read p99 {ms} ms in {region}; "
            "disk throughput {pct}% consumed by backup streams.",
            "symptom_b": "nightly latency spikes in {region}: reads at {ms} ms while "
            "backups eat {pct}% of disk bandwidth.",
            "cause": "Backup schedule drifted into regional peak after DST change.",
            "steps": "reschedule backup off-peak; cap backup IO priority; stagger by "
            "{n}-minute offsets per node; alert on p99 during backup window.",
        },
        {
            "key": "conn-storm",
            "title": "Connection storm — leaked pool exhausting server slots",
            "symptom_a": "server connections at max; new clients refused in {region}; "
            "one deployment holds {n}00 idle connections growing {pct}%/hour.",
            "symptom_b": "connection-refused errors for new pods in {region}; a single "
            "service leaks idle connections ({n}00 and climbing, +{pct}%/h).",
            "cause": "HTTP handler created a pool per request under a rare code path.",
            "steps": "hotfix pool reuse; set server-side idle timeout {n} minutes; add "
            "per-service connection quota and leak alert.",
        },
    ],
}

# Two runbooks per service, generalized from the archetype families (AC3 needs
# real runbook steps to cite; the sleep-cycle stretch would add more).
RUNBOOKS = {
    "api-gateway": [
        ("Upstream timeout triage", "upstream-timeout"),
        ("Edge certificate incident response", "cert-expiry"),
    ],
    "auth": [
        ("Token validation failure triage", "refresh-loop"),
        ("Auth latency runaway response", "bcrypt-cost"),
    ],
    "billing": [
        ("Webhook backlog recovery", "webhook-timeout"),
        ("Payment provider degradation playbook", "decline-spike"),
    ],
    "search": [
        ("Indexing lag recovery", "index-lag"),
        ("Hot shard mitigation", "shard-hotspot"),
    ],
    "notifications": [
        ("Delivery backlog drain", "email-backlog"),
        ("Push credential expiry response", "apns-cert"),
    ],
    "db-cluster": [
        ("Serialization contention playbook", "serialization-spike"),
        ("Hot range mitigation", "hot-range"),
    ],
}

INCIDENTS_PER_SERVICE = {s: 13 for s in SERVICES} | {"api-gateway": 14, "db-cluster": 14}
EVAL_TARGETS_PER_SERVICE = {s: 3 for s in SERVICES} | {"billing": 4, "db-cluster": 4}  # = 20
SEVERITIES = ("SEV-1", "SEV-2", "SEV-3")


def _params(rng: random.Random) -> dict:
    return {
        "region": rng.choice(REGIONS),
        "pct": rng.randint(11, 93),
        "ms": rng.choice((250, 400, 800, 1200, 2500, 4800)),
        "n": rng.randint(3, 40),
        "dep": rng.choice(DEPS),
    }


def build_corpus() -> dict:
    """Pure function of RNG_SEED/ANCHOR — returns {incidents, runbooks, eval_pairs}."""
    rng = random.Random(RNG_SEED)
    incidents, eval_pairs = [], []
    inc_num, alert_num = 1000, 2000

    for service in SERVICES:
        archetypes = ARCHETYPES[service]
        for i in range(INCIDENTS_PER_SERVICE[service]):
            arch = archetypes[i % len(archetypes)]
            p = _params(rng)
            age_days = rng.randint(5, 700)
            duration_h = rng.randint(1, 72)
            opened = ANCHOR - timedelta(days=age_days, hours=rng.randint(0, 23))
            external_id = f"INC-{inc_num}"
            inc_num += 1
            is_target = i < EVAL_TARGETS_PER_SERVICE[service]
            incidents.append(
                {
                    "external_id": external_id,
                    "service": service,
                    "title": arch["title"].format(**p),
                    "description": arch["symptom_a"].format(**p),
                    "severity": rng.choice(SEVERITIES),
                    "status": "resolved",
                    "resolution_summary": (
                        f"Root cause: {arch['cause'].format(**p)} "
                        f"Resolved by: {arch['steps'].format(**p)}"
                    ),
                    "opened_at": opened.isoformat(),
                    "resolved_at": (opened + timedelta(hours=duration_h)).isoformat(),
                    "archetype": arch["key"],
                    "is_eval_target": is_target,
                }
            )
            if is_target:
                eval_pairs.append(
                    {
                        "alert": {
                            "external_id": f"ALERT-{alert_num}",
                            "service": service,
                            "title": arch["title"].format(**p),
                            "description": arch["symptom_b"].format(**p),
                            "severity": "SEV-2",
                        },
                        "expected_incident_external_id": external_id,
                        "archetype": arch["key"],
                    }
                )
                alert_num += 1

    runbooks = []
    rb_num = 300
    for service in SERVICES:
        for title, arch_key in RUNBOOKS[service]:
            arch = next(a for a in ARCHETYPES[service] if a["key"] == arch_key)
            p = _params(rng)
            runbooks.append(
                {
                    "external_id": f"RB-{rb_num}",
                    "service": service,
                    "title": f"Runbook: {title}",
                    "content": (
                        f"Applies to: {arch['title'].format(**p)}. "
                        f"Typical cause: {arch['cause'].format(**p)} "
                        f"Steps: {arch['steps'].format(**p)} "
                        "Escalate if symptoms persist 30 minutes after step completion."
                    ),
                }
            )
            rb_num += 1

    return {"incidents": incidents, "runbooks": runbooks, "eval_pairs": eval_pairs}


def _assert_blameless(corpus: dict) -> None:
    for inc in corpus["incidents"]:
        for field in ("title", "description", "resolution_summary"):
            if scrub(inc[field]) != inc[field]:
                raise AssertionError(f"{inc['external_id']}.{field} would be scrubbed")
    unused = [n for n in NAME_LIST if not n]
    if unused:  # NAME_LIST sanity — empty entries would make the scrub regex match everything
        raise AssertionError("empty entry in NAME_LIST")


def main() -> int:
    corpus = build_corpus()
    _assert_blameless(corpus)
    seed_dir = REPO / "infra" / "seed"
    fixtures = REPO / "tests" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    corpus_out = {k: corpus[k] for k in ("incidents", "runbooks")}
    (seed_dir / "corpus.json").write_text(json.dumps(corpus_out, indent=2) + "\n")
    (fixtures / "eval_pairs.json").write_text(json.dumps(corpus["eval_pairs"], indent=2) + "\n")
    print(
        f"wrote {len(corpus['incidents'])} incidents, {len(corpus['runbooks'])} runbooks "
        f"-> infra/seed/corpus.json; {len(corpus['eval_pairs'])} eval pairs "
        "-> tests/fixtures/eval_pairs.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
