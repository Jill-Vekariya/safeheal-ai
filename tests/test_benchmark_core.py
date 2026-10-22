"""Evaluation guardrails: failed experiments and ambiguous evidence stay visible."""
from copy import deepcopy
import json

import pytest

from scripts.benchmark_core import (SCENARIOS, atomic_json, build_plan, create_trial_directory,
                                    evaluate_trial, summarize, utc)


T0 = 1_800_000_000.


def trial(scenario="process_crash", backend="kubernetes", trial_id="trial-one"):
    before = {service: {"uid": service + "-pod", "container_id": service + "-old",
                        "restart_count": 0, "ready": True} for service in ("gateway", "order", "payment")}
    after = deepcopy(before)
    mechanism = "fault_expiry"
    if scenario == "process_crash":
        after["payment"].update(container_id="payment-new", restart_count=1,
                                last_state={"terminated": {"containerID": "payment-old",
                                                           "exitCode": 137, "finishedAt": utc(T0 + 1)}})
        mechanism = "native_kubernetes" if backend == "kubernetes" else "local_process_supervisor"
    return {"trial_id": trial_id, "scenario": scenario, "repetition": 1, "backend": backend,
            "status": "completed", "timestamps": {
                "injection_requested_at": utc(T0), "injection_confirmed_at": utc(T0 + .1),
                "fault_effect_observed_at": utc(T0 + 1), "fault_removed_at": utc(T0 + 45),
                "sustained_recovery_at": utc(T0 + 50), "finished_at": utc(T0 + 120)},
            "ground_truth": {"target_service": "payment", "injection_verified": True, "effect_verified": True},
            "detector": {"eligible": True, "baseline_incident_ids": [], "observation_end_at": utc(T0 + 120),
                         "incidents": []},
            "recovery": {"before": before, "after": after, "native_ready_at": utc(T0 + 4),
                         "cleanup_verified": True, "business_recovery_verified": True,
                         "mechanism": mechanism, "supervisor_restart_verified": True}}


def incident(**changes):
    return {"id": "incident-one", "service": "payment", "rule": "scrape_unavailable",
            "state": "resolved", "detected_at": utc(T0 + 5), "opened_at": utc(T0 + 15),
            "resolved_at": utc(T0 + 70), "first_open_observed_at": utc(T0 + 16),
            "first_open_diagnosis": {"service": "payment", "classification": "service_or_metrics_endpoint_unavailable"},
            "diagnosis": {"service": "payment", "classification": "recovered"}, **changes}


def test_seeded_plan_is_reproducible_and_has_every_repeat():
    plan = build_plan()
    assert plan["duration_seconds"] == 90
    assert plan == build_plan()
    assert plan["trials"] != build_plan(seed=6)["trials"]
    assert {(r["scenario"], r["repetition"]) for r in plan["trials"]} == {
        (scenario, repeat) for scenario in SCENARIOS for repeat in (1, 2)}
    assert [r["sequence"] for r in plan["trials"]] == list(range(1, 7))
    assert "pod" not in json.dumps(plan)


@pytest.mark.parametrize("arguments", [
    {"scenarios": []}, {"scenarios": ["latency", "latency"]}, {"scenarios": ["wrong"]},
    {"scenarios": "latency"}, {"backend": "production"}, {"repeats": 0}, {"repeats": True},
    {"duration_seconds": float("nan")}, {"poll_seconds": float("inf")},
    {"duration_seconds": 120.001},
    {"request_interval_seconds": 0}, {"concurrency": 17}, {"seed": -1},
])
def test_plan_rejects_unbounded_or_ambiguous_input(arguments):
    with pytest.raises(ValueError):
        build_plan(**arguments)


def test_plan_duration_respects_application_lease_maximum():
    assert build_plan(duration_seconds=120)["duration_seconds"] == 120


def test_trial_directory_never_overwrites_prior_attempt(tmp_path):
    path = create_trial_directory(tmp_path, "attempt-1")
    atomic_json(path / "trial.json", {"status": "failed"})
    with pytest.raises(FileExistsError):
        create_trial_directory(tmp_path, "attempt-1")
    with pytest.raises(ValueError):
        create_trial_directory(tmp_path, "../escape")
    assert json.loads((path / "trial.json").read_text())["status"] == "failed"


