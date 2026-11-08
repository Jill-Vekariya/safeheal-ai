# SafeHeal AI — Day 8 AI reliability and robustness handoff

**Updated:** 24 October 2026. **Day 8 engineering acceptance: PASS. Overall milestones: 8/10 (80%). The full project is not complete.**

Continue the existing canonical repository at `C:\Users\jillv\Projects\safeheal-ai`
on Jill-Vekariya10, Desktop Commander device
`8025e560-e3a9-4f10-9084-a256f42ffb82`. Read this handoff together with current
`PROJECT_STATUS.md`, `WORKLOG.md`, `EXPERIMENTS.md`, `ROADMAP.md` and actual Git
state. This is a continuation note, not a source-code backup.

## Git and delivery state

Day 8 continues verified Day 7 commit
`d10575a79781eda91f942aef56ee5a90fa5e1aba` on local branch
`day8-ai-robustness`. Inspect actual Git history for the final Day 8 commit; the
saved user-facing copy adds its verified SHA after commit.

Repository: https://github.com/Jill-Vekariya/safeheal-ai (private).
No Day 8 push, merge, remote CI run, visibility change or branch-protection change
was performed. Earlier publication authorization/account-feature blockers remain
separate. Do not confuse a local engineering milestone with delivery to GitHub
`main`. Do not bypass the recorded GitHub-upload rejection. No fresh remote-main
state assertion is made here.

## Implementation delivered

- A fixed, reproducible robustness evaluator covering **33 diagnostic cases and
  three notification sequences**, using synthetic observations and mocked providers.
- Paired before/after runner that exports exact Day 7 source from Git into a
  temporary directory, uses an identical evaluator/case manifest for both arms,
  verifies baseline source hashes, preserves all attempted cases and refuses to
  overwrite reports.
- Actual sample-time freshness checks, preventing a recent collection envelope
  from refreshing older scrape samples. Current eligibility remains 15 seconds;
  bounded historical support remains 120 seconds.
- Pre-provider validation of every normalized evidence record, including uncited
  context: types/fields, source/service/support classes, timestamps, duplicate IDs,
  content hashes and derived support consistency. Corrupt or injected normalized
  evidence yields sanitized insufficient-evidence output with zero provider calls.
- Malformed platform records are excluded with fixed issue codes. Raw log text,
  labels, cached summaries and free-form platform reasons remain untrusted.
- Detached provider inputs and an independently held validation snapshot prevent
  adapter mutation from changing caller evidence or response grounding.
- Unexpected adapter exceptions produce a fixed, secret-free unavailable reason
  and low-confidence fallback without retry. Existing transport, abstention,
  confidence and unsupported-claim/action safeguards remain intact.
- Durable local notification intake with strict event schema/time bounds,
  identifier collision rejection, same-event and same-incident/evidence deduplication,
  concurrent-consumer serialization, claim-before-call, restart persistence,
  journal-capacity limits, decision audit and fail-closed interrupted/persistence paths.
- New `diagnose.py notification` route; existing direct `incident` and `benchmark`
  interfaces remain intentional one-shot/replay operations.
- **74 new automated robustness tests**, operational failure-contract documentation,
  paired-evaluation CI wiring and raw-evidence/source byte preservation.

Sources: `services/diagnosis/{agent,evidence,notifications}.py`,
`scripts/diagnose.py`, `scripts/evaluate_robustness.py`,
`scripts/compare_robustness.py`, `tests/test_diagnosis_robustness.py`.
Contract and reproduction: `docs/AI_ROBUSTNESS.md`.

No prompt change is credited: measured improvements come from evidence validation,
input isolation, error handling and durable intake. The model gains no approval,
credential, shell or execution authority. Day 7 recovery code/policy is unchanged.

## Verified results

| Check | Result |
|---|---|
| Final full Windows suite | **476 passed, 2 skipped, 0 failed**, one existing Starlette/httpx warning |
| New robustness tests | **74 passed** |
| Combined diagnosis-focused suite | **123 passed** |
| Fixed paired cases before | **27/36 passed**, 9 failed one or more declared checks |
| Fixed paired cases after | **36/36 passed**, 0 failed |
| Improved / regressed cases | **9 improved / 0 regressed** |
| Evaluator and scenario definitions | Identical SHA-256/definitions in both paired arms |
| Baseline source | Verified against exact Day 7 Git blobs |
| Five identical notifications | Simulated provider attempts **5 → 1** |
| Five new notification IDs, same incident/evidence | Attempts **5 → 1** |
| Stale notification | Attempts **1 → 0** |
| Real-model calls | **Zero** |
| Cluster writes / outgoing messages | **Zero** during Day 8 |

