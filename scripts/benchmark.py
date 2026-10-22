"""Reproducible, bounded fault experiments. Default is a non-mutating plan.

Examples:
  python scripts/benchmark.py run
  python scripts/benchmark.py run --execute --backend kubernetes --repeats 2
  python scripts/benchmark.py run --execute --backend local-process --repeats 2
  python scripts/benchmark.py summarize evidence/day5/run-...
"""
import argparse
from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import httpx
import k8s as lab
from benchmark_core import atomic_json, build_plan, create_trial_directory, evaluate_trial, expected_detection, summarize, utc
from services.incidents.controller import Controller
from services.incidents.rules import RULE_VERSION, HOLDS, MAX_GAP, RECOVERY_HOLD, evaluate
from services.incidents.telemetry import Collector, WINDOW, MAX_AGE


class Journal:
    def __init__(self, path):
        self.handle = Path(path).open("x", encoding="utf-8")
        self.lock = threading.Lock()
        self.last_sync = time.monotonic()

    def write(self, item):
        line = json.dumps(item, allow_nan=False, separators=(",", ":")) + "\n"
        with self.lock:
            self.handle.write(line)
            self.handle.flush()
            if time.monotonic() - self.last_sync >= 1:
                os.fsync(self.handle.fileno())
                self.last_sync = time.monotonic()

    def close(self):
        with self.lock:
            if not self.handle.closed:
                self.handle.flush()
                os.fsync(self.handle.fileno())
                self.handle.close()


def request_sample(client, url, request_id, trial_started, *, payment=False):
    start, mono = time.time(), time.monotonic()
    item = {"request_id": request_id, "started_at": utc(start), "started_elapsed_seconds": mono - trial_started,
            "endpoint": "payment" if payment else "gateway", "status": None, "valid_response": False}
    payload = {"order_id": request_id, "amount_cents": 2000} if payment else {"item_id": "benchmark", "quantity": 2}
    try:
        response = client.post(url + ("/payments" if payment else "/orders"), json=payload,
                               headers={"x-request-id": request_id})
        item["status"] = response.status_code
        item["fault_id"] = response.headers.get("x-safeheal-fault-id")
        item["fault_scenario"] = response.headers.get("x-safeheal-fault-scenario")
        try:
            body = response.json()
            item["valid_response"] = (response.status_code == 201 and isinstance(body, dict)
                and body.get("amount_cents") == 2000
                and body.get("status") == ("simulated_paid" if payment else "confirmed")
                and bool(body.get("payment_id"))
                and (body.get("order_id") == request_id if payment else
                     body.get("item_id") == "benchmark" and body.get("quantity") == 2 and bool(body.get("order_id"))))
        except ValueError:
            item["response_error"] = "invalid_json"
    except httpx.HTTPError as exc:
        item["transport_error"] = type(exc).__name__
    item.update(finished_at=utc(), elapsed_seconds=time.monotonic() - mono,
                finished_elapsed_seconds=time.monotonic() - trial_started)
    return item


def healthy_response(item):
    return item.get("valid_response") is True and item["elapsed_seconds"] < .5


def scenario_impact(item, scenario):
    return not item.get("valid_response") or (scenario == "latency" and item["elapsed_seconds"] >= 1.)


def sustained_recovery(samples, injection_elapsed):
    """Three or more consecutive healthy completions spanning >=2 seconds."""
    ordered = sorted((r for r in samples if r["started_elapsed_seconds"] >= injection_elapsed),
                     key=lambda r: r["finished_elapsed_seconds"])
    current = []
    for row in ordered:
        if healthy_response(row):
            current.append(row)
        else:
            current.clear()
    if len(current) >= 3 and current[-1]["finished_elapsed_seconds"] - current[0]["finished_elapsed_seconds"] >= 2:
        # First point where this latest uninterrupted good sequence met the hold.
        confirmed = next(row for i, row in enumerate(current)
                         if i >= 2 and row["finished_elapsed_seconds"] - current[0]["finished_elapsed_seconds"] >= 2)
        return current[0], confirmed
    return None


