# Day 8 — AI reliability and robustness evaluation

The engineering gate is a documented failure contract plus automated adversarial
tests. This evaluation uses **36 fixed development cases: 33 diagnostic cases and
three notification sequences**, with synthetic evidence and mocked providers.
It makes zero real-model calls, performs no cluster mutation and sends no messages.
The numbers measure safeguards on these cases; they are not held-out accuracy,
production failure rates, statistical reliability or an MTTR benefit.

## Measured comparison

The paired runner exports exact service source blobs from Day 7 commit
`d10575a79781eda91f942aef56ee5a90fa5e1aba` into a temporary directory. It runs the
same evaluator there and against the changed working tree. It checks identical
case definitions/evaluator SHA-256, verifies baseline source against Git, preserves
both complete reports and refuses to overwrite output directories.

| Measurement | Day 7 baseline | Day 8 |
|---|---:|---:|
| Fixed cases meeting every declared check | 27/36 | 36/36 |
| Cases failing one or more checks | 9 | 0 |
| Regressed cases | — | 0 |
| Repeated notification: diagnosis/provider attempts for five events | 5 | 1 |
| Different notification IDs, same incident/evidence: attempts for five events | 5 | 1 |
| Stale notification: attempts | 1 | 0 |
| Real-model calls | 0 | 0 |

The notification baseline invokes the shipped direct diagnosis call per event;
Day 7 had no durable notification intake. The after arm adds that explicit layer.
These counts describe simulated provider invocations, not purchased LLM calls.

Nine improvements were observed:

| Case | Baseline behavior | Day 8 behavior |
|---|---|---|
| Old samples inside a recent collection envelope | Collection freshness could admit samples 29 seconds old | Freshness uses actual scrape sample time; no provider call beyond 15 seconds |
| Malformed platform state shape | AttributeError escaped aggregation | Invalid platform entry is flagged and excluded |
| Tampered uncited context | Reached model/output; downstream scorer noticed corruption | Every record is validated before the provider call |
| Rehashed free text inserted into normalized evidence | Extra prose reached the prompt | Exact normalized schema excludes the field before provider use |
| Provider adapter mutates input | Caller evidence and output grounding could change | Provider receives a detached copy; validation uses independent trusted evidence |
| Unexpected adapter RuntimeError | Exception escaped diagnosis | Secret-free `provider_unavailable`, grounded low-confidence fallback, no retry |
| Same notification delivered five times | Five direct calls | One durable claim; four suppressed events |
| New event IDs for the same incident/evidence | Five direct calls | Canonical evidence fingerprint suppresses duplicate work |
| Notification over 60 seconds old | Direct call had no event-age gate | Rejected before provider use |

The other 27 cases continued to pass. They cover healthy/missing/incomplete/stale
or future evidence; forged cached summaries; prompt injection in labels; stale and
irrelevant logs; duplicate metric series; old termination history; explicit model
abstention and low confidence; unsupported OOM claims, fabricated/wrong-service
citations and unsafe action proposals; provider timeouts, connection failure, 429,
503, redirects, tool calls, invalid JSON and oversized responses.

## Diagnosis failure contract

Only the trusted raw-data Aggregator constructs evidence. Raw Prometheus data is
decoded again; cached summaries, logs, labels and free-form platform reasons do
not become trusted claims. Raw logs remain excluded rather than being treated as
instructions or proof. Platform shapes and termination identity/time requirements
are checked. Invalid platform entries add a fixed issue code and contribute no
fault evidence. Malformed raw decoding produces unavailable observations.

Before any model request, `validate_bundle` checks every record, including uncited
context: exact allowlisted fields/types, known service/source/support classes,
timestamps/window, duplicate IDs, full content hashes and normalized support
consistency. Unknown issue text or normalized prose is rejected. Invalid bundles
produce a sanitized `insufficient_evidence` result with `invalid_evidence`, empty
hypotheses and zero provider calls. The original untrusted payload is not echoed.

Collection time cannot refresh old samples. Current eligibility uses actual
`up_at` sample timestamps with a 15-second limit. At most 120 seconds of historical
support remains available to explain an incident. Recent scrape witnesses are
retained when selecting bounded evidence so freshness is not lost to truncation.
Historical support does not establish that a fault is currently active. Evidence
hashes and schemas cannot prove that an instrument reports the truth; plausible
false telemetry from a compromised source remains outside this guarantee.

