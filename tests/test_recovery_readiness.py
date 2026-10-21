"""HTTP readiness after a native restart must settle without retrying writes."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import socket
import urllib.request

import pytest

from test_k8s_safety import k8s, target

spec = importlib.util.spec_from_file_location(
    "in_cluster_check", Path(__file__).parents[1] / "scripts/in_cluster_check.py")
cluster_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster_check)


@pytest.mark.parametrize("readiness_only", [True, False])
def test_probe_mode_has_no_order_side_effect(monkeypatch, capsys, readiness_only):
    monkeypatch.setenv("CHECK_REQUEST_ID", "probe-test")
    monkeypatch.setenv("CHECK_READINESS_ONLY", str(int(readiness_only)))
    monkeypatch.setattr(socket, "gethostbyname", lambda name: "10.0.0.1")
    calls = []

    class Response(io.StringIO):
        def __init__(self, body, status=200):
            super().__init__(json.dumps(body))
            self.status = status
            self.headers = {"X-Request-ID": "probe-test"}

    def urlopen(request, timeout):
        calls.append(request)
        if isinstance(request, urllib.request.Request):
            assert request.get_method() == "POST"
            return Response({
                "status": "confirmed", "amount_cents": 2000,
                "item_id": "day2-demo", "quantity": 2,
                "order_id": "order-id", "payment_id": "payment-id",
            }, 201)
        role, endpoint = request.removeprefix("http://").split(":8000/")
        return Response({"service": role,
                         "status": "ok" if endpoint == "healthz" else "ready"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    cluster_check.main()
    result = json.loads(capsys.readouterr().out)
    assert result["passed"] is True
    assert sum(isinstance(request, urllib.request.Request) for request in calls) == (
        0 if readiness_only else 1)
    assert len(calls) == (6 if readiness_only else 7)
    assert ("order" in result) is not readiness_only


def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(k8s.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(k8s.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    return now


def test_routes_wait_retains_transient_errors_and_only_uses_get_probes(monkeypatch):
    now = clock(monkeypatch)
    calls = []

    def probe(request_id, *, readiness_only, timeout):
        assert readiness_only is True
        assert 0 < timeout <= 5
        calls.append(request_id)
        if len(calls) < 3:
            raise RuntimeError("connection refused")
        return {"passed": True, "readiness_only": True}

    monkeypatch.setattr(k8s, "check_services", probe)
    record = {"trial_id": "trial"}
    k8s.wait_for_service_routes(record, timeout=5)
    assert now[0] == 2
    assert calls == ["trial-routes-1", "trial-routes-2", "trial-routes-3"]
    assert [attempt["passed"] for attempt in record["route_readiness_attempts"]] == [
        False, False, True]
    assert "connection refused" in record["route_readiness_attempts"][0]["error"]


def test_routes_wait_fails_at_deadline_and_retains_every_failure(monkeypatch):
    now = clock(monkeypatch)

    def unavailable(request_id, *, readiness_only, timeout):
        assert readiness_only is True
        raise RuntimeError("still unavailable")

    monkeypatch.setattr(k8s, "check_services", unavailable)
    record = {"trial_id": "trial"}
    with pytest.raises(RuntimeError, match="within 3 seconds"):
        k8s.wait_for_service_routes(record, timeout=3)
    assert now[0] == 3
    assert len(record["route_readiness_attempts"]) == 3
    assert all(not attempt["passed"] for attempt in record["route_readiness_attempts"])


def test_malformed_probe_response_is_not_treated_as_health(monkeypatch):
    clock(monkeypatch)

    def malformed(*args, **kwargs):
        raise ValueError("invalid JSON")

    monkeypatch.setattr(k8s, "check_services", malformed)
    with pytest.raises(ValueError, match="invalid JSON"):
        k8s.wait_for_service_routes({"trial_id": "trial"})


def test_final_order_failure_is_not_retried_or_reported_as_recovery(monkeypatch, tmp_path):
    pod, cri = target()
    before = {role: {**k8s.pod_state(pod), "pod": role + "-pod",
                     "uid": role + "-uid"} for role in k8s.ROLES}
    after = deepcopy(before)
    after["payment"].update(container_id="containerd://new-id", restart_count=1,
                            last_state={"terminated": {"exitCode": 137}})
    snapshots = iter([before, after])
    monkeypatch.setattr(k8s, "guard_cluster", lambda: None)
    monkeypatch.setattr(k8s, "ready_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(k8s, "pod_for", lambda role: pod)
    monkeypatch.setattr(k8s, "pod_state", lambda value: after["payment"])
    monkeypatch.setattr(k8s, "guard_target", lambda *args: "abc123")
    monkeypatch.setattr(k8s, "provenance", lambda: {})
    monkeypatch.setattr(k8s, "kubectl", lambda *args, **kwargs: "")
    monkeypatch.setattr(k8s, "kjson", lambda *args: {"items": []})
    monkeypatch.setattr(k8s, "wait_for_service_routes", lambda record: None)
    monkeypatch.setattr(k8s, "ROOT", tmp_path)
    evidence = tmp_path / "failed-recovery.json"
    monkeypatch.setattr(k8s, "evidence_path", lambda prefix: evidence)
    stops = []

    def run(args, **kwargs):
        if "inspect" in args:
            return json.dumps(cri)
        assert "stop" in args
        stops.append(args)
        return "abc123"

    requests = []

    def services(request_id, **kwargs):
        requests.append(request_id)
        if request_id.endswith("-before"):
            return {"passed": True}
        raise RuntimeError("final order failed")

    monkeypatch.setattr(k8s, "run", run)
    monkeypatch.setattr(k8s, "check_services", services)
    with pytest.raises(RuntimeError, match="final order failed"):
        k8s.recovery(execute=True)
    assert len(stops) == 1
    assert len(requests) == 2
    record = json.loads(evidence.read_text())
    assert record["passed"] is False
    assert record["post_recovery_checks"] == []
    assert record["error"] == "final order failed"


def test_pod_lookup_and_exec_share_one_service_check_budget(monkeypatch):
    now = clock(monkeypatch)

    def lookup(role, *, timeout):
        assert role == "gateway" and timeout == 5
        now[0] += 2
        return {"metadata": {"name": "gateway-pod"}}

    def execute(*args, stdin, timeout):
        assert timeout == 3
        assert "CHECK_READINESS_ONLY=1" in args
        assert "CHECK_REQUEST_ID=budget" in args
        return '{"passed": true, "readiness_only": true}'

    monkeypatch.setattr(k8s, "pod_for", lookup)
    monkeypatch.setattr(k8s, "kubectl", execute)
    assert k8s.check_services("budget", readiness_only=True, timeout=5)["passed"]


def test_probe_without_get_only_confirmation_cannot_pass(monkeypatch):
    clock(monkeypatch)
    monkeypatch.setattr(k8s, "check_services", lambda *args, **kwargs: {"passed": True})
    record = {"trial_id": "trial"}
    with pytest.raises(RuntimeError, match="did not become healthy"):
        k8s.wait_for_service_routes(record, timeout=1)
    assert record["route_readiness_attempts"][0]["passed"] is False
