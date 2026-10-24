"""Read-only, offline verification of retained experimental artifacts.

No provider calls, shell execution, Kubernetes access or writes to source/evidence.
Only a newly selected output directory receives the reproduction report.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_controlled import analyze
from controlled_core import encoded


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def artifact(root, name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Invalid artifact path")
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Artifact escapes repository")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact escapes repository")
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError("Artifact symlink is not allowed")
    return path


def audit_events(path):
    previous, count = "0" * 64, 0
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Audit SQLite integrity failure")
        for seq, body, prior, digest in db.execute("SELECT seq,body,previous,hash FROM audit ORDER BY seq"):
            count += 1
            expected = hashlib.sha256(encoded({"seq":seq, "body":body, "previous":prior}).encode()).hexdigest()
            if seq != count or prior != previous or digest != expected:
                raise ValueError("Audit chain integrity failure")
            json.loads(body)
            previous = digest
    return count


def verify_instrument(root, entry, plan, inventory):
    sources = entry.get("instrument_sources")
    if sources is None:
        return 0
    if set(sources) != set(plan["source_sha256"]):
        raise ValueError("Instrument source inventory differs from protocol")
    for name, relative in sources.items():
        path = artifact(root, relative)
        if relative not in inventory or hashlib.sha256(path.read_bytes()).hexdigest() != plan["source_sha256"][name]:
            raise ValueError("Declared instrument source mismatch: " + name)
    return len(sources)


def verify(root, manifest):
    root = Path(root).resolve()
    if manifest.get("schema_version") != "safeheal-reproduction-v1" or not manifest.get("sha256"):
        raise ValueError("Invalid reproduction manifest")
    for name, expected in manifest["sha256"].items():
        if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
            raise ValueError("Invalid artifact digest")
        path = artifact(root, name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Artifact integrity mismatch: " + name)
    cohorts = []
    for entry in manifest["cohorts"]:
        folder = artifact(root, entry["directory"])
        expected_path = artifact(root, entry["analysis"])
        raw = read_json(folder / "manifest.json")
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
        if actual != set(raw["sha256"]) | {"manifest.json"}:
            raise ValueError("Raw inventory differs from finalized manifest")
        for path in [*actual]:
            relative = (folder / path).relative_to(root).as_posix()
            if relative not in manifest["sha256"]:
                raise ValueError("Raw artifact missing from reproduction inventory")
        if expected_path.relative_to(root).as_posix() not in manifest["sha256"]:
            raise ValueError("Analysis missing from reproduction inventory")
        instruments = verify_instrument(root, entry, read_json(folder / "protocol.json"), manifest["sha256"])
        replay = analyze(folder)
        if replay != read_json(expected_path):
            raise ValueError("Numerical analysis differs from retained findings")
        audits = sum(audit_events(p) for p in sorted(folder.glob("d9-*/audit.sqlite3")))
        cohorts.append({"directory":entry["directory"], "raw_files":len(raw["sha256"]),
                        "instrument_files":instruments, "audit_events":audits, "summary":replay["summary"]})
    return {"schema_version":"safeheal-reproduction-result-v1", "passed":True,
            "verified_artifacts":len(manifest["sha256"]), "cohorts":cohorts,
            "scope":"Offline byte integrity, raw metric replay and read-only audit verification; not a new live experiment."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evidence/final/artifact-manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(ROOT, read_json(args.manifest))
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "reproduction.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
