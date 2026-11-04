"""A scale-zero trial may replace a Pod, but never the enrolled Deployment."""
from contextlib import nullcontext
from copy import deepcopy
import json
import sys
from types import SimpleNamespace

import pytest

from scripts import controlled_suite as suite


@pytest.mark.parametrize("drift", [None, "uid", "template"])
def test_each_trial_rebinds_pod_and_rejects_deployment_drift(tmp_path, monkeypatch, drift):
    deployment = {"metadata": {"uid": "deployment-owned"},
                  "spec": {"replicas": 1, "template": {"spec": {"image": "fixed"}}},
                  "status": {"readyReplicas": 1}}
    current = {"pod": "payment-before", "deployment": deployment}
    backends = []
    attempted = []

    def require(condition, message):
        if not condition:
            raise RuntimeError(message)

    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    class Backend:
        def __init__(self, folder):
            self.folder, self.pod, self.closed = folder, current["pod"], False
            backends.append(self)

        def preflight(self):
            return {"payment_pod": self.pod}

        def start(self):
            pass

        def validate_target(self):
            require(self.pod == current["pod"], "Payment Pod changed since run preflight")

        def close(self):
            self.closed = True

    def trial(slot, plan, folder, backend, provider):
        folder.mkdir(parents=True)
        attempted.append(slot["scenario"])
        backend.validate_target()
        row = {**slot, "trial_id": folder.name, "attempted": True,
               "status": "observed", "cleanup_passed": True}
        save(folder / "trial.json", row)
        if slot["scenario"] == "payment_scale_zero":
            # Exactly the parent-preserving replacement observed in the failed CI run.
            current["pod"] = "payment-after"
            if drift == "uid":
                current["deployment"]["metadata"]["uid"] = "foreign-deployment"
            elif drift == "template":
                current["deployment"]["spec"]["template"]["spec"]["image"] = "changed"
        return row

    lab = SimpleNamespace(NAMESPACE="owned-test", recovery_lock=nullcontext,
                          kjson=lambda *args: deepcopy(current["deployment"]), require=require)
    monkeypatch.setitem(sys.modules, "k8s", lab)
    monkeypatch.setitem(sys.modules, "verify_recovery", SimpleNamespace(save=save))
    monkeypatch.setitem(sys.modules, "benchmark_kubernetes", SimpleNamespace(KubernetesBackend=Backend))
    monkeypatch.setitem(sys.modules, "controlled_experiment", SimpleNamespace(trial=trial))
    plan = suite.suite_protocol(repeats=1, horizon=30)
    plan["slots"] = [{"block": 1, "scenario": "payment_scale_zero", "arm": "native"},
                     {"block": 1, "scenario": "latency", "arm": "rule_policy"}]
    output = tmp_path / "run"
    if drift:
        with pytest.raises(RuntimeError, match="Deployment identity or template changed"):
            suite.run(plan, output)
        assert attempted == ["payment_scale_zero"]
        assert json.loads((output / "run.json").read_text())["planned_slots"] == 2
    else:
        suite.run(plan, output)
        assert attempted == ["payment_scale_zero", "latency"]
        assert len(backends) == 2 and backends[1].pod == "payment-after"
        first_ids = {r["trial_id"] for r in json.loads((output / "run.json").read_text())["rows"]}
        again = tmp_path / "second-run"
        suite.run(plan, again)
        second_ids = {r["trial_id"] for r in json.loads((again / "run.json").read_text())["rows"]}
        assert not first_ids & second_ids
    assert all(b.closed for b in backends)
