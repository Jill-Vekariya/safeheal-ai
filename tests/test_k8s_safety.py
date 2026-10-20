"""Scope checks for the real local recovery entry point; no cluster required."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("safeheal_k8s", Path(__file__).parents[1] / "scripts/k8s.py")
k8s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(k8s)


def config():
    return {"contexts": [{"name": "kind-safeheal-dev", "context": {"cluster": "kind-safeheal-dev"}}],
            "clusters": [{"name": "kind-safeheal-dev", "cluster": {"server": "https://127.0.0.1:45678"}}]}


@pytest.mark.parametrize("url", ["https://production.example:6443", "http://127.0.0.1:6443",
                                 "https://127.0.0.1.evil.example:6443"])
def test_remote_or_insecure_api_is_rejected(url):
    candidate = config()
    candidate["clusters"][0]["cluster"]["server"] = url
    with pytest.raises(RuntimeError):
        k8s.guard_config(candidate)


def test_context_cannot_point_to_another_cluster():
    candidate = config()
    candidate["contexts"][0]["context"]["cluster"] = "production"
    with pytest.raises(RuntimeError):
        k8s.guard_config(candidate)


def test_local_config_and_scope_labels():
    k8s.guard_config(config())
    k8s.guard_labels({"metadata": {"labels": k8s.LABELS}}, "namespace")
    with pytest.raises(RuntimeError):
        k8s.guard_labels({"metadata": {"labels": {"safeheal.ai/environment": "production"}}}, "namespace")


def target():
    pod = {"metadata": {"name": "payment-example", "namespace": "safeheal-dev", "uid": "pod-123",
                        "labels": {"app.kubernetes.io/name": "payment", "app.kubernetes.io/part-of": "safeheal-ai"}},
           "spec": {"nodeName": "safeheal-dev-control-plane", "restartPolicy": "Always"},
           "status": {"containerStatuses": [{"name": "payment", "containerID": "containerd://abc123",
                                              "restartCount": 0, "ready": True, "state": {"running": {}}}]}}
    cri = {"status": {"id": "abc123", "state": "CONTAINER_RUNNING", "labels": {
        "io.kubernetes.pod.namespace": "safeheal-dev", "io.kubernetes.pod.name": "payment-example",
        "io.kubernetes.pod.uid": "pod-123", "io.kubernetes.container.name": "payment"}}}
    return pod, cri


@pytest.mark.parametrize("mutation", ["namespace", "node", "role", "project", "not_ready", "restart_policy",
                                     "cri_id", "cri_uid", "cri_namespace", "cri_container", "cri_stopped"])
def test_fault_rejects_wrong_or_stale_target(mutation):
    pod, cri = deepcopy(target())
    if mutation == "namespace":
        pod["metadata"]["namespace"] = "production"
    elif mutation == "node":
        pod["spec"]["nodeName"] = "other-control-plane"
    elif mutation == "role":
        pod["metadata"]["labels"]["app.kubernetes.io/name"] = "gateway"
    elif mutation == "project":
        pod["metadata"]["labels"]["app.kubernetes.io/part-of"] = "other"
    elif mutation == "not_ready":
        pod["status"]["containerStatuses"][0]["ready"] = False
    elif mutation == "restart_policy":
        pod["spec"]["restartPolicy"] = "Never"
    elif mutation == "cri_id":
        cri["status"]["id"] = "different-container"
    elif mutation == "cri_uid":
        cri["status"]["labels"]["io.kubernetes.pod.uid"] = "replaced-pod"
    elif mutation == "cri_namespace":
        cri["status"]["labels"]["io.kubernetes.pod.namespace"] = "kube-system"
    elif mutation == "cri_container":
        cri["status"]["labels"]["io.kubernetes.container.name"] = "gateway"
    else:
        cri["status"]["state"] = "CONTAINER_EXITED"
    with pytest.raises(RuntimeError):
        k8s.guard_target(pod, cri)


def test_default_recovery_is_dry_run_and_never_stops(monkeypatch, capsys):
    pod, cri = target()
    calls = []
    monkeypatch.setattr(k8s, "guard_cluster", lambda: None)
    monkeypatch.setattr(k8s, "ready_snapshot", lambda: {"payment": k8s.pod_state(pod)})
    monkeypatch.setattr(k8s, "pod_for", lambda role: pod)

    def inspect_only(args, **kwargs):
        calls.append(args)
        assert args == ["docker", "exec", "safeheal-dev-control-plane", "crictl", "inspect", "abc123"]
        return json.dumps(cri)

    monkeypatch.setattr(k8s, "run", inspect_only)
    k8s.recovery()
    assert len(calls) == 1
    assert json.loads(capsys.readouterr().out)["dry_run"] is True


def test_second_fault_is_rejected_without_removing_active_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(k8s, "ROOT", tmp_path)
    with k8s.recovery_lock():
        with pytest.raises(FileExistsError):
            with k8s.recovery_lock():
                pytest.fail("A concurrent recovery must not start")
        assert (tmp_path / ".local/recovery.lock").exists()
    assert not (tmp_path / ".local/recovery.lock").exists()
