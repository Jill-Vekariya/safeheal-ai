"""The optional compact ranker cannot invent evidence or bypass output validation."""
from copy import deepcopy
import json
import math
import httpx
import pytest
from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.provider import (JsonProvider, ProviderConfig, candidate_context,
                                        expand_selection, CANDIDATE_PROMPT_VERSION)
from services.diagnosis.replay import grounded
from test_diagnosis import bundle, config, response


def test_compact_transport_maps_model_index_to_actual_supported_evidence():
    b = bundle()
    captured = []
    def handler(request):
        payload = json.loads(request.content)
        context = json.loads(payload["messages"][1]["content"])
        captured.append(context)
        assert context["prompt_version"] == CANDIDATE_PROMPT_VERSION
        assert "tools" not in payload and "functions" not in payload
        assert all(set(c) == {"candidate_index", "classification", "service"} for c in context["candidates"])
        return httpx.Response(200, json=response({"selections":[{"candidate_index":0,"confidence":.9}]}))
    p = JsonProvider(config(selection_mode="candidate_index"), httpx.MockTransport(handler))
    result = DiagnosisAgent(p).diagnose(b)
    assert result["source"] == "llm" and grounded(result)
    assert result["execution_allowed"] is False and p.calls == 1
    assert result["hypotheses"][0]["evidence_refs"] == b.candidates()[0]["evidence_refs"][-1:]
    assert len(captured) == 1


@pytest.mark.parametrize("value", [
    None, [], {"hypotheses":[]}, {"selections":{}},
    {"selections":[{"candidate_index":True,"confidence":.9}]},
    {"selections":[{"candidate_index":-1,"confidence":.9}]},
    {"selections":[{"candidate_index":999,"confidence":.9}]},
    {"selections":[{"candidate_index":0,"confidence":"0.9"}]},
    {"selections":[{"candidate_index":0,"confidence":True}]},
    {"selections":[{"candidate_index":0,"confidence":math.nan}]},
    {"selections":[{"candidate_index":0,"confidence":math.inf}]},
    {"selections":[{"candidate_index":0,"confidence":-.1}]},
    {"selections":[{"candidate_index":0,"confidence":1.1}]},
    {"selections":[{"candidate_index":0,"confidence":.9,"command":"anything"}]},
    {"selections":[{"candidate_index":0,"confidence":.9}],"execution_allowed":True},
    {"selections":[{"candidate_index":0,"confidence":.9}]*2},
    {"selections":[{"candidate_index":0,"confidence":.9}]*4},
])
def test_invalid_or_authority_bearing_selections_are_rejected(value):
    _, candidates = candidate_context(bundle())
    with pytest.raises(ValueError):
        expand_selection(value, candidates)


def test_abstention_is_explicit_and_does_not_manufacture_a_model_diagnosis():
    p = JsonProvider(config(selection_mode="candidate_index"),
                     httpx.MockTransport(lambda _: httpx.Response(200,json=response({"selections":[]}))))
    r = DiagnosisAgent(p).diagnose(bundle())
    assert r["provider_status"] == "model_abstained" and not r["hypotheses"]
    assert r["execution_allowed"] is False


def test_transport_rejection_and_budget_remain_bounded_in_compact_mode():
    def handler(_):
        return httpx.Response(200,json=response({"selections":[{"candidate_index":999,"confidence":.9}]}))
    p=JsonProvider(config(selection_mode="candidate_index"),httpx.MockTransport(handler))
    r=DiagnosisAgent(p).diagnose(bundle())
    assert r["provider_status"] == "provider_invalid_response" and r["source"] == "deterministic_fallback"
    assert DiagnosisAgent(p).diagnose(bundle())["provider_status"] == "call_budget_exhausted"
    assert p.calls == 1


def test_compact_projection_preserves_full_independent_input_validation():
    b=bundle()
    context,candidates=candidate_context(b)
    used={ref for c in candidates for ref in c["evidence_refs"]}
    assert used == {r["id"] for r in context["observations"]}
    assert all("raw_sha256" not in r["values"] for r in context["observations"])
    assert len(context["observations"]) <= len(candidates)
    bad=deepcopy(b);bad.records[-1].values["raw_sha256"]="0"*64
    with pytest.raises(ValueError):
        candidate_context(bad)


def test_selection_mode_is_explicit_and_legacy_remains_default(monkeypatch):
    monkeypatch.delenv("SAFEHEAL_LLM_SELECTION_MODE",raising=False)
    assert ProviderConfig.from_env().selection_mode == "hypotheses"
    monkeypatch.setenv("SAFEHEAL_LLM_SELECTION_MODE","candidate_index")
    assert ProviderConfig.from_env().selection_mode == "candidate_index"
    with pytest.raises(ValueError):
        config(selection_mode="shell")
