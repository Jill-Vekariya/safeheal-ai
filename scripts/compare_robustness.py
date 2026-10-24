"""Reproduce paired measurements using exact Git baseline blobs and one evaluator."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "d10575a79781eda91f942aef56ee5a90fa5e1aba"


def run(args):
    return subprocess.check_output([str(x) for x in args], cwd=ROOT)


def compare(baseline_ref, destination):
    if not re.fullmatch(r"[0-9a-f]{40}", baseline_ref):
        raise ValueError("An exact 40-character Git commit is required")
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="safeheal-day8-") as directory:
        export = Path(directory)
        names = run(["git","ls-tree","-r","--name-only",baseline_ref,"services"]).decode().splitlines()
        if not names:
            raise ValueError("Baseline source is missing")
        exported = {}
        for name in names:
            path = export/name
            if not path.resolve().is_relative_to(export.resolve()) or not name.endswith(".py"):
                raise ValueError("Unexpected baseline source path")
            data = run(["git","show",baseline_ref+":"+name])
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            exported[name] = hashlib.sha256(data).hexdigest()
        evaluator = export/"scripts/evaluate_robustness.py"
        evaluator.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/"scripts/evaluate_robustness.py", evaluator)
        subprocess.run([sys.executable,str(evaluator),"--phase","before","--source-ref",baseline_ref,
                        "--output",str(destination/"before.json")],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/"scripts/evaluate_robustness.py"),"--phase","after",
                    "--output",str(destination/"after.json")],cwd=ROOT,check=True)
    before = json.loads((destination/"before.json").read_text())
    after = json.loads((destination/"after.json").read_text())
    if before["case_manifest_sha256"] != after["case_manifest_sha256"] or before["evaluator_sha256"] != after["evaluator_sha256"]:
        raise ValueError("Before and after must use identical cases and evaluator")
    if any(name.startswith("services/") and exported.get(name) != sha for name,sha in before["source_sha256"].items()):
        raise ValueError("Baseline source differs from the exact Git export")
    b = {r["case"]["name"]:r for r in before["cases"]}
    a = {r["case"]["name"]:r for r in after["cases"]}
    if b.keys() != a.keys() or any(b[k]["case"] != a[k]["case"] for k in a):
        raise ValueError("Scenario definitions changed")
    summary = {"schema_version":"day8-paired-v1", "baseline_commit":baseline_ref,
               "before":before["summary"], "after":after["summary"],
               "improved_cases":[name for name in a if a[name]["passed"] and not b[name]["passed"]],
               "regressed_cases":[name for name in a if b[name]["passed"] and not a[name]["passed"]],
               "unchanged_case_manifest":True, "identical_evaluator":True,
               "baseline_source_verified_against_git":True,
               "report_sha256":{n:hashlib.sha256((destination/n).read_bytes()).hexdigest() for n in ("before.json","after.json")},
               "interpretation":"Fixed synthetic development safety cases; mocked providers, zero real-model calls. No statistical generalization or MTTR benefit."}
    (destination/"comparison.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8",newline="\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref",default=BASELINE)
    parser.add_argument("--output-dir",type=Path,required=True,help="New directory; existing reports are never overwritten")
    args = parser.parse_args()
    result = compare(args.baseline_ref,args.output_dir)
    print(json.dumps(result,indent=2))
    return 0 if result["after"]["failed"] == 0 and not result["regressed_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
