"""Bedrock Converse loop — custom, ~50 lines when done (docs/04).

ZERO SQL in this file, no psycopg import, ever (docs/05 module boundary — a test
greps for it). This module sees the four functions in tools.TOOL_MANIFEST and
nothing else. The system prompt is loaded from prompts/system.md at runtime,
never inlined — prompt changes must be diffable.
"""


def run_agent(incident_id: str) -> None:
    """Drive Claude on Bedrock over the 4-tool manifest until it proposes a
    diagnosis (AC3) or states confidence 'none' plainly and stops (AC13).
    Bedrock ThrottlingException gets the with_retry shape; after max attempts the
    run fails visibly — never a silent degrade (docs/02).
    """
    raise NotImplementedError("P2 — agent loop (docs/01 phase table)")
