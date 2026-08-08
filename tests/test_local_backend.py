"""M0': the credential-free local stack, end to end.

Bedrock model access has gated this project since Jul 8. These backends exist so the
loop, the decision log, the ingest path and the status page are runnable and testable
today; the seams are explicit opt-ins (EMBED_BACKEND / BEDROCK_BACKEND = "local") so
a missing credential can never silently select them.

What these tests protect is the *contract*: unit vectors of the real dimension,
deterministic across processes, and a loop that reaches a grounded diagnosis without
touching AWS. They deliberately assert nothing about retrieval quality — the stand-in
is lexical, not semantic, and any quality number taken from it is provisional.
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

import agent
import embed as embed_mod
import tools

LAMBDA_DIR = Path(__file__).resolve().parents[1] / "lambda"


# --- the embedding stand-in --------------------------------------------------


def test_local_vectors_are_unit_norm_and_the_right_width():
    """`<->` is only metric-safe against unit vectors — the contract Titan's
    normalize:true upholds and this backend must match."""
    vector = embed_mod.local_embed("payment webhooks timing out, p99 above 30s")
    assert len(vector) == embed_mod.EMBED_DIM
    assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-9)


def test_local_embedding_is_deterministic_within_a_process():
    text = "connection pool exhausted on the billing worker"
    assert embed_mod.local_embed(text) == embed_mod.local_embed(text)


def test_local_embedding_is_deterministic_across_processes():
    """The one that matters: PYTHONHASHSEED randomizes str hashing per process, so a
    corpus embedded in one run would be unmatchable by a query in the next. blake2b
    is used precisely to avoid that, and only a subprocess can prove it."""
    code = (
        "import embed; "
        "v = embed.local_embed('payment webhooks timing out'); "
        "print(sum(v[:64]))"
    )

    def run():
        return subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTHONPATH": str(LAMBDA_DIR), "PYTHONHASHSEED": "random"},
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    assert run() == run()


def test_local_embedding_separates_unrelated_text():
    """Not a quality claim — just that the backend is not degenerate. Identical text
    must be nearer to itself than to something unrelated, or every distance is noise
    and threshold tuning would be meaningless even provisionally."""
    def distance(a, b):
        va, vb = embed_mod.local_embed(a), embed_mod.local_embed(b)
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb)))

    alert = "payment webhooks timing out p99 above 30s"
    near = "payment webhooks timing out, p99 latency above 30s on billing"
    far = "kubernetes node pool autoscaler stuck scaling down in eu-west"
    assert distance(alert, near) < distance(alert, far)


def test_local_backend_is_never_selected_by_accident(monkeypatch):
    """A missing credential must fail loudly, not silently downgrade quality."""
    for value in ("", "  ", "true", "1", "yes", "bedrock"):
        monkeypatch.setattr(embed_mod, "EMBED_BACKEND", value.strip().lower())
        monkeypatch.setattr(embed_mod, "get_client", _explode)
        with pytest.raises(RuntimeError, match="would have called Bedrock"):
            embed_mod.embed("some text")


def _explode(*_a, **_kw):
    raise RuntimeError("would have called Bedrock")


def test_local_backend_warns_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(embed_mod, "EMBED_BACKEND", "local")
    monkeypatch.setattr(embed_mod, "_warned_local", False)
    embed_mod.embed("payment webhooks timing out")
    assert "EMBED_BACKEND=local" in capsys.readouterr().err


def test_empty_token_text_is_refused():
    with pytest.raises(ValueError):
        embed_mod.local_embed("--- ... !!!")


# --- the scripted model ------------------------------------------------------


@pytest.fixture
def local_model(monkeypatch):
    monkeypatch.setattr(agent, "BEDROCK_BACKEND", "local")
    monkeypatch.setattr(agent, "MODEL_ID", "")
    monkeypatch.setattr(agent, "get_client", _explode)  # proves AWS is never touched
    steps = []
    monkeypatch.setattr(tools, "log_step", lambda **kw: steps.append(kw))
    monkeypatch.setattr(tools, "record_retrieval", lambda *a, **kw: None)
    return steps


def _search_result(confidence="high", match_ids=("past-1",), runbook_ids=("rb-1",)):
    return tools.SearchResult(
        query="q", service="billing", confidence=confidence,
        runbook_ids=list(runbook_ids),
        matches=[tools.Match(id=mid, external_id=f"ext-{mid}", title="prior",
                             service="billing", distance=0.2, score=0.8)
                 for mid in match_ids],
    )


def test_local_loop_reaches_a_grounded_diagnosis(monkeypatch, local_model):
    """M0's exit criterion in miniature: search → runbook → propose → summarize,
    citing a real retrieved ID, with no AWS call anywhere in the path."""
    proposals = []
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result())
    monkeypatch.setitem(tools.TOOL_MANIFEST, "get_runbook",
                        lambda **kw: tools.Runbook(id="rb-1", service="billing",
                                                   title="drain", content="step 2: drain"))
    monkeypatch.setitem(tools.TOOL_MANIFEST, "propose_diagnosis",
                        lambda **kw: proposals.append(kw))

    out = agent.run_agent("inc-local", "billing", "webhooks timing out", "p99 > 30s")

    assert proposals, "the local loop never proposed a diagnosis"
    assert proposals[0]["cited_incident_ids"] == ["past-1"]  # cites what it retrieved
    assert "confidence high" in out
    assert [s for s in local_model if s["step_type"] == "tool_call"]


def test_local_loop_takes_the_honesty_branch_on_confidence_none(monkeypatch, local_model):
    """AC13 structurally: nothing close in memory means say so and stop, with no
    citations and no proposal."""
    proposals = []
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result("none", match_ids=(), runbook_ids=()))
    monkeypatch.setitem(tools.TOOL_MANIFEST, "propose_diagnosis",
                        lambda **kw: proposals.append(kw))

    out = agent.run_agent("inc-none", "billing", "something novel", "never seen")

    assert "confidence none" in out
    assert not proposals


def test_local_loop_never_calls_the_write_tool(monkeypatch, local_model):
    """T1 holds on this path too — the stand-in follows the same closed manifest."""
    written = []
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result())
    monkeypatch.setitem(tools.TOOL_MANIFEST, "get_runbook",
                        lambda **kw: tools.Runbook(id="rb-1", service="billing",
                                                   title="t", content="c"))
    monkeypatch.setitem(tools.TOOL_MANIFEST, "propose_diagnosis", lambda **kw: None)
    monkeypatch.setitem(tools.TOOL_MANIFEST, "write_incident",
                        lambda **kw: written.append(kw))

    agent.run_agent("inc-w", "billing", "t", "d")
    assert not written


def test_local_model_turns_are_labelled_in_the_decision_log(monkeypatch, local_model):
    """A run on the stand-in must be identifiable afterwards, not look like a real one."""
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result("none", match_ids=(), runbook_ids=()))
    agent.run_agent("inc-label", "billing", "t", "d")

    model_turns = [s for s in local_model if s["step_type"] == "model_turn"]
    assert model_turns and all(s["name"] == "local-scripted" for s in model_turns)


def test_ingest_handler_runs_end_to_end_on_the_local_stack(monkeypatch, local_model):
    """The whole POST path — validate → insert → agent → JSON response — with the DB
    write surface stubbed but the loop real."""
    import ingest_handler

    monkeypatch.setattr(tools, "insert_incident", lambda *a, **kw: "inc-e2e")
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result())
    monkeypatch.setitem(tools.TOOL_MANIFEST, "get_runbook",
                        lambda **kw: tools.Runbook(id="rb-1", service="billing",
                                                   title="t", content="step 2: drain"))
    monkeypatch.setitem(tools.TOOL_MANIFEST, "propose_diagnosis", lambda **kw: None)

    resp = ingest_handler.handler({"body": json.dumps({
        "external_id": "alert-local", "service": "billing",
        "title": "payment webhooks timing out", "description": "p99 > 30s",
        "severity": "sev2",
    })}, None)

    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    body = json.loads(resp["body"])
    assert body["incident_id"] == "inc-e2e"
    assert "confidence" in body["response"]


# --- AC12: the amnesia arm is a real run, not a display toggle ---------------


def test_memory_off_withholds_the_tools_entirely(monkeypatch, local_model):
    """`?memory=off` used to be CSS that blanked a panel — filming that as an A/B
    would have compared the page against itself. The arm now runs with no tools at
    all (not tools that return nothing), so what appears is what an ungrounded model
    actually says."""
    recorded = []
    monkeypatch.setattr(tools, "record_ungrounded_answer",
                        lambda iid, text: recorded.append((iid, text)))
    called = []
    for name in tools.TOOL_MANIFEST:
        monkeypatch.setitem(tools.TOOL_MANIFEST, name,
                            lambda _n=name, **kw: called.append(_n))

    out = agent.run_agent("inc-amnesia", "billing", "webhooks timing out", "p99 > 30s",
                          memory=False)

    assert not called, f"the amnesia arm reached memory: {called}"
    assert recorded and recorded[0][0] == "inc-amnesia"
    assert out == recorded[0][1] and out


def test_memory_off_is_labelled_in_the_decision_log(monkeypatch, local_model):
    monkeypatch.setattr(tools, "record_ungrounded_answer", lambda *a: None)
    agent.run_agent("inc-amnesia-2", "billing", "t", "d", memory=False)
    assert any("memory off" in s["name"] for s in local_model)


def test_memory_on_is_still_the_default(monkeypatch, local_model):
    """A missing query param must never silently select the ungrounded arm."""
    monkeypatch.setitem(tools.TOOL_MANIFEST, "search_incidents",
                        lambda **kw: _search_result("none", match_ids=(), runbook_ids=()))
    agent.run_agent("inc-default", "billing", "t", "d")
    assert any(s["step_type"] == "tool_call" for s in local_model)
