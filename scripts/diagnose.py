"""Read-only incident diagnosis or blind benchmark replay. Disabled provider is the default."""
import argparse
import json
from pathlib import Path
import sys
import time
import sqlite3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.evidence import timestamp
from services.diagnosis.provider import JsonProvider, ProviderConfig, parse_json
from services.diagnosis.replay import evaluate_run
from services.diagnosis.tools import IncidentTools
from services.diagnosis.notifications import NotificationPipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    replay = sub.add_parser("benchmark")
    replay.add_argument("directory", type=Path)
    once = sub.add_parser("incident")
    once.add_argument("--database", type=Path, default=Path(".local/incidents.sqlite3"))
    once.add_argument("--incident-id", required=True)
    once.add_argument("--as-of", help="Explicit timezone-bearing ISO timestamp for historical replay")
    notice = sub.add_parser("notification", help="Local durable intake; never sends a message or executes recovery")
    notice.add_argument("--database", type=Path, required=True)
    notice.add_argument("--event", type=Path, required=True)
    notice.add_argument("--journal", type=Path, default=Path(".local/diagnosis-notifications.sqlite3"))
    parser.add_argument("--output", type=Path, help="Create a new report; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.output and args.output.exists():
            raise ValueError("Output already exists")
        cfg = ProviderConfig.from_env()
        agent = DiagnosisAgent(JsonProvider(cfg))
        if args.mode == "benchmark":
            result = evaluate_run(args.directory, agent)
            ok = result["summary"]["structured_grounded_acceptance"]
        elif args.mode == "incident":
            reader = IncidentTools(args.database)
            try:
                bundle = reader.aggregate(args.incident_id, timestamp(args.as_of) if args.as_of else time.time())
            finally:
                reader.close()
            result = agent.diagnose(bundle)
            ok = result["status"] != "insufficient_evidence"
        else:
            with args.event.open("rb") as stream:
                data = stream.read(8193)
            if len(data) > 8192:
                raise ValueError("Oversized notification")
            event = parse_json(data)
            from services.diagnosis.notifications import parse_event
            parse_event(event, time.time())
            reader = IncidentTools(args.database)
            pipeline = None
            try:
                bundle = reader.aggregate(event["incident_id"], time.time())
                pipeline = NotificationPipeline(agent, args.journal)
                result = pipeline.handle(event, bundle)
            finally:
                reader.close()
                if pipeline:
                    pipeline.close()
            ok = result["status"] in ("diagnosed", "suppressed")
        payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
            print(json.dumps({"output": str(args.output), "passed": ok,
                              "summary": result.get("summary", {"status": result["status"]} if "status" in result else {})}))
        else:
            print(payload)
        return 0 if ok else 2
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error, RecursionError, OverflowError) as exc:
        # Do not print config values, remote response bodies, or exception strings containing credentials.
        print(json.dumps({"status": "error", "error_type": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
