# Day 5: fault injection and initial benchmark protocol

The benchmark runs controlled payment-service failures while recording application
requests, platform state, and the unchanged Day 4 deterministic detector. Native
Kubernetes recovery and rule-based diagnosis are observed during the same trial.
The detector performs no recovery action. Application fault expiry and harness
cleanup have their own recovery attribution.

This document describes the implemented protocol and how to reproduce it. It does
not assert that a particular run passed. Use the saved `trial.json`, `summary.json`,
and `run.json` records, together with [PROJECT_STATUS.md](../PROJECT_STATUS.md) and
[EXPERIMENTS.md](../EXPERIMENTS.md), for measured outcomes and retained failures.

## 1. Run from the existing project

Use the project Python environment with `requirements.lock` installed. In an
activated environment, the commands below use `python`. On the Windows development
computer, `.\.venv\Scripts\python.exe` can be substituted explicitly; on Linux,
use `.venv/bin/python`.

### Inspect a plan without injecting

```text
python scripts/benchmark.py run
python scripts/benchmark.py run --backend kubernetes --repeats 2 --seed 5
python scripts/benchmark.py run --scenario latency --repeats 1
```

`run` defaults to a printed, non-mutating plan. Without `--execute`, it does not
contact the cluster, identify a target, deploy software, or create an experiment
directory. Plan construction validates scenario names and bounded parameters.
This is a planning preview, not a successful cluster preflight.

### Prepare the designated Kubernetes lab

Reuse the existing `safeheal-dev` kind cluster and the project-local
`.local/kubeconfig`. The context and namespace must be `kind-safeheal-dev` and
`safeheal-dev`. See [KUBERNETES.md](KUBERNETES.md) for initial setup and
[OBSERVABILITY.md](OBSERVABILITY.md) for monitoring deployment.

When the current application image and monitoring configuration need deployment,
run the existing project commands before the experiment:

```text
python scripts/k8s.py status
python scripts/k8s.py deploy
python scripts/observe.py deploy
python scripts/k8s.py verify
```

The benchmark itself never deploys an image, changes a Deployment, deletes a Pod,
or switches the user's default Kubernetes context. Its preflight requires the
already-deployed payment source to match this checkout's `services/app.py` and
`services/benchmark_faults.py` hashes. The dedicated local-test payment manifest
explicitly sets `SAFEHEAL_FAULTS_ENABLED=local-test`; the application fault feature
is disabled when that opt-in is absent.

Loopback port `19090` must be available. The runner creates its own Prometheus
forward and refuses to reuse an unrelated listener. If an earlier project
Prometheus forward is still running, stop that known terminal/process normally
before starting the benchmark. The runner does not discover a port owner and kill
it. Gateway and payment forwards use available loopback ports. A separate detector
daemon is unnecessary: each trial creates its own read-only observer and database.

### Execute and inspect results

```text
python scripts/benchmark.py run --execute --backend kubernetes --repeats 2 --seed 5
python scripts/benchmark.py summarize evidence/day5/run-REPLACE_WITH_RUN_ID
```

The first command executes all three scenarios twice in the saved seeded order.
The printed result includes the actual run directory, execution counts, and the
Kubernetes acceptance decision. The summary command re-evaluates stored trial
records and rewrites only that directory's derived `summary.json` and
`summary.csv`; it does not inject another fault.

For a targeted engineering check:

```text
python scripts/benchmark.py run --execute --scenario http_5xx --repeats 1 --duration-seconds 90
```

One scenario or one repetition can finish successfully without satisfying the
full Day 5 acceptance gate. The process exit code reports whether the requested
plan completed with successful evaluated trials; inspect `acceptance.passed`
separately for the three-scenario Kubernetes gate.

The CLI exposes `--backend`, repeatable `--scenario`, `--repeats`, `--seed`,
`--duration-seconds`, `--baseline-seconds`, `--recovery-timeout-seconds`, and
`--output`. Application fault duration is restricted to 1–120 seconds; the default
is 90 seconds. Repetitions are restricted to 1–20. The process-crash scenario is a
single stop operation; its duration is not a request to keep killing containers.

## 2. Scenarios and independently recorded ground truth

Every scenario targets the synthetic payment service. The planned target and
fault class are written before mutation, independently of anything the detector
subsequently reports.

