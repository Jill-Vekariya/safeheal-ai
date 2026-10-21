import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import observe


def test_telemetry_deployment_refuses_foreign_resource_before_pulling(monkeypatch):
    monkeypatch.setattr(observe.lab, "guard_cluster", lambda: None)
    monkeypatch.setattr(observe.lab, "kubectl", lambda *a, **k: json.dumps({"metadata": {"labels": {}}}))
    def unexpected(*a, **k):
        raise AssertionError("No pull, load or apply is permitted for a foreign resource")
    monkeypatch.setattr(observe.lab, "run", unexpected)
    with pytest.raises(RuntimeError, match="foreign"):
        observe.deploy()


def test_fault_flag_cannot_be_used_with_deploy(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["observe.py", "deploy", "--native-fault"])
    with pytest.raises(RuntimeError, match="Fault flag"):
        observe.main()


def test_dashboard_acceptance_rejects_missing_scrape_targets():
    with pytest.raises(RuntimeError, match="three UP"):
        observe.validate_telemetry({"targets": {"data": {"activeTargets": []}}})
