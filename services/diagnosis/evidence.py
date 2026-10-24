"""Normalize observations, discard untrusted prose, and retain content-addressed evidence."""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import math
import re

from services.incidents.telemetry import SERVICES, decode

WINDOW = 120.
MAX_RECORDS = 96
MAX_INPUT = 4_000_000
CAUSES = ("process_exit", "server_errors", "latency", "endpoint_unavailable")
EXPLANATIONS = {
    "process_exit": "A recent container termination was observed; the initiating cause is unknown.",
    "server_errors": "Fresh eligible counters show a server-error spike; application mechanism is unknown.",
    "latency": "Fresh eligible histogram observations show elevated request latency; mechanism is unknown.",
    "endpoint_unavailable": "Scrapes failed; this alone does not prove a process crash.",
}
ISSUES = frozenset({"telemetry_outside_window", "unavailable_telemetry", "partial_telemetry",
                    "invalid_platform", "invalid_termination", "evidence_truncated",
                    "stale_or_missing_current_telemetry", "invalid_evidence", "invalid_observation"})


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def timestamp(value):
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Timestamps must include a timezone")
        value = dt.timestamp()
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 253402300799 or not math.isfinite(value):
        raise ValueError("Invalid timestamp")
    return float(value)


@dataclass(frozen=True)
class Evidence:
    id: str
    source: str
    service: str
    observed_at: float
    values: dict
    supports: tuple[str, ...]
    sha256: str


@dataclass
class Bundle:
    as_of: float
    records: list[Evidence] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    latest_telemetry: float | None = None

    def document(self):
        return {"schema_version": "day6-evidence-v1", "as_of": self.as_of,
                "window_seconds": WINDOW, "issues": sorted(set(self.issues)),
                "records": [asdict(r) for r in self.records]}

    @property
    def eligible(self):
        return self.latest_telemetry is not None and 0 <= self.as_of - self.latest_telemetry <= 15

    def candidates(self):
        grouped = {}
        for record in self.records:
            for cause in record.supports:
                grouped.setdefault((cause, record.service), []).append(record.id)
        return [{"classification": c, "service": s, "evidence_refs": refs[-6:]}
                for (c, s), refs in sorted(grouped.items(), key=lambda p: (
                    CAUSES.index(p[0][0]), -SERVICES.index(p[0][1])))]


