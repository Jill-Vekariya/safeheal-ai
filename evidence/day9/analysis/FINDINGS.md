# Day 9 controlled experiment findings

The study concerns one operator-induced payment Deployment scale-zero outage in the isolated Kubernetes lab.
The 45-second horizon, five matched blocks, randomized arm order, workload and decision rules were recorded before fault injection.

| Arm | Attempted / planned | Recovered within horizon | Censored | Mean observed recovery (s) | Mean restricted time (s) | Real provider requests |
|---|---:|---:|---:|---:|---:|---:|
| native | 5 / 5 | 0 | 5 | Not measured | 45.000 | 0 |
| rule_policy | 5 / 5 | 5 | 0 | 19.038 | 19.038 | 0 |
| ai_policy | 0 / 5 | 0 | 0 | Not measured | Not measured | 0 |

Censored trials did not recover during observation. Their actual recovery time is unknown; 45 seconds is a restricted-horizon value, not observed MTTR.

Matched native-minus-rule restricted-time differences (seconds): [23.093000000000757, 26.937000000005355, 27.25, 24.889999999999418, 27.64100000000326].
Mean matched difference: 25.962 seconds.
Exploratory 95% paired bootstrap interval: [24.283800000000337, 27.343800000002375]. This is conditional small-sample resampling, not production precision.

## Interpretation and trade-offs

For this deliberately narrow configuration fault, the fixed rule can request an independently permitted restore action. Native reconciliation does not change a Deployment's desired replica count back to one. This scenario therefore favors an explicit restore policy; it is not a test of generic process self-restart.
The rule path requires no model tokens or model availability. The same controller, credential scope and admission restrictions constrain every active arm. Fresh journals are operator-managed experimental episodes; continuous-production cooldown/budget behavior across journal resets is not evaluated.

**The real AI-assisted comparison is incomplete.** Provider settings/credentials were not available for the planned AI slots, which are retained as not run. No mock, deterministic fallback or LLM from this chat was substituted. AI accuracy, recovery benefit, token usage and monetary cost cannot be inferred from these baseline data.

## Limitations and error analysis

Only one scenario and five blocks on one shared cluster/machine were studied. Sequential order, shared caches, telemetry windows and host instrumentation can affect timing. The runtime waits eight seconds before decisions and samples business responses; measured times include those choices and API overhead.
The workload is closed-loop: slow failures reduce request throughput. Valid-response percentages are weighted by completed requests, not elapsed-time uptime or a fixed offered-load reliability estimate.
Ground truth was attached after diagnosis. The model sees normalized telemetry, not fixture labels. Target/symptom agreement does not prove the initiating mechanism. No benign-control false-positive rate, held-out accuracy or production safety rate is established.
Operator cleanup occurs after measurement and is excluded from recovery metrics. All setup failures, technical failures, censored and unrun slots remain explicit; no failed trial is silently replaced.

| Trial | Arm | Status | Reason | Censored |
|---|---|---|---|---|
| d9-01-native-17c645 | native | observed | no_recovery_within_horizon | True |
| d9-02-ai_policy-b40058 | ai_policy | not_run | real_provider_not_configured | None |
| d9-04-ai_policy-4a8350 | ai_policy | not_run | real_provider_not_configured | None |
| d9-05-native-288a6a | native | observed | no_recovery_within_horizon | True |
| d9-08-ai_policy-ad72c5 | ai_policy | not_run | real_provider_not_configured | None |
| d9-09-native-fb256e | native | observed | no_recovery_within_horizon | True |
| d9-10-native-476db0 | native | observed | no_recovery_within_horizon | True |
| d9-11-ai_policy-50a733 | ai_policy | not_run | real_provider_not_configured | None |
| d9-14-native-10da61 | native | observed | no_recovery_within_horizon | True |
| d9-15-ai_policy-1a96d4 | ai_policy | not_run | real_provider_not_configured | None |
