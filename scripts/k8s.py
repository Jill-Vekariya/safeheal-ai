"""Scoped local-kind lifecycle and auditable native-recovery demonstration.

Uses Python's standard library. Always supplies its own kubeconfig and context.
No delete/reset operation, global configuration edit, or automatic remediation.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CLUSTER = NAMESPACE = "safeheal-dev"
CONTEXT = "kind-safeheal-dev"
NODE = "safeheal-dev-control-plane"
ROLES = ("payment", "order", "gateway")
LABELS = {"safeheal.ai/environment": "local-test", "safeheal.ai/project": "safeheal-ai"}
KUBECONFIG = ROOT / ".local" / "kubeconfig"
KIND_VERSION = "v0.33.0"
NODE_IMAGE = "kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed"
KIND_HASHES = {
    "windows-amd64": "4b22adaa135368c5a465d56bbd8e520cbea87272a06ca00b6078e7b81515c9fc",
    "linux-amd64": "aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def recovery_lock():
    path = ROOT / ".local/recovery.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not guess whether an existing lock is stale or remove somebody else's lock.
    with path.open("x", encoding="utf-8") as handle:
        handle.write(utc() + "\n")
    try:
        yield
    finally:
        path.unlink()


def run(args, *, stdin=None, timeout=90, live=False):
    process = subprocess.run([str(a) for a in args], input=stdin, cwd=ROOT,
                             text=True, encoding="utf-8", errors="replace",
                             stdout=None if live else subprocess.PIPE,
                             stderr=None if live else subprocess.PIPE, timeout=timeout)
    if process.returncode:
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(map(str, args))}\n"
                           f"{(process.stdout or '')[-4000:]}\n{(process.stderr or '')[-4000:]}")
    return process.stdout or ""


def kind_path():
    local = ROOT / ".tools" / ("kind.exe" if sys.platform == "win32" else "kind")
    executable = str(local) if local.exists() else shutil.which("kind")
    require(executable, "Run: python scripts/k8s.py install-kind (or install pinned kind on PATH).")
    require(run([executable, "version"]).split()[1] == KIND_VERSION, f"Expected kind {KIND_VERSION}")
    return executable


def install_kind():
    machine = platform.machine().lower()
    require(machine in ("amd64", "x86_64"), "Automatic installation supports x86_64 only.")
    target = f"{platform.system().lower()}-amd64"
    require(target in KIND_HASHES, "Install kind v0.33.0 using the official instructions for your OS.")
    destination = ROOT / ".tools" / ("kind.exe" if sys.platform == "win32" else "kind")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        require(hashlib.sha256(destination.read_bytes()).hexdigest() == KIND_HASHES[target],
                "Existing local kind has an unexpected digest; refusing to overwrite it.")
    else:
        url = f"https://github.com/kubernetes-sigs/kind/releases/download/{KIND_VERSION}/kind-{target}"
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        require(hashlib.sha256(data).hexdigest() == KIND_HASHES[target], "kind checksum mismatch")
        destination.write_bytes(data)
        destination.chmod(0o755)
    print(run([destination, "version"]).strip(), flush=True)


def kubectl(*args, stdin=None, timeout=90):
    return run(["kubectl", "--kubeconfig", KUBECONFIG, "--context", CONTEXT,
                "--request-timeout=30s", *args], stdin=stdin, timeout=timeout)


def kjson(*args, timeout=90):
    return json.loads(kubectl(*args, "-o", "json", timeout=timeout))


def guard_labels(obj, label):
    require(all(obj.get("metadata", {}).get("labels", {}).get(k) == v for k, v in LABELS.items()),
            f"Refusing unlabelled or foreign {label}")


def guard_config(config):
    contexts = config.get("contexts", [])
    clusters = config.get("clusters", [])
    require(len(contexts) == 1 and contexts[0]["name"] == CONTEXT, "Unexpected context")
    require(len(clusters) == 1 and clusters[0]["name"] == CONTEXT, "Unexpected cluster")
    require(contexts[0]["context"]["cluster"] == CONTEXT, "Context points at a foreign cluster")
    url = urllib.parse.urlparse(clusters[0]["cluster"]["server"])
    require(url.scheme == "https" and url.hostname in ("127.0.0.1", "localhost", "::1"),
            "API server must be local HTTPS")


def guard_cluster(namespace=True):
    require(KUBECONFIG.is_file(), "Project kubeconfig is missing; run setup.")
    guard_config(json.loads(kubectl("config", "view", "--minify", "-o", "json")))
    nodes = run([kind_path(), "get", "nodes", "--name", CLUSTER]).split()
    require(nodes == [NODE], "Expected exactly the dedicated single kind node")
    docker_node = json.loads(run(["docker", "inspect", NODE]))[0]
    require(docker_node["Config"]["Labels"].get("io.x-k8s.kind.cluster") == CLUSTER,
            "Docker node does not belong to the designated kind cluster")
    guard_labels(kjson("get", "node", NODE), "node")
    if namespace:
        guard_labels(kjson("get", "namespace", NAMESPACE), "namespace")


def setup():
    require(run(["docker", "info", "--format", "{{.OSType}}"]).strip() == "linux",
            "Docker Desktop must be running Linux containers")
    kind = kind_path()
    KUBECONFIG.parent.mkdir(parents=True, exist_ok=True)
    clusters = run([kind, "get", "clusters"]).split()
    if CLUSTER in clusters:
        print("Checking existing named cluster before reuse", flush=True)
        run([kind, "export", "kubeconfig", "--name", CLUSTER, "--kubeconfig", KUBECONFIG])
    else:
        print(f"Creating {CLUSTER} using {NODE_IMAGE}", flush=True)
        result = run([kind, "create", "cluster", "--name", CLUSTER,
                      "--config", ROOT / "infrastructure/kind.yaml", "--image", NODE_IMAGE,
                      "--kubeconfig", KUBECONFIG, "--wait", "180s", "--retain"], timeout=900, live=True)
        print(result, flush=True)
    guard_cluster(namespace=False)
    kubectl("wait", "--for=condition=Ready", "node/" + NODE, "--timeout=180s", timeout=200)
    print(kubectl("get", "nodes", "-o", "wide"), flush=True)


def deploy():
    guard_cluster(namespace=False)
    existing = kubectl("get", "namespace", NAMESPACE, "--ignore-not-found", "-o", "json")
    if existing.strip():
        guard_labels(json.loads(existing), "namespace")
    print("Building image from this checkout", flush=True)
    run(["docker", "build", "-t", "safeheal-ai:day2-build", "."], timeout=600, live=True)
    image_id = run(["docker", "image", "inspect", "safeheal-ai:day2-build", "--format", "{{.Id}}"]).strip()
    image = "safeheal-ai:sha256-" + image_id.removeprefix("sha256:")[:16]
    run(["docker", "tag", "safeheal-ai:day2-build", image])
    print(f"Loading {image} into the dedicated node", flush=True)
    run([kind_path(), "load", "docker-image", image, "--name", CLUSTER], timeout=300, live=True)
    manifest = run(["kubectl", "kustomize", ROOT / "infrastructure/kubernetes"])
    require(manifest.count("image: safeheal-ai:day2") == 3, "Expected exactly three image placeholders")
    manifest = manifest.replace("image: safeheal-ai:day2", "image: " + image)
    # Namespace must exist before server validation of its namespaced resources.
    print(kubectl("apply", "-f", ROOT / "infrastructure/kubernetes/namespace.yaml"), flush=True)
    print(kubectl("apply", "--dry-run=server", "-f", "-", stdin=manifest), flush=True)
    print(kubectl("apply", "-f", "-", stdin=manifest), flush=True)
    for role in ROLES:
        print(kubectl("-n", NAMESPACE, "rollout", "status", f"deployment/{role}",
                      "--timeout=180s", timeout=200), flush=True)
    print(kubectl("-n", NAMESPACE, "get", "pods,services", "-o", "wide"), flush=True)


def pod_for(role, *, timeout=90):
    pods = kjson("-n", NAMESPACE, "get", "pods", "-l",
                 f"app.kubernetes.io/name={role},app.kubernetes.io/part-of=safeheal-ai",
                 timeout=timeout)["items"]
    active = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
    require(len(active) == 1, f"Expected one active {role} Pod; wait for rollout completion")
    return active[0]


def pod_state(pod):
    states = pod.get("status", {}).get("containerStatuses", [])
    require(len(states) == 1, "Expected one application container")
    state = states[0]
    return {"pod": pod["metadata"]["name"], "uid": pod["metadata"]["uid"],
            "node": pod["spec"]["nodeName"], "container": state["name"],
            "container_id": state.get("containerID"), "image_id": state.get("imageID"),
            "restart_count": state["restartCount"], "ready": state["ready"],
            "state": state["state"], "last_state": state.get("lastState", {})}


def check_services(request_id, *, readiness_only=False, timeout=90):
    deadline = time.monotonic() + timeout
    gateway = pod_for("gateway", timeout=timeout)["metadata"]["name"]
    script = (ROOT / "scripts/in_cluster_check.py").read_text(encoding="utf-8")
    remaining = deadline - time.monotonic()
    require(remaining > 0, "Service check deadline expired during Pod lookup")
    output = kubectl("-n", NAMESPACE, "exec", "-i", gateway, "-c", "gateway", "--",
                     "env", f"CHECK_REQUEST_ID={request_id}",
                     f"CHECK_READINESS_ONLY={int(readiness_only)}", "python", "-",
                     stdin=script, timeout=remaining)
    return json.loads(output)


def wait_for_service_routes(record, timeout=90):
    # Pod Ready can precede Service routing convergence. Poll GETs only;
    # the final three full checks (including POST /orders) are never retried.
    require(timeout > 0, "Service readiness timeout must be positive")
    deadline = time.monotonic() + timeout
    attempts = record["route_readiness_attempts"] = []
    while (remaining := deadline - time.monotonic()) > 0:
        attempt = {"at": utc(), "passed": False}
        attempts.append(attempt)
        try:
            attempt["check"] = check_services(
                record["trial_id"] + f"-routes-{len(attempts)}",
                readiness_only=True, timeout=min(30, remaining))
            require(attempt["check"].get("readiness_only") is True and
                    attempt["check"].get("passed") is True,
                    "Readiness probe did not confirm GET-only health")
        except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
            attempt["error"] = str(exc)
        else:
            attempt["passed"] = True
            return
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Service HTTP routes did not become healthy within {timeout} seconds")


def ready_snapshot():
    snapshot = {role: pod_state(pod_for(role)) for role in ROLES}
    require(all(s["ready"] for s in snapshot.values()), "Not all application containers are ready")
    return snapshot


def evidence_path(prefix):
    folder = ROOT / "evidence/day2"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}.json"


def write_evidence(path, record):
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence: {path.relative_to(ROOT)}", flush=True)


def provenance():
    paths = sorted((ROOT / "infrastructure").rglob("*.yaml")) + [ROOT / "scripts/k8s.py", ROOT / "scripts/in_cluster_check.py"]
    versions = json.loads(kubectl("version", "-o", "json"))
    return {"head": run(["git", "rev-parse", "HEAD"]).strip(),
            "working_tree": run(["git", "status", "--porcelain"]).splitlines(),
            "sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            "kind": run([kind_path(), "version"]).strip(),
            "kubectl": versions["clientVersion"]["gitVersion"],
            "kubernetes": versions["serverVersion"]["gitVersion"]}


def verify():
    guard_cluster()
    record = {"checked_at": utc(), "context": CONTEXT, "namespace": NAMESPACE,
              "source": provenance(), "pods": ready_snapshot(),
              "check": check_services("day2-" + uuid4().hex[:12])}
    request_id = record["check"]["request_id"]
    record["correlated_logs"] = {}
    for role in ROLES:
        lines = kubectl("-n", NAMESPACE, "logs", f"deployment/{role}", "--tail=200").splitlines()
        matches = [json.loads(line) for line in lines if line.startswith("{") and request_id in line]
        require(any(line.get("method") == "POST" and line.get("status") == 201 for line in matches),
                f"No successful correlated POST log for {role}")
        record["correlated_logs"][role] = matches
    record["services"] = kjson("-n", NAMESPACE, "get", "services")["items"]
    for service in record["services"]:
        role = service["metadata"]["name"]
        if role in ROLES:
            require(record["check"]["dns"][role]["short"] == service["spec"]["clusterIP"],
                    f"DNS did not return the {role} Service IP")
    record["endpoint_slices"] = kjson("-n", NAMESPACE, "get", "endpointslices")["items"]
    record["passed"] = True
    write_evidence(evidence_path("verification"), record)
    print("VERIFY PASS: DNS, all health/readiness endpoints, synthetic order, correlation across all services")


def guard_target(pod, cri):
    state = pod_state(pod)
    require(pod["metadata"]["namespace"] == NAMESPACE and state["node"] == NODE,
            "Target is outside the isolated namespace/node")
    labels = pod["metadata"].get("labels", {})
    require(labels.get("app.kubernetes.io/name") == "payment" and
            labels.get("app.kubernetes.io/part-of") == "safeheal-ai", "Target is not our payment Pod")
    require(state["container"] == "payment" and state["ready"], "Target payment is not ready")
    require(pod["spec"].get("restartPolicy") == "Always", "Expected restartPolicy Always")
    status = cri["status"]
    require(state["container_id"] == "containerd://" + status["id"], "CRI container ID mismatch")
    expected = {"io.kubernetes.pod.namespace": NAMESPACE, "io.kubernetes.pod.uid": state["uid"],
                "io.kubernetes.pod.name": state["pod"], "io.kubernetes.container.name": "payment"}
    require(all(status.get("labels", {}).get(k) == v for k, v in expected.items()), "CRI labels mismatch")
    require(status["state"] == "CONTAINER_RUNNING", "CRI target is not running")
    return status["id"]


def recovery(execute=False):
    guard_cluster()
    before = ready_snapshot()
    pod = pod_for("payment")
    container_id = before["payment"]["container_id"].removeprefix("containerd://")
    cri = json.loads(run(["docker", "exec", NODE, "crictl", "inspect", container_id]))
    container_id = guard_target(pod, cri)
    # The global timeout bounds the CRI RPC; stop's timeout is a separate kill grace.
    # crictl defaults to a 2s RPC deadline, which can expire on a busy CI runner.
    # Never retry an ambiguous stop: keep one scoped request and retain failures.
    command = ["docker", "exec", NODE, "crictl", "--timeout=30s",
               "stop", "--timeout", "0", container_id]
    if not execute:
        print(json.dumps({"dry_run": True, "target": before["payment"], "command": command,
                          "impact": "One payment container stops; kubelet restarts it. Brief order failures possible."}, indent=2))
        return
    record = {"trial_id": "day2-native-" + uuid4().hex[:12], "approach": "native-kubernetes",
              "scenario": "payment-container-stop", "context": CONTEXT, "namespace": NAMESPACE,
              "source": provenance(), "before": before, "command": command, "observations": [], "passed": False,
              "measurement": "Host elapsed time from stop request to three successful recovery checks; includes tool/API/poll overhead; not benchmark MTTR."}
    path = evidence_path("recovery")
    started = time.monotonic()
    try:
        record["baseline_check"] = check_services(record["trial_id"] + "-before")
        record["injection_requested_at"] = utc()
        started = time.monotonic()
        # CRI stop from the node avoids PID-1 signal-namespace ambiguity. No Pod deletion or manual restart.
        record["stop_output"] = run(command, timeout=45).strip()
        deadline = started + 180
        while time.monotonic() < deadline:
            current = pod_state(pod_for("payment"))
            record["observations"].append({"at": utc(), "elapsed_s": round(time.monotonic()-started, 3), **current})
            require(current["uid"] == before["payment"]["uid"], "Pod changed; cannot attribute this to container restart")
            if current["restart_count"] > before["payment"]["restart_count"] and current["ready"]:
                record["container_ready_at"] = utc()
                break
            time.sleep(1)
        else:
            raise RuntimeError("Native payment restart was not verified within 180 seconds")
        # Wait for dependency-aware readiness to recover through order and gateway.
        for role in ROLES:
            kubectl("-n", NAMESPACE, "wait", "--for=condition=Ready", "pod/" + before[role]["pod"],
                    "--timeout=90s", timeout=100)
        wait_for_service_routes(record)
        record["after"] = ready_snapshot()
        after = record["after"]["payment"]
        require(after["uid"] == before["payment"]["uid"], "Payment Pod was replaced during readiness checks")
        require(after["container_id"] != before["payment"]["container_id"], "Container ID did not change")
        require(after["last_state"].get("terminated"), "Missing termination evidence")
        for role in ("gateway", "order"):
            require(record["after"][role]["uid"] == before[role]["uid"] and
                    record["after"][role]["restart_count"] == before[role]["restart_count"],
                    f"Unexpected restart/replacement of upstream {role}")
        record["post_recovery_checks"] = []
        for sample in range(3):
            if sample:
                time.sleep(2)
            record["post_recovery_checks"].append({"at": utc(), **check_services(record["trial_id"] + f"-after-{sample}")})
        record["passed"] = True
        record["verified_at"] = utc()
    except Exception as exc:
        record["error"] = str(exc)
        raise
    finally:
        record["elapsed_to_final_check_s"] = round(time.monotonic() - started, 3)
        try:
            record["events"] = kjson("-n", NAMESPACE, "get", "events", "--field-selector",
                                     "involvedObject.name=" + before["payment"]["pod"])["items"]
        except Exception as exc:
            record["event_collection_error"] = str(exc)
        write_evidence(path, record)
    print("RECOVERY PASS: same Pod, new container, increased restart count, upstream containers stable, 3 healthy order checks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install-kind", "setup", "deploy", "verify", "recovery", "status", "port-forward"))
    parser.add_argument("--execute", action="store_true", help="Actually stop the isolated payment container during recovery")
    args = parser.parse_args()
    require(not args.execute or args.action == "recovery", "--execute applies only to recovery")
    if args.action == "install-kind":
        install_kind()
    elif args.action == "setup":
        setup()
    elif args.action == "deploy":
        deploy()
    elif args.action == "verify":
        verify()
    elif args.action == "recovery":
        if args.execute:
            with recovery_lock():
                recovery(True)
        else:
            recovery()
    elif args.action == "status":
        guard_cluster()
        print(kubectl("-n", NAMESPACE, "get", "deployments,pods,services", "-o", "wide"))
    else:
        guard_cluster()
        subprocess.run(["kubectl", "--kubeconfig", str(KUBECONFIG), "--context", CONTEXT, "-n", NAMESPACE,
                        "port-forward", "--address=127.0.0.1", "service/gateway", "18081:8000"], check=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
