# infra/seed — index
Deterministic Orbital corpus (live since Jul 8). Fixed RNG seed + fixed time anchor in `generate.py` — AC2's reproducibility depends on neither ever changing after P1 closes.

| item | what it is | read when |
|---|---|---|
| `generate.py` | 80 postmortems (6 services), 12 runbooks, 20 designed eval pairs | Changing corpus shape — regen in same commit |
| `corpus.json` | Committed generator output (incidents + runbooks) | Loaded into the DB post-probe |

## Invariants
- Generator imports `NAME_LIST` from `lambda/scrub.py` — one shared roster, zero-survivors test airtight.
- `corpus.json` + `tests/fixtures/eval_pairs.json` must equal fresh generator output (tested) — edit the generator ⇒ `make seed` in the same commit.
- Blameless by construction: `_assert_blameless` runs at every generation; no names/emails/handles in any seeded text.
- Embeddings are NOT in the corpus — they're computed at load time (post-probe, real model).
