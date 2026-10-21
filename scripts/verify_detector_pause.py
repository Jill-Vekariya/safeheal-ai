"""Scoped payment-container pause acceptance; default dry-run, no model calls.

The developer harness has host/cluster credentials. Detector modules do not call
cluster tools; this engineering check does not establish OS privilege separation.
The node-side script resumes the exact container automatically after 35 seconds,
including on shell signals. Kubernetes may also restart it through liveness.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import k8s as lab
from services.incidents.controller import Controller
from services.incidents.telemetry import Collector
from verify_detector_live import TRAFFIC_SCRIPT

PAUSE_SCRIPT = '''task_id="$1"
resume_task() { ctr --timeout 10s --connect-timeout 5s --namespace k8s.io tasks resume "$task_id" >/dev/null 2>&1 || true; }
trap resume_task EXIT HUP INT TERM
ctr --timeout 10s --connect-timeout 5s --namespace k8s.io tasks pause "$task_id" || exit 1
printf 'PAYMENT_TASK_PAUSED\n'
sleep 35
resume_task
printf 'PAYMENT_PAUSE_WINDOW_FINISHED\n'
'''


def pause_target(pod, cri):
    cid = lab.guard_target(pod, cri)
    lab.require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None, "Unexpected container ID")
    return cid


def pause_command(cid):
    lab.require(re.fullmatch(r"[0-9a-f]{64}", cid) is not None, "Unexpected container ID")
    return ["docker", "exec", lab.NODE, "sh", "-c", PAUSE_SCRIPT, "safeheal-day4-pause", cid]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    lab.guard_cluster()
    before = lab.ready_snapshot()
    pod = lab.pod_for("payment")
    cid = before["payment"]["container_id"].removeprefix("containerd://")
    cri = json.loads(lab.run(["docker", "exec", lab.NODE, "crictl", "inspect", cid]))
    cid = pause_target(pod, cri)
    command = pause_command(cid)
    if not args.execute:
        print(json.dumps({"dry_run": True, "target": before["payment"], "command": command,
                          "impact": "One validated payment task pauses for 35s, then resumes automatically. Native liveness restart is possible."}, indent=2))
        return
    trial = "day4-pause-"+uuid4().hex[:12]
    folder = lab.ROOT/"evidence/day4"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(trial+".json")
    dbpath = lab.ROOT/".local"/(trial+".sqlite3")
    record = {"trial_id": trial, "started_at": lab.utc(), "passed": False, "source": lab.provenance(),
              "scenario": "validated-payment-task-pause", "context": lab.CONTEXT, "namespace": lab.NAMESPACE,
              "before": before, "command": command, "llm_used": False,
              "measurement": "Engineering failure detection/lifecycle check, not a controlled benchmark or MTTR.",
              "privilege_boundary": "Privileged developer harness; detector library has no cluster-tool calls. OS privilege separation is not tested.",
              "polls": []}
    sources = sorted((lab.ROOT/"services/incidents").glob("*.py")) + [Path(__file__), lab.ROOT/"scripts/verify_detector_live.py"]
    record["source"]["detector_sha256"] = {str(p.relative_to(lab.ROOT)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    controller, collector = Controller(dbpath), Collector()
    traffic = holder = None

    def collect(phase):
        snapshot = collector.collect()
        eid = controller.ingest(snapshot)
        record["polls"].append({"phase": phase, "at": snapshot.at, "evidence_id": eid,
                                "services": {s: vars(v) for s,v in snapshot.services.items()},
                                "incidents": controller.list_incidents()})
        return snapshot

    def save():
        record["incidents"] = [controller.detail(i["id"]) for i in controller.list_incidents()]
        record["evidence"] = {str(row[0]): controller.evidence(row[0]) for row in controller.db.execute("SELECT id FROM evidence ORDER BY id")}
        lab.write_evidence(path, record)

    try:
        record["baseline"] = lab.check_services(trial+"-baseline")
        gateway = lab.pod_for("gateway")
        target = "http://"+gateway["status"]["podIP"]+":8000"
        script = "TARGET="+repr(target)+"\nTRIAL="+repr(trial)+"\n"+TRAFFIC_SCRIPT
        traffic = subprocess.Popen(["kubectl", "--kubeconfig", str(lab.KUBECONFIG), "--context", lab.CONTEXT,
                    "--request-timeout=180s", "-n", lab.NAMESPACE, "exec", "-i", gateway["metadata"]["name"],
                    "-c", "gateway", "--", "python", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=lab.ROOT)
        traffic.stdin.write(script)
        traffic.stdin.close()
        traffic.stdin = None
        print("Warming actual traffic and Prometheus evidence", flush=True)
        deadline = time.monotonic()+40
        while True:
            snapshot = collect("baseline")
            if all(v.up is True and not v.problems and v.requests is not None and v.requests >= 20 for v in snapshot.services.values()):
                break
            lab.require(time.monotonic()<deadline, "Baseline telemetry did not become eligible")
            time.sleep(5)
        lab.require(not controller.list_incidents(), "Unexpected baseline incident")
        with lab.recovery_lock():
            # Revalidate the exact task immediately before injection.
            lab.require(pause_target(lab.pod_for("payment"), json.loads(lab.run(["docker", "exec", lab.NODE, "crictl", "inspect", cid]))) == cid,
                        "Payment target changed")
            record["fault_requested_at"] = lab.utc()
            save()
            try:
                holder = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          text=True, encoding="utf-8", cwd=lab.ROOT)
                print("One validated payment task paused; node-side auto-resume is bounded to 35 seconds", flush=True)
                started = time.monotonic()
                while time.monotonic()-started < 42:
                    collect("fault-and-auto-resume")
                    time.sleep(5)
            finally:
                if holder is not None:
                    # Let the node-side auto-resume complete even if collection failed.
                    out, err = holder.communicate(timeout=55)
                    record["pause_process"] = {"returncode": holder.returncode, "stdout": out, "stderr": err}
                    record["pause_window_finished_at"] = lab.utc()
                    lab.require(holder.returncode == 0 and "PAYMENT_TASK_PAUSED" in out and "PAYMENT_PAUSE_WINDOW_FINISHED" in out,
                                "Pause/resume script did not finish cleanly; inspect the retained task/Pod evidence")
        payment = [i for i in controller.list_incidents() if i["service"]=="payment" and i["rule"]=="scrape_unavailable" and i["opened_at"]]
        lab.require(payment, "Observable payment failure did not open an incident")
        record["opened_payment_incident_id"] = payment[0]["id"]
        deadline = time.monotonic()+100
        while True:
            snapshot = collect("recovery")
            if all(v.up is True and not v.problems for v in snapshot.services.values()) and not controller.list_incidents(active_only=True):
                break
            lab.require(time.monotonic()<deadline, "Recovery evidence did not resolve all incidents")
            time.sleep(5)
        item = controller.detail(payment[0]["id"])
        states = [v["state"] for v in reversed(item["transitions"])]
        lab.require("pending" in states and "open" in states and states[-1]=="resolved", "Incomplete incident lifecycle")
        record["final"] = lab.check_services(trial+"-final")
        record["after"] = lab.ready_snapshot()
        lab.require(record["after"]["payment"]["uid"]==before["payment"]["uid"], "Payment Pod unexpectedly replaced")
        for role in ("gateway", "order"):
            lab.require(record["after"][role]["uid"]==before[role]["uid"] and
                        record["after"][role]["restart_count"]==before[role]["restart_count"], "Upstream container changed")
        out, err = traffic.communicate(timeout=90)
        lab.require(traffic.returncode==0, "Traffic worker failed: "+err[-1000:])
        record["traffic"] = json.loads(out)
        statuses = [r["status"] for r in record["traffic"]["observations"]]
        lab.require(201 in statuses and any(isinstance(s,int) and s>=500 for s in statuses), "Expected actual healthy and failed gateway requests")
        record["recovery_attribution"] = "Node-side timed task resume and/or native Kubernetes liveness; incident controller executed no remediation."
        record["finished_at"] = lab.utc()
        record["passed"] = True
    except Exception as exc:
        record["error"] = str(exc)
        raise
    finally:
        if traffic is not None and traffic.poll() is None:
            traffic.terminate()
            traffic.wait(timeout=10)
        save()
        controller.close()
    print("DETECTOR LIVE PASS: payment task failure detected without LLM, incident resolved, final health/orders verified", flush=True)


if __name__ == "__main__":
    main()