def test_failed_checkpoint_keeps_previous_record(tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    atomic_json(path, {"status": "started"})
    with pytest.raises(ValueError):
        atomic_json(path, {"value": float("nan")})
    def fail_replace(*_):
        raise OSError("simulated disk replacement failure")
    monkeypatch.setattr("scripts.benchmark_core.os.replace", fail_replace)
    with pytest.raises(OSError):
        atomic_json(path, {"status": "completed"})
    assert json.loads(path.read_text()) == {"status": "started"}
    assert list(tmp_path.iterdir()) == [path]


def test_brief_native_crash_can_recover_but_be_missed_by_rules():
    result = evaluate_trial(trial())
    assert result["trial_passed"]
    assert result["detection"]["status"] == "missed"
    assert result["detection"]["detection_latency_seconds"] is None
    assert result["detection"]["censored"]
    assert result["recovery"]["attribution"] == "native_kubernetes"
    assert not result["recovery"]["rule_executed_recovery"]


def test_only_opened_matching_new_incidents_count_and_opening_diagnosis_is_preserved():
    record = trial()
    record["detector"]["incidents"] = [incident()]
    original = deepcopy(record)
    result = evaluate_trial(record)
    assert record == original
    detection = result["detection"]
    assert detection["detected"] and detection["detection_latency_seconds"] == 15.
    assert detection["first_open_diagnosis"]["classification"] != "recovered"
    assert detection["diagnosis_target_match"]
    assert detection["all_matched_resolved"]


@pytest.mark.parametrize("changes", [
    {"opened_at": None, "state": "pending"},
    {"detected_at": utc(T0 - 5)},
    {"opened_at": utc(T0 + 121)},
    {"rule": "telemetry_unavailable"},
    {"service": "unrelated"},
    {"opened_at": "2027-01-15T08:00:15"},  # No timezone is ambiguous.
])
def test_pending_historical_unrelated_or_invalid_records_are_not_detections(changes):
    record = trial()
    record["detector"]["incidents"] = [incident(**changes)]
    assert not evaluate_trial(record)["detection"]["detected"]


def test_baseline_id_cannot_be_reused_as_new_fault_detection():
    record = trial()
    record["detector"]["baseline_incident_ids"] = ["incident-one"]
    record["detector"]["incidents"] = [incident()]
    assert not evaluate_trial(record)["detection"]["detected"]


def test_missing_telemetry_is_ineligible_not_zero_latency_or_a_miss():
    record = trial()
    record["detector"]["eligible"] = False
    result = evaluate_trial(record)["detection"]
    assert result["status"] == "not_eligible" and not result["censored"]
    assert result["detection_latency_seconds"] is None


@pytest.mark.parametrize("mutation", ["new_pod", "same_container", "same_count", "not_ready", "upstream_restart", "no_ready_time"])
def test_native_recovery_requires_all_identity_and_readiness_evidence(mutation):
    record = trial()
    state = record["recovery"]["after"]["payment"]
    if mutation == "new_pod":
        state["uid"] = "replacement-pod"
    elif mutation == "same_container":
        state["container_id"] = "payment-old"
    elif mutation == "same_count":
        state["restart_count"] = 0
    elif mutation == "not_ready":
        state["ready"] = False
    elif mutation == "upstream_restart":
        record["recovery"]["after"]["gateway"]["restart_count"] = 1
    else:
        record["recovery"]["native_ready_at"] = None
    result = evaluate_trial(record)
    assert not result["trial_passed"] and not result["recovery"]["native_restart_verified"]


@pytest.mark.parametrize("change", [
    {"containerID": "containerd://some-other-container"},
    {"exitCode": None}, {"exitCode": True}, {"exitCode": "137"}, {"exitCode": -1},
    {"finishedAt": None}, {"finishedAt": "not-a-timestamp"},
    {"finishedAt": utc(T0 - 1.001)}, {"finishedAt": utc(T0 + 4.001)},
])
def test_native_recovery_rejects_unrelated_or_invalid_termination_evidence(change):
    record = trial()
    record["recovery"]["after"]["payment"]["last_state"]["terminated"].update(change)
    result = evaluate_trial(record)
    assert not result["trial_passed"]
    assert not result["recovery"]["native_restart_verified"]


def test_native_recovery_requires_termination_record_and_accepts_second_precision():
    record = trial()
    del record["recovery"]["after"]["payment"]["last_state"]
    assert not evaluate_trial(record)["recovery"]["native_restart_verified"]
    record = trial()
    record["recovery"]["before"]["payment"]["container_id"] = "containerd://original"
    terminated = record["recovery"]["after"]["payment"]["last_state"]["terminated"]
    terminated.update(containerID="containerd://original", finishedAt=utc(T0))
    record["timestamps"]["injection_requested_at"] = utc(T0 + .75)
    record["timestamps"]["injection_confirmed_at"] = utc(T0 + .8)
    result = evaluate_trial(record)
    assert result["trial_passed"] and result["recovery"]["native_restart_verified"]
    # Latency is based on the host's request/ready observations, never finishedAt.
    assert result["recovery"]["native_ready_latency_seconds"] == 3.25


def test_local_supervisor_does_not_require_kubernetes_termination_fields():
    record = trial(backend="local-process")
    record["recovery"]["after"]["payment"].pop("last_state")
    result = evaluate_trial(record)
    assert result["trial_passed"]
    assert result["recovery"]["attribution"] == "local_process_supervisor"
    assert not result["recovery"]["native_restart_verified"]


@pytest.mark.parametrize("scenario", ["http_5xx", "latency"])
def test_application_expiry_never_gets_native_or_rule_recovery_credit(scenario):
    record = trial(scenario)
    result = evaluate_trial(record)
    assert result["trial_passed"]
    assert result["recovery"]["attribution"] == "fault_expiry"
    assert not result["recovery"]["native_restart_verified"]
    assert not result["recovery"]["rule_executed_recovery"]
    record["recovery"]["mechanism"] = "native_kubernetes"
    assert not evaluate_trial(record)["trial_passed"]


def test_local_supervisor_evidence_does_not_establish_kubernetes_recovery():
    record = trial(backend="local-process")
    result = evaluate_trial(record)
    assert result["trial_passed"]
    assert result["recovery"]["attribution"] == "local_process_supervisor"
    assert not result["recovery"]["native_restart_verified"]


@pytest.mark.parametrize("failure", ["unverified_effect", "cleanup_failed", "no_business_recovery", "aborted", "missing_time"])
def test_execution_failures_cannot_be_hidden_by_detection_success(failure):
    record = trial()
    record["detector"]["incidents"] = [incident()]
    if failure == "unverified_effect":
        record["ground_truth"]["effect_verified"] = False
    elif failure == "cleanup_failed":
        record["recovery"]["cleanup_verified"] = False
    elif failure == "no_business_recovery":
        record["recovery"]["business_recovery_verified"] = False
    elif failure == "aborted":
        record["status"] = "aborted"
    else:
        record["timestamps"]["injection_confirmed_at"] = None
    result = evaluate_trial(record)
    assert not result["trial_passed"] and result["reasons"]


def test_summary_requires_repeated_real_trials_and_retains_failures():
    records = [trial(s, trial_id=f"{s}-{r}") for s in SCENARIOS for r in (1, 2)]
    failure = trial("latency", trial_id="failed-attempt")
    failure["status"] = "failed"
    records.append(failure)
    result = summarize(records)
    assert result["acceptance"]["passed"]
    assert result["attempts"] == 7 and result["successful_executions"] == 6
    assert result["execution_success_rate"] == pytest.approx(6 / 7)
    assert result["by_scenario"]["latency"]["attempts"] == 3
    assert result["by_scenario"]["latency"]["execution_success_rate"] == pytest.approx(2 / 3)
    assert len(result["trials"]) == 7


def test_local_successes_and_duplicate_artifacts_never_manufacture_acceptance():
    records = [trial(s, backend="local-process", trial_id=f"{s}-{r}") for s in SCENARIOS for r in (1, 2)]
    assert not summarize(records)["acceptance"]["passed"]
    real = [trial(s, trial_id=f"{s}-1") for s in SCENARIOS]
    result = summarize(real + deepcopy(real))
    assert not result["acceptance"]["passed"]
    assert len(result["duplicate_trial_ids"]) == 3


def test_empty_and_not_injected_trials_have_no_fabricated_metrics():
    record = {"trial_id": "failed-preflight", "scenario": "process_crash", "backend": "kubernetes", "status": "failed"}
    result = evaluate_trial(record)
    assert not result["trial_passed"]
    assert result["detection"]["status"] == "not_eligible"
    assert result["recovery"]["business_recovery_seconds"] is None
    assert summarize([])["execution_success_rate"] is None
    assert not summarize([])["acceptance"]["passed"]
