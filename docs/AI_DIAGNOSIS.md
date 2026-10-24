# Day 6: bounded evidence-grounded diagnosis

**Day 8 update:** Current sample-time freshness, pre-provider evidence validation, adapter input isolation, exception fallback and durable notification intake are documented in [AI_ROBUSTNESS.md](AI_ROBUSTNESS.md). Those strengthened contracts supersede the earlier implementation notes below. The prompt and non-executable diagnosis schema remain unchanged.

The agent returns versioned JSON containing hypotheses, service, subjective confidence,
evidence references, uncertainty, source/fallback reason, next read-only step, and the
complete normalized evidence bundle. `execution_allowed` is always false. It does not
run shell commands, inject faults, mutate Kubernetes, or execute recovery.

## Operation

Run from the existing project environment. Offline benchmark replay requires no Docker,
Kubernetes connection, credentials, or new fault injection:

```text
python scripts/diagnose.py --output .local/day6-replay.json benchmark evidence/day5/ci-39774736343/run-03a9072a24f8
python scripts/diagnose.py incident --database .local/incidents.sqlite3 --incident-id INCIDENT_ID
python scripts/diagnose.py incident --database PATH_TO_RETAINED_DB --incident-id INCIDENT_ID --as-of 2026-10-22T12:06:55+00:00
```

Output is JSON on stdout, or a newly created file when `--output` precedes the subcommand.
Existing output files are refused. Exit 0 means a structured grounded replay or a
supported/low-confidence incident hypothesis; exit 2 means insufficient evidence or an
input/configuration error. Low-confidence output is not authority to remediate.

The read-only tools open an existing SQLite store with `mode=ro`, `query_only=ON`,
parameterized fixed queries, an atomic read transaction and row/byte bounds. They never
instantiate the detector's writable Controller. Fixed Prometheus reads reuse the Day 4
Collector, endpoint allowlist, sample validation, byte limits and timeouts. `execute_tool`
rejects unknown names and argument keys; there is no arbitrary SQL/PromQL/URL/shell tool.
The current agent supplies observations once and ranks them in one model call rather
than exposing an iterative tool loop to the model. `TelemetryTools` is available for
explicit collection by a caller; incident CLI reads the stored evidence only.

## Provider configuration and budget

Default `SAFEHEAL_LLM_PROVIDER=disabled` makes zero model/network requests. Existing
credentials alone do not enable paid calls. Explicitly choose the endpoint, model and
budget before enabling a provider. Use environment variables or an external secret
manager; never put keys into source, evidence, command arguments, or chat.

| Variable | Default / meaning |
|---|---|
| `SAFEHEAL_LLM_PROVIDER` | `disabled` or `openai-compatible` |
| `SAFEHEAL_LLM_BASE_URL` | `https://api.openai.com/v1`; HTTPS required except explicit loopback HTTP |
| `SAFEHEAL_LLM_MODEL` | No default; explicit provider model required |
| `SAFEHEAL_LLM_API_KEY` | Secret; falls back to `OPENAI_API_KEY`; keyless explicit loopback supported |
| `SAFEHEAL_LLM_MAX_CALLS` | 1 per provider instance/process, hard ceiling 32; six-trial model replay requires 6 |
| `SAFEHEAL_LLM_MAX_OUTPUT_TOKENS` | 800 per request, range 128–4096 |
| `SAFEHEAL_LLM_TIMEOUT_SECONDS` | 20, range 1–30; bounded HTTP operations plus elapsed deadline checks |
| `SAFEHEAL_LLM_TOKEN_FIELD` | `max_completion_tokens`; compatible servers may require `max_tokens` |
| `SAFEHEAL_RUN_LIVE_MODEL_TESTS` | Unset; `1` explicitly enables the six-call real integration test |

