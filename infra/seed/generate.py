"""Deterministic Orbital corpus generator — lands in P1 (docs/02 seed spec).

Contract, fixed by the design pack:
- Fictional SaaS "Orbital", six services: api-gateway, auth, billing, search,
  notifications, db-cluster.
- ~80 synthetic postmortems, fixed RNG seed committed here, so AC2 is reproducible.
- 20 designed pairs (historical incident + matching test alert) form the AC2 eval
  set; expected IDs pinned in a tests/ fixture.
- Every resolution passes the blameless scrub: this generator and lambda/scrub.py
  share one name list, so the scrub test is airtight (docs/05).

Run: uv run python infra/seed/generate.py   (or `make seed`)
"""

RNG_SEED = 20260818  # fixed forever once P1 lands — AC2 depends on it

SERVICES = ("api-gateway", "auth", "billing", "search", "notifications", "db-cluster")


def main() -> int:
    raise NotImplementedError("P1 — see docs/02 'Seed data spec' and docs/01 phase table")


if __name__ == "__main__":
    raise SystemExit(main())
