"""Declared protocol, pure decisions and replayable descriptive metrics."""
import hashlib
import json
import math
import random
import statistics

ARMS = ("native", "rule_policy", "ai_policy")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), allow_nan=False)


def protocol(repeats=5, seed=9, horizon=45):
    if type(repeats) is not int or not 1 <= repeats <= 10 or type(seed) is not int:
        raise ValueError("Invalid repetition/seed")
    if type(horizon) is not int or not 30 <= horizon <= 120:
        raise ValueError("Invalid observation horizon")
    rng = random.Random(seed)
    slots = []
    for block in range(1,repeats+1):
        arms = list(ARMS)
        rng.shuffle(arms)
        slots += [{"block":block,"arm":arm,"scenario":"payment_scale_zero"} for arm in arms]
    return {"schema_version":"day9-protocol-v1", "seed":seed,"repeats":repeats,
            "arms":list(ARMS),"scenario":"payment_scale_zero","slots":slots,
            "horizon_seconds":horizon,"decision_delay_seconds":8,
            "workload":{"concurrency":2,"request_interval_seconds":.2,"request_timeout_seconds":4},
            "business_recovery":"at least three consecutive valid <0.5s order completions spanning >=2s, after verified impact",
            "primary_metric":"restricted time to business recovery min(T,horizon); censored times are not observed MTTR",
            "safety":"one 0-to-1 scale request, same independent controller/RBAC/admission; no model credentials/tools for cluster access",
            "episode_reset":"operator enrolls a fresh per-trial journal/token; production journal rate limits are unchanged, not evaluated across episode resets",
            "stopping":"retain every attempted trial; no automatic failed-trial replacement; cleanup failure stops batch",
            "model_missing":"planned AI slots not run; never substitute mocks/fallback for real-model results",
            "scoring":"ground truth is attached after diagnosis; model gets only normalized telemetry",
            "limitations":["One deliberately narrow scale-zero scenario; no general recovery effectiveness claim.",
                           "One shared machine/cluster, sequential blocked ordering, warm caches and carryover possible.",
                           "Five repeats are exploratory; show individual outcomes and censoring."]}


def rule_support(bundle):
    return any(c["service"] == "payment" and c["classification"] == "endpoint_unavailable" for c in bundle.candidates()) and bundle.eligible


def ai_support(diagnosis):
    if diagnosis.get("source") != "llm" or diagnosis.get("status") != "supported_hypothesis":
        return False
    h = diagnosis.get("hypotheses", [])
    return bool(h and h[0]["service"] == "payment" and h[0]["classification"] == "endpoint_unavailable"
                and h[0]["confidence"] >= .65 and diagnosis.get("execution_allowed") is False)


def metrics(row, requests, horizon):
    start = row.get("injection_elapsed")
    if start is None or not row.get("injection_verified") or not row.get("effect_verified"):
        return {"eligible":False,"recovery_seconds":None,"restricted_seconds":None,"censored":None,
                "successful_requests":None,"total_requests":None}
    end = start+horizon
    samples = sorted((r for r in requests if start <= r["started_elapsed_seconds"] and r["finished_elapsed_seconds"] <= end),
                     key=lambda r:r["finished_elapsed_seconds"])
    impact = [r for r in samples if not r.get("valid_response") or
              (row.get("scenario") == "latency" and r["elapsed_seconds"] >= 1)]
    current, recovered = [], None
    for r in samples:
        if not impact or r["finished_elapsed_seconds"] < impact[0]["finished_elapsed_seconds"]:
            continue
        if r.get("valid_response") is True and r["elapsed_seconds"] < .5:
            current.append(r)
            if len(current) >= 3 and current[-1]["finished_elapsed_seconds"]-current[0]["finished_elapsed_seconds"] >= 2:
                recovered = r["finished_elapsed_seconds"]-start
                break
        else:
            current.clear()
    fully_observed = row.get("observation_elapsed_end", -1) >= end
    eligible = recovered is not None or fully_observed
    return {"eligible":eligible,"recovery_seconds":recovered,
            "restricted_seconds":recovered if recovered is not None else float(horizon) if fully_observed else None,
            "censored":recovered is None if eligible else None,
            "successful_requests":sum(r.get("valid_response") is True for r in samples),
            "total_requests":len(samples)}


def summarize(rows):
    result = {}
    for arm in ARMS:
        all_rows = [r for r in rows if r["arm"] == arm]
        valid = [r for r in all_rows if r.get("metrics",{}).get("eligible")]
        times = [r["metrics"]["recovery_seconds"] for r in valid if r["metrics"]["recovery_seconds"] is not None]
        result[arm] = {"planned":len(all_rows),"attempted":sum(r.get("attempted",False) for r in all_rows),
                       "eligible":len(valid),"recovered_within_horizon":len(times),
                       "censored":sum(r["metrics"]["censored"] is True for r in valid),
                       "technical_failures":sum(r.get("status")=="technical_failure" for r in all_rows),
                       "not_run":sum(not r.get("attempted",False) for r in all_rows),
                       "mean_observed_recovery_seconds":statistics.mean(times) if times else None,
                       "median_observed_recovery_seconds":statistics.median(times) if times else None,
                       "mean_restricted_seconds":statistics.mean(r["metrics"]["restricted_seconds"] for r in valid) if valid else None,
                       "real_provider_requests":sum(r.get("provider_calls",0) for r in all_rows),
                       "llm_validated_diagnoses":sum(r.get("diagnosis",{}).get("source")=="llm" for r in all_rows),
                       "policy_verified":sum(r.get("controller_result",{}).get("status")=="verified" for r in all_rows)}
    pairs = []
    for block in sorted({r["block"] for r in rows}):
        group = {r["arm"]:r for r in rows if r["block"]==block}
        if all(group.get(a,{}).get("metrics",{}).get("eligible") for a in ("native","rule_policy")):
            pairs.append(group["native"]["metrics"]["restricted_seconds"]-group["rule_policy"]["metrics"]["restricted_seconds"])
    return {"arms":result,"paired_native_minus_rule_restricted_seconds":pairs,
            "mean_paired_restricted_difference":statistics.mean(pairs) if pairs else None,
            "ai_comparison_complete":result["ai_policy"]["eligible"] == result["ai_policy"]["planned"] and result["ai_policy"]["planned"] >= 5
                                     and result["ai_policy"]["real_provider_requests"] >= result["ai_policy"]["planned"],
            "note":"Descriptive small-sample results. Observed-only means exclude censored cases; restricted means stop at the declared horizon."}