Transport uses POST `/chat/completions` with JSON response mode. A compatible endpoint
must implement that contract; this is not an Anthropic-native or arbitrary model API
adapter. The input envelope is limited to 64,000 UTF-8 bytes (conservative input-token
upper bound, not a tokenizer estimate), response to 65,536 bytes, and no streaming or
automatic retries. Timeouts consume a call because remote execution may have happened.
HTTP redirects and ambient proxy credentials are disabled. Usage counts are retained on
the provider object when supplied by the server; they are not an invoice or dollar cap.
Choose a model's actual prices separately before paid use. Config repr and error records
exclude secrets and response bodies. No model or budget has been silently selected for
paid execution.

## Evidence and confidence contract

Prometheus raw matrices are decoded again; cached `services` fields cannot forge a
signal. Normalize only allowlisted service names, timestamps and numeric observations.
Raw labels, logs, headers, arbitrary reason strings and instructions are excluded from
the prompt. Each record has a content-addressed ID and full SHA-256; every hypothesis
must cite matching service/class support. The scorer verifies every bundled record's
hash, including uncited records. Hashes detect changes, not the truth of the original
instrumentation or a malicious telemetry source.

At most 128 observations, 4 MB per input record and 96 normalized output records are
accepted. On truncation, retain the latest support for every observed class/service
before recent context. Input telemetry must be within the declared 120-second diagnosis
window; raw samples retain the Day 4 15-second freshness/coverage checks. Missing current
telemetry or a latest usable observation over 15 seconds old yields insufficient
evidence and no provider call. Historical samples within the window explain the incident,
including one that has recovered; the output does not claim every symptom is still active.

Only `process_exit`, `server_errors`, `latency`, and `endpoint_unavailable` can be selected.
Scrape failure alone cannot establish process exit. Termination requires a recent
platform termination, or a same-Pod restart increment with changed container and matching
previous termination identity. Historical `last_state` alone cannot prove a new exit.
HTTP counters and histogram observations establish symptoms rather than an injected
lease, exact added delay, OOM, code defect, or initiating crash mechanism.

The model returns only classification, service, confidence and evidence IDs. Explanation
text is rendered from validated templates, preventing unsupported free-text causal
claims. Unknown IDs, wrong service/class, extra keys/actions, duplicates, non-finite
confidence, truncated responses and malformed JSON are rejected. Output confidence is
capped at .80 for a witnessed exit and .70 for symptoms; default decision threshold is
.65. These are conservative policy values, not calibrated probabilities. Below threshold
requires further evidence. Empty model hypotheses preserve abstention. Provider outage,
timeout, budget exhaustion or rejected output retains a deterministic .55-confidence
fallback with an explicit reason; no evidence yields `insufficient_evidence`.

## Blind comparison and tests

Replay receives only fixed-name telemetry/platform artifacts. The cutoff is the first
telemetry observation plus 105 seconds (capped by the last observation), independent of
labels, injection times and recovery outcomes. The agent never sees scenario-bearing
paths, trial IDs, `trial.json`, fault headers or injector acknowledgements. Artifact hashes
and trial labels are attached to the report only after diagnosis, when a separate scorer
opens independently verified ground truth. All attempted records remain in denominators.

Ground truth `process_crash` maps to observed `process_exit`, `http_5xx` to `server_errors`,
and `latency` to `latency`. Report observable-class agreement, target agreement, grounded
count, and real-LLM versus fallback counts separately. A mock choosing a supplied
candidate verifies plumbing and grounding; it is not an AI accuracy measurement. The six
retained development trials do not establish general root-cause accuracy or AI benefit.

```text
python -m pytest tests/test_diagnosis.py tests/test_diagnosis_live.py -q
python -m pytest -q
```

The live test requires explicit provider/model/secret configuration, `MAX_CALLS>=6`, and
`SAFEHEAL_RUN_LIVE_MODEL_TESTS=1`. It performs exactly six calls; every response must pass
the real provider and grounding validator. Fallback cannot pass this test. Without that
opt-in it is explicitly skipped. No credentials were available during Day 6 implementation,
so real-model quality and paid-provider compatibility remain unmeasured. Review
`evidence/day6` for the actual test and replay results.

Day 7's independent least-privilege recovery policy/executor remains separate future work.
