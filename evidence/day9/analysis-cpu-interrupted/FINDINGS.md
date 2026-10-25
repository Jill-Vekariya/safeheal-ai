# Day 9 controlled experiment findings

The study concerns one operator-induced payment Deployment scale-zero outage in the isolated Kubernetes lab.
The 90-second horizon, 5 matched blocks, randomized arm order, workload and decision rules were recorded before fault injection.

| Arm | Attempted / planned | Recovered within horizon | Censored | Mean observed recovery (s) | Mean restricted time (s) | Real provider requests |
|---|---:|---:|---:|---:|---:|---:|
| native | 2 / 5 | 0 | 2 | Not measured | 90.000 | 0 |
| rule_policy | 2 / 5 | 2 | 0 | 20.624 | 20.624 | 0 |
| ai_policy | 2 / 5 | 1 | 1 | 30.000 | 60.000 | 2 |

Censored trials did not recover during observation. Their actual recovery time is unknown; 90 seconds is a restricted-horizon value, not observed MTTR.

Matched native-minus-rule restricted-time differences (seconds): [66.76600000000008, 71.98500000000013].
Mean matched difference: 69.376 seconds.
Exploratory 95% paired bootstrap interval: [66.76600000000008, 71.98500000000013]. This is conditional small-sample resampling, not production precision.

## Interpretation and trade-offs

For this deliberately narrow configuration fault, the fixed rule can request an independently permitted restore action. Native reconciliation does not change a Deployment's desired replica count back to one. This scenario therefore favors an explicit restore policy; it is not a test of generic process self-restart.
The rule path requires no model tokens or model availability. The same controller, credential scope and admission restrictions constrain every active arm. Fresh journals are operator-managed experimental episodes; continuous-production cooldown/budget behavior across journal resets is not evaluated.

**The real AI-assisted comparison is incomplete.** Inspect the explicit unrun or technical-failure records; the planned real-provider cohort was not fully observed. No mock, deterministic fallback or LLM from this chat was substituted. AI accuracy, recovery benefit, token usage and monetary cost cannot be inferred from these baseline data.

## AI-specific measurements

Paired restricted-time comparisons (left minus AI; negative means the AI path took longer): {'native_minus_ai_policy': {'paired_restricted_differences_seconds': [0.0, 60.0], 'mean_seconds': 30.0, 'exploratory_bootstrap_95': [0.0, 60.0]}, 'rule_policy_minus_ai_policy': {'paired_restricted_differences_seconds': [-66.76600000000008, -11.985000000000127], 'mean_seconds': -39.3755000000001, 'exploratory_bootstrap_95': [-66.76600000000008, -11.985000000000127]}}.
Equal restricted times for two censored arms mean neither recovered within the horizon; they do not establish equal actual recovery time.
Provider status counts: {'validated': 2}.
Reported provider tokens: {'input_tokens': 794, 'output_tokens': 36}. Reported usage only; failed/incomplete requests may consume compute without returning usage.
Mean measured model-call interval: 9.563000000000102 seconds. This includes cold/warm runtime and host contention.
Validated-output target/symptom agreement counts: {'real_llm_diagnoses': 2, 'target_matches': 1, 'observable_class_matches': 1, 'model_output_rejected': 0, 'provider_failures': 0}. These counts exclude fallback and do not establish causal accuracy.

## Limitations and error analysis

Only one scenario and five blocks on one shared cluster/machine were studied. Sequential order, shared caches, telemetry windows and host instrumentation can affect timing. The runtime waits eight seconds before decisions and samples business responses; measured times include those choices and API overhead.
The workload is closed-loop: slow failures reduce request throughput. Valid-response percentages are weighted by completed requests, not elapsed-time uptime or a fixed offered-load reliability estimate.
Ground truth was attached after diagnosis. The model sees normalized telemetry, not fixture labels. Target/symptom agreement does not prove the initiating mechanism. No benign-control false-positive rate, held-out accuracy or production safety rate is established.
Operator cleanup occurs after measurement and is excluded from recovery metrics. All setup failures, technical failures, censored and unrun slots remain explicit; no failed trial is silently replaced.

| Trial | Arm | Status | Reason | Censored |
|---|---|---|---|---|
| d9-01-native-b7e367 | native | observed | no_recovery_within_horizon | True |
| d9-02-ai_policy-6293fb | ai_policy | observed | validated | True |
| d9-05-native-0b7443 | native | observed | no_recovery_within_horizon | True |
| None | rule_policy | not_run | batch_stopped_before_slot | None |
| None | ai_policy | not_run | batch_stopped_before_slot | None |
| None | native | not_run | batch_stopped_before_slot | None |
| None | native | not_run | batch_stopped_before_slot | None |
| None | ai_policy | not_run | batch_stopped_before_slot | None |
| None | rule_policy | not_run | batch_stopped_before_slot | None |
| None | rule_policy | not_run | batch_stopped_before_slot | None |
| None | native | not_run | batch_stopped_before_slot | None |
| None | ai_policy | not_run | batch_stopped_before_slot | None |
