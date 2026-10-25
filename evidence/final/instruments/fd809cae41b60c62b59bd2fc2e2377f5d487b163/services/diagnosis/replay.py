"""Blind observation replay first; ground-truth labels are opened only by the scorer."""
import hashlib
import json
from pathlib import Path

from services.diagnosis.evidence import Aggregator, encoded, timestamp

HORIZON_SECONDS = 105.  # First telemetry observation + 105s; declared before label comparison.


def read_jsonl(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 32_000_000:
        raise ValueError("Missing, symlinked or oversized observation artifact")
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if len(line.encode()) > 4_000_000 or len(rows) >= 64:
                raise ValueError("Observation record budget exceeded")
            rows.append(json.loads(line))
    if not rows:
        raise ValueError("Empty observation artifact")
    times = [timestamp(r["at"]) for r in rows]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("Observations must be strictly chronological")
    return rows


def observations(directory):
    """No trial.json, labels, fault headers, injector acknowledgements or path names enter the bundle."""
    directory = Path(directory)
    telemetry = read_jsonl(directory / "telemetry.jsonl")
    platform = read_jsonl(directory / "platform.jsonl")
    as_of = min(timestamp(telemetry[-1]["at"]), timestamp(telemetry[0]["at"]) + HORIZON_SECONDS)
    agg = Aggregator(as_of)
    for row in telemetry:
        if timestamp(row["at"]) <= as_of:
            agg.snapshot(row)
    for row in platform:
        if timestamp(row["at"]) <= as_of:
            agg.platform(row)
    return agg.finish()


def grounded(diagnosis):
    records = {r["id"]: r for r in diagnosis["evidence"]["records"]}
    if len(records) != len(diagnosis["evidence"]["records"]):
        return False
    for ref, record in records.items():
        body = {k: record[k] for k in ("source", "service", "observed_at", "values", "supports")}
        digest = hashlib.sha256(encoded(body).encode()).hexdigest()
        if digest != record["sha256"] or ref != "ev-" + digest[:24]:
            return False
    if not diagnosis["hypotheses"]:
        return False
    for hypothesis in diagnosis["hypotheses"]:
        if not hypothesis["evidence_refs"]:
            return False
        for ref in hypothesis["evidence_refs"]:
            record = records.get(ref)
            if not record or record["service"] != hypothesis["service"] or hypothesis["classification"] not in record["supports"]:
                return False
    return diagnosis["execution_allowed"] is False


def compare(diagnosis, truth):
    mapping = {"process_crash": "process_exit", "http_5xx": "server_errors", "latency": "latency"}
    if not truth.get("injection_verified") or not truth.get("effect_verified") or truth.get("fault_class") not in mapping:
        raise ValueError("Ground truth must be independently verified")
    top = diagnosis["hypotheses"][0] if diagnosis["hypotheses"] else {}
    return {"grounded": grounded(diagnosis), "target_match": top.get("service") == truth["target_service"],
            "observable_class_match": top.get("classification") == mapping[truth["fault_class"]],
            "ground_truth_fault_class": truth["fault_class"], "ground_truth_target": truth["target_service"],
            "note": "Observable-class/target agreement does not prove the injection mechanism or general root-cause accuracy."}


def evaluate_run(directory, agent):
    directory = Path(directory)
    paths = sorted(p.parent for p in directory.glob("*/telemetry.jsonl"))
    if not 1 <= len(paths) <= 32:
        raise ValueError("Expected 1..32 benchmark trials")
    rows, ids = [], set()
    for path in paths:
        bundle = observations(path)
        diagnosis = agent.diagnose(bundle)  # Labels have not been loaded.
        trial = json.loads((path / "trial.json").read_text(encoding="utf-8"))
        if trial["trial_id"] in ids:
            raise ValueError("Duplicate benchmark trial ID")
        ids.add(trial["trial_id"])
        rows.append({"trial_id": trial["trial_id"], "diagnosis": diagnosis,
                     "comparison": compare(diagnosis, trial["ground_truth"]),
                     "artifact_sha256": {name: hashlib.sha256((path/name).read_bytes()).hexdigest()
                                         for name in ("telemetry.jsonl", "platform.jsonl", "trial.json")}})
    n = len(rows)
    counts = {key: sum(r["comparison"][key] for r in rows)
              for key in ("grounded", "target_match", "observable_class_match")}
    return {"schema_version": "day6-evaluation-v1", "horizon_seconds": HORIZON_SECONDS,
            "trials": rows, "summary": {"attempted": n, **counts,
                "llm_diagnoses": sum(r["diagnosis"]["source"] == "llm" for r in rows),
                "fallback_diagnoses": sum(r["diagnosis"]["source"] == "deterministic_fallback" for r in rows),
                "structured_grounded_acceptance": counts["grounded"] == n},
            "limitations": ["Retrospective observation replay, not online diagnosis latency or recovery evaluation.",
                            "All trials remain in the denominator; fallback is not a real-model accuracy result.",
                            "Six retained trials are development data, not a held-out performance estimate."]}
