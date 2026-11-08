# Design decisions

Each entry records a decision that is visible in the code, the alternative it rejects, and the cost accepted. File references point at where the decision is enforced.

## 1. The model proposes; a separate controller decides

**Decision.** Diagnosis (`services/diagnosis/`) produces typed hypotheses over a fixed set of services and failure classes. Execution lives in an independent controller (`services/recovery/controller.py`) that never receives free text from the model, only a parsed request that must match the single catalogued action `restore_payment_replica`.

**Rejected.** Giving the language model a `kubectl` tool, or letting it emit arbitrary patches that a human skims.

**Cost.** The system can recover from exactly one fault shape. Adding an action means adding a catalog entry, an admission rule and a verification routine, not a prompt line.

## 2. The model holds no credentials

**Decision.** Only the controller has a Kubernetes token, and that token is short-lived with named-resource, scale-only permissions. API-server admission independently restricts the allowed transition (zero to one replica of the enrolled Deployment). The model has no shell, kubeconfig, approval authority or executor.

**Rejected.** A shared service account for "the agent".

**Cost.** Two layers (RBAC and admission) have to be kept consistent; `docs/SAFE_RECOVERY.md` and the kind manifests are the source of truth.

## 3. Dry-run by default, approvals that expire and bind

**Decision.** `Controller.execute` returns a dry-run result unless an operator approval exists. Approvals are single-use, expire after 180 seconds, and bind the request hash and the Deployment fingerprint (UID, generation, resourceVersion, template digest). Autonomous mode is a trusted operator opt-in.

**Rejected.** A "confirm" button that approves whatever the system does next.

**Cost.** An approval can become stale while the operator reads it; they then approve again against the new fingerprint.

## 4. Claim before write; uncertain writes block, never retry

**Decision.** `Journal` records a claim before any write, enforces single-flight, cooldown and hourly limits, and if a write ends in a running or uncertain state the controller refuses further execution until an operator intervenes.

**Rejected.** Retrying a failed scale call. Retries hide the exact moment the cluster and the journal disagreed.

**Cost.** A transient API error stops autonomous recovery for that journal until someone looks.

## 5. Verification is generation-aware and repeated

**Decision.** `Controller._verify` requires three consecutive readiness observations at the exact expected Deployment generation, with `observedGeneration` caught up, inside a bounded window. The operator harness separately confirms Service routing and real confirmed orders.

**Rejected.** Treating `replicas == readyReplicas` once as success.

**Cost.** Recovery reports take a few seconds longer; the controlled experiments count that time against the AI and rule arms.

## 6. Reads are resampled, writes are not

**Decision.** `_consistent_snapshot` re-reads the Deployment and its scale subresource up to three times until the resourceVersions agree, and fails if UID, spec or replica count differ.

**Rejected.** Reading once and hoping; or holding a long optimistic lock.

**Cost.** Three extra GETs on a contended API server.

## 7. Evidence is normalised and content-addressed before the model sees it

**Decision.** `services/diagnosis/evidence.py` and `tools.py` run fixed Prometheus queries, validate sample freshness, and give every record a content hash. The provider receives only normalised fields and must cite `evidence_refs` that exist. Log prose and labels are never passed as instructions.

**Rejected.** Pasting raw logs into the prompt.

**Cost.** New evidence types require a schema change, not just a bigger context window.

## 8. The provider contract is a strict JSON schema with fail-closed validation

**Decision.** `services/diagnosis/provider.py` rejects unknown fields, unsupported references, non-finite or out-of-range confidence, and unsafe proposals; timeouts are bounded to 1–30 s. Invalid output yields a documented abstention or low-confidence fallback, which is recorded as such and never counted as model success.

**Rejected.** Best-effort parsing of partially valid JSON.

**Cost.** Smaller local models fail validation more often; the CPU study reports this instead of smoothing it over.

## 9. Incident state is a durable SQLite state machine

**Decision.** `services/incidents/controller.py` persists incidents with states `pending → open → recovering → resolved` and a transitions table, so a detector restart does not lose or duplicate an incident.

**Rejected.** In-memory state in the detector process.

**Cost.** A single-writer SQLite file; adequate for the one-node lab, not a multi-replica detector.

## 10. The audit journal is hash-chained, and its limits are stated

**Decision.** Every journal row carries the hash of the previous row. The docstring in `Journal` states what this does (detects accidental corruption, reordering and deletion) and what it does not (stop a privileged filesystem attacker who rewrites the whole chain).

**Rejected.** Claiming tamper-proof logging.

## 11. The lab harness is trusted and never a model tool

**Decision.** Fault injection and cleanup use administrative credentials in `scripts/`, outside the model's reach. Each trial uses a fresh journal and token. Cleanup time is excluded from recovery metrics.

**Rejected.** Letting the agent "fix" the fault it was allowed to create.

## 12. Negative results are retained

**Decision.** Failed CI runs, interrupted CPU studies and unrun AI slots are kept under `evidence/` with manifests; `scripts/reproduce.py` verifies them byte-for-byte. Large raw bundles that nothing reads moved to a release asset (`evidence/ARCHIVE.md`) with checksums.

**Rejected.** Re-running until the chart looks good.

## 13. Workloads run hardened even in the lab

**Decision.** Non-root users, dropped capabilities, read-only root filesystems, resource bounds and `automountServiceAccountToken: false` in every Deployment; CI installs tools by pinned checksum or digest and scans the whole history for secrets on every push.

**Rejected.** "It's a demo" defaults.

**Cost.** CI is slower (about 35 minutes with the kind cluster) and depends on upstream release downloads, which is why the install steps carry fallbacks.

## Known limits (unchanged by these decisions)

Single node, single fault shape, synthetic workload, uncalibrated confidence, and an operator who is trusted by construction. See `ARCHITECTURE.md` and `docs/RESEARCH_REPORT.md`.
