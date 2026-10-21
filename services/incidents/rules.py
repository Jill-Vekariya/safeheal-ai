"""Versioned deterministic thresholds and verdicts, independent of transport/storage."""
from dataclasses import dataclass
from services.incidents.telemetry import SERVICES, Snapshot

RULE_VERSION = "day4-v1"
MAX_GAP = 15.
RECOVERY_HOLD = 15.
HOLDS = {"telemetry_unavailable": 15., "scrape_unavailable": 10., "high_error_rate": 15., "high_latency": 15.}


@dataclass(frozen=True)
class Verdict:
    service: str
    rule: str
    decision: str  # alert, clear, hold (hysteresis), unknown
    sample_at: float
    reason: str
    value: float | None = None


def evaluate(snapshot: Snapshot):
    output = []
    for service in SERVICES:
        e = snapshot.services[service]
        output.append(Verdict(service, "telemetry_unavailable", "alert" if e.problems else "clear",
                              snapshot.at, ";".join(e.problems) or "fresh telemetry"))
        output.append(Verdict(service, "scrape_unavailable", "unknown" if e.up is None else
                              "clear" if e.up else "alert", e.up_at or snapshot.at,
                              "scrape success is availability evidence, not proof of process state"))
        for rule in ("high_error_rate", "high_latency"):
            value = None
            # API errors/partial results must never supply a zero denominator or healthy verdict.
            relevant = any(p.startswith("requests:") for p in e.problems)
            if rule == "high_latency":
                relevant = relevant or any(p.startswith("buckets:") for p in e.problems)
            if e.up is not True or relevant or e.requests is None or e.requests < 20:
                decision, reason = "unknown", "requires fresh complete counters and >=20 observed requests in 60s"
            else:
                value = e.errors / e.requests if rule == "high_error_rate" else e.p95
                if value is None:
                    decision, reason = "unknown", "insufficient histogram observations"
                else:
                    high, low = (.20, .05) if rule == "high_error_rate" else (1., .5)
                    decision = "alert" if value >= high else "clear" if value <= low else "hold"
                    reason = "60s observed counter increments; 4xx excluded from error numerator"
            output.append(Verdict(service, rule, decision, e.metrics_at or snapshot.at, reason, value))
    return output
