"""AC4: the tool manifest is memory read/write only — exactly 4 tools, these names.

The pitch depends on this being literally true (CLAUDE.md hard rule 1). If this
test is red, someone added/renamed a tool; the fix is to remove it, not to edit
the expected set.
"""

import tools

EXPECTED = {"search_incidents", "get_runbook", "propose_diagnosis", "write_incident"}


def test_manifest_is_exactly_four_tools():
    assert set(tools.TOOL_MANIFEST) == EXPECTED
    assert len(tools.TOOL_MANIFEST) == 4


def test_manifest_entries_are_callables():
    for name, fn in tools.TOOL_MANIFEST.items():
        assert callable(fn), f"{name} is not callable"
