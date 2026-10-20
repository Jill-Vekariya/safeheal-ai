# Experiment register

Status: protocol draft only. No recovery experiments or AI results have been collected.

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

Day 1 tests/smoke checks are engineering validation, not research benchmark evidence. Findings: none yet.
