# Experiment register

Status: research protocol remains a draft. Day 2 now has one recorded local native-recovery engineering acceptance trial and a successful independent CI execution. Day 3 observability also passed a recorded real-traffic engineering check, including basic distributed spans and an intentional native container interruption. No matched research benchmark, rule-controller result or AI result has been collected.

## Hypothesis

Evidence-grounded LLM diagnosis may improve root-cause classification and safe recovery compared with deterministic rules, but may increase latency/cost and may fail under incomplete evidence. Evaluate rather than assume improvement.

## Approaches

A: Native Kubernetes restart/reconciliation/probes only. B: deterministic detector/diagnosis and allowlisted recovery. C: same detector/evidence/action policy as B, with LLM-assisted diagnosis. Hold workload, resource limits, fault severity and recovery verification fixed. Native Kubernetes does not provide equivalent root-cause classification; mark unavailable diagnosis metrics N/A rather than fabricate labels.

## Scenarios

Process crash; HTTP 500 spike; added latency; CPU/memory saturation; faulty deployment/configuration; dependency outage as a stretch goal. Fault injection is limited to the named local test cluster/namespace and requires baseline restoration between trials.

## Measurements

- Trial ID: scenario/approach/repetition/seed; retain commit, prompt version, provider/model, config, workload and environment.
- t0: verified injection onset; t_detect: first qualifying detection; t_recover: first time the predeclared healthy window is satisfied.
- Detection latency = t_detect - t0; time to recovery = t_recover - t0; separately report post-detection remediation time.
- Diagnosis accuracy: predicted class versus withheld ground truth, separate from recovery success.
- Recovery success: health and error/latency SLOs sustained over a predeclared window before timeout. Choose thresholds before controlled trials.
- Record failed/censored trials, not only successes. Report success rate and median/mean recovery time with uncertainty and censoring limitations.
- False-positive/negative rates require labelled healthy and faulty windows. Record denominators.
- Unsafe proposals / all proposals, unsafe execution count, token usage, recorded provider pricing, executor overhead.

Aim for five repetitions per scenario/approach when resources permit. Randomize/counterbalance ordering, reset verified baseline state, retain individual JSONL/CSV records, and bootstrap uncertainty where appropriate; explain small-sample limits.

Day 1 tests/smoke checks and the Day 2 acceptance checks below are engineering validation, not controlled research benchmark evidence. Research findings: none yet.

## Day 2 native recovery acceptance record

| Field | Observed value |
|---|---|
| Local trial | `day2-native-d15965119813` |
| Source | `43abb2318280ff455ad9ab56e9359af9f5531eed`; source hashes and working-tree state in JSON |
| Environment | Windows/Docker Desktop, kind 0.33.0, Kubernetes 1.36.4, one node, namespace `safeheal-dev` |
| Approach | A: native kubelet restart, `restartPolicy: Always` |
| Fault | Host-operated `crictl stop --timeout 0` against the validated payment container only |
| Baseline | All three services Ready; DNS/health/readiness and synthetic order successful |
| Injection request | 2026-10-20 22:31:44.979649 UTC |
| Termination | 22:31:45 UTC, exit code 137, reason `Error` |
| Native recovery evidence | Same payment Pod UID, changed container ID, restart count 0 -> 1; upstream identities and counts unchanged |
| First observed payment Ready | 6.391 s after host stop request |
| Final verification | Three successful DNS/health/readiness/order checks, two-second gaps; orders HTTP 201 / 2000 cents / confirmed |
| End-to-final-check interval | 13.844 s, including host tooling, API, polling and verification overhead |
| Outcome | PASS; no manual restart or Pod deletion |
| Raw record | `evidence/day2/recovery-20261020T223144-4257ee.json` |
| Discovery/log evidence | `evidence/day2/verification-20261020T223105-a896d6.json` |
| CI reproduction | Run 39470648959, unit and live-kind jobs successful; `evidence/day2/implementation-ci.json` |

