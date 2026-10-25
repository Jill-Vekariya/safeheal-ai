# Experiment register

## Verified demo extension - 25 October 2026

[Dedicated end-to-end demo](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40145365194) and [full normal CI](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40145364797) passed at 9f6e268d2b5daad8caaff87e1c2e6c8b457d74de. Current tests: Windows 536 passed/2 skipped; Linux 537 passed/1 skipped. Replay verifies 241 artifacts. The demo's fresh controller episodes are engineering checks, not added randomized study trials. All original controlled measurements and their negative/inconclusive AI findings remain unchanged.

## Original project-completion checkpoint - 25 October 2026

All ten engineering gates passed; private PR4/main CI are green. Windows: 522 passed, 2 skipped. Offline replay checks 235 artifacts and both cohorts. Methods, charts, trade-offs, error analysis and limitations: docs/RESEARCH_REPORT.md and evidence/day9/analysis-local/FINDINGS.md.

Actual 90-second cohort: 15 trials; native 0/5 recovery, fixed rule 5/5 (mean 30.5436 s), AI 0/5. Five local-model calls timed out, with no validated model output or AI action. Retained 4035 requests, 75-file manifest, 120 forbidden denials, 20 audit events and 15 cleanups. Censored actual recovery times, model accuracy and total cost are unknown. Original 45-second cohort remains separate: rule 5/5 (mean 19.0378 s), five missing-provider AI slots.

Initial publication CI failed before recovery fixture injection on unproven admission enforcement. Its raw evidence remains in evidence/final/ci-40135721425. A bounded real-token enforcement gate, thirteen safety tests and fresh PR/main success verify the correction without rewriting original data or allowing real-write retries.

## Historical protocol and checkpoints

The original protocol and chronological records below describe their then-current scope; final outcomes above supersede pending-work statements. Original scope and failed outcomes are preserved.

Status: Day 5 initial benchmark is complete: six real Kubernetes trials, two repetitions each of process crash, HTTP 500 and added latency, with verified labels, rule observations, recovery attribution and stored raw evidence. All six executions and the final run gate passed. The broader matched native/rule/AI intervention study remains a draft; no rule recovery executor or AI outcome has been measured.

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

Day 1–4 tests and smoke/acceptance checks below are historical engineering validation. Day 5 adds the initial measured dataset recorded at the end of this register; no comparative AI-effectiveness finding is established.

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

## Day 5 initial measured benchmark — 2026-10-22

**Source:** `31f2af628e70487f1cd0098403bd3ab2304a4d46`. **CI:** [39774736343](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39774736343), both jobs successful. **Data:** [evidence/day5/ci-39774736343/run-03a9072a24f8](evidence/day5/ci-39774736343/run-03a9072a24f8). **Protocol:** [docs/BENCHMARKS.md](docs/BENCHMARKS.md). **Detailed findings/timestamps:** [evidence/day5/README.md](evidence/day5/README.md).

The real execution used a fresh Linux CI kind cluster (Kubernetes v1.36.4), seed 5, two repetitions, 30-second minimum baseline, four closed-loop workers with 0.2-second completion delay, five-second rule polling, 90-second application fault leases and 1.25-second added payment latency. The canonical rule implementation and thresholds were unchanged. The batch ran from 12:05:12.009502 to 12:22:41.030610 UTC.

| Trial | Scenario / repeat | Rule detection (s) | Sustained business recovery (s) | Observed native Ready (s) | Recovery attribution |
|---|---|---:|---:|---:|---|
| `d5-01-http_5xx-d6b754b6` | http_5xx / 1 | 27.130 | 93.040 | N/A | `fault_expiry` |
| `d5-02-process_crash-41c49801` | process_crash / 1 | 17.172 | 32.429 | 34.317 | `native_kubernetes` |
| `d5-03-process_crash-d3a98bd4` | process_crash / 2 | 12.033 | 51.740 | 50.340 | `native_kubernetes` |
| `d5-04-latency-f3613d30` | latency / 2 | 32.187 | 92.979 | N/A | `fault_expiry` |
| `d5-05-latency-caab66e3` | latency / 1 | 32.321 | 93.064 | N/A | `fault_expiry` |
| `d5-06-http_5xx-bea84ddf` | http_5xx / 2 | 32.103 | 93.107 | N/A | `fault_expiry` |

