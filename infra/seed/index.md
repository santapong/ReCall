# infra/seed — index
Deterministic Orbital corpus (live since Jul 8). Fixed RNG seed + fixed time anchor in `generate.py` — AC2's reproducibility depends on neither ever changing after P1 closes.

| item | what it is | read when |
|---|---|---|
| `generate.py` | 80 postmortems (6 services), 12 runbooks, 20 designed eval pairs | Changing corpus shape — regen in same commit |
| `corpus.json` | Committed generator output (incidents + runbooks) | Loaded into the DB post-probe |
| `pir_corpus.json` | 10 real public postmortems (Cloudflare, GitHub, GitLab, AWS ×2, Fastly, Slack, Roblox, Atlassian), hand-extracted from cited primary sources — service `public`, one demo shot, AC2 untouched | Real-World Impact shot (review 2026-08-04) |
| `load.py` | Embed + upsert both corpora through the one embedding surface | The day Bedrock creds land |

## Invariants
- Generator imports `NAME_LIST` from `lambda/scrub.py` — one shared roster, zero-survivors test airtight.
- `corpus.json` + `tests/fixtures/eval_pairs.json` must equal fresh generator output (tested) — edit the generator ⇒ `make seed` in the same commit.
- Blameless by construction: `_assert_blameless` runs at every generation; no names/emails/handles in any seeded text.
- `pir_corpus.json` is hand-authored from cited sources, not generated — `tests/test_pir_corpus.py` guards its shape, blamelessness and isolation from the eval set.
- Embeddings are NOT in the corpus — they're computed at load time (post-probe, real model).
