# Day 9 controlled experiment findings

The study concerns one operator-induced payment Deployment scale-zero outage in the isolated Kubernetes lab.
The 90-second horizon, 5 matched blocks, randomized arm order, workload and decision rules were recorded before fault injection.

| Arm | Attempted / planned | Recovered within horizon | Censored | Mean observed recovery (s) | Mean restricted time (s) | Real provider requests |
|---|---:|---:|---:|---:|---:|---:|
| native | 3 / 5 | 0 | 3 | Not measured | 90.000 | 0 |
| rule_policy | 3 / 5 | 3 | 0 | 21.630 | 21.630 | 0 |
| ai_policy | 3 / 5 | 2 | 1 | 39.828 | 56.552 | 3 |

Censored trials did not recover during observation. Their actual recovery time is unknown; 90 seconds is a restricted-horizon value, not observed MTTR.

Matched native-minus-rule restricted-time differences (seconds): [73.11000000000001, 56.312999999999874, 75.6869999999999].
Mean matched difference: 68.370 seconds.
Exploratory 95% paired bootstrap interval: [56.312999999999874, 75.6869999999999]. This is conditional small-sample resampling, not production precision.

## Interpretation and trade-offs

For this deliberately narrow configuration fault, the fixed rule can request an independently permitted restore action. Native reconciliation does not change a Deployment's desired replica count back to one. This scenario therefore favors an explicit restore policy; it is not a test of generic process self-restart.
The rule path requires no model tokens or model availability. The same controller, credential scope and admission restrictions constrain every active arm. Fresh journals are operator-managed experimental episodes; continuous-production cooldown/budget behavior across journal resets is not evaluated.

**The real AI-assisted comparison is incomplete.** Inspect the explicit unrun or technical-failure records; the planned real-provider cohort was not fully observed. No mock, deterministic fallback or LLM from this chat was substituted. AI accuracy, recovery benefit, token usage and monetary cost cannot be inferred from these baseline data.

## AI-specific measurements

Paired restricted-time comparisons (left minus AI; negative means the AI path took longer): {'native_minus_ai_policy': {'paired_restricted_differences_seconds': [0.0, 36.20399999999995, 64.1400000000001], 'mean_seconds': 33.448000000000015, 'exploratory_bootstrap_95': [0.0, 64.1400000000001]}, 'rule_policy_minus_ai_policy': {'paired_restricted_differences_seconds': [-73.11000000000001, -20.108999999999924, -11.546999999999798], 'mean_seconds': -34.92199999999991, 'exploratory_bootstrap_95': [-73.11000000000001, -11.546999999999798]}}.
Equal restricted times for two censored arms mean neither recovered within the horizon; they do not establish equal actual recovery time.
Provider status counts: {'validated': 3}.
Reported provider tokens: {'input_tokens': 1063, 'output_tokens': 65}. Reported usage only; failed/incomplete requests may consume compute without returning usage.
Mean measured model-call interval: 7.187333333333451 seconds. This includes cold/warm runtime and host contention.
Validated-output target/symptom agreement counts: {'real_llm_diagnoses': 3, 'target_matches': 2, 'observable_class_matches': 2, 'model_output_rejected': 0, 'provider_failures': 0}. These counts exclude fallback and do not establish causal accuracy.

## Limitations and error analysis

Only one scenario and five blocks on one shared cluster/machine were studied. Sequential order, shared caches, telemetry windows and host instrumentation can affect timing. The runtime waits eight seconds before decisions and samples business responses; measured times include those choices and API overhead.
The workload is closed-loop: slow failures reduce request throughput. Valid-response percentages are weighted by completed requests, not elapsed-time uptime or a fixed offered-load reliability estimate.
Ground truth was attached after diagnosis. The model sees normalized telemetry, not fixture labels. Target/symptom agreement does not prove the initiating mechanism. No benign-control false-positive rate, held-out accuracy or production safety rate is established.
Operator cleanup occurs after measurement and is excluded from recovery metrics. All setup failures, technical failures, censored and unrun slots remain explicit; no failed trial is silently replaced.

| Trial | Arm | Status | Reason | Censored |
|---|---|---|---|---|
| d9-01-native-8988d4 | native | observed | no_recovery_within_horizon | True |
| d9-02-ai_policy-48758c | ai_policy | observed | validated | True |
| d9-05-native-9868d2 | native | observed | no_recovery_within_horizon | True |
| d9-09-native-d528a2 | native | technical_failure | no_recovery_within_horizon | True |
| None | native | not_run | batch_stopped_before_slot | None |
| None | ai_policy | not_run | batch_stopped_before_slot | None |
| None | rule_policy | not_run | batch_stopped_before_slot | None |
| None | rule_policy | not_run | batch_stopped_before_slot | None |
| None | native | not_run | batch_stopped_before_slot | None |
| None | ai_policy | not_run | batch_stopped_before_slot | None |
