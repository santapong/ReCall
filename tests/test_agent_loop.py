"""AC3/AC13/AC4 loop mechanics, offline: the Converse loop dispatches only over the
closed manifest, persists retrievals, feeds tool validation errors back to the model
instead of persisting them, honors the honesty stop, and fails loudly rather than
spinning. Bedrock is a scripted fake — the loop logic is what's under test here;
the model's behavior is P2's live end-to-end run.
"""

import pytest

import agent
import tools


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("fake client ran out of scripted responses")
        return self.responses.pop(0)


def _text_msg(text):
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}}


def _tool_msg(name, args, use_id="t1"):
    return {"output": {"message": {"role": "assistant", "content": [
        {"toolUse": {"toolUseId": use_id, "name": name, "input": args}},
    ]}}}


def _search_result(confidence="high", matches=()):
    return tools.SearchResult(
        query="q", service="billing", confidence=confidence,
        matches=list(matches), runbook_ids=["rb-1"],
    )


@pytest.fixture(autouse=True)
def _model_id(monkeypatch):
    monkeypatch.setattr(agent, "MODEL_ID", "test-model")


@pytest.fixture
def recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, "record_retrieval", lambda iid, res: calls.append((iid, res)))
    return calls


def _install(monkeypatch, client, **tool_fns):
    monkeypatch.setattr(agent, "_client", client)
    for name, fn in tool_fns.items():
        monkeypatch.setitem(tools.TOOL_MANIFEST, name, fn)


def test_tool_specs_match_manifest_exactly():
    spec_names = [s["toolSpec"]["name"] for s in agent.TOOL_SPECS]
    assert spec_names == list(tools.TOOL_MANIFEST)  # AC4, both sides


def test_happy_path_search_runbook_propose(monkeypatch, recorded):
    proposals = []
    client = FakeClient([
        _tool_msg("search_incidents", {"query": "webhooks", "service": "billing"}),
        _tool_msg("get_runbook", {"runbook_id": "rb-1"}),
        _tool_msg("propose_diagnosis", {
            "incident_id": "inc-1", "diagnosis": "pool exhausted",
            "cited_incident_ids": ["past-1"],
        }),
        _text_msg("confidence high: webhook pool exhausted, see rb-1 step 2"),
    ])
    _install(
        monkeypatch, client,
        search_incidents=lambda **kw: _search_result(),
        get_runbook=lambda **kw: tools.Runbook(id="rb-1", service="billing",
                                               title="webhook", content="step 2: drain"),
        propose_diagnosis=lambda **kw: proposals.append(kw),
    )
    out = agent.run_agent("inc-1", "billing", "webhooks timing out", "p99 > 30s")
    assert "confidence high" in out
    assert proposals and proposals[0]["cited_incident_ids"] == ["past-1"]
    assert recorded and recorded[0][0] == "inc-1"  # the loop persisted the retrieval


def test_honesty_branch_stops_without_proposing(monkeypatch, recorded):
    client = FakeClient([
        _tool_msg("search_incidents", {"query": "novel", "service": "billing"}),
        _text_msg("confidence none: no close match exists in memory. Stopping."),
    ])
    _install(monkeypatch, client, search_incidents=lambda **kw: _search_result("none"))
    out = agent.run_agent("inc-2", "billing", "never seen this", "novel failure")
    assert "no close match" in out
    assert recorded[0][1].confidence == "none"


def test_invented_id_becomes_error_result_not_a_crash(monkeypatch, recorded):
    def rejecting_propose(**kw):
        raise LookupError("diagnosis cites unknown incident ids ['ghost'] (AC3)")

    client = FakeClient([
        _tool_msg("search_incidents", {"query": "q", "service": "billing"}),
        _tool_msg("propose_diagnosis", {"incident_id": "inc-3", "diagnosis": "d",
                                        "cited_incident_ids": ["ghost"]}),
        _text_msg("confidence low: cannot ground this; no valid citation."),
    ])
    _install(monkeypatch, client,
             search_incidents=lambda **kw: _search_result("low"),
             propose_diagnosis=rejecting_propose)
    out = agent.run_agent("inc-3", "billing", "t", "d")
    assert "no valid citation" in out
    # The rejection went back to the model as a tool error, in-band:
    statuses = [
        c["toolResult"]["status"]
        for m in client.calls[-1]["messages"] for c in m["content"] if "toolResult" in c
    ]
    assert "error" in statuses


def test_runaway_loop_fails_loudly(monkeypatch, recorded):
    client = FakeClient([
        _tool_msg("search_incidents", {"query": "q", "service": "billing"})
    ] * agent.MAX_TURNS)
    _install(monkeypatch, client, search_incidents=lambda **kw: _search_result())
    with pytest.raises(RuntimeError, match="refusing"):
        agent.run_agent("inc-4", "billing", "t", "d")


def test_unset_model_id_is_loud(monkeypatch):
    monkeypatch.setattr(agent, "MODEL_ID", "")
    with pytest.raises(RuntimeError, match="BEDROCK_MODEL_ID"):
        agent.run_agent("inc-5", "billing", "t", "d")


def test_system_prompt_loads_the_contract():
    prompt = agent.load_system_prompt()
    assert "confidence" in prompt and "none" in prompt
    assert "# Agent system prompt" not in prompt  # human preamble stripped
