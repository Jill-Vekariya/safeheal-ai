"""Create a new immutable raw-data manifest after an experiment has stopped."""
import argparse
import hashlib
import json
from pathlib import Path


def finalize(directory):
    directory=Path(directory).resolve()
    target=directory/"manifest.json"
    if target.exists():
        raise FileExistsError("Manifest already exists")
    run=json.loads((directory/"run.json").read_text())
    protocol=json.loads((directory/"protocol.json").read_text())
    rows=[json.loads(p.read_text()) for p in directory.glob("d9-*/trial.json")]
    keys=[(r["block"],r["arm"]) for r in rows]
    if len(keys)!=len(set(keys)) or any(r.get("status")=="running" for r in rows):
        raise ValueError("Duplicate or active trial")
    if run["completed"] and set(keys)!={(r["block"],r["arm"]) for r in protocol["slots"]}:
        raise ValueError("Completed run is missing planned outcomes")
    result={"schema_version":"day9-raw-manifest-v1","run_completed":run["completed"],
            "sha256":{str(p.relative_to(directory)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(directory.rglob("*")) if p.is_file()}}
    with target.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,indent=2); stream.write("\n")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    args=parser.parse_args()
    print(json.dumps({"files_hashed":len(finalize(args.directory)["sha256"])}))