class Workload:
    def __init__(self, backend, trial_id, started, folder, plan):
        self.url, self.trial_id, self.started = backend.gateway_url, trial_id, started
        self.interval, self.concurrency = plan["request_interval_seconds"], plan["concurrency"]
        self.journal = Journal(folder / "requests.jsonl")
        self.samples, self.errors, self.threads = [], [], []
        self.lock, self.stop_event = threading.Lock(), threading.Event()

    def _worker(self, worker):
        try:
            with httpx.Client(timeout=4, trust_env=False, follow_redirects=False) as client:
                sequence = 0
                while not self.stop_event.is_set():
                    item = request_sample(client, self.url, f"{self.trial_id}-{worker}-{sequence}", self.started)
                    self.journal.write(item)
                    with self.lock:
                        self.samples.append(item)
                    sequence += 1
                    self.stop_event.wait(self.interval)
        except Exception as exc:
            with self.lock:
                self.errors.append(f"{type(exc).__name__}: {exc}")
            self.stop_event.set()

    def start(self):
        for worker in range(self.concurrency):
            thread = threading.Thread(target=self._worker, args=(worker,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def rows(self):
        with self.lock:
            if self.errors:
                raise RuntimeError("Workload observer failed: " + self.errors[0])
            return list(self.samples)

    def close(self):
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout=6)
        if any(t.is_alive() for t in self.threads):
            raise RuntimeError("Workload thread failed to stop within HTTP timeout")
        self.journal.close()
        if self.errors:
            raise RuntimeError("Workload observer failed: " + self.errors[0])


class DetectorObserver:
    """Fixed polling independent of blocking kubectl/CRI operations; no mutation API."""
    def __init__(self, url, folder, interval):
        self.collector, self.controller = Collector(url), Controller(folder / "detector.sqlite3")
        try:
            self.journal = Journal(folder / "telemetry.jsonl")
        except BaseException:
            self.controller.close()
            raise
        self.interval = interval
        self.lock, self.stop_event = threading.RLock(), threading.Event()
        self.latest = None
        self.incidents, self.errors = {}, []
        self.thread = None

    def _run(self):
        while not self.stop_event.is_set():
            began = time.monotonic()
            try:
                snapshot = self.collector.collect()
                eid = self.controller.ingest(snapshot)
                self.journal.write({"observed_at": utc(), "evidence_id": eid, **snapshot.document()})
                with self.lock:
                    self.latest = snapshot
                    for summary in self.controller.list_incidents():
                        detail = self.controller.detail(summary["id"])
                        old = self.incidents.get(detail["id"], {})
                        if "first_open_diagnosis" in old:
                            detail["first_open_diagnosis"] = old["first_open_diagnosis"]
                            detail["first_open_observed_at"] = old["first_open_observed_at"]
                        elif detail.get("opened_at"):
                            detail["first_open_diagnosis"] = detail.get("diagnosis")
                            detail["first_open_observed_at"] = utc()
                        self.incidents[detail["id"]] = detail
            except Exception as exc:
                with self.lock:
                    self.errors.append({"at": utc(), "error": f"{type(exc).__name__}: {exc}"})
            self.stop_event.wait(max(0, self.interval - (time.monotonic() - began)))

    def start(self):
        self.thread = threading.Thread(target=self._run, name="read-only-rule-observer", daemon=True)
        self.thread.start()

    def state(self):
        with self.lock:
            return self.latest, list(self.incidents.values()), list(self.errors)

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=12)
            if self.thread.is_alive():
                raise RuntimeError("Detector collection did not stop within its deadline")
        self.journal.close()
        self.controller.close()


def eligible_healthy(snapshot):
    if snapshot is None or time.time() - snapshot.at > MAX_GAP:
        return False
    return all(v.decision == "clear" for v in evaluate(snapshot))


def verify_final_platform(record, current):
    """Validate the final observation, including changes during final HTTP checks."""
    before = record["recovery"]["before"]
    identity = ("uid", "container_id", "restart_count")
    for role in ("gateway", "order", "payment"):
        if current[role].get("ready") is not True:
            raise RuntimeError(f"Final platform observation is not ready: {role}")
    for role in ("gateway", "order"):
        if any(before[role].get(key) != current[role].get(key) for key in identity):
            raise RuntimeError(f"Unexpected upstream restart/replacement during final verification: {role}")
    if before["payment"].get("uid") != current["payment"].get("uid"):
        raise RuntimeError("Payment Pod changed during final verification")
    expected = (record["recovery"].get("native_ready_identity")
                if record["scenario"] == "process_crash" else before["payment"])
    if expected is None or any(expected.get(key) != current["payment"].get(key) for key in identity):
        raise RuntimeError("Payment container changed during final verification")