No local recovery trial failed. Two earlier cluster bootstrap attempts failed before application deployment because of an invalid node-registration label; the first was auto-cleaned by kind and the second retained for diagnosis. Earlier CI run 39469746459 failed for the same configuration error. These are retained as setup failures in WORKLOG.md and GitHub history; they are not counted as recovery trials.

Limitations: one local trial, three short post-recovery checks, no sustained load/SLO window, no matched rule/AI comparison or randomized repetitions. The host stop request is not a precisely instrumented service-outage onset. The 13.844 s value is neither downtime nor an estimate of MTTR. Liveness-triggered restarts, replacement of deleted Pods, node faults and high availability were not tested. No diagnosis score, cost saving or AI improvement can be inferred.


## Day 3 instrumentation checkpoint

Implemented metrics, JSON logs, basic distributed traces and monitoring configuration.
The 51-test engineering suite passes. Real-traffic telemetry acceptance is pending; no new
research trials, diagnostic gains, overhead gains or AI benefits are claimed.

## Day 3 observability engineering acceptance

Implementation `9b5fec7d517dd46b68eb65a9442335fcb4c77560`; clean source at trial start.
Trial `day3-c56cd5922e10` passed on 2026-10-21, 10:53:00.097837–10:53:57.942991 UTC.
A 45.352-second workload generated 108 gateway HTTP responses: 80 x 201, 21 x 422 and 7 x 503.
Workload targeted the validated gateway Pod IP to preserve observation through readiness withdrawal;
baseline/final Service-DNS checks passed separately. This workload is diagnostic and is not a production availability sample.

Prometheus scraped all three services; request/status counters and histograms populated. Gateway/order each recorded
seven 5xx responses for the same seven failed gateway requests. Eight Grafana panels and the real datasource proxy were checked.
JSON logs contain matching failure request/trace IDs at gateway and order. A successful request produced five linked
OpenTelemetry SERVER/CLIENT spans across all three services. Native payment-stop trial `day2-native-478183e561ad` passed;
no LLM, deterministic controller, manual restart or Pod deletion took part.

Raw telemetry: `evidence/day3/observability-20261021T105300-day3-c56cd5922e10.json`.
Native recovery: `evidence/day2/recovery-20261021T105312-78fdbe.json`.
CI: successful run 39587430249, metadata `evidence/day3/implementation-ci.json`.
Tests: 51 passed / one existing warning, `evidence/day3/tests.txt`.

Limitations: one engineering traffic run, no matched A/B/C scenarios, no randomized repetitions, no benchmark SLO/recovery
window and no overhead control. Five-second scrape timing, one-minute rate windows, ephemeral monitoring data, one-replica
Service scraping and synchronous JSON span export must be considered before experiments. No research effect size, MTTR,
false-alert estimate, diagnostic accuracy or AI benefit is inferred from this check. Setup/image/startup issues are in WORKLOG.md.

## CI client-deadline failure retained

Run 39588507641 failed during StopContainer at crictl's two-second default runtime-client deadline.
Its record does not establish a verified recovery outcome; it is an engineering acceptance failure,
not a matched research trial. Original raw record: `evidence/day3/ci-failure-recovery-20261021T110016-45fd40.json`;
run metadata: `evidence/day3/ci-failure-39588507641.json`.

After explicitly bounding that RPC at 30 seconds (kill grace still zero; outer process bound 45 seconds;
no automatic injection retry), 51 tests and a scoped local native recovery passed. Local raw record:
`evidence/day2/recovery-20261021T110508-9fb946.json`. This check exercises the corrected client configuration;
it does not prove that the preceding failed CI fault did not occur, or provide a controlled MTTR comparison.
No failed record was removed or relabelled as successful. Full CI is required for the correction commit.

## Day 4 deterministic baseline — offline engineering evidence

The detector and rule diagnosis are implemented and tested in an isolated source snapshot because the canonical development computer was offline and GitHub access was unconnected. See evidence/day4/source-provenance.json. Current canonical HEAD and existing cluster were not inspected or modified.

