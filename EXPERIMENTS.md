# Experiment register

Status: research protocol remains a draft. Day 2 now has one recorded local native-recovery engineering acceptance trial and a successful independent CI execution. No matched research benchmark, rule-controller result or AI result has been collected.

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
