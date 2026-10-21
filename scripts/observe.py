"""Reproducible observability deployment/acceptance in the existing isolated lab."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import k8s as lab

ROOT = lab.ROOT
CONFIG = ROOT / "infrastructure/observability"
SERVICES = ("prometheus", "grafana")


def deploy():
    lab.guard_cluster()
    resources = json.loads((CONFIG / "resources.json").read_text())["items"]
    for resource in resources:
        name, kind = resource["metadata"]["name"], resource["kind"].lower()
        current = lab.kubectl("-n", lab.NAMESPACE, "get", kind, name, "--ignore-not-found", "-o", "json")
        if current.strip():
            lab.guard_labels(json.loads(current), f"{kind}/{name}")
        if kind == "deployment":
            image = resource["spec"]["template"]["spec"]["containers"][0]["image"]
            lab.require("@sha256:" in image, "Telemetry images must be digest-pinned")
            # Let kubelet resolve the pinned index for its native architecture. Docker's
            # partial multi-platform save archives cannot always be imported by kind.
    manifest = lab.run(["kubectl", "kustomize", CONFIG])
    print(lab.kubectl("apply", "--dry-run=server", "-f", "-", stdin=manifest), flush=True)
    print(lab.kubectl("apply", "-f", "-", stdin=manifest), flush=True)
    for name in SERVICES:
        print(lab.kubectl("-n", lab.NAMESPACE, "rollout", "status", f"deployment/{name}",
                          "--timeout=240s", timeout=260), flush=True)


def exec_args(pod, mode, **env):
    return ["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
            "--request-timeout=90s", "-n", lab.NAMESPACE, "exec", "-i", pod, "-c", "gateway",
            "--", "env", "OBS_MODE=" + mode, *[f"OBS_{k}={v}" for k, v in env.items()], "python", "-"]


def validate_telemetry(data):
    targets = data["targets"]["data"]["activeTargets"]
    lab.require(len(targets) == 3 and all(t["health"] == "up" for t in targets), "Expected three UP scrape targets")
    for name, query in data["queries"].items():
        lab.require(query["status"] == "success", f"PromQL failed: {name}")
        # Empty error series are normal until a failure has occurred; other panels must populate.
        if name != "5xx_count":
            lab.require(query["data"]["result"], f"No telemetry for {name}")
    lab.require(data["grafana_health"]["database"] == "ok", "Grafana database not healthy")
    lab.require(len(data["dashboard"]["dashboard"]["panels"]) == 8, "Expected eight provisioned panels")
    proxy = data["grafana_query"]
    lab.require(proxy["status"] == "success" and len(proxy["data"]["result"]) == 3,
                "Grafana datasource did not return all three services")


def validate_traces(logs, rid):
    spans = [e for entries in logs.values() for e in entries if e.get("event") == "span" and
             e.get("attributes", {}).get("request_id") == rid]
    servers = {e["service"]: e for e in spans if e["kind"] == "SERVER"}
    lab.require(set(servers) == set(lab.ROLES), "Missing server spans for a complete three-service request")
    lab.require(len({e["trace_id"] for e in spans}) == 1, "Trace ID was not propagated")
    lab.require(len(spans) == 5 and len({e["span_id"] for e in spans}) == 5, "Expected five distinct spans")
    for upstream, downstream in (("gateway", "order"), ("order", "payment")):
        clients = [e for e in spans if e["service"] == upstream and e["kind"] == "CLIENT"]
        lab.require(len(clients) == 1, "Missing client span")
        lab.require(clients[0]["parent_span_id"] == servers[upstream]["span_id"] and
                    servers[downstream]["parent_span_id"] == clients[0]["span_id"], "Broken span parentage")
    return {"request_id": rid, "trace_id": servers["gateway"]["trace_id"], "spans": spans}


def verify(native_fault=False):
    lab.guard_cluster()
    folder = ROOT / "evidence/day3"
    folder.mkdir(parents=True, exist_ok=True)
    trial = "day3-" + uuid4().hex[:12]
    record = {"trial_id": trial, "started_at": lab.utc(), "passed": False,
              "source": lab.provenance(), "native_fault": native_fault,
              "measurement": "Engineering telemetry acceptance, not a controlled research benchmark or MTTR."}
    paths = [p for p in CONFIG.iterdir() if p.is_file()] + list((ROOT / "services").glob("*.py")) + [Path(__file__), ROOT / "scripts/in_cluster_observe.py", ROOT / "requirements.lock"]
    record["source"]["observability_sha256"] = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    path = folder / f"observability-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{trial}.json"
    try:
        record["baseline"] = lab.check_services(trial + "-baseline")
        gateway = lab.pod_for("gateway")
        # Direct Pod IP preserves a diagnostic observation path if readiness withdraws Service endpoints.
        # Baseline and final checks separately exercise the actual Service/DNS path.
        target = "http://" + gateway["status"]["podIP"] + ":8000"
        record["workload_note"] = "Diagnostic load uses the validated gateway Pod IP; bypasses readiness routing. Baseline/final use Service DNS."
        script = (ROOT / "scripts/in_cluster_observe.py").read_text(encoding="utf-8")
        with subprocess.Popen(exec_args(gateway["metadata"]["name"], "traffic", TRIAL=trial, TARGET=target),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8", cwd=ROOT) as traffic:
            traffic.stdin.write(script)
            traffic.stdin.close()
            traffic.stdin = None
            try:
                time.sleep(8)
                if native_fault:
                    with lab.recovery_lock():
                        lab.recovery(True)
                output, error = traffic.communicate(timeout=70)
                lab.require(traffic.returncode == 0, "Traffic generator failed: " + error[-2000:])
                record["traffic"] = json.loads(output)
            finally:
                if traffic.poll() is None:
                    traffic.terminate()
                    traffic.wait(timeout=10)
        counts = record["traffic"]["status_counts"]
        lab.require(int(counts.get("201", 0)) >= 10 and int(counts.get("422", 0)) >= 2,
                    "Expected actual valid and invalid traffic")
        time.sleep(7)  # At least one scrape after workload completion; rate window already populated.
        dashboard = json.loads((CONFIG / "safeheal.json").read_text())
        queries = {f"panel_{p['id']}_{t['refId']}": t["expr"] for p in dashboard["panels"] for t in p["targets"]}
        queries["5xx_count"] = 'sum by(service)(safeheal_http_requests_total{status_class="5xx"})'
        record["telemetry"] = json.loads(lab.run(exec_args(gateway["metadata"]["name"], "collect", QUERIES=json.dumps(queries)), stdin=script, timeout=90))
        validate_telemetry(record["telemetry"])
        record["logs"] = {}
        for role in lab.ROLES:
            lines = lab.kubectl("-n", lab.NAMESPACE, "logs", f"deployment/{role}", "--tail=2500").splitlines()
            if native_fault and role == "payment":
                lines += lab.kubectl("-n", lab.NAMESPACE, "logs", "deployment/payment", "--previous", "--tail=2500").splitlines()
            events = [json.loads(line) for line in lines if line.startswith("{")]
            record["logs"][role] = [e for e in events if str(e.get("request_id", "")).startswith(trial) or
                                    str(e.get("attributes", {}).get("request_id", "")).startswith(trial)]
        record["trace_verification"] = validate_traces(record["logs"], trial + "-0")
        for role in lab.ROLES:
            lab.require(any(e.get("request_id") == trial + "-0" and e.get("status") == 201 and e.get("trace_id")
                            for e in record["logs"][role]), f"Missing correlated JSON request log: {role}")
        if native_fault:
            lab.require(any(int(k) >= 500 and int(v) > 0 for k, v in counts.items() if k.isdigit()), "Fault generated no observed application 5xx")
            lab.require(record["telemetry"]["queries"]["5xx_count"]["data"]["result"], "5xx not visible in Prometheus")
        record["final"] = lab.check_services(trial + "-final")
        record["pods"] = lab.ready_snapshot()
        record["finished_at"] = lab.utc()
        record["passed"] = True
    except Exception as exc:
        record["error"] = str(exc)
        raise
    finally:
        lab.write_evidence(path, record)
    print("OBSERVABILITY PASS: three UP targets, real traffic, eight dashboard panels, Grafana datasource, JSON logs and five linked spans", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("deploy", "verify", "status", "forward-grafana", "forward-prometheus"))
    parser.add_argument("--native-fault", action="store_true", help="Repeat the authorized payment-container stop during diagnostic traffic")
    args = parser.parse_args()
    lab.require(not args.native_fault or args.action == "verify", "Fault flag applies only to verify")
    if args.action == "deploy":
        deploy()
    elif args.action == "verify":
        verify(args.native_fault)
    else:
        lab.guard_cluster()
        if args.action == "status":
            print(lab.kubectl("-n", lab.NAMESPACE, "get", "deployments,pods,services", "-o", "wide"))
        else:
            name, mapping = ("grafana", "13000:3000") if args.action.endswith("grafana") else ("prometheus", "19090:9090")
            subprocess.run(["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
                            "-n", lab.NAMESPACE, "port-forward", "--address=127.0.0.1", "service/" + name, mapping], check=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
