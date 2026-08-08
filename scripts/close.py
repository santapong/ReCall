"""Close an incident with a human-written resolution — the other half of AC5.

    uv run python scripts/close.py <incident-id|external-id> "<resolution>"

This is the *only* caller of write_incident. The diagnosis loop cannot reach that
tool: it is filtered out of the toolConfig and refused by _dispatch (see
lambda/agent.py). "You propose; humans dispose" is enforced by there being no path
from the model to this script — a person runs it, or the incident stays open.

Running it scrubs the resolution blamelessly, embeds it, and resolves the row, so the
very next similar alert can retrieve it. That retrieval is the close→retrieve shot.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lambda"))

import tools  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__.strip())
        return 2
    identifier, resolution = argv[1], argv[2]
    if not resolution.strip():
        print("refusing to close with an empty resolution — that is the memory")
        return 2

    # Accept the external ID the demo curls as well as the UUID, so the operator can
    # paste whichever one is on screen.
    snapshot = tools.status_snapshot(identifier)
    if snapshot is None:
        print(f"no incident matching {identifier!r}")
        return 1
    incident_id = snapshot["incident_id"]

    tools.write_incident(incident_id, resolution)

    closed = tools.status_snapshot(incident_id)
    print(f"closed {closed['external_id']} ({incident_id})")
    print(f"  status      {closed['status']}")
    print(f"  resolution  {closed.get('resolution_summary') or resolution}")
    print("\nThe resolution is scrubbed, embedded and searchable — the next similar "
          "alert can retrieve it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
