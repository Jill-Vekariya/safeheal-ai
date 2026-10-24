# Day 9 controlled experiments — protocol and limits

The predeclared machine-readable protocol is each run's `protocol.json`, written
and flushed before any fault injection. This study addresses the one recovery
action already permitted by Day 7: restore an enrolled payment Deployment from
desired replicas zero to one. It does not add an unrestricted remediation tool.

## Question and arms

In this isolated lab, how does a known, independently permitted restore action
compare with native reconciliation, and does real-model diagnosis improve upon
the fixed rule when both use the same recovery controller?

| Arm | Decision | Recovery authority |
|---|---|---|
| `native` | No intervention within observation | Native Kubernetes behavior only |
| `rule_policy` | Fresh payment scrape-down evidence | Existing independent typed controller |
| `ai_policy` | Real-provider validated top payment endpoint-unavailable hypothesis, confidence >=.65 | The same independent controller; never the model |

Five matched blocks each contain all three arms, shuffled within block by seed 9.
The operator induces the same payment scale-zero condition. Decision timing is
fixed at eight seconds after the host injection request. The observation horizon
is recorded in each protocol for every attempted arm, including early recoveries: 45 seconds in the original missing-provider cohort, and 90 seconds in the separate local-model cohort. The longer horizon was selected before the new run to accommodate bounded inference plus controller verification; the cohorts are not pooled. Two closed-loop
workers submit real order requests with a .2-second post-completion delay and a
four-second HTTP timeout. Every completion is retained.

The model sees only actual normalized Prometheus observations. Fixture labels,
the trial path and ground truth are not supplied. Ground truth is recorded after
the diagnostic decision and independently confirmed with desired/observed replica
state and business failures. Target/symptom agreement is distinct from proof of
the initiating mechanism.

The decision-to-action bridge is a fixed operator-selected experiment rule. It
can construct only `restore_payment_replica`, and only from a supported validated
payment endpoint-unavailable diagnosis. Fallback, low confidence, other services,
other symptom classes and extra action fields cannot qualify. The controller
still independently checks live state, enrolled UID/spec, replica zero and its
conditional patch. The model retains `execution_allowed: false`, and receives no
Kubernetes token, approval interface, shell or executable tool.

## Lab safety and episode state

Use only cluster `safeheal-day7`, context `kind-safeheal-day7`, namespace
`safeheal-dev`, and `.local/day7/kubeconfig`. Existing cluster/namespace/node
ownership guards and the shared recovery lock apply. The original stopped cluster
and its configuration are preserved. Prometheus uses the existing pinned source
configuration/image; no Grafana deployment or global Docker reset is necessary.

Each trial is a new **operator-enrolled experimental episode**, with an isolated
private journal and short-lived, named scale-only service-account token. This
allows repeated one-action experiments without modifying production controller
code or deleting earlier audit history. The model cannot reset an episode.
Continuous-production cooldown/hourly budgeting across journal resets is **not**
evaluated or claimed. Each actual action still passes unchanged RBAC and admission
policy. Actual forbidden-access probes must return HTTP 403. Tokens are removed
locally after the trial and are requested with ten-minute server lifetimes.

Measurement ends before operator cleanup. Cleanup restores only the same enrolled
Deployment if it still has zero desired replicas; identity/spec drift stops the
batch. Cleanup is explicitly labelled and cannot count as experimental recovery.
Workload/diagnosis/controller errors remain in the trial record. No failed trial
is automatically replaced. A cleanup failure halts the batch and retains evidence.

## Outcomes and analysis

Business recovery requires at least three consecutive confirmed, valid order
completions taking less than .5 seconds and spanning at least two seconds, after
the independently verified fault impact. Timing uses host monotonic offsets from
the injection request and includes API, fixed observation and instrumentation
overhead; it is not exact physical downtime.

Primary descriptive outcome is restricted time `min(T, H)` for that cohort's declared horizon. When recovery is not observed by H, actual recovery time is unknown: report a censored trial, never an observed H-second MTTR. Partial technical observations cannot be
imputed to a full horizon. Report observed-only means/medians, all individual
points, success/censor counts and matched restricted-time differences separately.
The paired bootstrap interval is exploratory resampling of only five blocks, not
production precision. No statistically established general benefit is claimed.

