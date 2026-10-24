# SafeHeal AI — Day 7 safe autonomous recovery handoff

**Updated:** 24 October 2026. **Day 7 engineering acceptance: PASS. Overall milestones: 7/10 (70%). The full project is not complete.**

Use the existing canonical repository at `C:\Users\jillv\Projects\safeheal-ai` on
Jill-Vekariya10, device `8025e560-e3a9-4f10-9084-a256f42ffb82`. Read this handoff
together with current `PROJECT_STATUS.md`, `WORKLOG.md`, `EXPERIMENTS.md`,
`ROADMAP.md`, and actual Git state. This document is not a source-code backup.

## Implementation

Day 7 continues canonical Day 6 commit `e8f2522` on local branch
`day7-safe-recovery`. Repository: https://github.com/Jill-Vekariya/safeheal-ai
(private). Day 7 publication and GitHub CI have not run. No push, merge, repository
visibility change or branch-protection change was attempted. The Day 6 handoff's
separate publication-authorization blocker still applies. Local `main` was checked
at `156da54a5de4ddf4977676ebf7ce29310089fb0f` (Day 4); this is not a fresh remote
GitHub state assertion. Inspect actual Git history for the Day 7 commit.

Delivered:

- Immutable typed allowlist with one action: `restore_payment_replica`, only the
  enrolled `safeheal-dev/payment` Deployment, desired replicas **0 → 1**.
- Independent deterministic controller with strict proposal schema, pinned UID and
  spec, ownership checks, live corroboration, conditional JSON Patch and no write
  retries. Mode, approval, namespace, replica count and command fields in a model
  proposal cannot grant authority. Day 6 diagnoses remain non-executable.
- Default dry-run; expiring request/spec/generation-bound, single-use operator
  approval; autonomous mode requiring trusted operator opt-in.
- Dedicated short-lived executor token, resource-name-limited Role, no pod/exec or
  secret access, no full Deployment patch, and a fail-closed admission policy that
  independently constrains the exact service account to the zero-to-one change.
- No controller shell, kubectl, kubeconfig, arbitrary URL, SQL or model-provider
  integration. Its HTTPS client uses fixed endpoints, verified CA, loopback-only
  server, bounded responses/timeouts, no redirects or environment proxies.
- Durable claim-before-write, duplicate prevention, single-flight execution,
  cooldown/hourly attempt limits, audit chain, and fail-closed uncertain outcomes.
- Recovery verification requires three consecutive ready observations with the
  exact expected generation, observed generation and replica counts. The separate
  operator harness checks Service DNS, health/readiness and a single order POST
  after bounded GET-only route convergence.
- 65 new recovery safety/failure tests, guarded live acceptance harness,
  operational documentation and CI wiring for both live modes.

Sources: `services/recovery/`, `scripts/recover.py`,
`scripts/verify_recovery.py`, `infrastructure/recovery/policy.yaml`,
`tests/test_safe_recovery.py`, `docs/SAFE_RECOVERY.md`.

## Verified evidence

| Check | Result |
|---|---|
| Final full Windows suite | **402 passed, 2 skipped, 0 failed**, one existing Starlette/httpx warning |
| Recovery safety tests | **65 passed** |
| Autonomous live acceptance | **PASS**, `d7-autonomous-5ba20e9e0e`, 16:45:51–16:46:08 UTC |
| Approval live acceptance | **PASS**, `d7-approval-324fc2fcfe`, 16:46:09–16:46:27 UTC |
| Real executor-token negative checks | Eight denied calls per successful trial; all HTTP 403 |
| Admission from zero replicas | Replica count two denied with HTTP 403 in both trials, using server dry-run |
| Dry-run | Desired replicas stayed zero; no action claimed/executed |
| Approval gate | Unapproved action denied, separate operator approval succeeded |
| Replay | Denied after each verified action |
| Final business checks/cleanup | Both passed; neither successful trial required operator restoration |
| Audit integrity | All **27 retained events** verified across available trial audit databases |
| Accepted source manifests | **Zero mismatches** against final executable sources/policy |
| Local token cleanup | No trial executor-token file remains; server-issued tokens expire after ten minutes |
| LLM calls | **Zero**; no paid or real-model quality claim |

