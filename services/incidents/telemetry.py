"""Bounded Prometheus matrix reads; retain original sample times, never fill gaps with zero."""
from dataclasses import asdict, dataclass, field
import math
import time

import httpx

SERVICES = ("gateway", "order", "payment")
INSTANCES = {f"{s}:8000": s for s in SERVICES}
WINDOW = 60
MAX_AGE = 15
MAX_BYTES = 1_048_576
BUCKETS = (.005, .01, .025, .05, .1, .25, .5, 1., 2., 3., 5., 10., math.inf)
QUERIES = {
    "up": 'up{job="safeheal"}[60s]',
    "requests": 'safeheal_http_requests_total{job="safeheal"}[60s]',
    "buckets": 'safeheal_http_request_duration_seconds_bucket{job="safeheal"}[60s]',
}
ALLOWED_URLS = frozenset({"http://127.0.0.1:19090", "http://localhost:19090", "http://prometheus:9090"})


@dataclass
class ServiceEvidence:
    up: bool | None = None
    up_at: float | None = None
    requests: float | None = None
    errors: float | None = None
    p95: float | None = None
    metrics_at: float | None = None
    problems: list[str] = field(default_factory=list)


@dataclass
class Snapshot:
    at: float
    services: dict[str, ServiceEvidence]
    raw: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)

    def document(self):
        return asdict(self)


def samples(row, now):
    values = row["values"]
    if not 1 <= len(values) <= 32:
        raise ValueError("sample count")
    parsed = [(float(t), float(v)) for t, v in values]
    if any(not math.isfinite(t) or not math.isfinite(v) or v < 0 or
           not now - WINDOW <= t <= now for t, v in parsed):
        raise ValueError("invalid sample")
    if any(a[0] >= b[0] for a, b in zip(parsed, parsed[1:])):
        raise ValueError("unordered samples")
    if now - parsed[-1][0] > MAX_AGE:
        raise ValueError("stale samples")
    return parsed


def delta(values):
    # Conservative observed increments, without extrapolation to window boundaries.
    # On a visible reset, count only the new counter value. Never count initial value.
    return sum(b if b < a else b - a for (_, a), (_, b) in zip(values, values[1:]))


def percentile(buckets):
    if set(buckets) != set(BUCKETS):
        raise ValueError("incomplete histogram")
    counts = [buckets[b] for b in BUCKETS]
    if any(a > b + 1e-8 for a, b in zip(counts, counts[1:])):
        raise ValueError("non-cumulative histogram")
    if counts[-1] < 20:
        return None
    rank, previous_count, previous_bound = .95 * counts[-1], 0., 0.
    for bound, count in zip(BUCKETS, counts):
        if count >= rank:
            if math.isinf(bound):
                return previous_bound  # Conservative lower bound for the unbounded tail.
            return previous_bound + (bound - previous_bound) * (rank - previous_count) / (count - previous_count)
        previous_count, previous_bound = count, bound
    raise ValueError("invalid histogram")


