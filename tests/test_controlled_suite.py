from scripts.controlled_core import metrics
from scripts.controlled_suite import SCENARIOS, suite_protocol, summary
import pytest


def test_all_cells_predeclared_and_missing_trials_retained():
    plan = suite_protocol()
    assert plan == suite_protocol() and len(plan["slots"]) == 27
    report = summary(plan, [])
    assert report["planned"] == 27 and report["attempted"] == 0
    for scenario in SCENARIOS:
        assert all(a["planned"] == 3 and a["not_run"] == 3
                   for a in report["scenarios"][scenario]["arms"].values())


def test_scenarios_never_pool_and_failure_stays_in_denominator():
    plan = suite_protocol(repeats=1)
    slot = plan["slots"][0]
    row = {**slot, "attempted": True, "status": "technical_failure", "cleanup_passed": False}
    report = summary(plan, [row])
    assert report["scenarios"][slot["scenario"]]["arms"][slot["arm"]]["technical_failures"] == 1
    assert report["scenarios"][slot["scenario"]]["cleanup_failures"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        summary(plan, [row, row])


def test_latency_impact_can_be_valid_but_slow_response():
    row = {"scenario": "latency", "injection_elapsed": 0, "injection_verified": True,
           "effect_verified": True, "observation_elapsed_end": 45}
    requests = [{"started_elapsed_seconds": 1, "finished_elapsed_seconds": 3,
                 "elapsed_seconds": 2, "valid_response": True}]
    requests += [{"started_elapsed_seconds": t - .1, "finished_elapsed_seconds": t,
                  "elapsed_seconds": .1, "valid_response": True} for t in (5, 6, 7)]
    assert metrics(row, requests, 45)["recovery_seconds"] == 7
