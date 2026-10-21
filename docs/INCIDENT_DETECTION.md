# Day 4 deterministic incident detection

`services.incidents` is a separate polling service with a read-only FastAPI API and SQLite persistence. It uses the existing Day 3 Prometheus metrics. It has no LLM client, model credentials, Kubernetes client, shell execution or recovery action. Diagnoses describe observable symptoms and suspected dependency effects, not verified root causes.

## Run in the existing lab

Start/reuse the loopback Prometheus forward from `docs/OBSERVABILITY.md`. In the canonical checkout and project virtual environment:

```text
python scripts/detect.py once
python scripts/detect.py serve
```

`once` writes a single evidence record and returns exit code 2 if telemetry is incomplete (rather than claiming a healthy system). `serve` binds to `127.0.0.1:18082`, uses one worker, and polls with five seconds between completed collections. Initial startup may require warm-up traffic and at least ten seconds of counter coverage. Only one long-running collector should own a database. Multiple SQLite connections serialize writes; conflicting/out-of-order evidence is rejected.

Read `http://127.0.0.1:18082/docs`, `/incidents`, `/incidents/{id}` and `/evidence/{id}`. List and detail history are bounded to 100 records each. `/healthz` reports process liveness; `/readyz` requires a successful recent database-backed poll with usable telemetry. It does not assert healthy application performance. There are no write/action endpoints.

`INCIDENT_DB` defaults to `.local/incidents.sqlite3`; SQLite WAL/SHM files stay in that ignored directory. `PROMETHEUS_URL` defaults to `http://127.0.0.1:19090`. Other permitted URLs are exactly `http://localhost:19090` and `http://prometheus:9090`. The latter supports a future internal deployment, which is not added in Day 4. There is no new ingress or cluster privilege. Do not expose this unauthenticated lab API publicly.

## Evidence and measurement rules

All rules have version `day4-v1`. The collector sends exactly three fixed GET queries to `/api/v1/query` at one common evaluation timestamp:

- `up{job="safeheal"}[60s]`
- `safeheal_http_requests_total{job="safeheal"}[60s]`
- `safeheal_http_request_duration_seconds_bucket{job="safeheal"}[60s]`

Matrices preserve actual sample timestamps, avoiding confusing query evaluation time with data freshness. A newest sample older than 15 seconds is stale. Target identity must match the three current static Service endpoints. Duplicate/unknown targets, non-finite/negative values, future/unordered samples, annotated partial responses and wrong result types fail closed to insufficient telemetry. One replica per service remains a requirement of the Day 3 scrape configuration.

Each response is capped at 1 MiB, 512 series and 32 samples per series. Queries have a one-second server timeout, two-second HTTP operation timeouts, no redirects/proxy inheritance/retries, and an eight-second shared collection deadline checked during streaming (a blocked socket read may add up to two seconds). Stored evidence is capped at 4 MB per poll. Errors retain exception classes rather than arbitrary response text. Storage failures make the API unready; they do not emit successful evidence.

Performance rules require aligned fresh series, at least two scrapes spanning ten seconds, and at least 20 **observed counter increments** in the trailing 60-second sample window. Counts are sums of consecutive counter differences, counting the new value after a visible reset. They are conservative observed counts, **not extrapolated PromQL `increase()` estimates**. Activity before a series' initial observed sample is excluded; new status/route series delay eligibility until alignment is restored. Unobserved resets between scrapes can undercount activity. Zero/insufficient traffic means unknown performance, while a fresh successful scrape remains availability evidence.

The error numerator counts 5xx only; the denominator includes all completed business requests, including 4xx, consistent with Day 3. Probe and metrics traffic is excluded by the existing middleware. Histogram p95 uses linear interpolation in the existing classic cumulative buckets; each label family must have the complete expected schema, and total histogram increments must match request increments. An unbounded upper tail returns the last finite bucket as a conservative lower bound. Quantiles are estimates, not exact per-request percentiles.

| Rule | Alert | Clear | Continuous alert hold |
|---|---|---|---|
| `scrape_unavailable` | Fresh `up=0` | Fresh `up=1` | 10 s |
| `high_error_rate` | 5xx / completed requests >=20% | <=5% | 15 s |
| `high_latency` | p95 >=1 s | <=0.5 s | 15 s |
| `telemetry_unavailable` | Missing/stale/invalid required telemetry or query failure | Current valid telemetry | 15 s |

No business series before first traffic is normal warm-up, not a scrape outage. All other insufficient/invalid performance data produces `unknown`; invalid/missing expected histogram data after traffic also flags telemetry loss. A failed scrape does not establish that a process crashed: network, readiness withdrawal, Service routing or metrics endpoint failure can yield the same symptom.

## Lifecycle and diagnosis

