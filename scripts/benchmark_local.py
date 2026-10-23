"""Real loopback services + Prometheus; explicitly NOT Kubernetes recovery evidence.

Only subprocesses created by this instance can be stopped. The local supervisor
restarts payment after an observed exit; its behavior is reported separately.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROMETHEUS = ROOT / ".tools/prometheus-3.15.0/prometheus"
ROLES = ("payment", "order", "gateway")


def utc():
    return datetime.now(timezone.utc).isoformat()


def unused_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class LocalProcessBackend:
    kind = "local-process"

    def __init__(self, artifact_dir):
        self.artifact_dir = Path(artifact_dir)
        self.runtime = ROOT / ".local/benchmarks" / self.artifact_dir.name
        self.processes = {}
        self.logs = []
        self.ports = {}
        self.restart_counts = {role: 0 for role in ROLES}
        self.identities = {role: f"local-{role}-{uuid4().hex}" for role in ROLES}
        self.terminations = {}
        self.supervisor_events = []
        self.supervisor_errors = []
        self._stop = threading.Event()
        self._mutex = threading.RLock()
        self._supervisor = None
        self._target = None
        self.prometheus_url = "http://127.0.0.1:19090"

    def preflight(self):
        if not PROMETHEUS.is_file():
            raise RuntimeError("Run python scripts/install_benchmark_prometheus.py for the optional local backend.")
        digest_file = PROMETHEUS.with_suffix(".sha256")
        digest = hashlib.sha256(PROMETHEUS.read_bytes()).hexdigest()
        if not digest_file.is_file() or digest_file.read_text().strip() != digest:
            raise RuntimeError("Local Prometheus binary does not match its verified installation digest")
        version = subprocess.run([str(PROMETHEUS), "--version"], capture_output=True,
                                 text=True, check=True, timeout=10).stdout.strip()
        if "version 3.15.0" not in version:
            raise RuntimeError("Expected Prometheus 3.15.0")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 19090))
        return {"backend": self.kind, "kubernetes": False, "platform": platform.platform(),
                "python": sys.version, "prometheus_version": version,
                "prometheus_binary_sha256": digest,
                "recovery_policy": "owned payment subprocess supervisor; 0.5 second fixed restart delay",
                "trace_sampler": "parentbased_traceidratio", "trace_sample_ratio": "0.01",
                "limitations": "Real HTTP, process exits and Prometheus; no kubelet, probes, DNS or container recovery measurement."}

    def _launch(self, role):
        env = os.environ.copy()
        for name in list(env):
            if name.startswith("UVICORN_") or name == "WEB_CONCURRENCY":
                env.pop(name)
        env.update(SERVICE_ROLE=role, PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
                   OTEL_TRACES_SAMPLER="parentbased_traceidratio", OTEL_TRACES_SAMPLER_ARG="0.01")
        env.pop("DOWNSTREAM_URL", None)
        env.pop("SAFEHEAL_FAULTS_ENABLED", None)
        env.pop("SAFEHEAL_FAULT_FILE", None)
        if role == "payment":
            env.update(SAFEHEAL_FAULTS_ENABLED="local-test", SAFEHEAL_FAULT_FILE=str(self.fault_file))
        else:
            dependency = "payment" if role == "order" else "order"
            env["DOWNSTREAM_URL"] = f"http://127.0.0.1:{self.ports[dependency]}"
        log = (self.runtime / f"{role}-{self.restart_counts[role]}.log").open("ab")
        self.logs.append(log)
        command = [sys.executable, "-m", "uvicorn", "services.app:from_env", "--factory",
                   "--host", "127.0.0.1", "--port", str(self.ports[role]), "--workers", "1", "--no-access-log"]
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)
        self.processes[role] = process
        return process

    def _supervise(self):
        while not self._stop.wait(.1):
            with self._mutex:
                process = self.processes.get("payment")
                if process is None or process.poll() is None:
                    continue
                dead_pid, code = process.pid, process.returncode
            observed = utc()
            if self._stop.wait(.5):
                return
            with self._mutex:
                if self._stop.is_set():
                    return
                self.terminations["payment"] = {"pid": dead_pid, "exit_code": code, "observed_at": observed}
                if self.restart_counts["payment"] >= 20:
                    self.supervisor_errors.append("Local supervisor restart limit reached")
                    return
                self.restart_counts["payment"] += 1
                try:
                    replacement = self._launch("payment")
                    self.supervisor_events.append({"exit_observed_at": observed, "old_pid": dead_pid,
                                                   "exit_code": code, "restart_requested_at": utc(),
                                                   "new_pid": replacement.pid})
                except Exception as exc:
                    self.supervisor_errors.append(str(exc))
                    return

    def start(self):
        self.runtime.mkdir(parents=True, exist_ok=False)
        self.fault_file = self.runtime / "payment-fault.json"
        for role in ROLES:
            self.ports[role] = unused_port()
        if len(set(self.ports.values())) != 3:
            raise RuntimeError("Port reservation raced; retry with a fresh run")
        self.gateway_url = f"http://127.0.0.1:{self.ports['gateway']}"
        self.payment_url = f"http://127.0.0.1:{self.ports['payment']}"
        try:
            for role in ROLES:
                self._launch(role)
            self._supervisor = threading.Thread(target=self._supervise, name="safeheal-payment-supervisor", daemon=True)
            self._supervisor.start()
            self._wait_healthy()
            config = {"global": {"scrape_interval": "5s", "scrape_timeout": "2s"},
                      "scrape_configs": [{"job_name": "safeheal", "static_configs": [
                          {"targets": [f"127.0.0.1:{self.ports[role]}"],
                           "labels": {"instance": f"{role}:8000"}} for role in ROLES]}]}
            config_file = self.artifact_dir / "prometheus-local.json"
            config_file.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            log = (self.runtime / "prometheus.log").open("ab")
            self.logs.append(log)
            self.prometheus_process = subprocess.Popen([
                str(PROMETHEUS), f"--config.file={config_file}", "--web.listen-address=127.0.0.1:19090",
                f"--storage.tsdb.path={self.runtime / 'tsdb'}", "--storage.tsdb.retention.time=1h",
                "--storage.tsdb.retention.size=64MB"], cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 30
            with httpx.Client(timeout=1, trust_env=False) as client:
                while time.monotonic() < deadline:
                    if self.prometheus_process.poll() is not None:
                        raise RuntimeError("Local Prometheus exited; see runtime log")
                    try:
                        if client.get(self.prometheus_url + "/-/ready").status_code == 200:
                            return
                    except httpx.HTTPError:
                        pass
                    time.sleep(.2)
            raise RuntimeError("Local Prometheus did not become ready")
        except BaseException:
            self.close()
            raise

    def _wait_healthy(self):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if all(value["ready"] for value in self.snapshot().values()):
                return
            time.sleep(.2)
        raise RuntimeError("Local services did not become healthy")

    def snapshot(self):
        if self.supervisor_errors:
            raise RuntimeError("Payment supervisor failed: " + self.supervisor_errors[-1])
        output = {}
        with httpx.Client(timeout=1, trust_env=False) as client:
            for role in ROLES:
                with self._mutex:
                    process = self.processes.get(role)
                    pid = process.pid if process else None
                    exited = process is None or process.poll() is not None
                    count = self.restart_counts[role]
                healthy = False
                if not exited:
                    try:
                        healthy = client.get(f"http://127.0.0.1:{self.ports[role]}/readyz").status_code == 200
                    except httpx.HTTPError:
                        pass
                with self._mutex:
                    if self.processes.get(role) is not process or self.restart_counts[role] != count:
                        healthy = False  # HTTP may have reached a newer process on the same port.
                output[role] = {"uid": self.identities[role], "container_id": f"pid:{pid}",
                                "restart_count": count, "ready": healthy, "pid": pid,
                                "last_state": self.terminations.get(role), "kubernetes": False}
        return output

    def validate_target(self):
        current = self.snapshot()
        if not all(s["ready"] for s in current.values()):
            raise RuntimeError("All local services must be healthy before injection")
        self._target = current["payment"]
        return self._target

    def inject(self, scenario, trial_id, duration_seconds, delay_seconds=1.25):
        if self._target is None:
            raise RuntimeError("validate_target must run before injection")
        with self._mutex:
            target = self.processes["payment"]
            if target.pid != self._target["pid"] or target.poll() is not None:
                raise RuntimeError("Local payment identity changed before injection")
            if scenario == "process_crash":
                target.kill()
                code = target.wait(timeout=5)
                return {"injection_verified": True, "pid": target.pid, "exit_code": code,
                        "acknowledged_at": utc(), "mechanism": "owned_subprocess_kill",
                        "kubernetes": False}
            if scenario not in {"http_5xx", "latency"}:
                raise ValueError("Unknown fault scenario")
            env = os.environ.copy()
            env["SAFEHEAL_FAULTS_ENABLED"] = "local-test"
            command = [sys.executable, "-c",
                       "import json,sys; from services.benchmark_faults import activate; "
                       "print(json.dumps(activate(sys.argv[1],sys.argv[2],float(sys.argv[3]),"
                       "float(sys.argv[4]),path=sys.argv[5])))",
                       trial_id, scenario, str(duration_seconds), str(delay_seconds), str(self.fault_file)]
            result = json.loads(subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                               text=True, check=True, timeout=10).stdout)
            return {"injection_verified": True, "acknowledged_at": utc(), "lease": result}

    def cleanup(self, trial_id, scenario):
        from services.benchmark_faults import remove
        if scenario == "process_crash":
            return {"verified": True, "action": "none; local supervisor owns restart", "kubernetes": False}
        return {"verified": True, "lease_cleanup": remove(trial_id, path=self.fault_file)}

    def final_check(self, trial_id):
        snapshot = self.snapshot()
        if not all(s["ready"] for s in snapshot.values()):
            raise RuntimeError("Local service readiness did not recover")
        with httpx.Client(timeout=4, trust_env=False) as client:
            for role in ROLES:
                for route in ("/healthz", "/readyz"):
                    response = client.get(f"http://127.0.0.1:{self.ports[role]}{route}")
                    response.raise_for_status()
            response = client.post(self.gateway_url + "/orders", json={"item_id": "benchmark", "quantity": 2},
                                   headers={"x-request-id": f"{trial_id}-final"})
            response.raise_for_status()
            body = response.json()
            if response.status_code != 201 or body.get("status") != "confirmed" or body.get("amount_cents") != 2000:
                raise RuntimeError("Final local order failed semantic checks")
        return {"at": utc(), "snapshot": snapshot, "order_status": response.status_code,
                "supervisor_events": list(self.supervisor_events), "kubernetes": False}

    def close(self):
        self._stop.set()
        if self._supervisor:
            self._supervisor.join(timeout=3)
        owned = list(self.processes.values())
        if hasattr(self, "prometheus_process"):
            owned.append(self.prometheus_process)
        for process in owned:
            if process.poll() is None:
                process.terminate()
        for process in owned:
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for log in self.logs:
            log.close()
