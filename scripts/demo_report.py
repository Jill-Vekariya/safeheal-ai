"""Read-only demo evidence reporter; never invokes a model or cluster command."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce import audit_events

ROOT = Path(__file__).resolve().parents[1]
STEPS = ("runtime", "checks", "replay", "diagnosis", "cluster", "services",
         "native", "autonomous", "approval", "observability", "detector", "final_services")
FILES = ("acceptance.json", "audit.json", "audit.sqlite3")


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")


def trial_checks(row):
    result = row.get("controller_result", {})
    observations = result.get("observations", [])[-3:]
    ready = (len(observations) == 3 and all(o.get("ready") is True and
             type(o.get("generation")) is int and o["generation"] > 0 and
             o["generation"] == o.get("observed_generation") for o in observations)
             and len({o.get("generation") for o in observations}) == 1)
    denied = row.get("denied_access", [])
    zero = row.get("admission_denied_from_zero", [])
    hashes = [row.get("dry_run", {}).get("request_hash"), result.get("request_hash")]
    if row.get("controller_mode") == "approval":
        hashes.append(row.get("approval", {}).get("request_hash"))
    return {
        "acceptance_and_cleanup": row.get("passed") is True and row.get("cleanup_passed") is True
            and not row.get("operator_cleanup_restore", False),
        "admission_ready": row.get("admission_ready") is True,
        "eight_forbidden_calls_denied": len(denied) == 8 and all(x.get("status_code") == 403 for x in denied),
        "forbidden_scale_from_zero_denied": len(zero) == 1 and zero[0].get("status_code") == 403,
        "unsafe_proposal_denied": row.get("rejected_proposal", {}).get("status") == "denied_or_failed",
        "dry_run_no_authority": row.get("dry_run", {}).get("status") == "dry_run"
            and row.get("dry_run", {}).get("execution_allowed") is False,
        "approval_gate": row.get("controller_mode") == "autonomous" or (
            row.get("unapproved_denial", {}).get("status") == "denied_or_failed"
            and row.get("approval", {}).get("status") == "approved"),
        "request_binding": all(isinstance(h, str) and re.fullmatch("[0-9a-f]{64}", h) for h in hashes)
            and len(set(hashes)) == 1,
        "verified_ready": result.get("status") == "verified" and ready,
        "business_order_confirmed": row.get("business_check", {}).get("passed") is True
            and row.get("business_check", {}).get("http_status") == 201
            and row.get("business_check", {}).get("order", {}).get("status") == "confirmed",
        "replay_denied": row.get("replay_denial", {}).get("status") == "denied_or_failed",
        "no_model_calls": row.get("llm_calls") == 0,
    }


def build_report(source, outcomes, trials):
    stages = {name: outcomes.get(name, {}).get("outcome", "not_run") for name in STEPS}
    modes = [t.get("mode") for t in trials]
    passed = (all(s == "success" for s in stages.values()) and len(trials) == 2
              and set(modes) == {"approval", "autonomous"}
              and all(t.get("passed") is True for t in trials))
    return {"schema_version": "safeheal-demo-v1", "passed": passed, "source_commit": source,
            "steps": stages, "trials": trials,
            "scope": "Fresh isolated Kubernetes recovery; retained diagnosis/experiment replay. No live-model inference."}


def begin(root, output, source):
    if not re.fullmatch("[0-9a-f]{40}", source):
        raise ValueError("Invalid source commit")
    output.mkdir(parents=True, exist_ok=False)
    save(output/"begin.json", {"source_commit": source,
         "existing_trials": sorted(p.name for p in (root/"evidence/day7").glob("d7-*") if p.is_dir())})


def finish(root, output, outcomes):
    baseline = json.loads((output/"begin.json").read_text(encoding="utf-8"))
    source = baseline["source_commit"]
    if not re.fullmatch("[0-9a-f]{40}", source):
        raise ValueError("Invalid source commit")
    paths = sorted(p for p in (root/"evidence/day7").glob("d7-*")
                   if p.name not in baseline["existing_trials"])
    trials = []
    for folder in paths:
        entry = {"trial_id": folder.name, "passed": False, "mode": None}
        trials.append(entry)
        if (folder.is_symlink() or not re.fullmatch("d7-(approval|autonomous)-[0-9a-f]{10}", folder.name)
                or not folder.is_dir()):
            entry["error"] = "invalid_trial_path"
            continue
        target = output/"trials"/folder.name
        target.mkdir(parents=True, exist_ok=False)
        try:
            for name in FILES:
                p = folder/name
                if p.is_symlink() or not p.is_file() or p.stat().st_size > 20*1024*1024:
                    raise ValueError("Invalid trial artifact")
                (target/name).write_bytes(p.read_bytes())
            row = json.loads((target/"acceptance.json").read_text(encoding="utf-8"))
            checks = trial_checks(row)
            expected = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
                *sorted((root/"services/recovery").glob("*.py")), root/"scripts/recover.py",
                root/"scripts/verify_recovery.py", root/"infrastructure/recovery/policy.yaml"]}
            checks["current_recovery_sources"] = row.get("source_sha256") == expected
            checks["trial_identity"] = row.get("trial_id") == folder.name
            count = audit_events(target/"audit.sqlite3")
            checks["audit_chain"] = count > 0
            entry.update(mode=row.get("controller_mode"), checks=checks, audit_events=count,
                         passed=all(checks.values()))
        except Exception:
            entry["error"] = "incomplete_or_invalid_trial_evidence"
    result = build_report(source, outcomes, trials)
    save(output/"result.json", result)
    lines = ["# SafeHeal AI: end-to-end demo", "",
             "**Result: "+("PASS" if result["passed"] else "FAIL / INCOMPLETE")+"**", "",
             "Source commit: "+source, "",
             "| Stage | Outcome |", "|---|---|"]
    lines += ["| "+name.replace("_", " ")+" | "+status+" |" for name, status in result["steps"].items()]
    lines += ["", "## Fresh recovery evidence", "", "| Mode | Trial | Verified | Audit events |",
              "|---|---|---|---:|"]
    lines += ["| "+str(t["mode"])+" | "+t["trial_id"]+" | "+str(t["passed"])+" | "
              +str(t.get("audit_events", 0))+" |" for t in trials]
    lines += ["", "Each successful trial includes eight forbidden API denials, a server dry-run denial from zero,",
              "dry-run, approval checks where applicable, three Ready observations, one confirmed business order,",
              "replay denial, source hashes and read-only audit-chain verification.", "",
              "The diagnosis stage replays retained evidence with deterministic fallback; it is separate from",
              "the fresh operator-created recovery fixtures. No live model or provider key is used.",
              "All five real local-model requests in the retained study timed out; AI benefit is unproven.", "",
              "Download the safeheal-demo-evidence artifact for result.json, replay outputs and raw trial records."]
    markdown = "\n".join(lines)+"\n"
    (output/"summary.md").write_text(markdown, encoding="utf-8", newline="\n")
    hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(output.rglob("*")) if p.is_file()}
    save(output/"manifest.json", {"sha256": hashes})
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(markdown)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("begin", "finish"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.phase == "begin":
        begin(ROOT, args.output, args.source or "")
        return
    result = finish(ROOT, args.output, json.loads(os.environ.get("DEMO_STEP_OUTCOMES", "{}")))
    print(json.dumps({"passed": result["passed"], "new_trials": len(result["trials"])}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