A qualifying alert creates `pending`; distinct source observations over the hold window promote it to `open`. A short condition that clears becomes `resolved` with resolution `transient` and no opened timestamp. An open incident needs a clear observation to enter `recovering`, then 15 seconds of continuous clear evidence to resolve. Alert recurrence reopens the same incident. Values between trigger/clear thresholds hold open incidents and interrupt pending/recovery timers. Unknown evidence or a collection gap over 15 seconds also interrupts those timers; it never resolves an open incident. Repeated identical scrape samples cannot mature timers. A later recurrence after resolution receives a new incident ID.

SQLite stores raw query responses, normalized service evidence, query errors, rule version, every verdict, incident timestamps, transition reasons, diagnosis and correlations in one transaction. A partial unique index permits only one unresolved incident per service/rule. Collection timestamps deduplicate replay; conflicting or older batches are rejected. Times are Unix UTC in raw evidence/history and UTC ISO 8601 in public incident fields. A process restart preserves state and applies the same gap rules.

Diagnoses identify server error spike, request latency degradation, unavailable service/metrics endpoint, or insufficient telemetry. When an open upstream 5xx incident overlaps a fresh downstream scrape failure and their first detections are within 60 seconds, the fixed gateway -> order -> payment topology produces a `suspected_dependency` link. The deepest evidenced downstream target is preferred. Both rule/service observations are referenced by evidence ID. Incident records remain distinct, so correlations do not erase independent symptoms. Correlation is a hypothesis; it does not prove common request identity or justify summing upstream/downstream errors as independent failures. Historical links remain timestamped; the latest diagnosis reflects current evidence.

## Verification and remaining acceptance

Run `python -m pytest -q`. Reproduce the labelled synthetic lifecycle checks with `python scripts/verify_detector.py`. For an actual loopback HTTP service smoke that detects absent Prometheus telemetry, run `python scripts/verify_detector_api.py` with unused ports 18082 and 19090; it starts and stops only its own detector process and uses a temporary SQLite database. Tests cover all rules, boundaries, transient faults, hysteresis, insufficient/malformed/stale telemetry, resets, fresh-source requirements, replay, persistence/restart, transaction rollback, concurrent duplicate ingestion, correlation and the collector/API path. An integration test creates **actual HTTP 503 responses in the existing order FastAPI app**, parses its real exported metrics, and opens a server-error incident. That integration uses TestClient and simulated scrape timestamps; Prometheus responses in collector tests are fixtures.

Implementation began offline and was integrated into the verified clean canonical checkout after reconnection. `python scripts/verify_detector_pause.py` performs a dry run of the scoped real-cluster acceptance; `--execute` pauses only the guarded payment container task. A fixed node-side script resumes that exact task after a nominal 35 seconds, also attempts resume on exit/signals, and gives ctr operations a ten-second total / five-second connect timeout. The existing fault lock prevents simultaneous developer faults. Kubernetes may restart payment through liveness; the controller executes no remediation. The harness records baseline/fault/recovery Prometheus responses, verdicts, actual HTTP requests, transitions and final Pod/health/order checks. This privileged developer harness is separate from the read-only service; operating-system privilege separation is not established here. GitHub Actions reproduces it in a fresh isolated kind cluster.

Two earlier Service-selector disconnection trials are retained as failed acceptance attempts. The first detected a payment scrape failure but did not generate the expected gateway 5xx; the second produced no failed payment scrape. Existing HTTP keep-alive connections can survive Service endpoint withdrawal, including Prometheus connections. Do not infer healthy new connections or a process crash from scrape results alone. `scripts/verify_detector_live.py` preserves that routing probe and its direct fresh-connection ground truth; it is not the reproducible CI acceptance gate. A native interruption shorter than the configured hold should remain transient; thresholds are not reduced to force incident opening. See WORKLOG.md and evidence/day4 for exact outcomes.

This lab stores append-only evidence without automatic retention/rotation or high availability. At a five-second cadence even bounded records can grow substantially. Stop the detector when not testing, retain labelled trial evidence separately, and design retention/export before long-running experiments. No process-crash identity, resource-saturation classification, safe recovery executor or research benchmark is supplied by this milestone.

Primary API/measurement references consulted: [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/), [querying basics and staleness](https://prometheus.io/docs/prometheus/latest/querying/basics/), [counter rate/extrapolation semantics](https://prometheus.io/docs/prometheus/latest/querying/functions/).


Day 4 local acceptance passed in trial `day4-pause-670cd6f0b91f` with real Prometheus and 250 actual gateway responses (187 x 201, 63 x 503). Payment scrape loss plus gateway/order latency and error signals opened five incidents; all resolved after timed resumption/native recovery. Payment restarted within the same Pod (2 -> 3), upstream containers stayed stable, and final health/orders passed. The 118-test Windows suite passes; see evidence/day4 for source hashes and full observations. This is an engineering check, not a research benchmark.
