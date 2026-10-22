"""Pure Day 5 plans, evidence evaluation and summaries; never injects a fault.

Record schema (all times accept UTC ISO strings or finite epoch seconds)::

    {
      "trial_id": "unique-id", "scenario": "process_crash", "repetition": 1,
      "backend": "kubernetes", "status": "completed",
      "timestamps": {"injection_requested_at": ..., "injection_confirmed_at": ...,
                     "fault_effect_observed_at": ..., "fault_removed_at": ...,
                     "first_business_recovered_at": ..., "sustained_recovery_at": ...,
                     "finished_at": ...},
      "ground_truth": {"target_service": "payment", "injection_verified": True,
                       "effect_verified": True, "expected_detection": [
                         {"service": "payment", "rule": "scrape_unavailable"}]},
      "detector": {"eligible": True, "baseline_incident_ids": [],
                   "observation_end_at": ..., "incidents": [controller_detail]},
      "recovery": {"before": {"payment": pod_state, "gateway": ..., "order": ...},
                   "after": {...}, "native_ready_at": ..., "cleanup_verified": True,
                   "business_recovery_verified": True, "mechanism": "native_kubernetes",
                   "supervisor_restart_verified": False}
    }

Controller details may additionally retain ``first_open_diagnosis`` and
``first_open_observed_at``. Final diagnoses often say only "recovered", so the
opening diagnosis must be captured by the runner. Native states use the existing
``k8s.pod_state`` shape: uid, container_id, restart_count, ready and
last_state.terminated. Native recovery requires the previous container's
termination record. Kubernetes finishedAt can have only second precision: the
identity check accepts up to one second before the host injection request, but
never uses that truncated timestamp to calculate a precise recovery duration.

Detection means a NEW, matching, OPENED incident, never a pending or telemetry
outage record. Primary latency is opened_at minus injection_requested_at; it is
not exact physical fault-onset latency. A brief crash can pass the execution
trial while the detector misses it. All counts retain failed attempts. The Day 5
gate requires real Kubernetes trials; a local supervisor or synthetic fixture
can never satisfy it. This module does not infer ground truth from detections.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
from uuid import uuid4


SCHEMA_VERSION = 1
SCENARIOS = ("process_crash", "http_5xx", "latency")
BACKENDS = ("kubernetes", "local-process", "synthetic")
SERVICES = ("gateway", "order", "payment")
EXPECTED_RULES = {
    "process_crash": ("scrape_unavailable", "high_error_rate", "high_latency"),
    "http_5xx": ("high_error_rate",),
    "latency": ("high_latency",),
}


def _number(name, value, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be in {low}..{high}")
    if integer and not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def utc(epoch=None):
    """Return an explicitly UTC ISO timestamp, defaulting to the current time."""
    if epoch is None:
        return datetime.now(timezone.utc).isoformat()
    _number("epoch", epoch, 0, 253402300799)
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _epoch(value):
    """Missing/invalid evidence times are unknown, never silently zero."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) and 0 <= value <= 253402300799 else None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return None
            result = parsed.timestamp()
            return result if math.isfinite(result) and result >= 0 else None
        except (ValueError, OverflowError, OSError):
            return None
    return None


def _elapsed(start, end):
    return round(end - start, 6) if start is not None and end is not None and end >= start else None


def build_plan(scenarios=None, repeats=2, seed=5, backend="kubernetes",
               duration_seconds=90, baseline_seconds=75, recovery_timeout_seconds=180,
               poll_seconds=5, request_interval_seconds=0.2, concurrency=4):
    """Build a seeded plan without discovering or changing any concrete target.

    Short timings support local engineering checks, not Kubernetes acceptance.
    The backend must enforce healthy telemetry/washout before each live fault.
    """
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS}")
    if isinstance(scenarios, str):
        raise ValueError("scenarios must be a sequence of scenario names")
    selected = list(SCENARIOS if scenarios is None else scenarios)
    if not selected or len(selected) > len(SCENARIOS):
        raise ValueError("Select one to three distinct scenarios")
    if any(s not in SCENARIOS for s in selected) or len(set(selected)) != len(selected):
        raise ValueError("Unknown or duplicate scenario")
    _number("repeats", repeats, 1, 20, integer=True)
    _number("seed", seed, 0, 2**32 - 1, integer=True)
    settings = {
        "duration_seconds": _number("duration_seconds", duration_seconds, 1, 120),
        "baseline_seconds": _number("baseline_seconds", baseline_seconds, 0, 600),
        "recovery_timeout_seconds": _number("recovery_timeout_seconds", recovery_timeout_seconds, 5, 900),
        "poll_seconds": _number("poll_seconds", poll_seconds, 0.1, 15),
        "request_interval_seconds": _number("request_interval_seconds", request_interval_seconds, 0.02, 10),
        "concurrency": _number("concurrency", concurrency, 1, 16, integer=True),
    }
    trials = [{"scenario": scenario, "repetition": repetition}
              for repetition in range(1, repeats + 1) for scenario in selected]
    random.Random(seed).shuffle(trials)
    for sequence, trial in enumerate(trials, 1):
        trial["sequence"] = sequence
    return {"schema_version": SCHEMA_VERSION, "kind": "benchmark_plan", "backend": backend,
            "scenarios": selected, "repeats": repeats, "seed": seed, **settings, "trials": trials}