- Full local suite: 107 passed / one existing warning, including 56 added detector and service-metrics integration tests. evidence/day4/tests.txt.
- Four controlled **synthetic** failure classes passed lifecycle acceptance with no LLM or recovery action. Full records and evidence references: evidence/day4/synthetic-acceptance.json. Source timestamps and observations are synthetic.
- One integration test derives the server-error signal from actual 503s and Prometheus metrics emitted by the existing order FastAPI app; TestClient transport and scrape timestamps are simulated. This verifies schema compatibility, not a live Prometheus/kind experiment.
- One initial full-suite failure was retained as a summary in evidence/day4/initial-test-failure.json. Host 1% trace sampling prevented an existing exporter assertion; test-only deterministic sampling resolved it. Production tracing code is unchanged.

No matched native/rule/AI trials, diagnosis accuracy denominator, false-alert rates, detection latency measurement, benchmark MTTR or overhead estimate has been collected. Thresholds are declared in docs/INCIDENT_DETECTION.md before future trials. Actual cluster acceptance and canonical publication/CI are pending; full gates remain 3/10.


Day 4 loopback service smoke also passed: started the actual detector as an isolated local process with no Prometheus listener, observed three open `telemetry_unavailable` incidents through real HTTP GET requests, health 200 and readiness 503, read their diagnoses/evidence, then stopped only that process. Raw record: `evidence/day4/api-smoke.json`; console: `evidence/day4/api-smoke.txt`. This verifies real detector execution and telemetry-outage detection, not business-fault detection in the existing kind cluster. Reproduce only with unused local ports 18082/19090 using `python scripts/verify_detector_api.py`.

## Day 4 canonical engineering attempts and observability limitation

Canonical source was integrated after reconnection and successful patch applicability checks, against clean local/remote main bc06bf52efe19db592932b824de5da864c8b8c8d. Private visibility and the five healthy existing Deployments were verified.

Two routing-disconnection acceptance attempts remain recorded as failed:

- day4-live-463536f6246c: payment scrape failure opened and resolved correctly, with successful final health/orders and exact selector restoration. The overall harness failed an additional gateway-5xx assertion because long-lived internal connections kept working.
- day4-live-b54f1ad56622: existing Prometheus connections also kept working, so there was no observable payment `up=0` and no incident opened. The selector was restored; separate service verification passed.

These records show that Service endpoint withdrawal need not interrupt existing TCP connections. They are retained as failed engineering acceptance attempts. Do not treat them as matched benchmark results, relabel them as successes, infer a research false-negative rate, or claim that metrics can detect a failure absent from their inputs. The final observable-fault harness pauses the validated payment task with timed resumption and allows native Kubernetes liveness recovery, while preserving all observations and recovery attribution. Provider/model usage remains zero.


## Day 4 final local engineering acceptance — PASS

Trial `day4-pause-670cd6f0b91f` passed from 2026-10-21T16:41:02.324443 to 16:43:49.611107 UTC. Fixed identity-checked payment task pause; node-side pause/resume command completed with exit 0. Actual Prometheus observations opened payment scrape outage, gateway/order latency and gateway/order 5xx incidents. All five completed pending -> open -> recovering -> resolved; error incidents carried suspected-payment correlation links and evidence IDs. Actual gateway workload: 250 responses, 187 x 201 / 63 x 503. Final fresh DNS/health/readiness/order checks passed (confirmed, 2000 cents). Payment retained its Pod UID with native restart count 2 -> 3; upstream identities/counts stayed unchanged (0 -> 0). Detector remediation/model calls: none. Runtime source hashes, raw query matrices and failed checks are retained in evidence/day4.