| Scenario | Injection | Evidence of application impact | Expected restoration |
|---|---|---|---|
| `process_crash` | One CRI stop of the validated payment container ID, with zero container-stop grace | Observed affected gateway request plus container termination/restart evidence | Kubernetes restarts the container; no harness restart or Pod deletion |
| `http_5xx` | Immutable 90-second lease makes payment business requests return HTTP 500 | Direct payment response has the exact trial/scenario headers and HTTP 500; an affected gateway request is also required | Lease expiry, or explicitly recorded harness cleanup |
| `latency` | Immutable 90-second lease adds up to 1.25 seconds to each payment business request | Direct payment response has matching headers, a valid receipt, and at least 1 second elapsed; an affected gateway request is also required | Lease expiry, or explicitly recorded harness cleanup |

The application hook affects `/payments` only. It does not deliberately fail or
delay `/healthz`, `/readyz`, or `/metrics`. Gateway and order translate downstream
HTTP errors into dependency failures, so an injected payment 500 need not appear
as a 500 at the gateway. The scenario name identifies the injection mechanism,
not a promise that all three services emit identical statuses.

Application verification checks the response headers `x-safeheal-fault-id` and
`x-safeheal-fault-scenario` against the current trial. The direct probe is retained
under `ground_truth.direct_effect_probe`. The earliest completed affected gateway
request observed so far is retained separately. Gateway impact means an invalid
or unsuccessful business response; for the latency scenario, a valid response
with elapsed time at least one second also qualifies.

An acknowledgement alone is insufficient. If the intended application fault or
gateway impact is not observable, the trial cannot pass by relabeling an unrelated
detector alert. A very short crash may produce no sampled gateway failure; that
attempt remains recorded as unsuccessful even if the platform restarted a
container.

### Bounded application leases

`services/benchmark_faults.py` accepts two application fault types and a small,
strictly validated data document. There is no HTTP control endpoint or supplied
code execution. In Kubernetes, the guarded developer harness writes the lease
through authenticated exec into the identified payment container at
`/tmp/safeheal-benchmark-fault.json`, using the existing `/tmp` volume.

The lease has an immutable trial ID, activation time, and expiry time. Activation
refuses an existing lease, including an expired lease belonging to another
attempt. Cleanup verifies the exact trial ID. Maximum lifetime is 120 seconds and
maximum delay is 1.5 seconds. Application evaluation uses the expiry time plus a
monotonic deadline cap; changing an already-observed trial's document cannot
extend its fault. Missing or malformed controls do not inject faults.

The 90-second default is fixed by the plan and does not depend on whether an alert
has opened. Stopping an injection as soon as detection succeeds would change
fault exposure according to the observed result and bias comparisons.

## 3. Repetition, workload and timing

| Setting | Default and interpretation |
|---|---|
| Scenario repetitions | Two per scenario: six planned trials |
| Order | Deterministic shuffle with seed `5` |
| Gateway workers | Four concurrent workers |
| Request pacing | Each worker waits 0.2 seconds after its preceding request completes |
| HTTP timeout | Four-second client operation timeout |
| Baseline duration | At least 75 seconds before injection |
| Clean baseline hold | At least 15 continuous seconds meeting all baseline conditions |
| Detector polling target | One collection cycle every five seconds, independently of blocking platform commands |
| Platform sampling | Approximately every five seconds after the previous platform read |
| App fault duration | Fixed 90-second lease; process crash is one instantaneous stop request |
| Recovery/observation budget | 180 seconds, plus the planned application-fault duration for app scenarios |
| Business recovery hold | At least three consecutive healthy completions spanning at least two seconds |

The workload is **closed loop**. Four workers with a 0.2-second completion delay
do not impose a constant 20 requests/second during a slow or failing service.
Offered throughput falls when requests take longer. Record the actual request
counts and durations; do not describe these trials as constant-rate load tests.

Each gateway request purchases quantity two of the synthetic `benchmark` item.
A valid success requires HTTP 201, `confirmed` status, 2000 cents, matching
quantity/item, and nonempty order/payment identifiers. A healthy response also
completes in less than 0.5 seconds. The recovery calculation orders completed
post-injection requests by completion time and resets its consecutive-success
sequence whenever an unhealthy result appears.

Baseline requires fresh, eligible telemetry with every rule clear, no active
incidents, at least 20 completed gateway requests, and the latest 20 responses
healthy. Previously resolved warm-up incidents are retained and excluded from
later detection matching. The baseline deadline is
`max(180, baseline_seconds + 120)` seconds: 195 seconds at defaults. The clean hold
can overlap the 75-second baseline; it is not unconditionally another 15 seconds.