All six attempts completed with verified ground truth, eligible matched detections, sustained business recovery and cleanup. Final run health/shutdown passed. There were no failed, missed, ineligible or censored benchmark outcomes in this batch; unsuccessful Windows unit/setup work is retained separately and is not benchmark execution. Each timing starts at the host injection request, including tool/polling overhead; it is not exact physical downtime or a population MTTR estimate.

Both process crashes were one forced exit of the validated payment container, recovered by native Kubernetes restart in the same Pod (restart count 2→3→4, old container termination IDs matched, exit 137). This does not assert that liveness probes detected the forced exit. Gateway/order container identities remained stable, although readiness temporarily dropped during both outages. HTTP and latency faults left container identities/restart counts unchanged and all three services Ready in the sampled platform observations; application recovery followed lease expiry. No rule or AI recovery execution occurred.

The first qualifying matched diagnosis described payment unavailability for the two crashes, server-error symptoms on order/gateway for the two HTTP trials, and latency on gateway/payment for the two latency trials. Its service matched the injected target in 3/6 records; suspected_root_service was null in all six first diagnoses. Additional telemetry incidents remain in raw SQLite evidence. The matched-detection count does not establish general root-cause accuracy or false-positive/negative rates.

Retained 15,180 request rows, 212 telemetry snapshots, six detector SQLite stores, per-trial ground truth/platform state, plan/source/runtime/rule metadata and workflow logs. Replaying stored summaries reproduced JSON content and CSV bytes; raw request aggregates matched and every SQLite integrity check returned ok. Original benchmark files were preserved byte-for-byte and hashes retained in audit.json. Only two repetitions per scenario, shared cluster/restart history, variable throughput under the closed-loop workload and absence of matched A/B/C arms limit interpretation. The initial engineering acceptance gate is satisfied; broader comparative research remains Day 9.

## Final Day 5 verification ? 2026-10-22

The previously pending evidence-commit CI39780164487 completed successfully, including unit and live Kubernetes jobs and six further completed/detected trials. Retained metadata/logs under evidence/day5/ci-39780164487. These later CI records are not pooled with the original benchmark dataset or used to rewrite its measured intervals. All39 original artifact hashes, six SQLite integrity checks and JSON/CSV replay remained valid.

Local API access was restored with a separate loopback TLS proxy on18082. Current application source was deployed with a documented cached dependency-equivalent source-refresh image after Docker Hub timed out; no fault was injected as part of repair. DNS/health/readiness/order checks, benchmark preflight and all10 deployed payment source hashes passed. See Day5_Verification_2026-10-22.md and evidence/day5/local-repair for failed setup attempts, workaround details, deployment identity and limits. This closes environment verification without claiming another local benchmark or a comparative recovery gain.


## Day 6 retrospective diagnosis replay — 2026-10-23

Implemented configurable disabled-by-default JSON provider, fixed read-only incident/telemetry tools, bounded evidence normalization, strict cited hypotheses, confidence/abstention/fallback handling and independent ground-truth scoring. Source/tests: services/diagnosis, scripts/diagnose.py, tests/test_diagnosis*.py. Protocol: docs/AI_DIAGNOSIS.md.

Replayed all six original Day 5 Kubernetes trials using telemetry/platform observations only, with a fixed first-observation +105s cutoff. Ground truth is read after each diagnosis. Mocked HTTP transport and deterministic fallback each obtained 6/6 grounded, target-matched and observable-class-matched outputs. Reports and input SHA-256 hashes are retained under evidence/day6. No new fault trials, real-model calls, recovery execution, held-out accuracy estimate, or comparative AI-benefit claim is made. Original Day 5 artifacts remained unchanged.