The provider receives a deep copy of validated evidence; the response is checked
against a separate trusted snapshot. Only the existing classification/service/
confidence/citation schema is accepted. Explanation text comes from fixed verified
templates. Extra action fields are rejected even for the allowlisted recovery
action. No diagnosis grants execution authority, changes configuration, approves
recovery, or provides a credential. Day 7's independent controller remains intact.

Provider timeout, transport failure or unexpected adapter exception produces a
fixed secret-free reason and a grounded fallback capped at .55 confidence. It does
not retry or count fallback as model success. Explicit model abstention stays an
abstention. Missing current evidence prevents the request entirely. Existing
provider byte/time/call limits, response restrictions and confidence caps remain.
The prompt is unchanged: the measured improvements come from evidence verification,
input isolation, error handling and durable intake, not an unmeasured prompt claim.

## Durable incident-notification intake

`services/diagnosis/notifications.py` accepts this exact event schema:

```json
{"schema_version":"day8-notification-v1","notification_id":"notice-1","incident_id":"incident-1","observed_at":1800000000.0}
```

Identifiers are bounded; unknown fields (including actions, commands, approvals
or modes), invalid times, future events and events older than 60 seconds are
rejected. The evidence view must be no more than 15 seconds old and valid.
The CLI bounds event files at 8192 bytes and rejects duplicate JSON keys/nonfinite
numbers. The operator supplies the incident store and journal paths; the model
does not select them.

The intake stores a durable SQLite claim **before** calling the agent. An event ID
cannot be reused with a conflicting payload. New IDs with the same incident and
canonical evidence records are suppressed too, including reordered records.
New incident IDs or genuinely different observations remain eligible. The moving
collection-envelope time is excluded from the deduplication fingerprint.

Transactions serialize concurrent consumers. Reopening the same journal preserves
deduplication. Provider failure/abstention results are recorded without retrying
the same evidence. A crash leaves a `pending` claim; an agent failure can leave
`uncertain`. Both suppress repeat work. An unwritable journal prevents provider
use; failed result persistence cannot return unrecorded success. Fixed audit rows
record decisions. A 10,000-event and 50,000-audit-row capacity fails closed and
requires operator maintenance; old entries are not silently discarded.

`diagnosed` in the outer intake envelope means that handling/result persistence
completed; inspect the inner diagnosis status for fallback, abstention or
insufficient evidence. Suppressed/rejected envelopes contain no diagnosis and
always disable execution. This local journal is not an external tamper-proof
audit service. Hostile same-user process isolation and global billing limits are
not established. Existing per-provider call budgets remain per instance/process.

Deduplication applies to the new **notification** route and callers using
`NotificationPipeline`. The existing direct `incident` and `benchmark` commands
remain intentional one-shot/replay interfaces. No notification service, outbound
messaging integration or automatic remediation loop is enabled.

## Reproduce and inspect

Use the existing pinned project environment, from the canonical checkout:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/compare_robustness.py --output-dir .local/day8-new-comparison
.\.venv\Scripts\python.exe scripts/diagnose.py notification --database .local/incidents.sqlite3 --event .local/event.json --journal .local/diagnosis-notifications.sqlite3
```

The paired command needs the exact Day 7 Git object; CI now fetches full history.
The output directory must be new. Reports retain all attempted cases, complete
diagnoses/checks, fixed source/reference hashes and simulated provider call counts.
The runner performs no fetch/push/merge or cluster operation. Existing benchmark
replays remain blind to ground truth and the original Day 5/6/7 evidence is intact.

Authoritative measured reports are under `evidence/day8/paired/`. Early development
reports and the evaluator's initial null-result handling failure are retained or
described separately in `engineering-notes.json`. That evaluator defect was
corrected, then **both** arms were rerun from exact baseline/current source with
the same corrected evaluator; no original report was overwritten.

CI runs automated safety tests, the paired comparison, the original six-trial
diagnosis replay and existing Kubernetes acceptance. It retains the reports.
Wiring is not a claim that unpublished Day 8 code has run on GitHub. See the
Day 8 handoff for final local suite/commit and publication state.