def validate_bundle(bundle):
    """Verify every record before provider use, including uncited context.

    Hashes detect corruption, not a dishonest instrument. Only the trusted raw
    Aggregator should construct bundles; this also checks the normalized schema.
    """
    def check(ok):
        if not ok:
            raise ValueError("Invalid evidence bundle")
    def number(value):
        return type(value) in (int, float) and 0 <= value <= 1e100 and math.isfinite(value)
    check(type(bundle) is Bundle)
    check(type(bundle.as_of) in (int, float))
    timestamp(bundle.as_of)
    check(bundle.latest_telemetry is None or type(bundle.latest_telemetry) in (int, float))
    check(type(bundle.records) is list and len(bundle.records) <= MAX_RECORDS)
    check(type(bundle.issues) is list and len(bundle.issues) <= 1024 and
          all(type(i) is str and i in ISSUES for i in bundle.issues))
    seen, fresh = set(), []
    for record in bundle.records:
        check(type(record) is Evidence and record.source in ("prometheus", "kubernetes") and record.service in SERVICES)
        check(type(record.supports) is tuple and all(c in CAUSES for c in record.supports) and
              len(set(record.supports)) == len(record.supports))
        check(type(record.observed_at) in (int, float) and bundle.as_of-WINDOW <= timestamp(record.observed_at) <= bundle.as_of)
        v = record.values
        check(type(v) is dict)
        support = []
        if record.source == "prometheus":
            check(set(v) == {"up", "up_at", "requests", "errors", "p95_seconds", "metrics_at", "incomplete", "raw_sha256"})
            check(v["up"] is None or type(v["up"]) is bool)
            check(type(v["incomplete"]) is bool and type(v["raw_sha256"]) is str and
                  re.fullmatch(r"[0-9a-f]{64}", v["raw_sha256"]) is not None)
            for key in ("requests", "errors", "p95_seconds"):
                check(v[key] is None or number(v[key]))
            for key in ("up_at", "metrics_at"):
                check(v[key] is None or type(v[key]) in (int, float) and record.observed_at-60 <= timestamp(v[key]) <= record.observed_at)
            if v["up"] is not None:
                check(v["up_at"] is not None)
                fresh.append(v["up_at"])
            if v["up"] is False:
                support.append("endpoint_unavailable")
            if v["requests"] is not None and v["errors"] is not None:
                check(v["errors"] <= v["requests"])
            valid = v["up"] is True and v["requests"] is not None and v["requests"] >= 20
            if valid and v["errors"] is not None and v["errors"] / v["requests"] >= .2:
                support.append("server_errors")
            if valid and v["p95_seconds"] is not None and v["p95_seconds"] >= 1:
                support.append("latency")
        else:
            check(set(v) in ({"ready", "restart_count"}, {"ready", "restart_count", "exit_code", "finished_at"}))
            check(type(v["ready"]) is bool and type(v["restart_count"]) is int and v["restart_count"] >= 0)
            if "exit_code" in v:
                check(type(v["exit_code"]) is int and type(v["finished_at"]) in (int, float) and
                      bundle.as_of-WINDOW <= timestamp(v["finished_at"]) <= record.observed_at)
                support.append("process_exit")
        check(tuple(support) == record.supports)
        body = {k: getattr(record, k) for k in ("source", "service", "observed_at", "values", "supports")}
        sha = hashlib.sha256(encoded(body).encode()).hexdigest()
        check(record.sha256 == sha and record.id == "ev-"+sha[:24] and record.id not in seen)
        seen.add(record.id)
    check(bundle.latest_telemetry == (max(fresh) if fresh else None))
    check(len(encoded(bundle.document()).encode()) <= MAX_INPUT)
    return bundle