def create_trial_directory(root, trial_id=None):
    """Reserve a new artifact directory exclusively; reruns cannot overwrite it."""
    trial_id = trial_id or f"trial-{uuid4().hex}"
    if not isinstance(trial_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", trial_id):
        raise ValueError("trial_id must be a safe, nonempty filename component")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / trial_id
    path.mkdir(mode=0o700, exist_ok=False)
    return path


def atomic_json(path, record):
    """Checkpoint JSON atomically, preserving the old checkpoint on write failure."""
    payload = json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def _uid(state):
    return state.get("uid") or state.get("pod_uid")


def _stable(before, after):
    count = before.get("restart_count")
    return bool(isinstance(count, int) and not isinstance(count, bool) and count >= 0
                and _uid(before) and before.get("container_id") and _uid(before) == _uid(after)
                and before.get("container_id") == after.get("container_id")
                and count == after.get("restart_count") and after.get("ready") is True)


def _native_restart(recovery, injection_at):
    before, after = recovery.get("before", {}), recovery.get("after", {})
    old, new = before.get("payment", {}), after.get("payment", {})
    old_count, new_count = old.get("restart_count"), new.get("restart_count")
    counts_valid = (isinstance(old_count, int) and not isinstance(old_count, bool)
                    and isinstance(new_count, int) and not isinstance(new_count, bool)
                    and old_count >= 0 and new_count > old_count)
    ready_at = _epoch(recovery.get("native_ready_at"))
    terminated = new.get("last_state", {}).get("terminated", {})
    exit_code = terminated.get("exitCode")
    finished_at = _epoch(terminated.get("finishedAt"))
    # Kubernetes serializes this event at second precision on some runtimes.
    # The tolerance validates event identity/order; it is NOT a duration value.
    termination_valid = (terminated.get("containerID") == old.get("container_id")
                         and isinstance(exit_code, int) and not isinstance(exit_code, bool)
                         and 0 <= exit_code <= 2**31 - 1
                         and injection_at is not None and ready_at is not None
                         and finished_at is not None and injection_at - 1 <= finished_at <= ready_at)
    return bool(_uid(old) and _uid(old) == _uid(new) and old.get("container_id")
                and new.get("container_id") and old["container_id"] != new["container_id"]
                and counts_valid and termination_valid and new.get("ready") is True
                and _elapsed(injection_at, ready_at) is not None
                and all(_stable(before.get(s, {}), after.get(s, {})) for s in ("gateway", "order")))


def expected_detection(scenario):
    """Predeclared symptom matchers, not labels inferred from detector output."""
    return [{"service": service, "rule": rule} for service in SERVICES
            for rule in EXPECTED_RULES.get(scenario, ())]


def evaluate_trial(record):
    """Return evaluation without modifying raw evidence.

    Stable public keys are ``trial_passed``, ``reasons``, ``detection`` and
    ``recovery``. Detection status is detected/missed/not_eligible. Recovery time
    describes host-observed sustained business verification, not exact downtime.
    Naming payment in a diagnosis is not proof of accurate physical root cause.
    """
    scenario, backend = record.get("scenario"), record.get("backend")
    times, truth = record.get("timestamps", {}), record.get("ground_truth", {})
    detector, recovery = record.get("detector", {}), record.get("recovery", {})
    injection_at = _epoch(times.get("injection_requested_at"))
    confirmed_at = _epoch(times.get("injection_confirmed_at"))
    effect_at = _epoch(times.get("fault_effect_observed_at"))
    finish_at = _epoch(times.get("finished_at"))
    end_at = _epoch(detector.get("observation_end_at"))
    if end_at is None:
        end_at = finish_at
    ground_truth_verified = (truth.get("target_service") == "payment"
                             and truth.get("injection_verified") is True
                             and truth.get("effect_verified") is True)
    observation_valid = _elapsed(injection_at, end_at) is not None
    eligible = detector.get("eligible") is True and ground_truth_verified and observation_valid
    baseline_ids = set(detector.get("baseline_incident_ids", []))
    matchers = truth.get("expected_detection", expected_detection(scenario))
    allowed = {(v["service"], v["rule"]) for v in expected_detection(scenario)}
    expected = {(v.get("service"), v.get("rule")) for v in matchers if isinstance(v, dict)} & allowed
    matched = []
    seen = set()
    for item in detector.get("incidents", []):
        opened = _epoch(item.get("opened_at"))
        pending = _epoch(item.get("detected_at"))
        iid = item.get("id")
        if (not iid or iid in baseline_ids or iid in seen or not observation_valid
                or (item.get("service"), item.get("rule")) not in expected
                or pending is None or opened is None
                or not injection_at <= pending <= opened <= end_at):
            continue
        seen.add(iid)
        matched.append((opened, item))
    matched.sort(key=lambda pair: (pair[0], pair[1]["id"]))
    first_open = matched[0][0] if matched else None
    first_item = matched[0][1] if matched else {}
    first_observed = _epoch(first_item.get("first_open_observed_at"))
    first_diagnosis = first_item.get("first_open_diagnosis")
    # Do not substitute a final "recovered" diagnosis for the opening diagnosis.
    if not isinstance(first_diagnosis, dict):
        first_diagnosis = None
    resolved_times = [_epoch(item.get("resolved_at")) for _, item in matched]
    all_resolved = bool(matched) and all(t is not None and opened <= t <= end_at
                                       for (opened, _), t in zip(matched, resolved_times))
    status = "detected" if matched else "missed" if eligible else "not_eligible"
    detection = {
        "eligible": eligible, "detected": bool(matched), "status": status,
        "matched_incident_ids": [item["id"] for _, item in matched],
        "first_opened_at": utc(first_open) if first_open is not None else None,
        "first_open_observed_at": utc(first_observed) if first_observed is not None else None,
        "detection_latency_seconds": _elapsed(injection_at, first_open),
        "latency_from_first_observed_effect_seconds": _elapsed(effect_at, first_open),
        "latency_time_origin": "injection_requested_at",
        "censored": bool(eligible and not matched),
        "observation_window_seconds": _elapsed(injection_at, end_at),
        "first_open_diagnosis": first_diagnosis,
        "diagnosis_target_match": None if first_diagnosis is None else (
            first_diagnosis.get("service") == "payment"
            or first_diagnosis.get("suspected_root_service") == "payment"),
        "all_matched_resolved": all_resolved,
        "all_matched_resolved_at": utc(max(resolved_times)) if all_resolved else None,
    }

    native_ready_at = _epoch(recovery.get("native_ready_at"))
    native = (backend == "kubernetes" and scenario == "process_crash"
              and _native_restart(recovery, injection_at)
              and _elapsed(native_ready_at, finish_at) is not None)
    mechanism = recovery.get("mechanism")
    attribution = "unverified"
    if native and mechanism == "native_kubernetes":
        attribution = "native_kubernetes"
    elif (backend == "local-process" and scenario == "process_crash"
          and mechanism == "local_process_supervisor" and recovery.get("supervisor_restart_verified") is True):
        attribution = "local_process_supervisor"
    elif scenario in ("http_5xx", "latency") and mechanism in ("fault_expiry", "harness_cleanup"):
        if _elapsed(injection_at, _epoch(times.get("fault_removed_at"))) is not None:
            attribution = mechanism
    sustained_at = _epoch(times.get("sustained_recovery_at"))
    business = (recovery.get("business_recovery_verified") is True
                and _elapsed(injection_at, sustained_at) is not None)
    cleanup = recovery.get("cleanup_verified") is True
    evaluated_recovery = {
        "attribution": attribution, "native_restart_verified": native,
        "business_recovery_verified": business, "cleanup_verified": cleanup,
        "rule_executed_recovery": False,
        "native_ready_latency_seconds": _elapsed(injection_at, _epoch(recovery.get("native_ready_at"))) if native else None,
        "business_recovery_seconds": _elapsed(injection_at, sustained_at) if business else None,
        "business_recovery_time_origin": "injection_requested_at",
        "censored": not business,
    }
    reasons = []
    if scenario not in SCENARIOS:
        reasons.append("unknown_scenario")
    if backend not in BACKENDS:
        reasons.append("unknown_backend")
    if record.get("status") != "completed":
        reasons.append("execution_not_completed")
    if not ground_truth_verified:
        reasons.append("ground_truth_not_verified")
    if (_elapsed(injection_at, confirmed_at) is None or _elapsed(injection_at, effect_at) is None
            or _elapsed(injection_at, finish_at) is None or confirmed_at > finish_at or effect_at > finish_at):
        reasons.append("injection_timestamps_missing_or_inconsistent")
    if not cleanup:
        reasons.append("cleanup_not_verified")
    if not business:
        reasons.append("business_recovery_not_verified")
    if sustained_at is not None and finish_at is not None and sustained_at > finish_at:
        reasons.append("recovery_after_trial_finished")
    if attribution == "unverified":
        reasons.append("recovery_attribution_not_verified")
    return {"schema_version": SCHEMA_VERSION, "trial_id": record.get("trial_id"),
            "scenario": scenario, "backend": backend, "trial_passed": not reasons,
            "ground_truth_verified": ground_truth_verified, "reasons": reasons,
            "detection": detection, "recovery": evaluated_recovery}


def summarize(records, required_repeats=2):
    """Summarize every attempt; only independent actual Kubernetes IDs count.

    Failed attempts remain in success-rate denominators. A repeated copy of one
    record is retained but cannot manufacture repeatability. No false-positive
    or diagnostic-accuracy population estimate is inferred from a warmup segment.
    """
    _number("required_repeats", required_repeats, 2, 20, integer=True)
    records = list(records)
    evaluations = [evaluate_trial(record) for record in records]
    counts = Counter(record.get("trial_id") for record in records if record.get("trial_id"))
    duplicates = sorted(trial_id for trial_id, count in counts.items() if count > 1)
    rows = []
    for record, evaluation in zip(records, evaluations):
        rows.append({"trial_id": record.get("trial_id"), "scenario": record.get("scenario"),
                     "repetition": record.get("repetition"), "backend": record.get("backend"),
                     "status": record.get("status"), **evaluation})
    scenarios = {}
    missing = []
    for scenario in SCENARIOS:
        group = [r for r in rows if r["scenario"] == scenario]
        successful = [r for r in group if r["trial_passed"]]
        eligible = [r for r in group if r["detection"]["eligible"]]
        live_ids = {r["trial_id"] for r in successful if r["backend"] == "kubernetes" and r["trial_id"]
                    and r["trial_id"] not in duplicates}
        if len(live_ids) < required_repeats:
            missing.append(scenario)
        scenarios[scenario] = {
            "attempts": len(group), "successful_executions": len(successful),
            "execution_success_rate": len(successful) / len(group) if group else None,
            "eligible_detection_trials": len(eligible),
            "detected_eligible_trials": sum(r["detection"]["detected"] for r in eligible),
            "missed_eligible_trials": sum(not r["detection"]["detected"] for r in eligible),
            "ineligible_detection_trials": len(group) - len(eligible),
            "kubernetes_successful_repeats": len(live_ids),
        }
    passed = sum(e["trial_passed"] for e in evaluations)
    return {"schema_version": SCHEMA_VERSION, "kind": "initial_benchmark_summary",
            "attempts": len(rows), "successful_executions": passed,
            "execution_success_rate": passed / len(rows) if rows else None,
            "by_scenario": scenarios, "trials": rows, "duplicate_trial_ids": duplicates,
            "acceptance": {"passed": not missing and not duplicates,
                           "required_backend": "kubernetes", "required_repeats_per_scenario": required_repeats,
                           "required_scenarios": list(SCENARIOS), "missing_scenarios": missing},
            "limitations": ["Rules observed recovery; no rule or AI recovery executor was used.",
                            "Local-process/synthetic trials do not establish Kubernetes behavior.",
                            "Timing includes sampling and observation overhead; it is not exact downtime.",
                            "Small initial repetitions do not establish superiority or production reliability.",
                            "No population false-positive rate or root-cause accuracy is inferred."]}