Final Windows suite: 118 passed / one existing dependency warning in 28.26 s, evidence/day4/windows-tests.txt. Linux suite: 118 passed. Expanded CI installs the existing locked runtime, forwards Prometheus locally, executes the guarded dry run and observable task-pause check in fresh kind, and uploads Day 4 evidence. Canonical implementation/docs/evidence are committed privately; publication SHA/CI is verified after commit and appended to the portable completion copy. Day 4 checklist 8/8; full gates 4/10 (40%). Next: Day 5 controlled fault runner/ground truth/native and rule-diagnosis baselines. No controlled benchmark, MTTR, model benefit or OS privilege-separation claim is made.


## CI warm-up baseline correction

Initial branch CI run 39638639803 (76d78187619e45da87fbe85601e37c822e13b860) passed the unit job and failed the new live acceptance **before fault injection**. Raw CI trial day4-pause-3416e684d4a5 had two baseline polls: the first recorded incomplete warm-up telemetry; the second had all targets UP, eligible zero-error traffic, no telemetry problems, and that transient incident already resolved without opening. The harness incorrectly rejected any historical incident. Failure logs, metadata and raw trial remain under evidence/day4.

Changed only harness readiness: require eligible current telemetry and no active incidents; resolved warm-up history remains visible and no longer blocks a healthy baseline. Active incidents still block acceptance. Added two regression tests; suite now 120 tests, rules/thresholds/state machine unchanged. No fault is automatically retried after ambiguous injection. The corrected commit runs the full CI suite again; its final result is verified after private review-branch publication. A console Unicode error while printing the downloaded log was a retrieval-display issue; the UTF-8 failure file and downloaded raw JSON were already retained.


## Day 4 publication checkpoint - 2026-10-21

GitHub PR #1 tracks integration of the completed deterministic detector and retained engineering evidence: https://github.com/Jill-Vekariya/safeheal-ai/pull/1. The implementation at 87e2ec25e9264fe0d48b3e5fae97c39762dc03e4 passed both jobs in CI run 39640164313. The publication documentation does not change rules, thresholds, fault behavior, or experimental outcomes. No additional local trial or benchmark was conducted; previous failed attempts remain intact. Final PR/main CI state is available from GitHub. Controlled research benchmarks remain Day 5 work.


## Native recovery verification settling - 2026-10-21

PR run 39646024404 remains a failed engineering acceptance: post-restart HTTP Service access was refused after Pod Ready. Original JSON, log and run metadata are retained. The developer harness now records bounded GET-only readiness attempts before the unchanged three end-to-end order checks; failed final checks still fail the trial, with no POST or fault retry. This corrects readiness verification, not production recovery, detector thresholds, or a benchmark outcome. Eight regression cases bring Windows tests to 128 passing. Fresh Linux/Kubernetes correction CI is verified after publication through PR #1. No new controlled-trial dataset or model call was produced.


## Day 5 protocol implementation checkpoint — 2026-10-22

The executable protocol in docs/BENCHMARKS.md declares three payment faults: one-shot process crash,90-second HTTP500 lease and90-second1.25-second added-latency lease. Default seed5 shuffles two repetitions of each. Four closed-loop workers wait0.2s between completed requests. The existing Day4 detector runs unchanged as an observer; native recovery and application-fault expiration are separately attributed. Detection, business-recovery and native-ready intervals start at the host injection request and include tooling/polling overhead. Failed, missed or censored observations remain explicit; unavailable timestamps are null.

Ground truth is persisted before mutation, then verified with CRI identity/termination or direct fault-ID response proof and gateway impact. Each trial retains requests.jsonl,telemetry.jsonl,platform.jsonl,detector.sqlite3 and trial.json. Run/summary JSON and trial CSV include every attempt and require complete finalization for acceptance. At least two successful Kubernetes trials per scenario are required by the implementation, exceeding the requested three-repeatable-scenario gate. Local-process or synthetic fixtures cannot satisfy it.

This checkpoint contains protocol/test evidence only; actual six-trial dataset is pending. Initial Windows test failures and Docker API publishing setup failures are retained separately and are not benchmark outcomes. No matched intervention comparison, model benefit, recovery-executor result, statistical precision or research MTTR claim is made.