def source_provenance():
    def git(*args):
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return result.stdout.strip() if result.returncode == 0 else None
    paths = list((ROOT / "services").rglob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    paths += list((ROOT / "infrastructure").rglob("*.yaml")) + [ROOT / "requirements.lock"]
    return {"head": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "working_tree": git("status", "--porcelain"),
            "sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(paths)}}


def run_trial(backend, plan, entry, run_dir, source):
    trial_id = f"d5-{entry['sequence']:02d}-{entry['scenario']}-{uuid4().hex[:8]}"
    folder = create_trial_directory(run_dir, trial_id)
    started = time.monotonic()
    record = {"schema_version": 1, "trial_id": trial_id, **entry, "backend": backend.kind,
              "status": "planned", "timestamps": {"started_at": utc()}, "monotonic_elapsed_seconds": {},
              "source": source, "settings": {k: v for k, v in plan.items() if k != "trials"},
              "ground_truth": {"target_service": "payment", "fault_class": entry["scenario"],
                               "expected_affected_services": ["payment", "order", "gateway"],
                               "expected_detection": expected_detection(entry["scenario"]),
                               "injection_verified": False, "effect_verified": False},
              "detector": {"eligible": False, "rule_version": RULE_VERSION, "baseline_incident_ids": [], "incidents": []},
              "recovery": {"cleanup_verified": False, "business_recovery_verified": False,
                           "mechanism": "unverified"}, "artifacts": {"requests": "requests.jsonl", "telemetry": "telemetry.jsonl",
                           "platform": "platform.jsonl", "detector_database": "detector.sqlite3"}}
    path = folder / "trial.json"
    atomic_json(path, record)  # Plan and ground truth exist before any fault.
    workload = observer = platform_journal = None
    attempted, cleaned, injected_elapsed = False, False, None

    def stamp(name):
        record["timestamps"][name] = utc()
        record["monotonic_elapsed_seconds"][name] = time.monotonic() - started

    def checkpoint():
        snapshot, incidents, errors = observer.state()
        if errors:
            raise RuntimeError("Detector observer failed: " + errors[0]["error"])
        record["detector"].update(incidents=incidents, observer_errors=errors, observation_end_at=utc())
        atomic_json(path, record)

    try:
        workload = Workload(backend, trial_id, started, folder, plan)
        observer = DetectorObserver(backend.prometheus_url, folder, plan["poll_seconds"])
        platform_journal = Journal(folder / "platform.jsonl")
        record["status"] = "baseline"
        workload.start()
        observer.start()
        baseline_start = time.monotonic()
        clean_since = None
        while time.monotonic() - baseline_start < max(180, plan["baseline_seconds"] + 120):
            snapshot, incidents, errors = observer.state()
            if errors:
                raise RuntimeError("Detector observer failed: " + errors[0]["error"])
            rows = workload.rows()
            healthy = (eligible_healthy(snapshot) and not any(i["state"] != "resolved" for i in incidents)
                       and len(rows) >= 20 and all(healthy_response(row) for row in rows[-20:]))
            clean_since = (clean_since or time.monotonic()) if healthy else None
            if (time.monotonic() - baseline_start >= plan["baseline_seconds"] and clean_since is not None
                    and time.monotonic() - clean_since >= 15):
                break
            time.sleep(.25)
        else:
            raise RuntimeError("Healthy, eligible telemetry and clean baseline did not stabilize before deadline")
        record["detector"]["baseline_incident_ids"] = [i["id"] for i in incidents]
        record["baseline"] = {"completed_requests": len(rows), "resolved_warmup_incidents": incidents,
                              "eligible_snapshot": snapshot.document()}
        record["recovery"]["before"] = backend.snapshot()
        record["ground_truth"]["target_identity"] = backend.validate_target()
        if any(record["ground_truth"]["target_identity"].get(key) != record["recovery"]["before"]["payment"].get(key)
               for key in ("uid", "container_id", "restart_count")):
            raise RuntimeError("Payment identity changed between baseline snapshot and validation")
        stamp("baseline_ready_at")
        record["status"] = "running"
        stamp("injection_requested_at")
        injected_elapsed = record["monotonic_elapsed_seconds"]["injection_requested_at"]
        attempted = True  # An ambiguous injection failure still requires guarded cleanup.
        checkpoint()
        print(f"{trial_id}: injecting {entry['scenario']}", flush=True)
        acknowledgement = backend.inject(entry["scenario"], trial_id, plan["duration_seconds"], 1.25)
        record["injection_acknowledgement"] = acknowledgement
        record["ground_truth"]["injection_verified"] = True
        stamp("injection_confirmed_at")
        expiry_deadline = time.monotonic() + plan["duration_seconds"] + .5
        if entry["scenario"] != "process_crash":
            with httpx.Client(timeout=4, trust_env=False) as client:
                proof = request_sample(client, backend.payment_url, trial_id + "-proof", started, payment=True)
            record["ground_truth"]["direct_effect_probe"] = proof
            proof_ok = proof.get("fault_id") == trial_id and proof.get("fault_scenario") == entry["scenario"]
            proof_ok = proof_ok and (proof["status"] == 500 if entry["scenario"] == "http_5xx" else
                                    proof["valid_response"] and proof["elapsed_seconds"] >= 1.)
            if not proof_ok:
                raise RuntimeError("Direct payment probe did not independently verify the intended application fault")
        else:
            record["recovery"]["mechanism"] = "native_kubernetes" if backend.kind == "kubernetes" else "local_process_supervisor"
            record["cleanup_result"] = backend.cleanup(trial_id, entry["scenario"])
            record["recovery"]["cleanup_verified"] = cleaned = True
        checkpoint()
        deadline = time.monotonic() + plan["recovery_timeout_seconds"] + (plan["duration_seconds"] if entry["scenario"] != "process_crash" else 0)
        next_platform = next_checkpoint = 0.
        while time.monotonic() < deadline:
            now = time.monotonic()
            rows = workload.rows()
            affected = [r for r in rows if r["started_elapsed_seconds"] >= injected_elapsed and scenario_impact(r, entry["scenario"])]
            if affected and not record["ground_truth"]["effect_verified"]:
                record["ground_truth"]["effect_verified"] = True
                first_effect = min(affected, key=lambda r: r["finished_elapsed_seconds"])
                record["ground_truth"]["first_affected_gateway_request"] = first_effect
                record["timestamps"]["fault_effect_observed_at"] = first_effect["finished_at"]
                record["monotonic_elapsed_seconds"]["fault_effect_observed_at"] = first_effect["finished_elapsed_seconds"]
            if now >= next_platform:
                current = backend.snapshot()
                platform_journal.write({"at": utc(), "elapsed_seconds": time.monotonic() - started, "services": current})
                record["recovery"]["after"] = current
                old, new = record["recovery"]["before"]["payment"], current["payment"]
                for role in ("gateway", "order"):
                    old_up, new_up = record["recovery"]["before"][role], current[role]
                    if any(old_up.get(key) != new_up.get(key) for key in ("uid", "container_id", "restart_count")):
                        raise RuntimeError(f"Unexpected upstream restart/replacement: {role}")
                if old.get("uid") != new.get("uid"):
                    raise RuntimeError("Payment identity changed; replacement is outside this scenario")
                restarted = (new["restart_count"] > old["restart_count"] and new["container_id"] != old["container_id"] and new["ready"])
                if entry["scenario"] == "process_crash" and restarted:
                    if "native_ready_at" not in record["recovery"]:
                        record["recovery"]["native_ready_at"] = utc()
                        record["recovery"]["native_ready_identity"] = dict(new)
                    record["recovery"]["supervisor_restart_verified"] = backend.kind == "local-process"
                elif entry["scenario"] != "process_crash" and any(new.get(key) != old.get(key) for key in ("restart_count", "container_id")):
                    raise RuntimeError("Application fault unexpectedly restarted payment")
                next_platform = time.monotonic() + 5
            if entry["scenario"] != "process_crash" and not cleaned and now >= expiry_deadline:
                with httpx.Client(timeout=4, trust_env=False) as client:
                    expired = request_sample(client, backend.payment_url, trial_id + "-expiry", started, payment=True)
                record["expiry_probe"] = expired
                if expired.get("fault_id") is None and healthy_response(expired):
                    record["recovery"]["mechanism"] = "fault_expiry"
                    stamp("fault_removed_at")
                else:
                    record["recovery"]["mechanism"] = "harness_cleanup"
                record["cleanup_result"] = backend.cleanup(trial_id, entry["scenario"])
                if "fault_removed_at" not in record["timestamps"]:
                    stamp("fault_removed_at")
                record["recovery"]["cleanup_verified"] = cleaned = True
            snapshot, incidents, errors = observer.state()
            if errors:
                raise RuntimeError("Detector observer failed: " + errors[0]["error"])
            if snapshot and snapshot.at >= __import__("datetime").datetime.fromisoformat(record["timestamps"]["injection_requested_at"]).timestamp():
                expected = {(v["service"], v["rule"]) for v in record["ground_truth"]["expected_detection"]}
                if any(v.decision != "unknown" and (v.service, v.rule) in expected for v in evaluate(snapshot)):
                    record["detector"]["eligible"] = True
            recovery = sustained_recovery(rows, injected_elapsed)
            if recovery and record["ground_truth"]["effect_verified"]:
                record["timestamps"]["first_business_recovered_at"] = recovery[0]["finished_at"]
                record["timestamps"]["sustained_recovery_at"] = recovery[1]["finished_at"]
                record["monotonic_elapsed_seconds"]["first_business_recovered_at"] = recovery[0]["finished_elapsed_seconds"]
                record["monotonic_elapsed_seconds"]["sustained_recovery_at"] = recovery[1]["finished_elapsed_seconds"]
                record["recovery"]["business_recovery_verified"] = True
            else:
                record["recovery"]["business_recovery_verified"] = False
                for key in ("first_business_recovered_at", "sustained_recovery_at"):
                    record["timestamps"].pop(key, None)
                    record["monotonic_elapsed_seconds"].pop(key, None)
            observed_minimum = time.monotonic() - started - injected_elapsed >= max(WINDOW + RECOVERY_HOLD, plan["duration_seconds"] if entry["scenario"] != "process_crash" else 0)
            crash_restarted = entry["scenario"] != "process_crash" or "native_ready_at" in record["recovery"]
            if (cleaned and recovery and record["ground_truth"]["effect_verified"] and crash_restarted
                    and observed_minimum and eligible_healthy(snapshot) and not any(i["state"] != "resolved" for i in incidents)):
                record["final_check"] = backend.final_check(trial_id)
                record["status"] = "completed"
                break
            if now >= next_checkpoint:
                checkpoint()
                next_checkpoint = time.monotonic() + 5
            time.sleep(.25)
        else:
            raise RuntimeError("Recovery/observation deadline exceeded; retain censored outcomes")
    except BaseException as exc:
        record["status"] = "aborted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        if attempted and not cleaned:
            try:
                record["cleanup_result"] = backend.cleanup(trial_id, entry["scenario"])
                record["recovery"]["cleanup_verified"] = True
                if entry["scenario"] != "process_crash":
                    record["recovery"]["mechanism"] = "harness_cleanup"
                    stamp("fault_removed_at")
            except Exception as exc:
                record["cleanup_error"] = str(exc)
                record["recovery"]["cleanup_verified"] = False
        def finalization_error(stage, exc):
            record.setdefault("finalization_errors", []).append({
                "stage": stage, "error": f"{type(exc).__name__}: {exc}"})
            if record["status"] != "aborted":
                record["status"] = "failed"

        def close_resource(name, resource):
            if resource is None:
                return
            try:
                resource.close()
            except Exception as exc:
                record.setdefault("observer_shutdown_errors", {})[name] = str(exc)
                finalization_error(name + "_shutdown", exc)

        # Drain all in-flight HTTP requests before deciding that the last healthy
        # sequence is sustained. Keep the detector running during final platform
        # reads so a slow API call cannot make the final telemetry stale by design.
        close_resource("workload", workload)
        if attempted:
            try:
                current = backend.snapshot()
                record["recovery"]["after"] = current
                stamp("final_platform_observed_at")
                if platform_journal is not None:
                    platform_journal.write({"at": record["timestamps"]["final_platform_observed_at"],
                                            "elapsed_seconds": record["monotonic_elapsed_seconds"]["final_platform_observed_at"],
                                            "phase": "final", "services": current})
                verify_final_platform(record, current)
            except Exception as exc:
                finalization_error("final_platform", exc)
        close_resource("detector", observer)
        close_resource("platform", platform_journal)
        snapshot, incidents, errors = observer.state() if observer else (None, [], [])
        record["detector"].update(incidents=incidents, observer_errors=errors,
                                  observation_end_at=utc(snapshot.at) if snapshot else None, observer_stopped_at=utc())
        record["workload_errors"] = list(workload.errors) if workload else []
        if errors or record["workload_errors"]:
            record["status"] = "failed"
        rows = list(workload.samples) if workload else []
        final_recovery = sustained_recovery(rows, injected_elapsed) if injected_elapsed is not None else None
        if final_recovery and record["ground_truth"]["effect_verified"]:
            record["recovery"]["business_recovery_verified"] = True
            for key, row in zip(("first_business_recovered_at", "sustained_recovery_at"), final_recovery):
                record["timestamps"][key] = row["finished_at"]
                record["monotonic_elapsed_seconds"][key] = row["finished_elapsed_seconds"]
        else:
            record["recovery"]["business_recovery_verified"] = False
            for key in ("first_business_recovered_at", "sustained_recovery_at"):
                record["timestamps"].pop(key, None)
                record["monotonic_elapsed_seconds"].pop(key, None)
        if record["status"] == "completed":
            if not record["recovery"]["business_recovery_verified"]:
                finalization_error("final_workload", RuntimeError("Final workload did not retain sustained business recovery"))
            if not eligible_healthy(snapshot) or any(i["state"] != "resolved" for i in incidents):
                finalization_error("final_detector", RuntimeError("Final detector evidence is not healthy, eligible and resolved"))
        record["workload_summary"] = {"requests": len(rows), "status_counts": dict(Counter(str(r["status"]) for r in rows)),
                                      "valid_responses": sum(r["valid_response"] for r in rows),
                                      "transport_errors": sum(r.get("transport_error") is not None for r in rows),
                                      "schedule": "closed-loop workers; fixed delay after each completion"}
        stamp("finished_at")
        record["evaluation"] = evaluate_trial(record)
        atomic_json(path, record)
    print(f"{trial_id}: {record['status']}; detection={record['evaluation']['detection']['status']}; "
          f"recovery={record['evaluation']['recovery']['attribution']}", flush=True)
    return record


def save_summary(run_dir):
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(run_dir).glob("d5-*/trial.json"))]
    summary = summarize(records)
    # Trial repeatability is necessary but cannot override a failed run-level
    # final health check or backend shutdown. Preserve both decisions explicitly.
    metadata_path = Path(run_dir) / "run.json"
    metadata, metadata_error = {}, None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Run metadata must be an object")
    except (OSError, ValueError) as exc:
        metadata, metadata_error = {}, f"{type(exc).__name__}: {exc}"
    try:
        finished = datetime.fromisoformat(metadata.get("finished_at", "").replace("Z", "+00:00"))
        finished_valid = finished.tzinfo is not None
    except (TypeError, ValueError, AttributeError):
        finished_valid = False
    final_health_verified = (metadata.get("final_health_verified") is True
                             and isinstance(metadata.get("final_health"), dict)
                             and bool(metadata["final_health"]))
    shutdown_verified = metadata.get("shutdown_verified") is True
    finalized = (metadata.get("status") == "completed" and final_health_verified
                 and shutdown_verified and finished_valid)
    summary["run_finalization"] = {"passed": finalized, "status": metadata.get("status", "missing"),
                                   "final_health_verified": final_health_verified,
                                   "shutdown_verified": shutdown_verified,
                                   "finished_at": metadata.get("finished_at"), "metadata_error": metadata_error}
    summary["acceptance"]["trials_passed"] = summary["acceptance"]["passed"]
    summary["acceptance"]["run_finalization_passed"] = finalized
    summary["acceptance"]["passed"] = summary["acceptance"]["trials_passed"] and finalized
    atomic_json(Path(run_dir) / "summary.json", summary)
    with (Path(run_dir) / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["trial_id", "scenario", "backend", "status", "trial_passed", "detection", "detection_seconds",
                  "business_recovery_seconds", "recovery_attribution"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in summary["trials"]:
            writer.writerow({k: row[k] for k in fields[:5]} | {
                "detection": row["detection"]["status"], "detection_seconds": row["detection"]["detection_latency_seconds"],
                "business_recovery_seconds": row["recovery"]["business_recovery_seconds"],
                "recovery_attribution": row["recovery"]["attribution"]})
    return summary


def execute_plan(plan, output):
    run_dir = create_trial_directory(output, "run-" + uuid4().hex[:12])
    atomic_json(run_dir / "plan.json", plan)
    source = source_provenance()
    atomic_json(run_dir / "source.json", source)
    atomic_json(run_dir / "rule-config.json", {"rule_version": RULE_VERSION, "holds_seconds": HOLDS,
                "max_collection_gap_seconds": MAX_GAP, "recovery_hold_seconds": RECOVERY_HOLD,
                "window_seconds": WINDOW, "max_sample_age_seconds": MAX_AGE,
                "high_error_rate": .2, "error_clear": .05, "high_latency_seconds": 1., "latency_clear_seconds": .5,
                "minimum_observed_requests": 20, "executor": "none"})
    backend = None
    metadata = {"started_at": utc(), "backend": plan["backend"], "status": "preflight", "source": source,
                "final_health_verified": False, "shutdown_verified": False}
    try:
        if plan["backend"] == "kubernetes":
            from benchmark_kubernetes import KubernetesBackend
            backend = KubernetesBackend(run_dir)
        else:
            from benchmark_local import LocalProcessBackend
            backend = LocalProcessBackend(run_dir)
        with lab.recovery_lock():
            try:
                metadata["environment"] = backend.preflight()
                atomic_json(run_dir / "run.json", metadata)
                backend.start()
                for entry in plan["trials"]:
                    record = run_trial(backend, plan, entry, run_dir, source)
                    save_summary(run_dir)
                    if (record["status"] != "completed" or not record["recovery"].get("cleanup_verified")
                            or not record["evaluation"]["trial_passed"]):
                        raise RuntimeError("Run stopped after unsuccessful trial; inspect retained artifacts before another fault")
                metadata["final_health"] = backend.final_check("d5-run-final")
                metadata["final_health_verified"] = True
                metadata["status"] = "completed"
            finally:
                backend.close()
                metadata["shutdown_verified"] = True
                backend = None
    except BaseException as exc:
        metadata.update(status="aborted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
                        error=f"{type(exc).__name__}: {exc}")
    finally:
        if backend is not None:
            try:
                backend.close()
                metadata["shutdown_verified"] = True
            except Exception as exc:
                metadata["shutdown_error"] = str(exc)
                metadata["status"] = "failed"
        metadata["finished_at"] = utc()
        atomic_json(run_dir / "run.json", metadata)
        summary = save_summary(run_dir)
    print(json.dumps({"run_directory": str(run_dir), "run_status": metadata["status"],
                      "attempts": summary["attempts"], "successful_executions": summary["successful_executions"],
                      "kubernetes_acceptance": summary["acceptance"]}, indent=2), flush=True)
    return 0 if metadata["status"] == "completed" and summary["successful_executions"] == len(plan["trials"]) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="Print plan; --execute explicitly enables scoped fault injection")
    run.add_argument("--execute", action="store_true")
    run.add_argument("--backend", choices=("kubernetes", "local-process"), default="kubernetes")
    run.add_argument("--scenario", action="append", choices=("process_crash", "http_5xx", "latency"))
    run.add_argument("--repeats", type=int, default=2)
    run.add_argument("--seed", type=int, default=5)
    run.add_argument("--duration-seconds", type=float, default=90)
    run.add_argument("--baseline-seconds", type=float, default=75)
    run.add_argument("--recovery-timeout-seconds", type=float, default=180)
    run.add_argument("--output", type=Path, default=ROOT / "evidence/day5")
    summary = sub.add_parser("summarize")
    summary.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    if args.action == "summarize":
        print(json.dumps(save_summary(args.directory), indent=2))
        return 0
    plan = build_plan(scenarios=args.scenario, repeats=args.repeats, seed=args.seed, backend=args.backend,
                      duration_seconds=args.duration_seconds, baseline_seconds=args.baseline_seconds,
                      recovery_timeout_seconds=args.recovery_timeout_seconds)
    if not args.execute:
        print(json.dumps({"dry_run": True, "plan": plan}, indent=2))
        return 0
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    return execute_plan(plan, args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