class Aggregator:
    def __init__(self, as_of):
        self.bundle = Bundle(timestamp(as_of))
        self._records = {}
        self._platform = {}
        self._snapshots = {}
        self._calls = 0

    def _bounded(self, document):
        self._calls += 1
        if self._calls > 128 or len(encoded(document).encode()) > MAX_INPUT:
            raise ValueError("Evidence input budget exceeded")

    def _within(self, at):
        return self.bundle.as_of - WINDOW <= at <= self.bundle.as_of

    def _add(self, source, service, at, values, supports):
        body = {"source": source, "service": service, "observed_at": at, "values": values,
                "supports": tuple(supports)}
        digest = hashlib.sha256(encoded(body).encode()).hexdigest()
        eid = "ev-" + digest[:24]
        self._records[eid] = Evidence(eid, source, service, at, values, tuple(supports), digest)

    def snapshot(self, document):
        """Recompute from raw samples: cached derived service fields cannot forge support."""
        self._bounded(document)
        at = timestamp(document["at"])
        if not self._within(at):
            self.bundle.issues.append("telemetry_outside_window")
            return
        fingerprint = hashlib.sha256(encoded(document.get("raw", {})).encode()).hexdigest()
        if at in self._snapshots:
            if self._snapshots[at] != fingerprint:
                raise ValueError("Conflicting telemetry at one timestamp")
            return
        self._snapshots[at] = fingerprint
        try:
            snapshot = decode(document.get("raw", {}), {}, at)
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError, RecursionError):
            self.bundle.issues.append("invalid_observation")
            snapshot = decode({}, {}, at)
        if any(e.up is not None for e in snapshot.services.values()):
            latest = max(e.up_at for e in snapshot.services.values() if e.up is not None)
            self.bundle.latest_telemetry = max(self.bundle.latest_telemetry or latest, latest)
        else:
            self.bundle.issues.append("unavailable_telemetry")
        for service, e in snapshot.services.items():
            supports = []
            if e.up is False:
                supports.append("endpoint_unavailable")
            valid = e.up is True and e.requests is not None and e.requests >= 20
            error_valid = valid and not any(p.startswith("requests:") for p in e.problems)
            if error_valid and e.errors is not None and e.errors / e.requests >= .20:
                supports.append("server_errors")
            if error_valid and not any(p.startswith("buckets:") for p in e.problems) and e.p95 is not None and e.p95 >= 1.:
                supports.append("latency")
            if e.problems:
                self.bundle.issues.append("partial_telemetry")
            # No metric labels, logs, headers, instructions or arbitrary error text enter the prompt.
            self._add("prometheus", service, at,
                      {"up": e.up, "up_at": e.up_at, "requests": e.requests, "errors": e.errors,
                       "p95_seconds": e.p95, "metrics_at": e.metrics_at,
                       "incomplete": bool(e.problems), "raw_sha256": fingerprint}, supports)

    def platform(self, document):
        """Allowlisted platform fields only; historical last_state alone is insufficient."""
        self._bounded(document)
        at = timestamp(document["at"])
        if not self._within(at):
            return
        if any(at < old["at"] for old in self._platform.values()):
            raise ValueError("Platform observations must be chronological")
        services = document.get("services", {})
        if not isinstance(services, dict):
            self.bundle.issues.append("invalid_platform")
            return
        for service in SERVICES:
            state = services.get(service)
            if not isinstance(state, dict):
                continue
            count = state.get("restart_count")
            if type(count) is not int or count < 0 or type(state.get("ready")) is not bool:
                self.bundle.issues.append("invalid_platform")
                continue
            if not isinstance(state.get("state", {}), dict) or not isinstance(state.get("last_state", {}), dict):
                self.bundle.issues.append("invalid_platform")
                continue
            current = state.get("state", {}).get("terminated")
            previous = self._platform.get(service)
            restart = (previous and state.get("uid") == previous["uid"] and
                       count > previous["count"] and state.get("container_id") != previous["container_id"])
            terminated = current or (state.get("last_state", {}).get("terminated") if restart else None)
            supports, values = [], {"ready": state["ready"], "restart_count": count}
            if isinstance(terminated, dict):
                try:
                    finished = timestamp(terminated["finishedAt"])
                    exit_code = terminated["exitCode"]
                    identity_ok = bool(state.get("uid") and state.get("container_id"))
                    if current:
                        identity_ok = identity_ok and terminated.get("containerID") == state["container_id"]
                    if restart:
                        identity_ok = identity_ok and terminated.get("containerID") == previous["container_id"]
                    if identity_ok and type(exit_code) is int and self.bundle.as_of-WINDOW <= finished <= at:
                        values.update({"exit_code": exit_code, "finished_at": finished})
                        supports.append("process_exit")
                except (ValueError, KeyError, TypeError):
                    self.bundle.issues.append("invalid_termination")
            self._add("kubernetes", service, at, values, supports)
            self._platform[service] = {"at": at, "uid": state.get("uid"), "count": count,
                                       "container_id": state.get("container_id")}

    def finish(self):
        records = list(self._records.values())
        # Keep the latest supporting record for every service/cause before filling recent history.
        anchors = {}
        for record in sorted(records, key=lambda r: (r.observed_at, r.id)):
            for cause in record.supports:
                anchors[(record.service, cause)] = record
        selected = {r.id: r for r in anchors.values()}
        # Preserve the freshness witness as well as historical fault anchors.
        for service in SERVICES:
            current = [r for r in records if r.source == "prometheus" and r.service == service and r.values["up_at"] is not None]
            if current:
                newest = max(current, key=lambda r: r.values["up_at"])
                selected[newest.id] = newest
        for r in sorted(records, key=lambda r: (-r.observed_at, r.id)):
            if len(selected) >= MAX_RECORDS:
                break
            selected[r.id] = r
        if len(records) > MAX_RECORDS:
            self.bundle.issues.append("evidence_truncated")
        self.bundle.records = sorted(selected.values(), key=lambda r: (r.observed_at, r.id))
        if not self.bundle.eligible:
            self.bundle.issues.append("stale_or_missing_current_telemetry")
        return self.bundle
