"""Finalize and verify a stopped CPU study without making model/cluster calls.

Failed, partial and censored trials remain in the report. Exit success requires a
complete experiment, all cleanup checks, and at least one real AI recovery.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_controlled import analyze, findings
from finalize_controlled import finalize
from reproduce import audit_events


def verify(directory):
    directory = Path(directory)
    if not (directory / "manifest.json").exists():
        finalize(directory)
    data = analyze(directory)
    rows = data["trials"]
    run = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    ai = [r for r in rows if r["arm"] == "ai_policy"]
    denied = [d for r in rows for d in r.get("denied_access", [])]
    linked = [r for r in ai if r.get("provider_calls") == 1
              and r.get("diagnosis", {}).get("source") == "llm"
              and r.get("diagnosis", {}).get("provider_status") == "validated"
              and r.get("controller_result", {}).get("status") == "verified"
              and (r.get("metrics") or {}).get("recovery_seconds") is not None
              and (directory / r["trial_id"] / "audit.sqlite3").is_file()]
    report = {
        "schema_version": "safeheal-cpu-study-check-v1",
        "run": run,
        "attempted": sum(r.get("attempted", False) for r in rows),
        "cleanup_passed": sum(r.get("cleanup_passed") is True for r in rows),
        "statuses": dict(Counter(r.get("status") for r in rows)),
        "ai_provider_requests": sum(r.get("provider_calls", 0) for r in ai),
        "ai_provider_statuses": dict(Counter(r.get("diagnosis", {}).get("provider_status", "not_run") for r in ai)),
        "ai_controller_verified": sum(r.get("controller_result", {}).get("status") == "verified" for r in ai),
        "ai_business_recovered": sum((r.get("metrics") or {}).get("recovery_seconds") is not None for r in ai),
        "forbidden_probes_denied": sum(d["status_code"] == 403 for d in denied),
        "audit_events": sum(audit_events(p) for p in directory.glob("d9-*/audit.sqlite3")),
        "reported_provider_usage": data.get("reported_provider_usage", {}),
        "scope": "One scale-zero cohort; censored outcomes and prior failed cohorts are not replaced or pooled.",
    }
    report["passed"] = (
        run["completed"] and run["attempted_slots"] == run["planned_slots"] == len(rows) == 15
        and report["attempted"] == report["cleanup_passed"] == 15
        and report["statuses"] == {"observed": 15}
        and report["ai_provider_requests"] == 5
        and report["ai_controller_verified"] >= 1 and report["ai_business_recovered"] >= 1
        and bool(linked) and report["audit_events"] > 0
        and len(denied) == report["forbidden_probes_denied"] == 120
    )
    return report, data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report, data = verify(args.directory)
    for name, value in [("verification.json", report), ("analysis.json", data)]:
        (args.output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    (args.output / "FINDINGS.md").write_text(findings(data), encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
