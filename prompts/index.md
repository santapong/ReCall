# prompts — index
Agent prompts, versioned like code and loaded at runtime (docs/05) — prompt changes must be diffable.

| item | what it is | read when |
|---|---|---|
| `system.md` | Agent system prompt (v0 draft; finalized P2) | Before changing agent behavior |

## Invariants
- Confidence-first + never-invent-IDs (AC3/AC13) survive every revision.
- `agent.py` reads this file at runtime; no prompt strings in Python.
