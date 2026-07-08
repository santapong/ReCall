# infra/seed — index
Deterministic Orbital corpus generator (P1). Fixed RNG seed lives in `generate.py` — AC2's reproducibility depends on it never changing after P1.

| item | what it is | read when |
|---|---|---|
| `generate.py` | ~80 postmortems, 6 services, 20 designed eval pairs | At P1; rerun via `make seed` |

## Invariants
- Generator and `lambda/scrub.py` share one name list — the scrub test depends on it.
- Expected eval IDs are pinned in a `tests/` fixture the same day the corpus lands.
