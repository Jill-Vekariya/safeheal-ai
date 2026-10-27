# Stage 3 provider-boundary validation — preregistered local protocol

Defined before executing the new paired experiment. Baseline: exact merged commit
`a95d0b5c216094052e0c37e7d99d1242dcea03d4`. Treatment: local changes to
`services/diagnosis/provider.py`, `services/diagnosis/agent.py` and
`services/recovery/kubernetes.py`. Existing experiment artifacts are read-only.

## Hypothesis and intervention

Bounded application response accumulation and refusal of unexpected compression
can reject oversized/encoded responses before appending/decompressing an unlimited
body, while retaining valid diagnosis, independent validation and fail-closed
recovery behavior. The existing Kubernetes adapter has the same post-append
pattern; apply the same transport restriction there without changing its fixed
endpoint, credentials, JSON Patch preconditions or controller permissions.

Use `Accept-Encoding: identity`, reject a non-identity Content-Encoding before
body iteration, check every incoming chunk without chunk-size coalescing and check the remaining byte
budget before extending the accumulator. Preserve one charged call per request,
no automatic provider retries, context-managed stream closure, and fixed redacted
failure codes. HTTP phase timeouts and between-chunk elapsed checks are not hard
preemptive cancellation of arbitrary synchronous transports.

## Design and experimental units

A paired census of 19 deliberately selected synthetic development fixtures, one
baseline and one treatment observation each, no repeated or independent draws:

1. Valid full hypothesis; 2. valid candidate index; 3. malformed outer JSON;
4. unsupported evidence reference; 5. injected action field; 6. provider tool call;
7. explicit abstention; 8. transport timeout; 9. connection failure; 10. HTTP 503;
11. oversized identity response; 12. gzip-encoded otherwise valid response;
13. injected between-chunk elapsed deadline; 14. reported output-token excess;
15. duplicate outer JSON keys; 16. exhausted one-call budget;
17. valid Kubernetes response; 18. oversized Kubernetes response;
19. gzip-encoded Kubernetes response.

Experimental unit is the named fixture. Pair identical fixture definitions and
one evaluator across exact baseline source and treatment source, in fixed order.
No timing-effect inference is attempted, so there is no randomized timing study.
TLS context bypass and HTTP fault injection exist only in the evaluator's
MockTransport adapter. No real model, external provider, cluster mutation or
message delivery is involved. Model names and keys are synthetic markers.

## Outcomes and success criteria

Retain all 38 planned arm/fixture attempts, exceptions and failures. Every
application bytearray must remain <=65,536 provider bytes or <=262,144 Kubernetes
bytes; encoded responses must be refused with zero stream chunks consumed;
response streams must close. Valid fixtures must remain valid; malformed,
unsupported, unavailable and over-budget provider responses must degrade with
redacted codes and execution_allowed=false. Persist each provider fixture's
result in an owned notification journal and prove a duplicate notification does
not issue another request. Kernel/network-buffer memory is not this accumulator
metric. The controller test suite independently checks allowlists, approvals,
identity binding, conditional writes, claims, audit and failure behavior.

Treatment success requires all 19 fixtures to satisfy their expectations and
no baseline-passing fixture to regress. Baseline failures remain failures; the
protocol does not demand a fixed number of improvements. A failed harness is
retained and reported separately, not relabeled as an application result.

## Sample size, analysis, budget and stopping

Nineteen purposive branch fixtures are sufficient only for these regression
checks, not for statistical adequacy, population safety rates, MTTR, causal model
accuracy or superiority. Use paired pass/fail counts, per-case statuses, consumed
chunks and maximum accumulator sizes; no binomial confidence intervals or tests
on this nonrandom census. Repeated assertions are not additional trials.

Budget: exactly two arms x19 fixture slots, at most 32 synthetic provider request
invocations total (one per provider fixture/arm), $0 external-provider spending,
zero model inference and zero cluster writes. Each arm subprocess has a 60-second
host timeout. Stop on unexpected network access, credential exposure, evaluator
integrity mismatch or actual cluster interaction. Preserve partial outputs and
unattempted slots after a technical stop; never replace failed trials silently.
A treatment failure prevents a passing conclusion; repair and rerun only in a new
retained run directory with the reason and new source fingerprint recorded.

## Existing real-model studies

Replay the shipped artifact inventory and separately verify each existing
cohort. Retain failed, interrupted, censored and unrun records and original
instrument snapshots. The completed 15-trial CPU cohort has five matched blocks
and a 90-second restricted horizon. Distinguish two AI recoveries from four
validated diagnoses and five real requests; never count deterministic fallback as
real-model success. Its small paired bootstrap intervals are descriptive and
conditional, not population precision. This new local transport experiment does
not add real-model evidence or re-run the old study under modified code.

## Pre-execution amendment 1

Before any paired fixture run, inspected the installed HTTPX 0.28.1
`Response.iter_bytes` and `ByteChunker`: a fixed chunk size coalesces small raw
chunks and can delay elapsed checks. Use uncoalesced identity-decoded chunks and
pre-append budget checks instead. The application accumulator stays bounded;
underlying transport allocation is outside that metric. Keep the original
protocol snapshot and this amended hash. Apply the same small correction to the
unpublished Stage 1 ReleaseLens change, with a tiny-chunk regression test.
The paired fixture count, expectations, budget and analysis remain unchanged.

## Harness correction before run 002

Run 001 retained all 38 rows and failed its persistence check on every provider
case. Inspection found a measurement bug: comparing the JSON-decoded database
payload with the in-memory diagnosis treats JSON lists and evidence tuples as
unequal. Runtime persistence correctly stores `encoded(diagnosis)`. Change only
the evaluator comparison to require the stored bytes equal that serialized output.
Keep run 001, its original evaluator hash and all its failed rows. Re-run the
unchanged 19 cases in a new directory with the corrected evaluator shared by both
arms. Application source and outcome expectations do not change. Permit 32 more
synthetic invocations (64 total across the two experimental runs); external spend,
real-model calls and cluster writes remain zero. Separately reported regression
tests are repeated engineering checks, not extra independent experiment units.
