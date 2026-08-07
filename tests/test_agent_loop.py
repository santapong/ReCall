"""AC3/AC13/AC4 loop mechanics, offline: the Converse loop dispatches only over the
closed manifest, persists retrievals, feeds tool validation errors back to the model
instead of persisting them, honors the honesty stop, and fails loudly rather than
spinning. Bedrock is a scripted fake — the loop logic is what's under test here;
the model's behavior is P2's live end-to-end run.
"""

import pytest

import agent
import tools

# Captured before the autouse `logged` fixture swaps it out, so one test can exercise
# the shipping implementation rather than the capture stub.
_REAL_LOG_STEP = tools.log_step


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


@pytest.fixture(autouse=True)
def logged(monkeypatch):
    """Capture the decision log instead of writing it. Autouse because every run in
    this module logs; the captured list is what the log-shape tests assert against."""
    steps = []
    monkeypatch.setattr(tools, "log_step", lambda **kw: steps.append(kw))
    return steps


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


def test_decision_log_records_every_step_in_order(monkeypatch, recorded, logged):
    """Observability is a contract, not a side effect: one row per model turn and per
    tool call, sequential seq, one run_id for the whole run."""
    client = FakeClient([
        {**_tool_msg("search_incidents", {"query": "q", "service": "billing"}),
         "usage": {"inputTokens": 900, "outputTokens": 40}},
        _text_msg("confidence none: no close match exists in memory."),
    ])
    _install(monkeypatch, client, search_incidents=lambda **kw: _search_result("none"))
    agent.run_agent("inc-6", "billing", "t", "d")

    assert [s["seq"] for s in logged] == list(range(len(logged)))
    assert len({s["run_id"] for s in logged}) == 1
    assert all(s["incident_id"] == "inc-6" for s in logged)
    assert [(s["step_type"], s["name"]) for s in logged] == [
        ("model_turn", "test-model"),
        ("tool_call", "search_incidents"),
        ("model_turn", "test-model"),
    ]
    assert logged[0]["input_tokens"] == 900 and logged[0]["output_tokens"] == 40
    assert logged[1]["confidence"] == "none"  # AC13's audit trail
    assert all(isinstance(s["latency_ms"], int) for s in logged)


def test_decision_log_records_the_rejected_citation(monkeypatch, recorded, logged):
    """The enforcement working is the most valuable row in the log — it must be there."""
    def rejecting_propose(**kw):
        raise LookupError("cites unknown incident ids ['ghost'] (AC3)")

    client = FakeClient([
        _tool_msg("search_incidents", {"query": "q", "service": "billing"}),
        _tool_msg("propose_diagnosis", {"incident_id": "inc-7", "diagnosis": "d",
                                        "cited_incident_ids": ["ghost"]}),
        _text_msg("confidence low: cannot ground this."),
    ])
    _install(monkeypatch, client,
             search_incidents=lambda **kw: _search_result("low"),
             propose_diagnosis=rejecting_propose)
    agent.run_agent("inc-7", "billing", "t", "d")

    errors = [s for s in logged if s["outcome"] == "error"]
    assert len(errors) == 1
    assert errors[0]["name"] == "propose_diagnosis"
    assert "ghost" in errors[0]["detail"]


def test_unreachable_decision_log_never_breaks_a_diagnosis(monkeypatch, recorded, capsys):
    """The ADR in tools.log_step, asserted end-to-end with the REAL logger against an
    unreachable database: the run completes, and the drop is visible rather than silent.
    """
    monkeypatch.setattr(tools, "log_step", _REAL_LOG_STEP)  # undo the autouse capture
    monkeypatch.delenv("CRDB_CONN_STRING", raising=False)
    client = FakeClient([
        _tool_msg("search_incidents", {"query": "q", "service": "billing"}),
        _text_msg("confidence none: no close match exists in memory."),
    ])
    _install(monkeypatch, client, search_incidents=lambda **kw: _search_result("none"))

    out = agent.run_agent("inc-8", "billing", "t", "d")

    assert "no close match" in out  # the diagnosis survived the observability outage
    assert "agent_runs log dropped" in capsys.readouterr().out  # and said so


def test_system_prompt_loads_the_contract():
    prompt = agent.load_system_prompt()
    assert "confidence" in prompt and "none" in prompt
    assert "# Agent system prompt" not in prompt  # human preamble stripped


# --- T1: propose-only is structural, not instructional -----------------------
# README's "The guarantee" says Recall never executes a fix and that the close path
# is a separate tool a human triggers. Until these tests existed, the only thing
# enforcing that was a sentence in prompts/system.md, and write_incident — which
# does UPDATE incidents SET status='resolved', embedding=... — was offered to the
# model on every single Converse call.