Recovery observation continues long enough to cover at least the detector's
60-second lookback plus 15-second recovery hold, and at least the application
fault duration when applicable. Completion also requires successful cleanup,
observed business impact and sustained recovery, healthy eligible telemetry,
no active incidents, and fresh final service checks. The budget does not promise
an exact total wall-clock duration: bounded preflight, commands, probes and final
checks add overhead.

After the final service check, the runner drains in-flight workload requests,
reads platform identities again while telemetry collection continues, and then
closes the observer. It recomputes business recovery from the complete request
record. Late unhealthy responses, unexpected identity/restart changes, or final
unresolved/ineligible telemetry prevent a successful trial; the conflicting
evidence remains saved.

The seed reproduces scenario ordering. Actual timestamps, UUIDs, process/container
identities, scheduling and response durations vary. Separate repetitions measure
that variation; they are not expected to produce byte-identical records.

## 4. Unchanged rule baseline and the 90-second choice

The benchmark uses the existing Collector, Controller, SQLite lifecycle, and
`day4-v1` rules. The observer runs in a background thread so CRI and kubectl waits
do not stop telemetry polling. It records each original snapshot and the first
opening diagnosis before a later `recovered` diagnosis can replace it.

| Rule | Qualifying condition | Opening hold |
|---|---|---|
| `scrape_unavailable` | Observed scrape failure for the service | 10 seconds |
| `high_error_rate` | At least 20 observed requests and 5xx fraction at least 20% | 15 seconds |
| `high_latency` | Eligible histogram with estimated p95 at least 1 second | 15 seconds |
| `telemetry_unavailable` | Missing, stale, malformed or incomplete telemetry | 15 seconds |

The counter/histogram lookback is 60 seconds. Error clear threshold is 5%; latency
clear threshold is 0.5 seconds. Recovery requires 15 continuous seconds of
qualifying healthy evidence. Maximum sample age and maximum uninterrupted
collection gap are each 15 seconds. Low traffic, missing evidence and hysteresis
do not count as continuous failure or healthy recovery. See
[INCIDENT_DETECTION.md](INCIDENT_DETECTION.md) for the complete rule semantics.

