"""Guarded backend for benchmark trials in the existing, isolated kind lab.

The runner owns the shared ``lab.recovery_lock()`` for the entire experiment.
This backend never deploys, deletes Pods, restarts Deployments, or changes a
context. Fault injection is explicit; preflight is read-only. All forwarding
processes are owned by this instance and bind only to loopback.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import socket
import subprocess
import time
import urllib.request

import k8s as lab


SCENARIOS = frozenset({"process_crash", "http_5xx", "latency"})
FAULT_PATH = "/tmp/safeheal-benchmark-fault.json"
FAULT_VERSION = "day5-v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
_IDENTITY_FIELDS = ("pod", "uid", "node", "container", "container_id", "restart_count")
_RUNTIME = (
    "{'pid_namespace_inode':os.stat('/proc/self/ns/pid').st_ino,"
    "'pid1_start_ticks':Path('/proc/1/stat').read_text().rsplit(')',1)[1].split()[19]}"
)
_INFO_CODE = "\n".join([
    "import hashlib,json,os,time",
    "from pathlib import Path",
    "import services.app as app",
    "import services.benchmark_faults as faults",
    "path=faults.configured_path()",
    "lease=None",
    "if path.exists() or path.is_symlink():",
    "    lease=faults._read(path)[0]",
    "print(json.dumps({'version':faults.VERSION,'enabled':faults.enabled(),",
    "'path':str(path),'runtime_identity':" + _RUNTIME + ",",
    "'source_sha256':{name:hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()",
    " for name,module in [('services/app.py',app),('services/benchmark_faults.py',faults)]},",
    "'lease':lease,'target_epoch':time.time()},allow_nan=False))",
])
_ACTIVATE_CODE = "\n".join([
    "import json,os,sys",
    "from pathlib import Path",
    "from services import benchmark_faults as faults",
    "request=json.loads(sys.argv[1])",
    "if " + _RUNTIME + " != request.pop('runtime_identity'):",
    "    raise RuntimeError('Payment runtime changed before activation')",
    "if str(faults.configured_path()) != '" + FAULT_PATH + "':",
    "    raise RuntimeError('Unexpected fault control path')",
    "print(json.dumps(faults.activate(**request),allow_nan=False))",
])
_REMOVE_CODE = "\n".join([
    "import json,os,sys",
    "from pathlib import Path",
    "from services import benchmark_faults as faults",
    "request=json.loads(sys.argv[1])",
    "if " + _RUNTIME + " != request.pop('runtime_identity'):",
    "    raise RuntimeError('Payment runtime changed before cleanup')",
    "if str(faults.configured_path()) != '" + FAULT_PATH + "':",
    "    raise RuntimeError('Unexpected fault control path')",
    "print(json.dumps(faults.remove(**request),allow_nan=False))",
])


def _same_identity(current, expected):
    lab.require(all(current.get(k) == expected.get(k) for k in _IDENTITY_FIELDS),
                "Target identity changed; refusing to retarget the fault")


def _scope(pod, role):
    state = lab.pod_state(pod)
    labels = pod.get("metadata", {}).get("labels", {})
    lab.require(pod.get("metadata", {}).get("namespace") == lab.NAMESPACE and
                state["node"] == lab.NODE and state["container"] == role and
                labels.get("app.kubernetes.io/name") == role and
                labels.get("app.kubernetes.io/part-of") == "safeheal-ai" and
                not pod["metadata"].get("deletionTimestamp"),
                f"Foreign, terminating, or unexpected {role} Pod")
    return state


def _free_port(port=0):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(
                f"Loopback port {port} is busy. Stop its known owner before the benchmark; "
                "the runner will not reuse or terminate an unrelated listener."
            ) from exc
        return sock.getsockname()[1]


class KubernetesBackend:
    kind = "kubernetes"

    def __init__(self, artifact_dir):
        self.artifact_dir = Path(artifact_dir)
        self.gateway_url = self.payment_url = self.prometheus_url = None
        self._preflight = None
        self._validated_target = None
        self._trial = None
        self._forwards = []
        self._started = False

    def snapshot(self):
        """Read identities and readiness; unready is an observation, not an error."""
        return {role: _scope(lab.pod_for(role), role) for role in lab.ROLES}

    def _payment(self, expected=None, require_ready=True):
        pod = lab.pod_for("payment")
        state = _scope(pod, "payment")
        lab.require(pod["spec"].get("shareProcessNamespace", False) is False and
                    pod["spec"].get("hostPID", False) is False,
                    "Payment requires an isolated container PID namespace for runtime identity checks")
        if expected is not None:
            _same_identity(state, expected)
        container = state.get("container_id") or ""
        lab.require(container.startswith("containerd://") and len(container) > 13,
                    "Expected an identified containerd payment container")
        cri = json.loads(lab.run(["docker", "exec", lab.NODE, "crictl", "--timeout=30s",
                                 "inspect", container.removeprefix("containerd://")], timeout=40))
        if require_ready:
            lab.guard_target(pod, cri)
        else:
            # Cleanup must remain possible while readiness is temporarily false.
            # Retain CRI ownership/running checks explicitly; readiness is not
            # permission to remove a lease that this same trial created.
            status = cri["status"]
            expected_labels = {
                "io.kubernetes.pod.namespace": lab.NAMESPACE,
                "io.kubernetes.pod.uid": state["uid"],
                "io.kubernetes.pod.name": state["pod"],
                "io.kubernetes.container.name": "payment",
            }
            lab.require(pod["spec"].get("restartPolicy") == "Always" and
                        state["container_id"] == "containerd://" + status["id"] and
                        status["state"] == "CONTAINER_RUNNING" and
                        all(status.get("labels", {}).get(k) == v for k, v in expected_labels.items()),
                        "Cleanup CRI identity or running-state mismatch")
        return state, cri

    def _exec(self, target, code, request=None):
        args = ["-n", lab.NAMESPACE, "exec", target["pod"], "-c", "payment", "--",
                "python", "-c", code]
        if request is not None:
            args.append(json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False))
        return json.loads(lab.kubectl(*args, timeout=40))

    def preflight(self):
        """Verify the existing cluster, deployed source, and explicit test opt-in."""
        lab.require(not self._started and self._trial is None, "Backend is already active")
        lab.guard_cluster()
        baseline = self.snapshot()
        lab.require(all(s["ready"] for s in baseline.values()), "Application baseline is not ready")
        deployment = lab.kjson("-n", lab.NAMESPACE, "get", "deployment", "payment")
        labels = deployment.get("metadata", {}).get("labels", {})
        lab.require(deployment.get("metadata", {}).get("namespace") == lab.NAMESPACE and
                    labels.get("app.kubernetes.io/name") == "payment" and
                    labels.get("app.kubernetes.io/part-of") == "safeheal-ai" and
                    deployment["spec"].get("replicas") == 1,
                    "Expected the single owned payment Deployment")
        containers = deployment["spec"]["template"]["spec"]["containers"]
        lab.require(len(containers) == 1 and containers[0]["name"] == "payment",
                    "Unexpected payment Deployment containers")
        enabled = [v for v in containers[0].get("env", []) if v["name"] == "SAFEHEAL_FAULTS_ENABLED"]
        lab.require(len(enabled) == 1 and enabled[0].get("value") == "local-test" and
                    "valueFrom" not in enabled[0],
                    "Deploy the explicit local-test fault opt-in before benchmarking")
        prometheus = lab.kjson("-n", lab.NAMESPACE, "get", "service", "prometheus")
        lab.guard_labels(prometheus, "Prometheus Service")
        lab.require(prometheus["metadata"].get("namespace") == lab.NAMESPACE and
                    prometheus["spec"].get("selector", {}).get("app.kubernetes.io/name") == "prometheus" and
                    prometheus["spec"].get("selector", {}).get("app.kubernetes.io/part-of") == "safeheal-ai",
                    "Unexpected Prometheus Service target")
        target, _ = self._payment(expected=baseline["payment"])
        runtime = self._exec(target, _INFO_CODE)
        source = {name: hashlib.sha256((lab.ROOT / name).read_bytes()).hexdigest()
                  for name in ("services/app.py", "services/benchmark_faults.py")}
        lab.require(runtime.get("enabled") is True and runtime.get("version") == FAULT_VERSION and
                    runtime.get("path") == FAULT_PATH,
                    "Payment image does not have the expected local-test fault controls")
        lab.require(runtime.get("source_sha256") == source,
                    "Deployed payment source differs from this checkout; deploy the tested image first")
        lab.require(runtime.get("lease") is None,
                    "An existing fault lease must be resolved by its owner before benchmarking")
        _same_identity(_scope(lab.pod_for("payment"), "payment"), target)
        provenance = lab.provenance()
        provenance["benchmark_runtime_sha256"] = source
        self._preflight = {
            "backend": self.kind, "at": lab.utc(), "context": lab.CONTEXT,
            "namespace": lab.NAMESPACE, "baseline": baseline,
            "runtime": runtime, "source": provenance,
            "workload_route": "owned gateway Pod loopback port-forward; final checks use Service DNS",
        }
        return deepcopy(self._preflight)

    def validate_target(self):
        """Capture a new trial target; inject revalidates this exact identity."""
        lab.require(self._preflight is not None and self._trial is None,
                    "Preflight and previous-trial cleanup are required")
        lab.guard_cluster()
        target, _ = self._payment()
        lab.require(target["uid"] == self._preflight["baseline"]["payment"]["uid"],
                    "Payment Pod changed since run preflight; refusing a new trial target")
        runtime = self._exec(target, _INFO_CODE)
        lab.require(runtime.get("enabled") is True and runtime.get("version") == FAULT_VERSION and
                    runtime.get("path") == FAULT_PATH and runtime.get("lease") is None and
                    runtime.get("source_sha256") == self._preflight["runtime"]["source_sha256"],
                    "Payment controls changed or an existing lease is present")
        _same_identity(_scope(lab.pod_for("payment"), "payment"), target)
        target["runtime_identity"] = runtime["runtime_identity"]
        self._validated_target = target
        return deepcopy(target)

    def _forward(self, name, resource, port, remote_port, expected_service=None):
        log_path = self.artifact_dir / f"port-forward-{name}.txt"
        log = log_path.open("x", encoding="utf-8")
        command = ["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
                   "-n", lab.NAMESPACE, "port-forward", "--pod-running-timeout=20s",
                   "--address=127.0.0.1", resource, f"{port}:{remote_port}"]
        try:
            process = subprocess.Popen(command, cwd=lab.ROOT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT,
                                       text=True, encoding="utf-8")
        except BaseException:
            log.close()
            raise
        self._forwards.append({"process": process, "log": log, "path": log_path,
                               "name": name, "command": command})
        deadline = time.monotonic() + 25
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        health = "/healthz" if expected_service else "/-/ready"
        marker = f"Forwarding from 127.0.0.1:{port} -> {remote_port}"
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Owned {name} port-forward exited; see {log_path.name}")
            if marker in log_path.read_text(encoding="utf-8", errors="replace"):
                try:
                    with opener.open(f"http://127.0.0.1:{port}{health}", timeout=1) as response:
                        body = response.read(4097)
                        lab.require(response.status == 200 and len(body) <= 4096,
                                    "Unexpected forwarded health response")
                        if expected_service:
                            lab.require(json.loads(body) == {"status": "ok", "service": expected_service},
                                        "Forwarded endpoint has the wrong service identity")
                    return f"http://127.0.0.1:{port}"
                except (OSError, ValueError):
                    pass
            time.sleep(.1)
        raise RuntimeError(f"Owned {name} port-forward was not ready within 25 seconds")

    def start(self):
        """Start only the three forwarding processes owned by this experiment."""
        lab.require(self._preflight is not None and not self._started and not self._forwards,
                    "Run preflight once before starting the backend")
        lab.guard_cluster()
        current = self.snapshot()
        for role, before in self._preflight["baseline"].items():
            lab.require(current[role]["uid"] == before["uid"] and current[role]["ready"],
                        "Application Pod changed or became unready before forwarding")
        # Check the fixed allowlisted telemetry port before starting any process.
        _free_port(19090)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.gateway_url = self._forward("gateway", "pod/" + current["gateway"]["pod"],
                                             _free_port(), 8000, "gateway")
            self.payment_url = self._forward("payment", "pod/" + current["payment"]["pod"],
                                             _free_port(), 8000, "payment")
            self.prometheus_url = self._forward("prometheus", "service/prometheus", 19090, 9090)
            self._started = True
        except BaseException:
            self.close()
            raise
        return {"gateway_url": self.gateway_url, "payment_url": self.payment_url,
                "prometheus_url": self.prometheus_url,
                "forwards": [{"name": f["name"], "pid": f["process"].pid,
                              "log": f["path"].name} for f in self._forwards]}

    def inject(self, scenario, trial_id, duration_seconds, delay_seconds=1.25):
        lab.require(scenario in SCENARIOS and isinstance(trial_id, str) and _ID.fullmatch(trial_id),
                    "Unknown fault scenario or invalid trial ID")
        for value, upper, name in ((duration_seconds, 120, "duration"), (delay_seconds, 1.5, "delay")):
            lab.require(isinstance(value, (int, float)) and not isinstance(value, bool) and
                        math.isfinite(value) and 0 < value <= upper, f"Invalid fault {name}")
        lab.require(self._started and self._validated_target is not None and self._trial is None,
                    "A started backend and an identity-checked trial baseline are required")
        lab.guard_cluster()
        target, cri = self._payment(expected=self._validated_target)
        target["runtime_identity"] = self._validated_target["runtime_identity"]
        self._trial = {"trial_id": trial_id, "scenario": scenario, "target": deepcopy(target),
                       "requested_at": lab.utc(), "mutation_attempted": True}
        if scenario == "process_crash":
            container_id = cri["status"]["id"]
            command = ["docker", "exec", lab.NODE, "crictl", "--timeout=30s",
                       "stop", "--timeout", "0", container_id]
            self._trial["command"] = command
            # One immutable container ID, one request. An ambiguous RPC result
            # is retained by the runner and is never retried against a new ID.
            output = lab.run(command, timeout=45).strip()
            ack = {"applied": True, "trial_id": trial_id, "scenario": scenario,
                   "stop_output": output, "command": command,
                   "mechanism": "single_container_cri_stop", "expected_recovery": "kubernetes_native"}
        else:
            request = {"trial_id": trial_id, "scenario": scenario,
                       "duration_seconds": duration_seconds, "delay_seconds": delay_seconds,
                       "runtime_identity": target["runtime_identity"]}
            ack = self._exec(target, _ACTIVATE_CODE, request)
            lab.require(ack.get("trial_id") == trial_id and ack.get("scenario") == scenario and
                        ack.get("applied") is True and ack.get("path") == FAULT_PATH,
                        "Fault helper returned an unexpected acknowledgement")
            ack["mechanism"] = "target_local_expiring_application_lease"
            ack["expected_recovery"] = "application_fault_expiry_or_harness_cleanup"
        ack["target"] = deepcopy(target)
        ack["requested_at"] = self._trial["requested_at"]
        ack["acknowledged_at"] = lab.utc()
        return ack

    def cleanup(self, trial_id, scenario):
        """Remove only this trial's lease; a crash has no mutation to undo."""
        if self._trial is None:
            return {"trial_id": trial_id, "scenario": scenario, "not_injected": True,
                    "mutation": False, "at": lab.utc()}
        lab.require(self._trial["trial_id"] == trial_id and self._trial["scenario"] == scenario,
                    "Cleanup does not belong to the active trial")
        target = self._trial["target"]
        lab.guard_cluster()
        if scenario == "process_crash":
            current = _scope(lab.pod_for("payment"), "payment")
            result = {"trial_id": trial_id, "scenario": scenario, "mutation": False,
                      "mechanism": "no_crash_undo_native_recovery_observed_separately",
                      "payment": current, "at": lab.utc()}
        else:
            current, _ = self._payment(expected=target, require_ready=False)
            result = self._exec(current, _REMOVE_CODE,
                                {"trial_id": trial_id, "runtime_identity": target["runtime_identity"]})
            lab.require(result.get("trial_id") == trial_id and result.get("path") == FAULT_PATH and
                        isinstance(result.get("removed"), bool), "Invalid cleanup acknowledgement")
            result.update({"scenario": scenario, "mutation": result["removed"], "at": lab.utc()})
        self._trial = None
        self._validated_target = None
        return result

    def final_check(self, trial_id):
        lab.guard_cluster()
        checks = lab.check_services(trial_id + "-final")
        current = self.snapshot()
        lab.require(all(state["ready"] for state in current.values()), "Final application state is not ready")
        lab.require(current["payment"]["uid"] == self._preflight["baseline"]["payment"]["uid"],
                    "Payment Pod was replaced; native container recovery cannot be attributed")
        for role in ("gateway", "order"):
            _same_identity(current[role], self._preflight["baseline"][role])
        result = {"at": lab.utc(), "check": checks, "pods": current}
        try:
            events = lab.kjson("-n", lab.NAMESPACE, "get", "events", "--field-selector",
                               "involvedObject.name=" + current["payment"]["pod"])["items"]
            result["payment_events"] = events[-100:]
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
            result["event_collection_error"] = str(exc)
        return result

    def close(self):
        """Terminate only owned forwards. Never signal a discovered PID/listener."""
        errors = []
        for forward in reversed(self._forwards):
            process = forward["process"]
            try:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(f"{forward['name']}: {exc}")
            finally:
                forward["log"].close()
        self._forwards.clear()
        self._started = False
        if errors:
            raise RuntimeError("Owned forward cleanup failed: " + "; ".join(errors))
