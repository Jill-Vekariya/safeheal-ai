"""Safety and resource ownership tests; all cluster effects are faked here."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_kubernetes as backend


def pod(role="payment"):
    return {
        "metadata": {"name": role + "-example", "namespace": "safeheal-dev", "uid": role + "-uid",
                     "labels": {"app.kubernetes.io/name": role,
                                "app.kubernetes.io/part-of": "safeheal-ai"}},
        "spec": {"nodeName": "safeheal-dev-control-plane", "restartPolicy": "Always"},
        "status": {"containerStatuses": [{"name": role, "containerID": "containerd://" + role + "123",
                                          "imageID": "sha256:example", "restartCount": 0, "ready": True,
                                          "state": {"running": {}}, "lastState": {}}]},
    }


def cri_for(target):
    return {"status": {"id": target["status"]["containerStatuses"][0]["containerID"].removeprefix("containerd://"),
                       "state": "CONTAINER_RUNNING", "labels": {
                           "io.kubernetes.pod.namespace": target["metadata"]["namespace"],
                           "io.kubernetes.pod.name": target["metadata"]["name"],
                           "io.kubernetes.pod.uid": target["metadata"]["uid"],
                           "io.kubernetes.container.name": "payment"}}}


@pytest.fixture
def lab(monkeypatch, tmp_path):
    calls = []
    pods = {role: pod(role) for role in backend.lab.ROLES}
    deployment = {
        "metadata": deepcopy(pods["payment"]["metadata"]),
        "spec": {"replicas": 1, "template": {"spec": {"containers": [{
            "name": "payment", "env": [{"name": "SAFEHEAL_FAULTS_ENABLED", "value": "local-test"}],
        }]}}},
    }
    prometheus = {
        "metadata": {"namespace": "safeheal-dev", "labels": dict(backend.lab.LABELS)},
        "spec": {"selector": {"app.kubernetes.io/name": "prometheus",
                               "app.kubernetes.io/part-of": "safeheal-ai"}},
    }
    runtime = {
        "version": backend.FAULT_VERSION, "enabled": True, "path": backend.FAULT_PATH,
        "source_sha256": {name: hashlib.sha256((backend.lab.ROOT / name).read_bytes()).hexdigest()
                          for name in ("services/app.py", "services/benchmark_faults.py")},
        "runtime_identity": {"pid_namespace_inode": 456, "pid1_start_ticks": "123"}, "lease": None,
    }
    monkeypatch.setattr(backend.lab, "guard_cluster", lambda: calls.append(("guard",)))
    monkeypatch.setattr(backend.lab, "pod_for", lambda role: deepcopy(pods[role]))
    monkeypatch.setattr(backend.lab, "provenance", lambda: {"head": "fixture", "working_tree": []})
    monkeypatch.setattr(backend.lab, "check_services", lambda rid: {"request_id": rid, "ok": True})

    def kjson(*args):
        calls.append(("kjson", args))
        if "deployment" in args:
            return deepcopy(deployment)
        if "service" in args:
            return deepcopy(prometheus)
        if "events" in args:
            return {"items": []}
        raise AssertionError(args)

    def run(args, **kwargs):
        calls.append(("run", list(args)))
        if "inspect" in args:
            return json.dumps(cri_for(pods["payment"]))
        if "stop" in args:
            return "payment123\n"
        raise AssertionError(args)

    def kubectl(*args, **kwargs):
        calls.append(("kubectl", args))
        if backend._INFO_CODE in args:
            return json.dumps(runtime)
        request = json.loads(args[-1])
        if backend._ACTIVATE_CODE in args:
            return json.dumps({"applied": True, "schema_version": 1, "trial_id": request["trial_id"],
                               "scenario": request["scenario"], "activated_at": 100., "expires_at": 160.,
                               "delay_seconds": request["delay_seconds"], "path": backend.FAULT_PATH})
        if backend._REMOVE_CODE in args:
            return json.dumps({"trial_id": request["trial_id"], "path": backend.FAULT_PATH,
                               "removed": True, "already_absent": False})
        raise AssertionError(args)

    monkeypatch.setattr(backend.lab, "kjson", kjson)
    monkeypatch.setattr(backend.lab, "run", run)
    monkeypatch.setattr(backend.lab, "kubectl", kubectl)
    instance = backend.KubernetesBackend(tmp_path / "artifacts")
    return instance, calls, pods, deployment, runtime


def active(lab):
    instance, calls, pods, deployment, runtime = lab
    instance.preflight()
    instance._started = True  # No real kubectl forwarding in unit tests.
    instance.validate_target()
    return instance


def test_preflight_only_reads_and_does_not_create_artifacts(lab):
    instance, calls, *_ = lab
    result = instance.preflight()
    assert result["backend"] == "kubernetes"
    assert not instance.artifact_dir.exists()
    assert all("stop" not in call[1] for call in calls if call[0] == "run")
    assert all(backend._INFO_CODE in call[1] for call in calls if call[0] == "kubectl")


def test_wrong_cluster_stops_before_target_access(lab, monkeypatch):
    instance, calls, *_ = lab
    def forbidden():
        raise RuntimeError("Foreign namespace")
    monkeypatch.setattr(backend.lab, "guard_cluster", forbidden)
    with pytest.raises(RuntimeError, match="Foreign"):
        instance.preflight()
    assert calls == []


@pytest.mark.parametrize("shared", ["shareProcessNamespace", "hostPID"])
def test_shared_pid_namespace_cannot_supply_container_runtime_identity(lab, shared):
    instance = lab[0]
    lab[2]["payment"]["spec"][shared] = True
    with pytest.raises(RuntimeError, match="isolated container PID namespace"):
        instance.preflight()
    assert not any(c[0] == "kubectl" for c in lab[1])


def test_target_refresh_refuses_pod_replacement_since_run_preflight(lab):
    instance = lab[0]
    instance.preflight()
    lab[2]["payment"]["metadata"]["uid"] = "replacement"
    with pytest.raises(RuntimeError, match="changed since run preflight"):
        instance.validate_target()


@pytest.mark.parametrize("invalid", ["opt_in", "runtime_opt_in", "source", "lease", "path"])
def test_preflight_rejects_wrong_runtime_or_existing_lease(lab, invalid):
    instance, calls, pods, deployment, runtime = lab
    if invalid == "opt_in":
        deployment["spec"]["template"]["spec"]["containers"][0]["env"] = []
    elif invalid == "runtime_opt_in":
        runtime["enabled"] = False
    elif invalid == "source":
        runtime["source_sha256"]["services/app.py"] = "undeployed"
    elif invalid == "lease":
        runtime["lease"] = {"trial_id": "someone_else"}
    else:
        runtime["path"] = "/tmp/unrelated.json"
    with pytest.raises(RuntimeError):
        instance.preflight()
    assert instance._preflight is None
    assert not instance.artifact_dir.exists()


@pytest.mark.parametrize("field", ["uid", "containerID", "restartCount"])
def test_identity_change_after_validation_cannot_retarget(lab, field):
    instance = active(lab)
    pods = lab[2]
    if field == "uid":
        pods["payment"]["metadata"][field] = "replacement"
    else:
        pods["payment"]["status"]["containerStatuses"][0][field] = 2 if field == "restartCount" else "containerd://new"
    before = len(lab[1])
    with pytest.raises(RuntimeError, match="identity changed"):
        instance.inject("process_crash", "trial-one", 60)
    assert not any(c[0] == "run" and "stop" in c[1] for c in lab[1][before:])
    assert instance._trial is None


def test_crash_is_one_immutable_cri_stop_and_cleanup_never_restarts(lab):
    instance = active(lab)
    result = instance.inject("process_crash", "trial-one", 60)
    stops = [c[1] for c in lab[1] if c[0] == "run" and "stop" in c[1]]
    assert stops == [["docker", "exec", "safeheal-dev-control-plane", "crictl", "--timeout=30s",
                      "stop", "--timeout", "0", "payment123"]]
    assert result["expected_recovery"] == "kubernetes_native"
    count = len(lab[1])
    cleanup = instance.cleanup("trial-one", "process_crash")
    assert cleanup["mutation"] is False
    assert all(c[0] != "run" for c in lab[1][count:])
    assert instance._trial is None


def test_ambiguous_crash_timeout_is_not_retried(lab, monkeypatch):
    instance = active(lab)
    real = backend.lab.run
    attempted = []
    def timeout(args, **kwargs):
        if "stop" in args:
            attempted.append(args)
            raise subprocess.TimeoutExpired(args, 45)
        return real(args, **kwargs)
    monkeypatch.setattr(backend.lab, "run", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        instance.inject("process_crash", "trial-one", 60)
    assert len(attempted) == 1
    assert instance._trial["mutation_attempted"] is True
    instance.cleanup("trial-one", "process_crash")
    assert len(attempted) == 1


@pytest.mark.parametrize("scenario", ["http_5xx", "latency"])
def test_application_fault_includes_target_runtime_guard_and_attribution(lab, scenario):
    instance = active(lab)
    result = instance.inject(scenario, "trial-one", 60, 1.25)
    commands = [c[1] for c in lab[1] if c[0] == "kubectl" and backend._ACTIVATE_CODE in c[1]]
    assert len(commands) == 1
    request = json.loads(commands[0][-1])
    assert request["runtime_identity"] == lab[4]["runtime_identity"]
    assert request["duration_seconds"] == 60
    assert result["expected_recovery"] == "application_fault_expiry_or_harness_cleanup"
    with pytest.raises(RuntimeError, match="active trial"):
        instance.cleanup("other-trial", scenario)
    assert instance.cleanup("trial-one", scenario)["removed"] is True


def test_cleanup_refuses_replacement_but_works_when_only_unready(lab):
    instance = active(lab)
    instance.inject("http_5xx", "trial-one", 60)
    status = lab[2]["payment"]["status"]["containerStatuses"][0]
    status["ready"] = False
    assert instance.cleanup("trial-one", "http_5xx")["removed"] is True
    status["ready"] = True
    instance.validate_target()
    instance.inject("latency", "trial-two", 60)
    lab[2]["payment"]["metadata"]["uid"] = "replacement"
    before = len(lab[1])
    with pytest.raises(RuntimeError, match="identity changed"):
        instance.cleanup("trial-two", "latency")
    assert not any(c[0] == "kubectl" and backend._REMOVE_CODE in c[1] for c in lab[1][before:])
    assert instance._trial["trial_id"] == "trial-two"


@pytest.mark.parametrize("duration,delay", [(float("nan"), 1.25), (121, 1.25), (True, 1.25),
                                           (60, float("inf")), (60, 1.51), (0, 1.25)])
def test_invalid_fault_bounds_do_not_access_cluster(lab, duration, delay):
    instance, calls, *_ = lab
    with pytest.raises(RuntimeError, match="Invalid fault"):
        instance.inject("latency", "trial-one", duration, delay)
    assert calls == []


def test_active_trial_blocks_another_injection_and_target_refresh(lab):
    instance = active(lab)
    instance.inject("http_5xx", "trial-one", 60)
    with pytest.raises(RuntimeError):
        instance.inject("latency", "trial-two", 60)
    with pytest.raises(RuntimeError):
        instance.validate_target()


def test_busy_telemetry_port_starts_no_forward_and_never_takes_listener(lab, monkeypatch):
    instance = lab[0]
    instance.preflight()
    def busy(port=0):
        assert port == 19090
        raise RuntimeError("busy")
    monkeypatch.setattr(backend, "_free_port", busy)
    def forbidden(*args, **kwargs):
        pytest.fail("No process may start or be killed for a busy unowned port")
    monkeypatch.setattr(backend.subprocess, "Popen", forbidden)
    with pytest.raises(RuntimeError, match="busy"):
        instance.start()
    assert instance._forwards == []


def test_start_failure_closes_only_already_owned_forward(lab, monkeypatch):
    instance = lab[0]
    instance.preflight()
    monkeypatch.setattr(backend, "_free_port", lambda port=0: port or 31000)
    signals = []
    class Process:
        def poll(self): return None
        def terminate(self): signals.append("terminate-owned")
        def wait(self, timeout): return 0
    def forward(name, *args):
        if name == "gateway":
            handle = (instance.artifact_dir / "owned.txt").open("w")
            instance._forwards.append({"process": Process(), "log": handle, "name": name})
            return "http://127.0.0.1:31000"
        raise RuntimeError("payment forwarding failed")
    monkeypatch.setattr(instance, "_forward", forward)
    with pytest.raises(RuntimeError, match="payment forwarding"):
        instance.start()
    assert signals == ["terminate-owned"]
    assert instance._forwards == []


@pytest.mark.parametrize("code,method", [(backend._ACTIVATE_CODE, "activate"), (backend._REMOVE_CODE, "remove")],
                         ids=["activation", "cleanup"])
@pytest.mark.parametrize("matching", [False, True], ids=["replacement-refused", "same-runtime-allowed"])
def test_runtime_guard_before_file_mutation(code, method, matching, monkeypatch, capsys):
    from services import benchmark_faults
    original_stat, original_read = os.stat, Path.read_text
    monkeypatch.setattr(os, "stat", lambda p, *a, **k: SimpleNamespace(st_ino=456)
                        if str(p) == "/proc/self/ns/pid" else original_stat(p, *a, **k))
    process_stat = "1 (uvicorn process) " + " ".join(["S"] + ["0"] * 18 + ["123"] + ["0"] * 5)
    # The snippet executes in a Linux container even when pytest runs on
    # Windows. Normalize only this fixture's host Path and return a POSIX
    # control path; do not weaken the production Linux-path identity checks.
    monkeypatch.setattr(Path, "read_text", lambda p, *a, **k: process_stat
                        if p.as_posix() == "/proc/1/stat" else original_read(p, *a, **k))
    monkeypatch.setattr(benchmark_faults, "configured_path", lambda: PurePosixPath(backend.FAULT_PATH))
    invoked = []
    def helper(**kwargs):
        invoked.append(kwargs)
        return {"ok": True}
    monkeypatch.setattr(benchmark_faults, method, helper)
    identity = {"pid_namespace_inode": 456, "pid1_start_ticks": "123"} if matching else {"wrong": True}
    monkeypatch.setattr(sys, "argv", ["-c", json.dumps({"runtime_identity": identity, "trial_id": "trial-one"})])
    if matching:
        exec(code, {})
        assert invoked == [{"trial_id": "trial-one"}]
        assert json.loads(capsys.readouterr().out) == {"ok": True}
    else:
        with pytest.raises(RuntimeError, match="runtime changed"):
            exec(code, {})
        assert invoked == []


def test_final_check_retains_service_dns_and_rejects_upstream_restart(lab):
    instance = lab[0]
    instance.preflight()
    final = instance.final_check("trial-one")
    assert final["check"]["request_id"] == "trial-one-final"
    lab[2]["order"]["status"]["containerStatuses"][0]["restartCount"] = 1
    with pytest.raises(RuntimeError, match="identity changed"):
        instance.final_check("trial-two")
