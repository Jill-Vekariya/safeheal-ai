"""Operator entry point. Only --request JSON is untrusted/model-produced input."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.recovery.controller import Controller, Denied, Journal, require
from services.recovery.kubernetes import KubernetesAPI


def read_request(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(8193)
    require(len(raw) <= 8192, "proposal_too_large")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(Denied("nonfinite_json")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "approve", "audit"))
    parser.add_argument("--config", type=Path, required=True, help="Trusted operator enrollment")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--mode", choices=("dry-run", "approval", "autonomous"), default="dry-run")
    args = parser.parse_args()
    api = journal = None
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        journal = Journal(config["journal"])
        if args.operation == "audit":
            journal.verify()
            print(json.dumps([json.loads(r[0]) for r in journal.db.execute("SELECT body FROM audit ORDER BY seq")]))
            return 0
        require(args.request is not None, "request_required")
        api = KubernetesAPI(config["server"], config["ca_file"], config["token_file"])
        controller = Controller(api, journal, config["enrollment"],
                                autonomous_enabled=config.get("autonomous_enabled", False))
        try:
            request = read_request(args.request)
        except (ValueError, OSError, Denied):
            with journal.transaction():
                journal.event(controller.clock(), "unparsed", "denial", "invalid_proposal_file")
            raise Denied("invalid_proposal_file") from None
        result = controller.approve(request) if args.operation == "approve" else controller.run(request, mode=args.mode)
        print(json.dumps(result, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "denied_or_failed", "code": str(exc) if isinstance(exc, Denied) else "operator_configuration_or_audit_failure"}))
        return 1
    finally:
        if api:
            api.close()
        if journal:
            journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