def test_diagnosis_loop_is_never_offered_the_write_tool(monkeypatch, recorded):
    """The invariant, at the only place it can actually be enforced: the toolConfig."""
    client = FakeClient([_text_msg("confidence none: nothing close in memory.")])
    _install(monkeypatch, client)
    agent.run_agent("inc-t1", "billing", "t", "d")

    assert client.calls, "the loop never called Converse"
    for call in client.calls:
        offered = [s["toolSpec"]["name"] for s in call["toolConfig"]["tools"]]
        assert "write_incident" not in offered
        assert offered == ["search_incidents", "get_runbook", "propose_diagnosis"]


def test_write_incident_is_refused_mid_diagnosis_even_if_called(monkeypatch, recorded, logged):
    """Belt and braces: if a spec ever drifts back into the diagnosis config, dispatch
    still refuses, the model gets a correctable error, and nothing is written."""
    written = []
    client = FakeClient([
        _tool_msg("write_incident", {"incident_id": "inc-t2", "resolution_summary": "faked"}),
        _text_msg("understood — that is the close path."),
    ])
    _install(monkeypatch, client, write_incident=lambda **kw: written.append(kw))
    out = agent.run_agent("inc-t2", "billing", "t", "d")

    assert not written, "write_incident executed during diagnosis"
    assert "close path" in out
    errors = [s for s in logged if s["outcome"] == "error"]
    assert errors and errors[0]["name"] == "write_incident"
    assert "not available during diagnosis" in errors[0]["detail"]


def test_manifest_still_holds_all_four_tools():
    """AC4 is about the manifest, not the diagnosis config — filtering one out of the
    Converse call must not shrink the manifest the pitch counts."""
    assert len(tools.TOOL_MANIFEST) == 4
    assert len(agent.TOOL_SPECS) == 4
    assert len(agent.DIAGNOSIS_TOOL_SPECS) == 3


# --- B6: recoverable errors reach the model, not the caller as a 502 ---------


def test_unknown_tool_name_is_correctable_not_fatal(monkeypatch, recorded, logged):
    """The manifest lookup used to sit outside the try, so a hallucinated tool name
    escaped as an uncaught KeyError and the Function URL returned 502."""
    client = FakeClient([
        _tool_msg("restart_the_service", {"host": "web-1"}),
        _text_msg("confidence none: I only have memory tools."),
    ])
    _install(monkeypatch, client)
    out = agent.run_agent("inc-b6a", "billing", "t", "d")

    assert "confidence none" in out
    assert [s for s in logged if s["outcome"] == "error"]


def test_extra_kwarg_is_correctable_not_fatal(monkeypatch, recorded, logged):
    """A model passing an argument the tool doesn't take raises TypeError, which the
    original narrow (LookupError, ValueError) catch let through."""
    client = FakeClient([
        _tool_msg("search_incidents", {"query": "q", "service": "billing", "nonsense": 1}),
        _text_msg("confidence none: retrying without that argument."),
    ])
    def real_signature(query, service, k=5):  # as shipped — rejects the extra kwarg
        return _search_result()

    _install(monkeypatch, client, search_incidents=real_signature)
    out = agent.run_agent("inc-b6b", "billing", "t", "d")

    assert "confidence none" in out
    errors = [s for s in logged if s["outcome"] == "error"]
    assert errors and errors[0]["name"] == "search_incidents"
    assert "nonsense" in errors[0]["detail"]


# --- C6: MAX_TURNS is the real ceiling, not one below it ---------------------


def test_converse_budget_never_exceeds_max_turns(monkeypatch, recorded):
    """A run that proposes on its last available iteration used to make MAX_TURNS + 1
    Converse calls, because the closing summary fired inside the same iteration —
    putting the documented cost and latency ceilings a full turn under the truth."""
    scripted = [_tool_msg("search_incidents", {"query": "q", "service": "billing"})
                for _ in range(agent.MAX_TURNS - 2)]
    scripted.append(_tool_msg("propose_diagnosis", {
        "incident_id": "inc-c6", "diagnosis": "d", "cited_incident_ids": ["past-1"]}))
    scripted.append(_text_msg("confidence high: summarized on the last turn"))

    client = FakeClient(scripted)
    _install(monkeypatch, client,
             search_incidents=lambda **kw: _search_result(),
             propose_diagnosis=lambda **kw: None)
    out = agent.run_agent("inc-c6", "billing", "t", "d")

    assert "summarized on the last turn" in out
    assert len(client.calls) <= agent.MAX_TURNS