def decode(raw, errors, now):
    if not math.isfinite(now) or now < 0:
        raise ValueError("invalid collection time")
    result = {s: ServiceEvidence() for s in SERVICES}
    grouped = {name: {s: [] for s in SERVICES} for name in QUERIES}
    for name in QUERIES:
        try:
            body = raw[name]
            if body.get("warnings") or body.get("infos"):
                raise ValueError("partial or annotated result")
            data = body["data"]
            rows = data["result"]
            if body["status"] != "success" or data["resultType"] != "matrix" or not isinstance(rows, list) or len(rows) > 512:
                raise ValueError("invalid matrix")
            seen = set()
            for row in rows:
                labels = row["metric"]
                service = INSTANCES.get(labels.get("instance"))
                if labels.get("job") != "safeheal" or service is None:
                    raise ValueError("unexpected target")
                if name != "up" and labels.get("service") != service:
                    raise ValueError("service/instance mismatch")
                key = tuple(sorted(labels.items()))
                if key in seen:
                    raise ValueError("duplicate series")
                seen.add(key)
                grouped[name][service].append((labels, row))
        except (KeyError, TypeError, ValueError, AttributeError):
            for s in SERVICES:
                result[s].problems.append(f"{name}:unavailable_or_invalid")
            grouped[name] = {s: [] for s in SERVICES}

    for service, evidence in result.items():
        try:
            rows = grouped["up"][service]
            if len(rows) != 1:
                raise ValueError("missing or ambiguous up")
            values = samples(rows[0][1], now)
            if any(v not in (0., 1.) for _, v in values):
                raise ValueError("invalid up")
            evidence.up_at, value = values[-1]
            evidence.up = bool(value)
        except (KeyError, TypeError, ValueError):
            evidence.problems.append("up:missing_stale_or_invalid")

        if evidence.up is not True:
            continue  # Old counters cannot describe the current failed scrape.
        parsed = {}
        for name in ("requests", "buckets"):
            try:
                rows = grouped[name][service]
                if not rows:
                    continue  # No request series before first business traffic is normal.
                series = [(labels, samples(row, now)) for labels, row in rows]
                times = {tuple(t for t, _ in values) for _, values in series}
                if len(times) != 1:
                    raise ValueError("unaligned/new series")
                timeline = next(iter(times))
                if len(timeline) < 2 or timeline[-1] - timeline[0] < 10:
                    continue  # Warm-up/insufficient coverage, not healthy performance.
                parsed[name] = (series, timeline)
            except (KeyError, TypeError, ValueError):
                evidence.problems.append(f"{name}:stale_or_invalid")
        if "requests" in parsed:
            series, timeline = parsed["requests"]
            if any(labels.get("status_class") not in {"1xx", "2xx", "3xx", "4xx", "5xx"} for labels, _ in series):
                evidence.problems.append("requests:invalid_status")
            else:
                evidence.requests = sum(delta(v) for _, v in series)
                evidence.errors = sum(delta(v) for labels, v in series if labels["status_class"] == "5xx")
                evidence.metrics_at = timeline[-1]
        if "buckets" in parsed:
            try:
                series, timeline = parsed["buckets"]
                buckets, families = {}, {}
                for labels, values in series:
                    bound = float(labels["le"])
                    if math.isnan(bound) or bound not in BUCKETS:
                        raise ValueError("invalid bucket")
                    family = tuple(sorted((k, v) for k, v in labels.items() if k != "le"))
                    families.setdefault(family, set()).add(bound)
                    buckets[bound] = buckets.get(bound, 0.) + delta(values)
                if any(bounds != set(BUCKETS) for bounds in families.values()):
                    raise ValueError("incomplete histogram family")
                evidence.p95 = percentile(buckets)
                if "requests" not in parsed or timeline != parsed["requests"][1]:
                    raise ValueError("request/histogram misalignment")
                if abs(buckets[math.inf] - evidence.requests) > 1e-6:
                    raise ValueError("request/histogram count mismatch")
            except (KeyError, TypeError, ValueError):
                evidence.p95 = None
                evidence.problems.append("buckets:incomplete_or_invalid")
        elif evidence.requests and evidence.requests >= 20:
            evidence.problems.append("buckets:missing")
    return Snapshot(now, result, raw, errors)


class Collector:
    def __init__(self, url="http://127.0.0.1:19090", transport=None):
        if url not in ALLOWED_URLS:
            raise ValueError("Only the configured lab Prometheus endpoints are allowed")
        self.url, self.transport = url, transport

    def collect(self, at=None):
        now = time.time() if at is None else at
        raw, errors = {}, {}
        deadline = time.monotonic() + 8.
        with httpx.Client(timeout=2., follow_redirects=False, trust_env=False, transport=self.transport) as client:
            for name, expression in QUERIES.items():
                try:
                    if time.monotonic() >= deadline:
                        raise ValueError("collection deadline")
                    with client.stream("GET", self.url + "/api/v1/query",
                                       params={"query": expression, "time": str(now), "timeout": "1s"}) as response:
                        response.raise_for_status()
                        payload = bytearray()
                        for chunk in response.iter_bytes():
                            if time.monotonic() >= deadline:
                                raise ValueError("collection deadline")
                            payload.extend(chunk)
                            if len(payload) > MAX_BYTES:
                                raise ValueError("response too large")
                    import json
                    raw[name] = json.loads(payload)
                except (httpx.HTTPError, ValueError) as exc:
                    errors[name] = type(exc).__name__  # No URL credentials or arbitrary response text.
        return decode(raw, errors, now)
