# Independent safe recovery (Day 7)

The model may propose JSON data. It has no shell, kubectl, SQL, approval tool,
executor token, or configuration-write interface. Day 6 diagnoses still have
`execution_allowed: false`. This controller is a separate deterministic process;
model confidence or text never grants permission. No paid model call is needed.

## Catalog and enforcement

There is deliberately one immutable catalog entry, `restore_payment_replica`:
the enrolled `safeheal-dev/payment` Deployment must have **zero** desired replicas;
the only write sets its scale subresource to **one**. Restarts, pod deletion,
arbitrary scaling, namespace changes, commands, image/configuration updates and
other services are unsupported. The bounded action restores a scale-zero outage;
it does not claim to repair arbitrary process, latency or HTTP faults.

The controller independently reads live Kubernetes state. It validates the pinned
Deployment UID, namespace/name, ownership labels and entire enrolled spec except
replica count. Approval additionally binds the exact request hash, generation and
spec fingerprint. Deployment and scale reads must have identical resource versions;
status-only version churn permits at most three read-only snapshot attempts.
A single JSON Patch tests UID, resourceVersion and the complete zero-valued scale
spec before adding replicas=one. Kubernetes serializes a zero ScaleSpec as `{}`;
both that representation and explicit integer zero are supported. There is no
write retry or retargeting on conflict.

`infrastructure/recovery/policy.yaml` adds defense in depth:

| Layer | Actual restriction |
|---|---|
| Service account | Dedicated `safeheal-recovery`; automount disabled |
| Namespaced Role | GET only the named payment Deployment; GET/PATCH only its scale subresource |
| Excluded rights | No secrets, pods, exec, workload creation/deletion, full Deployment patch, other services, other namespaces or RBAC administration |
| ValidatingAdmissionPolicy + Deny binding | For this exact service-account identity, only old replicas=0 to new replicas=1 in the designated namespace/Deployment; fail closed |
| HTTPS client | Loopback HTTPS, verified CA, fixed endpoints, no kubeconfig/auth plugins, redirects, proxy environment or shell; short-lived token |

RBAC alone cannot restrict the replica value. The operator must install **both**
RBAC and admission policy before issuing a token. The acceptance harness uses the
real token to prove forbidden calls return HTTP 403, including server dry-run
requests for replicas=2 from both zero and one. Forbidden requests never introduce
an actual unauthorized scale change, even if admission is misconfigured.

## Modes and operator boundary

The only accepted proposal schema is:

```json
{"schema_version":"day7-recovery-v1","request_id":"unique-request-1","incident_id":"incident-1","action":"restore_payment_replica"}
```

All extra keys are denied, including `mode`, `approved`, `replicas`, `command`,
`namespace`, confidence and `execution_allowed`. Identifiers are bounded and
validated. CLI proposal files are capped at 8192 bytes; duplicate JSON keys and
nonfinite constants are rejected. Audit retains request hashes, not raw prose.

The operator owns a private config directory, enrollment, mode, journal and
approval command. Neither config nor CLI operation is model-produced input.

```powershell
# Read-only default; never claims an action or mutates Kubernetes.
.\.venv\Scripts\python.exe scripts/recover.py run --config <private-config> --request <proposal-json>
# Human operator separately approves exactly this request for 180 seconds.
.\.venv\Scripts\python.exe scripts/recover.py approve --config <private-config> --request <proposal-json>
.\.venv\Scripts\python.exe scripts/recover.py run --config <private-config> --request <proposal-json> --mode approval
# Requires autonomous_enabled=true in trusted operator configuration.
.\.venv\Scripts\python.exe scripts/recover.py run --config <private-config> --request <proposal-json> --mode autonomous
.\.venv\Scripts\python.exe scripts/recover.py audit --config <private-config>
```

The trusted configuration contains `server`, `ca_file`, `token_file`, `journal`,
`enrollment: {deployment_uid, template_sha256}`, and `autonomous_enabled` (default
false). Enrollment is performed by the guarded acceptance harness below. No token
or admin kubeconfig belongs in the repository or model prompt. Long-running
operations must obtain a fresh short-lived token through the operator; the
controller has no token-issuance or refresh permission.

## Verification, audit and failure handling

Verification requires three consecutive fresh observations, one second apart:
the same UID/spec, exactly the expected post-patch generation, observedGeneration
at least that generation, desired/updated/ready/available/total replicas all one,
and unavailable replicas zero. Kubernetes readiness probes cover the application.
The operator harness additionally checks Service DNS, readiness, a synthetic order
and correlated service logs. This broader business check has developer credentials;
the recovery controller does not receive pod exec permission.

