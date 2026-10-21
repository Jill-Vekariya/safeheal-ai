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
