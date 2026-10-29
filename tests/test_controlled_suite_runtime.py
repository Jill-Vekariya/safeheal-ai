"""Exercise new fault/cleanup paths with deterministic adapters, not a real cluster."""

import json
from types import SimpleNamespace

import pytest

from scripts import controlled_experiment as experiment


@pytest.mark.parametrize("scenario", ["http_5xx", "latency"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_negative_control_observes_fault_and_preserves_cleanup_failure(
        tmp_path, monkeypatch, scenario, cleanup_fails):
    now = [0.0]
    monkeypatch.setattr(experiment, "time", SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda duration: now.__setitem__(0, now[0] + duration)))
    deployment = {"metadata": {"uid": "owned"},
                  "spec": {"replicas": 1, "template": {"image": "fixed"}},
                  "status": {"readyReplicas": 1}}
    api = SimpleNamespace(deployment=lambda: deployment, close=lambda: None)
    monkeypatch.setattr(experiment.lab, "kjson", lambda *a: deployment)
    monkeypatch.setattr(experiment.lab, "kubectl", lambda *a, **kw: "ready")
    monkeypatch.setattr(experiment.lab, "wait_for_service_routes", lambda *a, **kw: None)
    monkeypatch.setattr(experiment, "enroll", lambda *a: api)
    monkeypatch.setattr(experiment.recovery, "forbidden_checks", lambda *a: {"fixture": "not a live RBAC check"})
    monkeypatch.setattr(experiment, "rule_support", lambda bundle: False)
    monkeypatch.setattr(experiment, "Collector", lambda *a: SimpleNamespace(
        collect=lambda: SimpleNamespace(document=lambda: {"at": 0})))
    monkeypatch.setattr(experiment, "Aggregator", lambda *a: SimpleNamespace(
        snapshot=lambda *a: None, finish=lambda: object()))
    monkeypatch.setattr(experiment, "MeasurementJournal", lambda *a: SimpleNamespace(
        write=lambda *a: None, close=lambda: None))

    class Workload:
        def __init__(self, *args):
            pass

        def start(self):
            pass

        def close(self):
            pass

        def rows(self):
            return [{"started_elapsed_seconds": 2, "finished_elapsed_seconds": 4,
                     "elapsed_seconds": 2, "valid_response": scenario == "latency"}] + [
                        {"started_elapsed_seconds": t - .1, "finished_elapsed_seconds": t,
                         "elapsed_seconds": .1, "valid_response": True} for t in (20, 21, 22)]

    class Backend:
        prometheus_url = "http://fixture.invalid"
        gateway_url = "http://fixture.invalid"

        def validate_target(self):
            self.validated = True

        def inject(self, name, trial_id, duration):
            assert self.validated and name == scenario and duration == 15
            return {"applied": True}

        def cleanup(self, trial_id, name):
            self.cleaned = True
            if cleanup_fails:
                raise RuntimeError("injected cleanup failure")
            return {"removed": True}

    monkeypatch.setattr(experiment, "Workload", Workload)
    # No policy permission: invoking the recovery CLI would be a test failure.
    monkeypatch.setattr(experiment.subprocess, "run", lambda *a, **kw: pytest.fail("unexpected recovery authority"))
    backend = Backend()
    slot = {"block": 1, "arm": "rule_policy", "scenario": scenario}
    plan = {"horizon_seconds": 45, "decision_delay_seconds": 8, "fault_duration_seconds": 15}
    folder = tmp_path / "trial"
    if cleanup_fails:
        with pytest.raises(RuntimeError, match="cleanup failure"):
            experiment.trial(slot, plan, folder, backend, None)
    else:
        experiment.trial(slot, plan, folder, backend, None)
    saved = json.loads((folder / "trial.json").read_text())
    assert backend.cleaned and saved["attempted"] and saved["effect_verified"]
    assert saved["ground_truth"]["fault"] == scenario
    assert saved["metrics"]["recovery_seconds"] == 20
    assert saved["cleanup_passed"] is not cleanup_fails
    assert saved["status"] == ("technical_failure" if cleanup_fails else "observed")