Skips remain the existing Windows symlink-creation privilege check and explicit
real-provider opt-in/credentials check. CI is wired but not executed for this local
branch. These two successful live trials establish the narrow engineering gate,
not population reliability, benchmark MTTR gains, general diagnosis/recovery
quality, or AI superiority.

Evidence: `evidence/day7/verification.json`, `windows-tests.txt`, and every
`d7-*/{acceptance.json,audit.json,audit.sqlite3}` where an audit was produced.
Failed attempts remain failed and retain their source hashes; do not replace
their outcomes with later passing results. Original Day 5/6 evidence is unchanged.

## Retained failures and corrections

The initial new-test run had **53 passed, 1 failed**. A follow-up assertion still
used a fake API configured to return a replaced UID. Correcting that fixture reset
made the intended unresolved-execution assertion test the right condition. Final
tests pass; the initial test failure is not hidden.

Four unsuccessful live engineering attempts are retained:

1. Admission rejected the forbidden request as HTTP 422; the harness required
   HTTP 403. Specifying `reason: Forbidden` made that result explicit. This stopped
   before fault injection; it was not unauthorized execution.
2. Two attempts safely rejected the zero-scale precondition. Server-side dry-run
   inspection confirmed that Kubernetes serializes zero ScaleSpec as `{}`. The
   controller now validates that representation and atomically tests the entire
   scale spec before adding replicas=one. Four regression cases cover omitted
   zero and invalid specs. Bounded read-only consistent-snapshot handling also
   covers resource-version churn, with two additional regression tests.
3. A later attempt verified controller recovery but failed the separate business
   check on Service connection refusal. It remains failed. The harness now reuses
   the existing bounded GET-only route wait before its one unretried order POST.

Operator cleanup restored only the two precondition-failed scale-zero fixtures;
those restorations are explicitly recorded and do not count as controller success.

## Environment and continuation

The original `safeheal-dev-control-plane` is preserved but stopped. Docker could
not start it because Windows rejects its reserved loopback API port 49693. Its
existing loopback proxy container remains running. No cluster deletion, Docker
reset, system-wide port change or default-context change was performed.

Acceptance used a separate pinned kind **v0.33.0 / Kubernetes v1.36.4** lab:

- Cluster `safeheal-day7`; context `kind-safeheal-day7`.
- Node `safeheal-day7-control-plane`; namespace `safeheal-dev`, labelled local-test.
- Dedicated kubeconfig `.local/day7/kubeconfig`; always supply it explicitly.
- Existing verified application image `safeheal-ai:sha256-311922d1b56ffd31` loaded
  from cache. Day 7 modifies host-side recovery code, not application services.
- Dedicated service account/Role/RoleBinding and narrow admission policy remain
  installed for reproducibility. Controller tokens were held in private ignored
  per-trial directories and deleted locally after the trials.

Reproduce with the existing `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode autonomous
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode approval
```

`--execute` is a lab-only operator harness: it records and introduces a scale-zero
fixture, then invokes the independent credential-limited controller. It must never
be exposed as a model tool. See `docs/SAFE_RECOVERY.md` for enrollment, direct
controller usage, trust boundaries, failure investigation and exact limitations.

An interrupted/failed controller write leaves a durable `running` or `uncertain`
claim that blocks further writes. Investigate live state and audit before manual
reconciliation; no automatic retry/override exists. The audit is local and can be
rewritten by an OS administrator; hostile same-user process isolation and an
external tamper-proof audit service are not established.

**Next:** Day 8 robustness against missing/stale/misleading evidence, provider
outage and unsupported claims. Day 9 matched controlled experiments and Day 10
final reproducibility/report/demo remain incomplete. Real-provider performance,
private GitHub publication/integration and branch-protection availability remain
separate outstanding items from the earlier handoff.
