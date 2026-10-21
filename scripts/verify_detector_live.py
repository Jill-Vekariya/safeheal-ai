"""One scoped real-Prometheus engineering check; default dry-run, no model/executor.

Temporarily disconnects only the payment Service selector in our local test lab,
then restores the exact selector in finally. This developer harness has cluster
write access; the incident detector has none. It is not a Day 5 benchmark runner.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import k8s as lab
from services.incidents.controller import Controller
from services.incidents.telemetry import Collector


TRAFFIC_SCRIPT = '''import json, time, urllib.request, urllib.error
started=time.monotonic()
rows=[]
while time.monotonic()-started < 150:
    at=time.time()
    request=urllib.request.Request(TARGET+'/orders',data=json.dumps({'item_id':'day4-live','quantity':2}).encode(),headers={'Content-Type':'application/json','X-Request-ID':TRIAL+'-'+str(len(rows))})
    try:
        with urllib.request.urlopen(request,timeout=5) as response:
            body=json.load(response)
            status=response.status
            assert body['status']=='confirmed' and body['amount_cents']==2000
    except urllib.error.HTTPError as error:
        status=error.code
    except OSError:
        status='transport_error'
    fresh_at=time.time()
    fresh_request=urllib.request.Request('http://payment:8000/payments',data=json.dumps({'order_id':TRIAL+'-fresh-'+str(len(rows)),'amount_cents':2000}).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(fresh_request,timeout=1) as response:
            fresh_status=response.status
            body=json.load(response)
            assert body['status']=='simulated_paid' and body['amount_cents']==2000
    except urllib.error.HTTPError as error:
        fresh_status=error.code
    except OSError:
        fresh_status='transport_error'
    rows.append({'at':at,'status':status,'fresh_payment_at':fresh_at,'fresh_payment_status':fresh_status,'duration_s':time.time()-at})
    time.sleep(.4)
print(json.dumps({'observations':rows,'elapsed_s':time.monotonic()-started}))
'''


def service_identity(service):
    metadata = service.get("metadata", {})
    labels = metadata.get("labels", {})
    selector = service.get("spec", {}).get("selector", {})
    lab.require(metadata.get("name") == "payment" and metadata.get("namespace") == lab.NAMESPACE,
                "Refusing a foreign Service")
    lab.require(labels.get("app.kubernetes.io/name") == "payment" and
                labels.get("app.kubernetes.io/part-of") == "safeheal-ai", "Refusing unowned payment Service")
    lab.require(selector == {"app.kubernetes.io/name": "payment", "app.kubernetes.io/part-of": "safeheal-ai"},
                "Unexpected payment selector; refusing fault")
    lab.require(metadata.get("uid"), "Missing Service UID")
    return metadata["uid"], selector.copy()


def patch_selector(uid, expected, desired):
    patch = [{"op": "test", "path": "/metadata/uid", "value": uid},
             {"op": "test", "path": "/spec/selector", "value": expected},
             {"op": "replace", "path": "/spec/selector", "value": desired}]
    return json.loads(lab.kubectl("-n", lab.NAMESPACE, "patch", "service", "payment", "--type=json",
                                 "-p", json.dumps(patch), "-o", "json"))


def validate_traffic(record):
    rows = record["traffic"]["observations"]
    start = datetime.fromisoformat(record["fault_applied_at"]).timestamp()
    end = datetime.fromisoformat(record["restored_at"]).timestamp()
    failed = [r for r in rows if start <= r["fresh_payment_at"] <= end and
              (r["fresh_payment_status"] == "transport_error" or
               isinstance(r["fresh_payment_status"], int) and r["fresh_payment_status"] >= 500)]
    lab.require(any(r["status"] == 201 for r in rows) and
                any(r["fresh_payment_status"] == 201 for r in rows) and failed,
                "Expected healthy orders/payment calls and fresh-connection payment failures during the scoped fault")
    return {"fresh_payment_failures_during_fault": len(failed),
            "note": "Existing internal keep-alive connections may preserve gateway orders; fresh payment connections establish routing-fault ground truth."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    lab.guard_cluster()
    service = lab.kjson("-n", lab.NAMESPACE, "get", "service", "payment")
    uid, original = service_identity(service)
    before = lab.ready_snapshot()
    if not args.execute:
        print(json.dumps({"dry_run": True, "namespace": lab.NAMESPACE, "service_uid": uid,
                          "selector": original, "fault": "temporarily add a unique unmatched payment Service selector",
                          "hold_seconds": 25, "restore": "exact prior selector; UID/selector JSON Patch tests"}, indent=2))
        return
    folder = lab.ROOT / "evidence/day4"
    folder.mkdir(parents=True, exist_ok=True)
    trial = "day4-live-" + uuid4().hex[:12]
    path = folder / (trial + ".json")
    dbpath = lab.ROOT / ".local" / (trial + ".sqlite3")
    record = {"trial_id": trial, "started_at": lab.utc(), "passed": False, "source": lab.provenance(),
              "context": lab.CONTEXT, "namespace": lab.NAMESPACE, "before": before,
              "scenario": "payment-service-selector-disconnect", "service_uid": uid, "original_selector": original,
              "measurement": "Engineering detector acceptance with real Prometheus and HTTP; not a matched benchmark/MTTR.",
              "llm_used": False, "detector_has_cluster_write_access": False, "polls": []}
    record["source"]["detector_sha256"] = {
        str(p.relative_to(lab.ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((lab.ROOT/"services/incidents").glob("*.py")) + [Path(__file__)]}
    controller, collector = Controller(dbpath), Collector()
    traffic = None
    disconnected = {**original, "safeheal.ai/day4-trial": trial}
    fault_attempted = False

    def collect(phase):
        snapshot = collector.collect()
        eid = controller.ingest(snapshot)
        record["polls"].append({"phase": phase, "at": snapshot.at, "evidence_id": eid,
                                "services": {s: vars(v) for s, v in snapshot.services.items()},
                                "incidents": controller.list_incidents()})
        return snapshot

    def save():
        record["incidents"] = [controller.detail(i["id"]) for i in controller.list_incidents()]
        record["evidence"] = {str(row[0]): controller.evidence(row[0])
                              for row in controller.db.execute("SELECT id FROM evidence ORDER BY id")}
        lab.write_evidence(path, record)

    try:
        record["baseline"] = lab.check_services(trial + "-baseline")
        gateway = lab.pod_for("gateway")
        target = "http://" + gateway["status"]["podIP"] + ":8000"
        script = "TARGET=" + repr(target) + "\nTRIAL=" + repr(trial) + "\n" + TRAFFIC_SCRIPT
        command = ["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
                   "--request-timeout=180s", "-n", lab.NAMESPACE, "exec", "-i", gateway["metadata"]["name"],
                   "-c", "gateway", "--", "python", "-"]
        traffic = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", cwd=lab.ROOT)
        traffic.stdin.write(script)
        traffic.stdin.close()
        traffic.stdin = None
        print("Warming real HTTP traffic and Prometheus counters", flush=True)
        deadline = time.monotonic()+35
        while True:
            snapshot = collect("baseline")
            if all(v.up is True and not v.problems and v.requests is not None and v.requests >= 20
                   for v in snapshot.services.values()):
                break
            lab.require(time.monotonic() < deadline, "Baseline traffic/telemetry did not become eligible")
            time.sleep(5)
        lab.require(not controller.list_incidents(), "Unexpected baseline incident")
        with lab.recovery_lock():
            try:
                # Persist restoration data BEFORE attempting the mutation. A transport error may be ambiguous.
                record["fault_requested_at"] = lab.utc()
                fault_attempted = True
                save()
                patch_selector(uid, original, disconnected)
                record["fault_applied_at"] = lab.utc()
                started = time.monotonic()
                print("Scoped payment Service disconnection applied; detector remains read-only", flush=True)
                while time.monotonic()-started < 25:
                    collect("fault")
                    time.sleep(5)
                collect("fault-final")
                payment = [i for i in controller.list_incidents() if i["service"] == "payment" and i["rule"] == "scrape_unavailable"]
                lab.require(payment and payment[0]["state"] == "open", "Known payment routing failure did not open an incident")
                record["opened_payment_incident_id"] = payment[0]["id"]
            finally:
                if fault_attempted:
                    current = lab.kjson("-n", lab.NAMESPACE, "get", "service", "payment")
                    lab.require(current["metadata"]["uid"] == uid, "Service replaced during fault; refusing unrelated restoration")
                    selector = current["spec"]["selector"]
                    if selector == disconnected:
                        patch_selector(uid, disconnected, original)
                    else:
                        lab.require(selector == original, "Concurrent selector edit; refusing to overwrite it")
                    record["restored_at"] = lab.utc()
                    record["restored_selector"] = lab.kjson("-n", lab.NAMESPACE, "get", "service", "payment")["spec"]["selector"]
                    lab.require(record["restored_selector"] == original, "Restoration not verified")
                    save()
                    print("Exact payment Service selector restored", flush=True)
        deadline = time.monotonic()+100
        while True:
            snapshot = collect("recovery")
            active = controller.list_incidents(active_only=True)
            if all(v.up is True and not v.problems for v in snapshot.services.values()) and not active:
                break
            lab.require(time.monotonic() < deadline, "Incidents did not resolve after restoration")
            time.sleep(5)
        item = controller.detail(record["opened_payment_incident_id"])
        states = [t["state"] for t in reversed(item["transitions"])]
        lab.require(states == ["pending", "open", "recovering", "resolved"], "Unexpected payment lifecycle")
        record["final"] = lab.check_services(trial + "-final")
        record["after"] = lab.ready_snapshot()
        for role in lab.ROLES:
            lab.require(record["after"][role]["uid"] == before[role]["uid"] and
                        record["after"][role]["restart_count"] == before[role]["restart_count"],
                        "Unexpected application restart/replacement during Service-only fault")
        output, error = traffic.communicate(timeout=90)
        lab.require(traffic.returncode == 0, "Traffic worker failed: " + error[-1000:])
        record["traffic"] = json.loads(output)
        record["traffic_verification"] = validate_traffic(record)
        record["passed"] = True
        record["finished_at"] = lab.utc()
    except Exception as exc:
        record["error"] = str(exc)
        raise
    finally:
        if traffic is not None and traffic.poll() is None:
            traffic.terminate()
            traffic.wait(timeout=10)
        save()
        controller.close()
    print("DETECTOR LIVE PASS: real routing failure, evidence-grounded incident lifecycle, exact restoration and healthy orders", flush=True)


if __name__ == "__main__":
    main()