Reads/patches use five-second HTTP timeouts, a ten-second streaming response budget
(up to one read-timeout overshoot), 256 KiB response limits, no redirects or write retry.
Verification polls for at most 120 seconds plus a bounded in-flight read. A
transport error, changed UID/spec/generation, stale status or deadline failure
cannot return success. An acknowledged patch is distinct from verified recovery.

SQLite stores a durable write intent and single-flight claim **before** contacting
Kubernetes. `BEGIN IMMEDIATE` serializes claims, request IDs cannot execute twice,
and approvals are consumed atomically. Attempts have a 300-second cooldown and
three-per-hour budget across controller restarts using the same journal. Backward
wall-clock movement fails closed. A crash, uncertain patch outcome or failed
verification leaves `running`/`uncertain` state that blocks further writes. The
operator must investigate live state and audit before reconciling that record;
there is no automatic override, retry, rollback or stale-lock removal command.

Audit records policy decisions, fixed target/patch, approvals/denials, durable
intent, API acknowledgement, verification observations and failures. FULL
synchronous transactions, append-only triggers and a checked SHA-256 chain detect
ordinary corruption. An unwritable/corrupt audit prevents execution. This is a
local audit, not an external tamper-proof service: an OS administrator can rewrite
the database. The lab does not claim hostile-local-process isolation, production
hardening, general recovery effectiveness or a comparative MTTR improvement.

## Reproduce engineering acceptance

Use the existing pinned `.venv` and `requirements.lock`. The normal fresh-cluster
CI provisions/deploys the existing `safeheal-dev` lab, then runs both modes:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_recovery.py
.\.venv\Scripts\python.exe scripts/verify_recovery.py --execute --mode autonomous
.\.venv\Scripts\python.exe scripts/verify_recovery.py --execute --mode approval
```

The harness guards the dedicated local kind cluster and labelled namespace, owns
the shared recovery lock, starts from healthy replicas=1, installs only the reserved
project-owned security resources, uses a 10-minute service-account token, records
fixture intent before setting replicas=0, and invokes `recover.py` in a separate
process. Dry-run preserves zero; approval mode first rejects an unapproved request;
both modes verify recovery and reject replay. A failed trial is retained and cannot
be made successful by operator cleanup. Cleanup restores only this fixture if its
UID/spec still match, and removes the local token; server-side expiry still applies.

For the separate Windows acceptance lab, add `--lab safeheal-day7`. It uses
`.local/day7/kubeconfig`, context `kind-safeheal-day7`, node
`safeheal-day7-control-plane` and the same labelled `safeheal-dev` namespace.
Provision with pinned project-local kind and `infrastructure/kind.yaml`; this
leaves the historical `safeheal-dev` cluster/default kubeconfig intact. Day 7 adds
host-side controller code, so the existing verified application image can be loaded
into this fresh cluster without changing application source/dependencies.

Evidence is saved under `evidence/day7/d7-*/`: acceptance JSON, complete redacted
audit events/database, source hashes, real authorization results and separate
business verification. Original Day 5/6 evidence is preserved. See the Day 7
handoff for measured results and environment failures.

## Primary references

- https://kubernetes.io/docs/reference/access-authn-authz/rbac/
- https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/
- https://kubernetes.io/docs/reference/using-api/api-concepts/
- https://kubernetes.io/docs/concepts/security/service-accounts/


## Admission enforcement readiness before enrollment

Applying the policy and binding is not treated as evidence of active enforcement. The operator installer keeps the dedicated token private and withholds controller configuration until two consecutive server-side dry-run scale-to-two requests receive HTTP 403 with this exact policy's denial message. RBAC denial, HTTP 200, malformed/oversized responses, transport errors or absence of the policy do not establish readiness. The bounded gate fails closed after 30 seconds, and failed enrollment removes the locally held token. No real controller call or fault fixture begins before the gate and the unchanged eight strict forbidden-operation checks pass. The probes always use the fixed `dryRun=All` endpoint and do not persist replica changes. They are installer checks, not retries of a recovery write or model tools.

Fresh Linux CI40135721425 exposed the missing bootstrap condition: its scale-to-two server dry-run returned 200 before fault injection or controller invocation. The failed run and artifacts remain in evidence/final/ci-40135721425. The policy/value restriction was not weakened; operator enrollment now proves enforcement before releasing executable configuration. Cluster/OS administrators remain trusted, and this single-node lab check is not a distributed multi-API-server rollout guarantee.