Windows final full suite: 337 passed, 2 skipped, 0 failed; one existing dependency warning. The skips are symlink privilege and unavailable real-model opt-in/credentials. Initial targeted run: 42 passed, one failed, one skipped; it exposed that the scorer checked only cited record hashes. Corrected to verify every bundled record, and retained the failure description. Additional malformed JSON, oversized confidence and corrupt-database handling passed. CLI benchmark replay passed. Final test log and acceptance manifest are retained.

Canonical private review branch day6-ai-diagnosis begins at e04a506. No main merge. CI publication/final result is checked after push. PC connected; Docker engine stopped, so no local cluster operation was attempted. Next: independent Day 7 safe-recovery controls; real-provider quality remains unmeasured until an explicit model/call budget and credentials are available.

Publication boundary: automatic approval review rejected the combined local commit/private push as an unapproved disclosure to GitHub. The rejected terminal command did not run. Local commit is explicitly authorized and is completed separately; no push or Day 6 CI run is claimed. Remote publication requires explicit approval.


## Day 6 delivery and repository-state recheck - 2026-10-23

Implementation remains 33b27a43b18f808474e9778ce432aebc789d69e0. All retained source hashes match; both six-trial reports pass grounding recheck. Credentials remain unavailable. GitHub main remains Day 4 at156da54; Day5 branch e04a506 and PR2 are published, Day6 is local only. ADMIN access does not enable branch protection on this private repository plan: GitHub returns403 requiring an eligible upgrade or public visibility. Neither purchase nor visibility change was performed. The proposed docs/MAIN_BRANCH_PROTECTION.json is not applied or enforced. Automatic approval review rejected the source/documentation/benchmark-evidence push again after broad user authorization, requiring explicit destination-and-payload authorization; do not bypass it. No Day6 remote CI or main integration is claimed. See PROJECT_STATUS_Day6_2026-10-23.md and evidence/day6/publication-blockers.json.


## Day 7 safe autonomous recovery — 2026-10-24

Implemented services/recovery, operator CLI, guarded acceptance, resource-name-scoped RBAC plus admission, one immutable action (payment replicas 0 to 1), independently checked live preconditions, default dry-run, request/spec/generation-bound 180-second single-use approvals, opted-in autonomous mode, conditional one-shot JSON Patch, bounded read-only consistent snapshots, durable single-flight claims, cooldown/hourly budget, fail-closed uncertainty and chained audit. Verification requires three consecutive ready observations at the exact expected generation. No model shell/token/approval interface was added.

Final Windows suite: 402 passed, 2 existing skips, one existing warning; 65 recovery tests. Actual autonomous d7-autonomous-5ba20e9e0e and approval d7-approval-324fc2fcfe both passed in safeheal-day7 with eight real-token access denials plus a zero-state admission denial each; all HTTP 403. Dry-run, unapproved request and replay gates passed. Both business checks and cleanup passed without operator restoration. All 27 available retained audit records verify and accepted source manifests match final executable code/policy. No local trial token files remain.

Retained four failed live attempts: explicit denial-reason mismatch (422 instead of required 403, before injection), two safe zero-scale precondition denials (Kubernetes omitted zero ScaleSpec field), and one verified controller action whose separate business check hit Service route convergence. Corrected representation/conditional patch, added bounded read snapshots and reused existing GET-only route wait before one unretried order POST. The failed outcomes remain failed. Initial test-fixture reset failure (53 passed, one failed) is described in engineering notes; final full suite passes.

Original safeheal-dev node remains preserved/stopped after Windows rejected its reserved API port. Created the separate pinned safeheal-day7 cluster with independent project kubeconfig and loaded the previously verified application image. No global reset, cluster deletion, default-context change or original benchmark rewrite. No paid model call, general reliability or A/B/C recovery gain claim.

