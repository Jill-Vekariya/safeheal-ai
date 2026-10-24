# Day 9 controlled experiment findings

The study concerns one operator-induced payment Deployment scale-zero outage in the isolated Kubernetes lab.
The 90-second horizon, 5 matched blocks, randomized arm order, workload and decision rules were recorded before fault injection.

| Arm | Attempted / planned | Recovered within horizon | Censored | Mean observed recovery (s) | Mean restricted time (s) | Real provider requests |
|---|---:|---:|---:|---:|---:|---:|
| native | 5 / 5 | 0 | 5 | Not measured | 90.000 | 0 |
| rule_policy | 5 / 5 | 5 | 0 | 30.544 | 30.544 | 0 |
| ai_policy | 5 / 5 | 0 | 5 | Not measured | 90.000 | 5 |

Censored trials did not recover during observation. Their actual recovery time is unknown; 90 seconds is a restricted-horizon value, not observed MTTR.

Matched native-minus-rule restricted-time differences (seconds): [69.0, 64.625, 61.875, 55.14100000000326, 46.64100000000326].
Mean matched difference: 59.456 seconds.
Exploratory 95% paired bootstrap interval: [51.93780000000261, 65.825]. This is conditional small-sample resampling, not production precision.

## Interpretation and trade-offs

For this deliberately narrow configuration fault, the fixed rule can request an independently permitted restore action. Native reconciliation does not change a Deployment's desired replica count back to one. This scenario therefore favors an explicit restore policy; it is not a test of generic process self-restart.
The rule path requires no model tokens or model availability. The same controller, credential scope and admission restrictions constrain every active arm. Fresh journals are operator-managed experimental episodes; continuous-production cooldown/budget behavior across journal resets is not evaluated.

The AI arm used the configured real provider. Distinguish validated model outputs, abstentions, provider failures and policy denials in the raw diagnosis records; source fallback is never model success.

## AI-specific measurements

Paired restricted-time comparisons (left minus AI; negative means the AI path took longer): {'native_minus_ai_policy': {'paired_restricted_differences_seconds': [0.0, 0.0, 0.0, 0.0, 0.0], 'mean_seconds': 0.0, 'exploratory_bootstrap_95': [0.0, 0.0]}, 'rule_policy_minus_ai_policy': {'paired_restricted_differences_seconds': [-69.0, -64.625, -61.875, -55.14100000000326, -46.64100000000326], 'mean_seconds': -59.4564000000013, 'exploratory_bootstrap_95': [-65.825, -51.93780000000261]}}.
Equal restricted times for two censored arms mean neither recovered within the horizon; they do not establish equal actual recovery time.
Provider status counts: {'provider_timeout': 5}.
Reported provider tokens: {'input_tokens': 0, 'output_tokens': 0}. Reported usage only; failed/incomplete requests may consume compute without returning usage.
Mean measured model-call interval: 31.987399999999617 seconds. This includes cold/warm runtime and host contention.
Validated-output target/symptom agreement counts: None. These counts exclude fallback and do not establish causal accuracy.

## Limitations and error analysis

Only one scenario and five blocks on one shared cluster/machine were studied. Sequential order, shared caches, telemetry windows and host instrumentation can affect timing. The runtime waits eight seconds before decisions and samples business responses; measured times include those choices and API overhead.
The workload is closed-loop: slow failures reduce request throughput. Valid-response percentages are weighted by completed requests, not elapsed-time uptime or a fixed offered-load reliability estimate.
Ground truth was attached after diagnosis. The model sees normalized telemetry, not fixture labels. Target/symptom agreement does not prove the initiating mechanism. No benign-control false-positive rate, held-out accuracy or production safety rate is established.
Operator cleanup occurs after measurement and is excluded from recovery metrics. All setup failures, technical failures, censored and unrun slots remain explicit; no failed trial is silently replaced.

| Trial | Arm | Status | Reason | Censored |
|---|---|---|---|---|
| d9-01-native-494ad9 | native | observed | no_recovery_within_horizon | True |
| d9-02-ai_policy-f1ce7a | ai_policy | observed | provider_timeout | True |
| d9-04-ai_policy-623b3d | ai_policy | observed | provider_timeout | True |
| d9-05-native-d9394a | native | observed | no_recovery_within_horizon | True |
| d9-08-ai_policy-cd7693 | ai_policy | observed | provider_timeout | True |
| d9-09-native-3cef1e | native | observed | no_recovery_within_horizon | True |
| d9-10-native-f60d15 | native | observed | no_recovery_within_horizon | True |
| d9-11-ai_policy-603d90 | ai_policy | observed | provider_timeout | True |
| d9-14-native-5a282b | native | observed | no_recovery_within_horizon | True |
| d9-15-ai_policy-d6c4dd | ai_policy | observed | provider_timeout | True |