Prometheus separates scrape interval from query evaluation. Its range selectors
retrieve samples over a time window; the benchmark reads the original samples
and timestamps instead of inventing samples at collection times. See the official
[scrape configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
and [range-vector documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/#range-vector-selectors).

The local decoder deliberately rejects request/histogram families with unaligned
sample timelines. A newly observed HTTP status class creates new metric series;
those series may need approximately one 60-second lookback to align with existing
families. Short application faults can therefore end before the existing rules
receive enough eligible failure observations to complete their 15-second hold.
The 90-second default leaves time for that alignment, the hold, and scrape/poll
phase differences. This is a documented protocol choice, not a lowered detection
threshold or a guarantee that every fault will be detected. Preserve earlier
short-duration attempts and their source/configuration alongside later runs.

Newly opened incidents match only predefined `(service, rule)` pairs across
gateway/order/payment: crash matches scrape, error-rate or latency symptoms;
HTTP error matches error-rate symptoms; latency matches latency symptoms.
`telemetry_unavailable` does not count as successful detection of a business
fault. Neither a pending-only incident nor an incident originating before
injection counts. Several correlated symptoms can arise from one injected fault;
they remain one ground-truth trial.

## 5. Recovery attribution

### Kubernetes container restart

Kubernetes restart policy governs restarting terminated containers in a Pod;
readiness determines eligibility for Service traffic, while liveness/startup
failures have their own restart behavior. These distinctions are documented in
the official [Pod lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
and [probe guide](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/).

The crash scenario stops a container directly. It tests native restart following
that termination, not whether a liveness threshold was exceeded. Native
attribution requires all of the following evidence:

- Payment retains its Pod UID and receives a different container ID.
- Payment restart count increases and the new container is observed Ready.
- The final `last_state.terminated.containerID` identifies the original container.
- The termination has an integer exit code and a parseable `finishedAt` between
  injection request minus one second and the observed native readiness time.
- Gateway and order retain their Pod/container identities and restart counts and
  are healthy; sustained business responses and final checks also succeed.

The one-second lower tolerance accommodates Kubernetes termination timestamps
with second precision. It is an event-consistency tolerance, not a precise fault
duration. The evaluator never derives high-resolution downtime from that field.
Unexpected Pod replacement or an upstream restart fails the controlled scenario.

Kubernetes trials end with checks through the existing in-cluster Service DNS
path as well as platform state. Diagnostic workload reaches the owned gateway
Pod through its loopback forward, so gateway readiness withdrawal cannot hide
every application error from the workload.

### Application expiry and harness cleanup

After the planned lease duration and a small observation allowance, a direct
payment probe checks that the trial header is absent and the response is healthy.
If verified before lease removal, attribution is `fault_expiry`. If removal is
needed, attribution is `harness_cleanup`. Both require recorded cleanup and
business recovery. An unexpected payment restart during either application
scenario is a failure, not evidence that Kubernetes fixed the business fault.

Rules only observe these recoveries. The evidence always records
`rule_executed_recovery: false`. There is no model call, token expenditure or AI
recovery executor in this protocol.

## 6. Timestamps and metric meanings

Raw records contain UTC timestamps and runner monotonic elapsed times where
available. Read the source event and observation event separately.

| Field or metric | Meaning |
|---|---|
| `injection_requested_at` | Host recorded its intent to call the guarded injector; includes subsequent command overhead |
| `injection_confirmed_at` | Injector returned an acknowledgement |
| `fault_effect_observed_at` | Completion time of the first affected gateway request recorded for this trial |
| `first_opened_at` | Detector's timestamp for its first matching opened incident |
| `first_open_observed_at` | Host observer first retrieved that opened incident |
| `detection_latency_seconds` | `first_opened_at - injection_requested_at` |
| `native_ready_at` | First platform observation satisfying replacement-container readiness checks |
| `native_ready_latency_seconds` | Host native-ready observation minus injection request, only with verified native attribution |
| `fault_removed_at` | Host verified expiry or completed guarded lease removal |
| `first_business_recovered_at` | First completion in the currently qualifying uninterrupted healthy sequence |
| `sustained_recovery_at` | First point where that sequence contains at least three successes spanning two seconds |
| `business_recovery_seconds` | Sustained business recovery minus injection request |
| `all_matched_resolved_at` | Latest resolution time, only when all matched opened incidents have resolved |

These measurements include observation, HTTP and command overhead. They are not
exact physical fault-onset-to-recovery intervals or production downtime. Detector
event times derive from collection snapshots; fetching an event occurs later.
An effect-relative latency is null if the event ordering cannot support a
nonnegative interval. UTC comparison assumes the development environment's clock
consistency; this harness does not independently calibrate host/node clock skew.

An eligible trial with no matched opened incident has detection status `missed`,
null detection latency and a censored observation interval. Insufficient eligible
evidence is `not_eligible`, not a zero latency. The runner's eligibility flag means
at least one expected rule had an evaluable post-injection observation; it does
not claim continuously complete telemetry throughout the fault. Inspect raw
snapshots and unknown verdicts for that stronger assessment.

`diagnosis_target_match` only asks whether the captured opening diagnosis names
payment as its service or suspected root service. It is not a validated
root-cause-accuracy score. A correct symptom label does not prove the physical
cause was diagnosed.

## 7. Stored evidence and failure handling

Each execution reserves a new `evidence/day5/run-<id>/` directory. Each attempted
trial gets its own `d5-<sequence>-<scenario>-<id>/` subdirectory. Existing trial
directories cannot be overwritten by a rerun.

| Artifact | Contents |
|---|---|
| `plan.json` | Scenarios, repetitions, seed, deterministic order and settings |
| `source.json` | Commit, branch, working-tree status and relevant source/configuration hashes |
| `rule-config.json` | Detector version, thresholds, windows, holds and absence of an executor |
| `run.json` | Environment/preflight evidence, run status, verified final health/backend shutdown, completion timestamp and errors |
| `summary.json` / `summary.csv` | Derived evaluation for every stored attempted trial |
| `port-forward-*.txt` | Owned Kubernetes forwarding logs, when that backend is used |
| Trial `trial.json` | Planned labels, acknowledgements, direct probes, event times, identities, incidents, cleanup and evaluation |
| Trial `requests.jsonl` | Each gateway workload request, response validation, status and elapsed time |
| Trial `telemetry.jsonl` | Original Prometheus/decoded snapshots, evidence IDs and observation times |
| Trial `platform.jsonl` | Sampled service identities, readiness and restart observations |
| Trial `detector.sqlite3` | Per-trial evidence, verdicts, lifecycle transitions, diagnoses and correlations |

JSON checkpoints are written atomically. JSONL records are flushed after each
write, periodically synced, and synced at close. Controlled exceptions and normal
interrupt handling attempt guarded cleanup and preserve failure details. No
program can guarantee a final checkpoint after host power loss or an uncatchable
process kill; application leases still have their independently enforced expiry.

The runner stops after an unsuccessful trial, cleanup failure or failed
evaluation. It does not silently retry the fault, reselect a replacement target,
or continue injecting until a favourable record appears. Re-running creates a
new run with distinct IDs. Keep failed runs when presenting later successful
ones. A preflight failure appears in `run.json` even when no trial was started.
Summary denominators count attempted trial records, not unstarted plan entries;
compare plan, run status and summary together.

## 8. Acceptance and optional local-process checks

`summary.acceptance.passed` requires at least two successful, uniquely identified
actual Kubernetes trials for **each** of `process_crash`, `http_5xx`, and
`latency`, followed by successful run-level final health and backend shutdown.
The persisted run must have completed and recorded its finish timestamp.
`acceptance.trials_passed` retains the trial-count decision separately from
`acceptance.run_finalization_passed`; six good trial records cannot hide a later
failed final check, failed cleanup, or incomplete run. Successful trial execution
requires independently verified injection and
impact, consistent timestamps, verified cleanup, business recovery and correct
recovery attribution. A detector miss is reported separately and does not itself
invalidate an otherwise valid execution trial. Duplicate record IDs cannot
manufacture repetitions; failed attempts remain in success-rate denominators.

The optional local backend launches three actual FastAPI processes and a
checksum-pinned Prometheus 3.15.0 process on loopback. Its installer supports
Linux x86_64:

```text
python scripts/install_benchmark_prometheus.py
python scripts/benchmark.py run --backend local-process --repeats 2
python scripts/benchmark.py run --execute --backend local-process --repeats 2
```

Local runtime logs and Prometheus data live under `.local/benchmarks/<run-id>/`;
experiment records still use the selected evidence directory. The backend only
signals subprocesses it created and uses its own payment supervisor after an
authorized crash. Its recovery is `local_process_supervisor`, never
`native_kubernetes`. Local records contain real process exits, requests and
Prometheus observations, but no kubelet, Kubernetes probes, Service DNS or
container recovery measurement. Local-process and synthetic/unit-test results
cannot satisfy the Kubernetes acceptance gate.

## 9. Scope and limits

- This is a single-node, one-replica development lab with simulated payments. It
  does not establish high availability, node-failure tolerance or production SLOs.
- Native behavior and rule diagnosis are observed in the same trials. These are
  not separate matched A/B recovery-policy arms and do not demonstrate that rules
  improved recovery over Kubernetes.
- Two repetitions establish initial reproducibility only. They are insufficient
  for strong reliability estimates, effectiveness claims or narrow uncertainty
  bounds. Larger matched experiments belong to the later research phase.
- Workload is closed loop, and the diagnostic gateway route uses port-forwarding.
  Load changes during latency, and forwarding/API overhead affects measurements.
- Single direct payment proof/expiry probes and final verification calls add some
  application traffic. They are evidence probes, not gateway workload rows.
- Histogram p95 is a bucket estimate. The raw HTTP durations, counter windows,
  scrape times and detector times describe different measurements.
- Warm-up, new-series alignment, missing evidence, short faults and scheduling
  phase can cause delayed or missed detections. Absence of a detected incident
  does not prove absence of the injected fault.
- Restart history and native backoff can affect repeated crash trials. The runner
  verifies healthy baselines but does not reset the cluster or erase restart
  history to equalize these conditions.
- Application TTL determines much of HTTP-error/latency recovery time. These runs
  cannot measure an executor's ability to repair an enduring application defect.
- No statistical false-positive rate is inferred from the short healthy baseline,
  and no detector/AI accuracy claim follows from symptom matching alone.
- The developer harness has host Docker/cluster privileges. Explicit allowlists,
  ownership checks, exact identities, shared fault locking, bounded leases and
  cleanup constrain this experiment; they are not OS privilege separation or the
  future least-privilege recovery executor. Never expose the harness as an
  unrestricted model tool.

## References and implementation map

Official references checked on 2026-10-22:

- [Kubernetes: Pod lifecycle and container restarts](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [Kubernetes: configure liveness, readiness and startup probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Prometheus: scrape configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus: range-vector query semantics](https://prometheus.io/docs/prometheus/latest/querying/basics/#range-vector-selectors)

Implementation: `scripts/benchmark.py` orchestrates the run;
`scripts/benchmark_core.py` validates plans and evaluates stored evidence;
`scripts/benchmark_kubernetes.py` and `scripts/benchmark_local.py` implement the
scoped backends; `services/benchmark_faults.py` enforces application leases.
The existing `services/incidents/` package remains the rule baseline. Consult
the recorded source hashes when interpreting an older run against newer code.