CI now includes both guarded recovery modes and artifact retention, but local branch day7-safe-recovery was not published; no remote CI or main integration is claimed. Overall gate count 7/10; Day 8 next. Detailed handoff: PROJECT_STATUS_Day7_2026-10-24.md.


## Day 8 AI reliability and robustness — 2026-10-24

Implemented fixed synthetic adversarial development evaluation and exact-Git baseline comparison; actual-sample freshness, normalized schema/hash/support validation of every record, detached provider input, malformed platform exclusion and generic adapter-exception fallback. Added local notification intake with strict time/ID schema, durable duplicate notification/evidence suppression, concurrency/restart persistence, claim-before-call, collision/capacity checks and fail-closed journal/crash behavior. Added CLI route, 74 tests, operational contract and paired CI/artifact wiring. No recovery authority or new model tool was exposed.

Authoritative paired reports: evidence/day8/paired/{before,after,comparison}.json. Same evaluator/case manifest; baseline exported from d10575a79781eda91f942aef56ee5a90fa5e1aba and independently verified against Git. Before: 27/36 passed; after: 36/36 passed; nine improved, zero regressed. Five repeated notifications or new IDs for identical incident/evidence: five simulated calls -> one; stale notification: one -> zero. Complete case outcomes, diagnoses and source hashes retained. These are mocked/synthetic development safeguards, not held-out/real-model performance, production reliability or an MTTR result.

The first after-evaluator attempt raised AttributeError while reading diagnosis=null for a suppressed notification. Corrected null handling, retained the description and exact early evaluator variants verified against their recorded SHA-256, then reran both paired arms using the same corrected evaluator. Early before.json/after-initial.json remain separate. Initial new tests: 71 passed; final new coverage: 74 passed. Final full Windows suite: 476 passed, two existing skips, one existing warning; focused diagnosis suite 123 passed. Original Day 5/6/7 evidence remains unchanged.

No real-provider call, cluster mutation, new fault trial, Docker reset or kubeconfig change was performed in Day 8. The notification journal is local; compromised same-user processes or dishonest telemetry instruments remain outside the guarantee. Pending/uncertain claims suppress automatic retry; operator investigation/maintenance is required. Direct incident/benchmark CLI calls remain intentional one-shot/replay interfaces.

Canonical branch day8-ai-robustness continues the tested Day 7 history. Commit is local; no Day 8 GitHub publication, remote CI or main integration is claimed. Overall milestones 8/10 (80%); Day 9 matched controlled experiments next. Detailed handoff: PROJECT_STATUS_Day8_2026-10-24.md.


## Day 9 controlled baseline study and pending AI arm — 2026-10-24

Predeclared five matched blocks/seed 9, one payment scale-zero fault, same workload, eight-second decision delay and 45-second observation horizon. Actual lab run 17:54:55–18:06:55 UTC: five native and five fixed-rule/safe-policy trials. Native 0/5 recoveries within horizon (all censored); rule 5/5, mean business recovery 19.0378 s, median 18.063 s, range 17.359–21.907 s. Matched difference in 45-second restricted time 25.9622 s; exploratory paired bootstrap [24.2838,27.3438]. This is not observed native MTTR, generic recovery performance, population precision or an AI benefit.

User selected A provider I configure. No active local profile was supplied; all five AI slots are retained as not_run, with no real-model accuracy/cost/recovery claim or mock substitute. Provider profile/credential/budget is the remaining dependency. Run a new matched cohort after configuration; do not fill old slots or pool silently.

Saved 1,767 raw request completions, raw platform/Prometheus data and controller audit SQLite/JSON under evidence/day9/run-primary; verified the 60-file manifest and exact metric replay. Twenty audit events pass chain verification; all 80 forbidden probes denied, five controller actions verified, ten trial cleanups passed, and tokens removed locally. Five operator restorations happened after measurement only. Figures/CSV/findings under evidence/day9/analysis. Closed-loop valid-response fractions (17/345 native; 1219/1370 rule) are not time-weighted uptime.

