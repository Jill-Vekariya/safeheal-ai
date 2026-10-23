"""Opt-in paid/local-model integration; never substitute mocked or fallback output for success."""
import os

import pytest

from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.provider import JsonProvider, ProviderConfig
from services.diagnosis.replay import evaluate_run
from test_diagnosis import DATASET


@pytest.mark.skipif(os.getenv("SAFEHEAL_RUN_LIVE_MODEL_TESTS") != "1",
                    reason="Explicit provider/model/budget opt-in unavailable; no real model was called")
def test_real_model_on_all_six_benchmark_incidents():
    config = ProviderConfig.from_env()
    assert config.provider == "openai-compatible" and config.max_calls >= 6
    provider = JsonProvider(config)
    report = evaluate_run(DATASET, DiagnosisAgent(provider))
    assert provider.calls == 6
    assert report["summary"]["llm_diagnoses"] == 6, "Fallback or rejected output cannot pass the real-model test"
    assert report["summary"]["grounded"] == 6
    # Accuracy is measured separately; this is an integration/grounding gate, not a promised score.