The nine improved cases are: stale samples in a recent collection envelope;
malformed platform shape; tampered uncited context; rehashed normalized prose;
provider input mutation; unexpected adapter exception; repeated notification;
different IDs for identical evidence; and stale notification.

The other cases continued to cover missing/incomplete/stale/future evidence,
irrelevant or stale logs, prompt injection in labels, cached-summary forgery,
duplicate metric series, historical termination, abstention/low confidence,
unsupported OOM claims/citations/actions, and mocked provider timeout, connection
failure, 429/503, redirect, tool call, invalid JSON and oversized response.

These are fixed **development safety cases**. The before notification arm represents
the shipped direct call per event; Day 7 did not have durable intake. The after arm
adds that layer. Counts are simulated provider attempts, not paid LLM calls.
They do not establish held-out accuracy, a population failure rate, real-provider
quality, online diagnosis latency, production reliability, MTTR improvement or AI
superiority. A failed check did not imply that the baseline executed a command.

Authoritative measurements: `evidence/day8/paired/{before,after,comparison}.json`.
Final tests: `evidence/day8/windows-tests.txt` and `diagnosis-tests.txt`.
Independent verification/provenance: `evidence/day8/acceptance.json`.
Original Day 5/6/7 evidence remains unchanged; new diagnostics intentionally evolve
the Day 6 implementation, so historical source manifests describe their old revisions.

## Failure handling and retained development issue

An initial after-evaluation attempt raised `AttributeError` in the evaluator when
it treated a suppressed notification's `diagnosis: null` as a dictionary. No after
report was produced by that attempt. Its description is retained in engineering
notes. The evaluator's null handling was corrected, then **both arms** were rerun
using the same corrected evaluator and exact baseline/current source. Initial
`before.json` and `after-initial.json` remain separately retained and are not the
authoritative paired comparison. Initial new-test run: 71 passed; later timestamp
and plausible uncited-tamper regressions bring the final new-test count to 74.

The two full-suite skips remain the Windows symlink-creation privilege requirement
and explicit real-provider opt-in/credentials test. No paid model was selected.

For notification intake, `diagnosed` means intake/result persistence completed;
the inner diagnosis may still be low-confidence, abstaining or insufficient.
Suppressed/rejected results contain no diagnosis and never permit execution.
Event IDs cannot be reused for different payloads. Fresh evidence or a distinct
incident is not suppressed. Replayed evidence after provider failure is not
automatically retried. A crash can leave `pending`; an agent failure can leave
`uncertain`. Investigate before operator reconciliation. There is no automatic
retry/claim deletion command. Direct incident/benchmark calls are not covered by
the notification journal's deduplication guarantee.

An unwritable journal prevents a provider call. A post-call persistence failure
cannot return unrecorded success and leaves the durable claim. Journal capacity
fails closed at 10,000 events/50,000 audit rows and requires operator maintenance.
The local audit is not externally tamper-proof; same-user filesystem attackers and
global billing limits are outside this milestone. Hashes cannot authenticate a
dishonest telemetry instrument. Historical evidence is not proof of an active fault.

## Reproduce and continue

Use the existing project `.venv` and pinned dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/compare_robustness.py --output-dir .local/day8-new-comparison
.\.venv\Scripts\python.exe scripts/diagnose.py notification --database .local/incidents.sqlite3 --event .local/event.json --journal .local/diagnosis-notifications.sqlite3
```

Comparison output must be a new directory. It requires the exact Day 7 Git object,
but no Docker/Kubernetes/model credentials. The CI test checkout now fetches full
history and preserves paired reports; wiring is not a successful GitHub run.

No cluster repair, new fault trial, Docker reset or kubeconfig/context change was
performed during Day 8. The Day 7 lab/environment notes are historical; inspect
actual state before future cluster operations. Continue to supply the dedicated
project kubeconfig/context explicitly and preserve the original stopped cluster.

**Next: Day 9 matched controlled experiments.** Declare A/B/C arms, scenarios,
repetitions, stopping/censoring rules and analysis before running trials. Aim for at
least five repetitions per scenario/approach where feasible; retain all raw outcomes,
uncertainty and limitations. Day 10 reproducibility/report/demo remains incomplete.
Real-provider quality and private GitHub publication/integration remain separate
outstanding work. The project is **80%, not 100%, complete** by milestone count.
