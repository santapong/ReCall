# Recall — On-call Incident Copilot

> An on-call agent that remembers every incident your team ever had — and whose memory survives the very outages it's diagnosing.

CockroachDB × AWS hackathon entry. Status: **P0 — probe** (phases + acceptance criteria in [`docs/01-objective-roadmap.md`](docs/01-objective-roadmap.md)).

*This is the dev-stage README. The judge-facing README — memory-layer diagram (AC6), 15-minute stranger setup (AC9), the "why CockroachDB" table — is built in P4 per the roadmap.*

## Quickstart

```
uv sync          # deps (Python 3.12, managed by uv)
uv run pytest    # fast suite — structural tests, all green
make help        # everything else (probe, migrate, seed, deploy…)
```

## Map

- [`CLAUDE.md`](CLAUDE.md) — agent-facing index + the eight hard rules; start here
- [`docs/`](docs/index.md) — the design pack (objective, backend, frontend, stack, patterns, harness)
- [`docs/07-branching-worktrees.md`](docs/07-branching-worktrees.md) — branch roles (`main`/`test`/`dev`/`feature/*`…), merge flow, and the worktree workflow (`scripts/wt.sh`)
- Every folder has an `index.md` — navigate by index

## License

[MIT](LICENSE)
