"""Reproducible synthetic engineering check; no live faults or benchmark measurements."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.incidents.controller import Controller
from services.incidents.rules import RULE_VERSION
from services.incidents.telemetry import SERVICES, ServiceEvidence, Snapshot


def verify():
    scenarios = {
        "scrape_unavailable": {"up": False},
        "high_error_rate": {"errors": 30.},
        "high_latency": {"p95": 1.5},
        "telemetry_unavailable": {"up": None, "problems": ["up:missing"]},
    }
    results = {}
    with tempfile.TemporaryDirectory(prefix="safeheal-detector-") as folder:
        for rule, changes in scenarios.items():
            c = Controller(Path(folder)/(rule+".sqlite3"))
            for t in range(0, 36, 5):
                at = 1_800_000_000.+t  # Synthetic, controlled source times.
                values = {s: ServiceEvidence(True, at, 100., 0., .05, at) for s in SERVICES}
                if t <= 15:
                    for key, value in changes.items():
                        setattr(values["payment"], key, value)
                c.ingest(Snapshot(at, values, raw={"synthetic": True}))
            item = next(i for i in c.list_incidents() if i["service"] == "payment" and i["rule"] == rule)
            detail = c.detail(item["id"])
            states = [t["state"] for t in reversed(detail["transitions"])]
            assert states == ["pending", "open", "recovering", "resolved"]
            assert detail["diagnosis"]["controller"] == "deterministic"
            results[rule] = {"passed": True, "incident": detail,
                             "last_evidence": c.evidence(item["last_evidence_id"])}
            c.close()
    return {"kind": "synthetic_engineering_acceptance", "live_cluster": False, "llm_used": False,
            "rule_version": RULE_VERSION, "recorded_at": datetime.now(timezone.utc).isoformat(),
            "scenarios": results, "passed": True,
            "limitations": "Synthetic source times and observations; not live Prometheus/kind or research benchmark evidence."}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, allow_nan=False))
