"""Run one read-only collection or start the loopback-only detector service."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.incidents.controller import Controller
from services.incidents.telemetry import Collector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("once", "serve"))
    args = parser.parse_args()
    if args.mode == "serve":
        import uvicorn
        uvicorn.run("services.incidents.app:from_env", factory=True, host="127.0.0.1", port=18082, workers=1)
        return
    import os
    collector = Collector(os.getenv("PROMETHEUS_URL", "http://127.0.0.1:19090"))
    controller = Controller(os.getenv("INCIDENT_DB", ".local/incidents.sqlite3"))
    try:
        evidence = collector.collect()
        eid = controller.ingest(evidence)
        print(json.dumps({"evidence_id": eid, "telemetry_ok": all(not e.problems for e in evidence.services.values()),
                          "incidents": controller.list_incidents()}, indent=2))
        return 0 if all(not e.problems for e in evidence.services.values()) else 2
    finally:
        controller.close()


if __name__ == "__main__":
    raise SystemExit(main())
