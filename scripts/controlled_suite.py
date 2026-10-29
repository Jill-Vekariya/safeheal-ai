"""Predeclared multi-fault comparison using the existing independent executor.

Plan is the default. Live provider calls remain disabled unless separately
configured and authorized; missing AI arms stay visible in planned denominators.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from controlled_core import ARMS, protocol, summarize

SCENARIOS = ("payment_scale_zero", "http_5xx", "latency")


def suite_protocol(repeats=3, seed=41, horizon=45):
    base = protocol(repeats, seed, horizon)
    rng = random.Random(seed)
    slots = []
    for block in range(1, repeats + 1):
        cells = [(s, a) for s in SCENARIOS for a in ARMS]
        rng.shuffle(cells)
        slots.extend({"block": block, "scenario": s, "arm": a} for s, a in cells)
    return {**base, "schema_version": "stage4-controlled-suite-v1",
            "scenario": None, "scenarios": list(SCENARIOS), "slots": slots,
            "fault_duration_seconds": 15,
            "hypothesis": "Recovery benefit depends on the fault; scale-only authority cannot repair application latency or 5xx faults.",
            "experimental_unit": "scenario x repetition block; three arms randomized within block",
            "sample_size_rationale": f"{repeats} repeats per cell are a bounded exploratory check, not a powered effectiveness study.",
            "limits": {"max_trials": 90, "max_workload_concurrency": 2,
                       "live_provider_enabled": False},
            "success_criteria": ["all attempted trials and cleanup outcomes retained",
                                 "no expansion of deterministic controller authority",
                                 "no pooling recovery times across faults"],
            "limitations": ["One shared local cluster; warm caches and carryover possible.",
                            "Fault expiry is recovery by the fixture, not a policy effect.",
                            "Missing AI arms are blocked, never replaced by fake model results."]}


def summary(plan, rows):
    keyed = {(r["scenario"], r["block"], r["arm"]): r for r in rows}
    if len(keyed) != len(rows):
        raise ValueError("Duplicate trial slot")
    expected = {(s["scenario"], s["block"], s["arm"]) for s in plan["slots"]}
    if set(keyed) - expected:
        raise ValueError("Trial outside protocol")
    complete = []
    for slot in plan["slots"]:
        complete.append(keyed.get((slot["scenario"], slot["block"], slot["arm"]),
                                 {**slot, "attempted": False, "status": "not_run"}))
    scenarios = {}
    for scenario in SCENARIOS:
        group = [r for r in complete if r["scenario"] == scenario]
        report = summarize(group)
        # Block-paired exploratory bootstrap; preserve all restricted/censored times.
        differences = report["paired_native_minus_rule_restricted_seconds"]
        interval = None
        if len(differences) >= 2:
            rng = random.Random(plan["seed"])
            samples = sorted(statistics.mean(rng.choices(differences, k=len(differences)))
                             for _ in range(2000))
            interval = [samples[49], samples[1949]]
        scenarios[scenario] = {**report, "exploratory_paired_bootstrap_95": interval,
                               "cleanup_failures": sum(r.get("cleanup_passed") is False for r in group)}
    return {"planned": len(complete), "attempted": sum(bool(r.get("attempted")) for r in complete),
            "scenarios": scenarios, "uncertainty": "Block bootstrap, 2000 resamples; tiny local sample, not population coverage."}


def run(plan, folder):
    from controlled_experiment import trial
    from benchmark_kubernetes import KubernetesBackend
    import k8s as lab
    import verify_recovery as recovery

    folder.mkdir(parents=True, exist_ok=False)
    # Provider deliberately absent; configuring a profile cannot silently enable calls.
    plan["provider"] = {"configured": False, "reason": "separate_live_pilot_authorization_required"}
    plan["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [Path(__file__), ROOT / "scripts/controlled_core.py",
                                       ROOT / "scripts/controlled_experiment.py"]}
    recovery.save(folder / "protocol.json", plan)
    rows = []
    backend = KubernetesBackend(folder)
    with lab.recovery_lock():
        try:
            recovery.save(folder / "preflight.json", backend.preflight())
            backend.start()
            for index, slot in enumerate(plan["slots"], 1):
                name = f"s4-{index:02d}-{slot['scenario']}-{slot['arm']}"
                try:
                    row = trial(slot, plan, folder / name, backend, None)
                except BaseException:
                    path = folder / name / "trial.json"
                    rows.append(json.loads(path.read_text()) if path.exists() else
                                {**slot, "attempted": False, "status": "technical_failure"})
                    raise
                rows.append(row)
                recovery.save(folder / "summary.json", summary(plan, rows))
                if row.get("status") == "technical_failure":
                    raise RuntimeError("Stop after technical failure; retain all planned slots")
        finally:
            backend.close()
            recovery.save(folder / "summary.json", summary(plan, rows))
            recovery.save(folder / "run.json", {"completed_slots": len(rows),
                          "planned_slots": len(plan["slots"]), "rows": rows})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--horizon", type=int, default=45)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--lab", choices=("safeheal-dev", "safeheal-day7"),
                        help="Explicit project-owned lab; required for execution")
    args = parser.parse_args()
    plan = suite_protocol(args.repeats, args.seed, args.horizon)
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return
    if args.output is None:
        parser.error("--execute requires a new --output directory")
    if args.lab is None:
        parser.error("--execute requires an explicit --lab")
    plan["lab"] = args.lab
    import verify_recovery as recovery
    recovery.configure_lab(args.lab)
    run(plan, args.output)


if __name__ == "__main__":
    main()