The workload is closed-loop. Outages reduce throughput, so the proportion of valid
completed responses is request weighted; it is neither elapsed-time uptime nor
reliability under a fixed offered load. The response-comparison chart makes this
distinction explicit. Retain denominators as well as percentages.

Diagnostic metrics distinguish actual validated model outputs from fallback,
abstention, rejected output, transport failure and absent configuration. Do not
substitute mocked diagnoses or responses from this chat for real-provider results.
Record observed token usage and request counts, but leave monetary cost unknown
without provider prices/account billing. Baseline arms use no LLM requests; their
total compute/operating cost is still unmeasured.

## Provider configuration

The original cohort retained five `not_run` AI slots while the user-selected provider was unconfigured. A later instruction delegated completion of the project. Automatic review rejected the proposed cloud destination before execution, so the follow-up study uses actual local model weights and loopback inference instead. No cloud diagnosis was sent. The original missing-provider records remain unchanged; they are not filled later or silently pooled with the new study.

For local inference, copy tracked `examples/provider.local.json` to the ignored `.local/day9/provider-local.json`. For another explicitly authorized endpoint, create `.local/day9/provider.json` with the same exact fields and supply
the endpoint, model, explicit maximum calls/output tokens/timeout/token-field and
credential-file location. Keep the credential in the referenced local file rather
than source, command arguments, reports or chat. The profile supports the existing
OpenAI-compatible JSON transport and its HTTPS/loopback, byte, timeout and call
bounds. It does not enable Ollama's installed cloud model automatically.

The protocol freezes provider availability/settings at run start. If configuration
arrives later, run a new complete matched cohort in a **new** directory; do not
fill old slots out of order, overwrite records, or pool cohorts silently. Five AI
slots require a budget of at least five requests. No real-model claim is made for
a fallback or HTTP failure.

For the retained local cohort, the explicit profile uses base URL `http://127.0.0.1:11434/v1`, model `qwen2.5:1.5b-instruct-q4_K_M`, `max_calls: 5`, `max_output_tokens: 800`, `timeout_seconds: 30`, `token_field: "max_tokens"`, and `api_key_file: ""`. The loader removes the empty key-file field before constructing the provider; it is not passed as extra authority/configuration. Local model digest and Ollama version are recorded in `evidence/day9/local-model-environment.json`. Provider settings are frozen before the run; cold/warm loading and low available host memory can affect measured latency. A timeout consumes its one request and does not trigger a retry or action.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts/controlled_experiment.py plan --horizon 90
.\.venv\Scripts\python.exe scripts/controlled_experiment.py setup --execute
.\.venv\Scripts\python.exe scripts/controlled_experiment.py run --execute --horizon 90 --provider-profile .local/day9/provider-local.json --output evidence/day9/new-run
.\.venv\Scripts\python.exe scripts/finalize_controlled.py evidence/day9/new-run
.\.venv\Scripts\python.exe scripts/analyze_controlled.py evidence/day9/new-run --output .local/day9-new-analysis --no-plots
```

Before analysis, use `finalize_controlled.py` to create the raw run's `manifest.json` from all retained files
after owned forwarding/workload processes have stopped. The analysis verifies
every hash and replays raw request metrics instead of trusting stored summaries.
Run/output directories must be new; previously recorded data is not overwritten.
See the retained run and handoff for the final manifest and exact results.

Figure rendering uses the optional pinned `requirements-analysis.txt`. Numerical
analysis requires only the existing project runtime. The same script can render
from verified `analysis.json` on a machine with those plotting packages installed:

```powershell
python -m pip install -r requirements-analysis.txt
python scripts/analyze_controlled.py --render-analysis evidence/day9/analysis/analysis.json --output .local/day9-figures
```

This is one intentionally policy-addressable configuration fault, on one shared
cluster, with five sequential matched blocks. It favors explicit restoration of
a desired replica count that native reconciliation does not automatically change.
It does not compare generic crash recovery, all existing fault scenarios, benign
false-positive behavior or production safety. Conclusions must remain within that
scope. Real AI benefit must be judged from the separately retained configured local-model cohort, including failures and censored outcomes; completion of an experiment does not imply an AI advantage.