Nineteen new tests; final full suite 495 passed, 2 existing skips, one existing warning. An initial chart preparation error assumed an unrun metrics field could not be null; null-safe rendering/CSV regression added. Numerical findings and raw measurements did not change; the earlier 494-pass test log remains. Added pinned optional plotting requirements and CI raw replay. Production controller/RBAC/admission unchanged; per-trial fresh operator enrollment/journals are documented and do not establish continuous-production budgeting across resets.

Only the existing isolated safeheal-day7 lab was used; pinned Prometheus added, app image unchanged, old stopped cluster/default context/prior evidence preserved. No paid/model call, Docker reset, GitHub publication, merge or remote Day 9 CI. Local branch day9-controlled-experiments. Day 9 remains partial; overall completed milestones 8/10 (80%). See PROJECT_STATUS_Day9_Partial_2026-10-24.md.


## Public CPU model study - verified implementation

A fresh isolated Linux GitHub runner completed five randomized matched blocks and all 15 planned scale-zero trials with the predeclared 90-second horizon. Its exact implementation source is `fd809cae41b60c62b59bd2fc2e2377f5d487b163`. The separate standard demo and normal CI passed at that source: Linux 559 passed, 1 opt-in skip; Windows 558 passed, 2 expected skips.

| Arm | Attempts | Recovered / 5 | Censored | Observed mean (s) | Restricted mean (s) |
|---|---:|---:|---:|---:|---:|
| native | 5 | 0 | 5 | Not measured | 90.000 |
| rule_policy | 5 | 5 | 0 | 14.107 | 14.107 |
| ai_policy | 5 | 2 | 3 | 14.836 | 59.934 |

The AI arm made 5 real local CPU-model requests, with provider statuses {"provider_invalid_response": 1, "validated": 4}. It recorded 2 independently controller-verified recoveries and 2 sustained business recoveries within the horizon. Reported token usage was {"input_tokens": 2106, "output_tokens": 134}; failed requests may consume compute without returning usage. Actual monetary compute cost is unknown.

All 15 cleanup checks passed, all 120 forbidden probes returned HTTP 403, and 28 audit events verified. The model had no Kubernetes credential, shell tool, approval power or action authority. The runner pinned the official Ollama image and base model digest, served inference only on loopback, disabled cloud inference, capped it at two CPUs and 1536 MiB, and warmed the model outside measurement. Model metadata confirms CPU residency.

Full evidence validation precedes compact candidate projection, and expanded selected hypotheses are checked independently. This ranks deterministic evidence-supported candidates; it is not unrestricted root-cause discovery. Confidence is uncalibrated. The same independent one-action policy constrains rule and AI arms.

The two Windows CPU attempts remain incomplete: six of fifteen attempted before interruption, then nine of fifteen before a cleanup rollout timeout. The latter preserves eight passed cleanups, one failed cleanup and six unrun slots; a later independent healthy-order check does not change that failure. The original 45-second baseline and larger-model timeout cohort remain unchanged. No attempt was replaced or resumed, and differing hosts, horizons, runtimes or prompt formats are not pooled.

Six retrospective development incidents also produced six grounded, target-matched and observable-class-matched real-model diagnoses without fallback. Those are development checks, not held-out accuracy. One policy-addressable scenario, five shared-host blocks, warm state, telemetry windows, closed-loop workload and host contention limit generalization. Observed-only means exclude censored observations; the horizon is not observed MTTR. No general AI superiority, calibrated diagnostic accuracy, production safety rate or universal recovery gain is established. CPU/memory fault coverage, held-out benign controls, multi-host replication and external audit anchoring remain future research.

Raw measurements: `evidence/day9/run-ci-cpu-40206671248`. Full findings and charts: `evidence/day9/analysis-ci-cpu-40206671248`. Permanent CI archives and source/runtime provenance: `evidence/public-release/ci-40206671248` and `ci-40206669554`.
