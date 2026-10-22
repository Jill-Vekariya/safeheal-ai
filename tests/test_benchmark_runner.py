"""Runner control-flow checks with controlled clocks and no live mutations."""
import json
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark
from benchmark_core import build_plan, evaluate_trial, utc
from services.incidents.telemetry import SERVICES, ServiceEvidence, Snapshot


def healthy_snapshot(at):
    return Snapshot(at, {service: ServiceEvidence(True, at, 100.0, 0.0, 0.05, at)
                         for service in SERVICES}, raw={"fixture": True})


def response(start, finish, *, valid=True, duration=0.05):
    return {"started_elapsed_seconds": start, "finished_elapsed_seconds": finish,
            "finished_at": utc(1800000000 + finish), "valid_response": valid,
            "elapsed_seconds": duration, "status": 201 if valid else 503}


def test_default_dry_run_does_not_create_artifacts_or_discover_cluster(tmp_path, monkeypatch, capsys):
    output = tmp_path / "not-created"
    def forbidden(*args, **kwargs):
        raise AssertionError("Dry-run must not discover a target, start services, or execute faults")
    monkeypatch.setattr(benchmark, "execute_plan", forbidden)
    monkeypatch.setattr(benchmark, "source_provenance", forbidden)
    monkeypatch.setattr(benchmark.lab, "guard_cluster", forbidden)
    assert benchmark.main(["run", "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["dry_run"] is True
    assert len(result["plan"]["trials"]) == 6
    assert result["plan"]["backend"] == "kubernetes"
    assert not output.exists()


def test_recovery_requires_three_healthy_completions_over_two_seconds():
    assert benchmark.sustained_recovery([response(11, 11.1), response(14, 14.1)], 10) is None
    assert benchmark.sustained_recovery([response(11, 11.1), response(11.2, 11.3), response(12, 12.1)], 10) is None
    rows = [response(11, 11.1), response(12, 12.1), response(13.1, 13.2)]
    assert benchmark.sustained_recovery(rows, 10) == (rows[0], rows[2])


def test_late_bad_completion_breaks_recovery_even_when_other_workers_succeeded():
    rows = [response(11, 11.1), response(12, 12.1), response(13.1, 13.2),
            response(10.5, 14.0, valid=False), response(15, 15.1)]
    assert benchmark.sustained_recovery(rows, 10) is None
    rows += [response(16, 16.1), response(17.1, 17.2)]
    assert benchmark.sustained_recovery(list(reversed(rows)), 10) == (rows[4], rows[6])


def test_slow_success_is_not_healthy_recovery_and_preinjection_rows_are_excluded():
    rows = [response(1, 11), response(2, 12), response(3, 13)]
    assert benchmark.sustained_recovery(rows, 10) is None
    assert not benchmark.healthy_response(response(10, 11.3, duration=1.3))


@pytest.mark.parametrize("body", [
    {"order_id": "wrong", "payment_id": "p", "amount_cents": 2000, "status": "simulated_paid"},
    {"order_id": "trial", "payment_id": "p", "amount_cents": 1000, "status": "simulated_paid"},
    {"order_id": "trial", "payment_id": "", "amount_cents": 2000, "status": "simulated_paid"},
])
def test_payment_probe_rejects_mismatched_success_receipt(body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(201, json=body))) as client:
        sample = benchmark.request_sample(client, "http://test", "trial", time.monotonic(), payment=True)
    assert sample["status"] == 201
    assert not sample["valid_response"]


def test_workload_worker_exception_is_visible_and_stops_work(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("injected journal failure")
    workload = benchmark.Workload(SimpleNamespace(gateway_url="http://unused"), "trial", time.monotonic(),
                                  tmp_path, build_plan())
    monkeypatch.setattr(benchmark, "request_sample", fail)
    workload._worker(0)  # Synchronous worker invocation; no network request occurs.
    assert workload.stop_event.is_set()
    assert "injected journal failure" in workload.errors[0]
    with pytest.raises(RuntimeError, match="injected journal failure"):
        workload.rows()
    # The outer runner owns failed-trial classification; close must release the
    # file even if a worker failed before producing its first row.
    try:
        workload.close()
    except RuntimeError:
        pass
    assert workload.journal.handle.closed


def test_observer_retains_opening_diagnosis_through_resolution_and_closes_database(tmp_path):
    observer = benchmark.DetectorObserver("http://127.0.0.1:19090", tmp_path, 0.001)
    finished = threading.Event()
    snapshots = []
    for seconds in range(0, 36, 5):
        snapshot = healthy_snapshot(1800000000.0 + seconds)
        if seconds <= 15:
            snapshot.services["payment"].errors = 30.0
        snapshots.append(snapshot)
    class Collector:
        def collect(self):
            snapshot = snapshots.pop(0)
            if not snapshots:
                observer.stop_event.set()
                finished.set()
            return snapshot
    observer.collector = Collector()
    observer.start()
    assert finished.wait(3), "Controlled observer did not consume its finite snapshots"
    observer.close()
    latest, incidents, errors = observer.state()
    assert not errors
    incident = next(item for item in incidents if item["service"] == "payment" and item["rule"] == "high_error_rate")
    assert incident["state"] == "resolved"
    assert incident["diagnosis"]["classification"] == "recovered"
    assert incident["first_open_diagnosis"]["classification"] == "server_error_spike"
    assert incident["first_open_observed_at"]
    assert not observer.thread.is_alive()
    assert observer.journal.handle.closed
    assert len((tmp_path / "telemetry.jsonl").read_text().splitlines()) == 8


def test_failed_baseline_worker_is_saved_without_injecting(tmp_path, monkeypatch):
    instances = {}
    class Workload:
        def __init__(self, *args):
            self.samples, self.errors, self.closed = [], ["OSError: fixture worker failed"], False
            instances["workload"] = self
        def start(self):
            pass
        def rows(self):
            raise RuntimeError("Workload observer failed: fixture worker failed")
        def close(self):
            self.closed = True
    class Observer:
        def __init__(self, *args):
            self.closed = False
            instances["observer"] = self
        def start(self):
            pass
        def state(self):
            return None, [], []
        def close(self):
            self.closed = True
    def forbidden(*args, **kwargs):
        raise AssertionError("No injection or cleanup belongs to a failed baseline")
    backend = SimpleNamespace(kind="local-process", gateway_url="http://unused", prometheus_url="http://unused",
                              inject=forbidden, cleanup=forbidden)
    monkeypatch.setattr(benchmark, "Workload", Workload)
    monkeypatch.setattr(benchmark, "DetectorObserver", Observer)
    plan = build_plan(scenarios=["process_crash"], repeats=1)
    result = benchmark.run_trial(backend, plan, plan["trials"][0], tmp_path, {})
    saved = json.loads(next(tmp_path.glob("d5-*/trial.json")).read_text())
    assert result == saved
    assert saved["status"] == "failed"
    assert "fixture worker failed" in saved["error"]
    assert saved["workload_errors"] == instances["workload"].errors
    assert instances["workload"].closed and instances["observer"].closed
    assert not saved["ground_truth"]["injection_verified"]


def test_observer_initialization_failure_finalizes_trial_and_closes_workload(tmp_path, monkeypatch):
    instances = {}
    class Workload:
        def __init__(self, *args):
            self.samples, self.errors, self.closed = [], [], False
            instances["workload"] = self
        def close(self):
            self.closed = True
    def fail(*args, **kwargs):
        raise OSError("fixture detector database unavailable")
    monkeypatch.setattr(benchmark, "Workload", Workload)
    monkeypatch.setattr(benchmark, "DetectorObserver", fail)
    backend = SimpleNamespace(kind="local-process", gateway_url="http://unused", prometheus_url="http://unused")
    plan = build_plan(scenarios=["process_crash"], repeats=1)
    result = benchmark.run_trial(backend, plan, plan["trials"][0], tmp_path, {})
    saved = json.loads(next(tmp_path.glob("d5-*/trial.json")).read_text())
    assert result == saved
    assert saved["status"] == "failed"
    assert "detector database unavailable" in saved["error"]
    assert instances["workload"].closed


def test_observer_constructor_closes_database_when_journal_creation_fails(tmp_path, monkeypatch):
    controller = SimpleNamespace(closed=False)
    def close():
        controller.closed = True
    controller.close = close
    monkeypatch.setattr(benchmark, "Controller", lambda path: controller)
    def fail(path):
        raise OSError("fixture journal unavailable")
    monkeypatch.setattr(benchmark, "Journal", fail)
    with pytest.raises(OSError, match="journal unavailable"):
        benchmark.DetectorObserver("http://127.0.0.1:19090", tmp_path, 5)
    assert controller.closed


@pytest.mark.parametrize("late_error", [None, "workload", "detector", "request", "slow_request",
                                       "restart", "not_ready", "incident", "ineligible"])
def test_finalization_rechecks_late_evidence_after_final_health(tmp_path, monkeypatch, late_error):
    """Drive the runner to final health, then change its final evidence.

    This exercises the finalization race without starting a service or waiting
    through real benchmark windows. All timestamps are explicitly fixture data.
    """
    clock = {"elapsed": 0.0, "injected": None, "finished_check": False}
    epoch = 1800000000.0
    def monotonic():
        clock["elapsed"] += 0.01
        return clock["elapsed"]
    def wall():
        return epoch + clock["elapsed"]
    def sleep(seconds):
        clock["elapsed"] += seconds
    monkeypatch.setattr(benchmark, "time", SimpleNamespace(monotonic=monotonic, time=wall, sleep=sleep))
    monkeypatch.setattr(benchmark, "utc", lambda at=None: utc(wall() if at is None else at))
    instances = {}
    class Workload:
        def __init__(self, *args):
            self.samples, self.errors = [], []
            instances["workload"] = self
        def start(self):
            pass
        def rows(self):
            if clock["injected"] is None:
                self.samples = [response(0, 0.01) for _ in range(20)]
            else:
                base = clock["injected"]
                self.samples = [response(base + 0.1, base + 0.2, valid=False)]
                self.samples += [response(base + x, base + x + 0.1) for x in (1, 2, 3.1)
                                 if clock["elapsed"] >= base + x + 0.1]
            return list(self.samples)
        def close(self):
            if late_error == "workload" and clock["finished_check"]:
                self.errors.append("OSError: fixture late workload failure")
            elif late_error in ("request", "slow_request") and clock["finished_check"]:
                clock["elapsed"] += 1.5
                self.samples.append(response(clock["elapsed"] - 1.4, clock["elapsed"],
                                             valid=late_error != "request", duration=1.4))
    class Observer:
        def __init__(self, *args):
            self.errors = []
            self.closed = False
        def start(self):
            pass
        def state(self):
            snapshot, incidents = healthy_snapshot(wall()), []
            if self.closed and late_error == "incident":
                incidents = [{"id": "late-open", "state": "open", "service": "payment",
                              "rule": "high_error_rate", "detected_at": utc(wall() - 1),
                              "opened_at": utc(wall())}]
            if self.closed and late_error == "ineligible":
                snapshot.services["payment"].requests = None
            return snapshot, incidents, list(self.errors)
        def close(self):
            self.closed = True
            if late_error == "detector" and clock["finished_check"]:
                self.errors.append({"at": utc(wall()), "error": "OSError: fixture late detector failure"})
    class Backend:
        kind, gateway_url, prometheus_url = "local-process", "http://unused", "http://unused"
        def snapshot(self):
            result = {role: {"uid": role, "container_id": role + "-0", "restart_count": 0, "ready": True}
                      for role in SERVICES}
            if clock["injected"] is not None:
                result["payment"].update(container_id="payment-1", restart_count=1)
            if clock["finished_check"] and late_error == "restart":
                result["payment"].update(container_id="payment-2", restart_count=2)
            if clock["finished_check"] and late_error == "not_ready":
                result["payment"]["ready"] = False
            return result
        def validate_target(self):
            return self.snapshot()["payment"]
        def inject(self, *args):
            clock["injected"] = clock["elapsed"]
            return {"injection_verified": True}
        def cleanup(self, *args):
            return {"verified": True}
        def final_check(self, *args):
            clock["finished_check"] = True
            return {"fixture": "healthy"}
    monkeypatch.setattr(benchmark, "Workload", Workload)
    monkeypatch.setattr(benchmark, "DetectorObserver", Observer)
    plan = build_plan(scenarios=["process_crash"], repeats=1, baseline_seconds=0,
                      recovery_timeout_seconds=180, backend="local-process")
    result = benchmark.run_trial(Backend(), plan, plan["trials"][0], tmp_path, {})
    assert clock["finished_check"], "The fixture must reach final health before introducing the evidence failure"
    assert result["status"] == ("completed" if late_error is None else "failed")
    assert result["evaluation"]["trial_passed"] is (late_error is None)
    if late_error == "workload":
        assert "fixture late workload failure" in result["workload_errors"][0]
    elif late_error == "detector":
        assert "fixture late detector failure" in result["detector"]["observer_errors"][0]["error"]
    elif late_error in ("request", "slow_request"):
        assert not result["recovery"]["business_recovery_verified"]
        assert "sustained_recovery_at" not in result["timestamps"]
        assert "first_business_recovered_at" not in result["monotonic_elapsed_seconds"]
        assert result["workload_summary"]["requests"] == len(instances["workload"].samples)
        assert result["workload_summary"]["requests"] == 5
    elif late_error == "restart":
        assert result["recovery"]["after"]["payment"]["container_id"] == "payment-2"
        assert result["recovery"]["native_ready_identity"]["container_id"] == "payment-1"
    elif late_error == "not_ready":
        assert not result["recovery"]["after"]["payment"]["ready"]
    elif late_error in ("incident", "ineligible"):
        assert any(e["stage"] == "final_detector" for e in result["finalization_errors"])
    saved = json.loads(next(tmp_path.glob("d5-*/trial.json")).read_text())
    assert saved == result


def successful_fixture(entry):
    """Explicit fabricated evidence for control-flow tests, never a live result."""
    epoch = 1800000000.0
    before = {role: {"uid": role + "-pod", "container_id": role + "-0", "restart_count": 0,
                     "ready": True} for role in SERVICES}
    after = deepcopy(before)
    mechanism = "fault_expiry"
    if entry["scenario"] == "process_crash":
        after["payment"].update(container_id="payment-1", restart_count=1,
                                last_state={"terminated": {"containerID": "payment-0", "exitCode": 137,
                                                           "finishedAt": utc(epoch + 1)}})
        mechanism = "native_kubernetes"
    record = {"trial_id": f"d5-fixture-{entry['sequence']}", **entry, "backend": "kubernetes",
              "status": "completed", "source": {"fixture": True}, "timestamps": {
                  "injection_requested_at": utc(epoch), "injection_confirmed_at": utc(epoch + .1),
                  "fault_effect_observed_at": utc(epoch + 1), "fault_removed_at": utc(epoch + 90),
                  "sustained_recovery_at": utc(epoch + 95), "finished_at": utc(epoch + 180)},
              "ground_truth": {"target_service": "payment", "injection_verified": True, "effect_verified": True},
              "detector": {"eligible": True, "incidents": [], "baseline_incident_ids": [],
                           "observation_end_at": utc(epoch + 180)},
              "recovery": {"before": before, "after": after, "native_ready_at": utc(epoch + 5),
                           "cleanup_verified": True, "business_recovery_verified": True, "mechanism": mechanism}}
    record["evaluation"] = evaluate_trial(record)
    assert record["evaluation"]["trial_passed"]
    return record


@pytest.mark.parametrize("failure_stage", [None, "final_health", "shutdown"])
def test_run_finalization_failure_cannot_publish_passed_acceptance(tmp_path, monkeypatch, failure_stage):
    """Six passing trials cannot hide a later run-level health/cleanup failure."""
    class Backend:
        def preflight(self):
            return {"fixture": True}
        def start(self):
            pass
        def final_check(self, *args):
            if failure_stage == "final_health":
                raise RuntimeError("fixture final run health failed")
            return {"fixture": "final run healthy"}
        def close(self):
            if failure_stage == "shutdown":
                raise RuntimeError("fixture backend shutdown failed")
    monkeypatch.setitem(sys.modules, "benchmark_kubernetes", SimpleNamespace(KubernetesBackend=lambda path: Backend()))
    monkeypatch.setattr(benchmark.lab, "recovery_lock", nullcontext)
    monkeypatch.setattr(benchmark, "source_provenance", lambda: {"fixture": True})
    def fake_trial(backend, plan, entry, folder, source):
        record = successful_fixture(entry)
        target = Path(folder) / record["trial_id"]
        target.mkdir()
        (target / "trial.json").write_text(json.dumps(record), encoding="utf-8")
        return record
    monkeypatch.setattr(benchmark, "run_trial", fake_trial)
    code = benchmark.execute_plan(build_plan(), tmp_path)
    folder = next(tmp_path.glob("run-*"))
    metadata = json.loads((folder / "run.json").read_text())
    saved = json.loads((folder / "summary.json").read_text())
    assert saved["attempts"] == saved["successful_executions"] == 6
    assert saved["acceptance"]["trials_passed"]
    assert saved["acceptance"]["passed"] is (failure_stage is None)
    assert saved["run_finalization"]["passed"] is (failure_stage is None)
    assert code == (0 if failure_stage is None else 1)
    assert metadata["status"] == ("completed" if failure_stage is None else "failed")
    if failure_stage is not None:
        assert "fixture" in metadata["error"]
    # Re-reading durable records must retain the same decision, not overwrite
    # failed run finalization with the six otherwise successful trial rows.
    assert benchmark.save_summary(folder) == saved


@pytest.mark.parametrize("metadata", [None, {}, {"status": "completed"},
    {"status": "completed", "final_health_verified": True, "final_health": {"fixture": True},
     "shutdown_verified": True, "finished_at": "missing-timezone"},
])
def test_missing_or_partial_run_metadata_cannot_claim_acceptance(tmp_path, metadata):
    for entry in build_plan()["trials"]:
        record = successful_fixture(entry)
        folder = tmp_path / record["trial_id"]
        folder.mkdir()
        (folder / "trial.json").write_text(json.dumps(record), encoding="utf-8")
    if metadata is not None:
        (tmp_path / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    summary = benchmark.save_summary(tmp_path)
    assert summary["successful_executions"] == 6
    assert summary["acceptance"]["trials_passed"]
    assert not summary["acceptance"]["passed"]
