# SafeHeal AI

## Current Day 8 checkpoint — 2026-10-24

**DAY 8 COMPLETE: documented AI failure handling and automated robustness acceptance passed. Overall milestones: 8/10 (80%). Next: Day 9 controlled experiments. The full project is not complete.** Previous checkpoint counts below are historical.

Fixed paired development evaluation: **27/36 cases before -> 36/36 after; nine improved, zero regressions**. The runner exports exact Day 7 d10575a source and uses identical evaluator/cases for both arms, with source/hash verification. This is synthetic evidence and mocked-provider engineering acceptance, not real-model accuracy or MTTR improvement. Simulated calls for five duplicate notifications fell from five to one; stale notification calls fell from one to zero. No real-model call or cluster mutation occurred.

Added actual-sample freshness, all-record normalized-schema/hash/support validation before model use, detached provider inputs, malformed-platform exclusion and secret-free unexpected-adapter fallback. Added durable local notification intake with strict event/time schema, repeated-ID/evidence deduplication across restarts/concurrent consumers, claim-before-call, collision/capacity checks, audit and fail-closed interrupted/persistence handling. Existing diagnosis outputs remain non-executable; Day 7 recovery code/policy is unchanged.

Final Windows suite: **476 passed, 2 skipped, 0 failed**, one existing warning; **74 new robustness tests**, combined diagnosis-focused suite 123 passed. Existing symlink privilege and real-provider opt-in skips remain. Initial evaluator null-result bug and early reports are retained/described; both final paired arms use the corrected evaluator. Original Day 5/6/7 evidence is unchanged.

Canonical local branch: day8-ai-robustness, based on d10575a79781eda91f942aef56ee5a90fa5e1aba. This milestone is committed locally; inspect git log for the final SHA. No Day 8 push, merge or remote CI is claimed. CI wiring includes full baseline history, paired evaluation and retained reports. See PROJECT_STATUS_Day8_2026-10-24.md, docs/AI_ROBUSTNESS.md and evidence/day8/acceptance.json. Prior GitHub publication/account-feature blockers remain separate.


## Current Day 7 checkpoint — 2026-10-24

**DAY 7 COMPLETE: independent safe autonomous recovery acceptance passed. Overall milestones: 7/10 (70%). Next: Day 8 robustness. The full project remains incomplete.** Earlier checkpoint counts below are historical and superseded.

The immutable catalog permits only restoration of the enrolled safeheal-dev/payment Deployment from zero to one replica. A separate deterministic controller validates live UID/spec/generation and typed proposals; default dry-run, expiring single-use operator approval and explicitly opted-in autonomous modes are implemented. The model receives no shell, Kubernetes credential, approval/configuration authority or arbitrary execution interface. The dedicated token has named scale-only RBAC; fail-closed admission independently restricts replica values. Durable audit/claims, duplicate/single-flight protection, rate limits, no write retries and consecutive generation-aware readiness checks are enforced.

Final Windows suite: **402 passed, 2 skipped, 0 failed**, one existing warning; **65 new recovery tests**. Both actual Kubernetes acceptance trials passed in the separate safeheal-day7 lab: autonomous d7-autonomous-5ba20e9e0e and approval d7-approval-324fc2fcfe. Real-token forbidden calls returned 403; dry-run preserved zero, unapproved/replayed requests were denied, controller recovery and separate business checks passed, and no operator restoration was needed for either successful trial. All 27 retained audit events verified; accepted source manifests have zero mismatches. No real-model call or comparative MTTR claim.

Four unsuccessful engineering live attempts and the initial fixture-test failure are retained/described. Original Day 5/6 evidence is unchanged. The original safeheal-dev node could not start because Windows blocks its reserved API port; it was preserved. The fresh pinned safeheal-day7 cluster uses only .local/day7/kubeconfig and kind-safeheal-day7 context, with the existing verified application image. No global Docker reset/default-context change.

Local review branch: day7-safe-recovery, continuing canonical e8f2522. Changes are committed locally for this milestone; inspect actual git log for the final SHA. No Day 7 GitHub push, merge or remote CI was performed. The earlier publication blocker remains separate. See PROJECT_STATUS_Day7_2026-10-24.md, docs/SAFE_RECOVERY.md and evidence/day7/verification.json.


An isolated research testbed for evidence-grounded AI diagnosis and policy-controlled recovery of distributed services.

**Current scope:** Synthetic gateway/order/payment services, scoped Kubernetes deployment, Prometheus/Grafana observability, a deterministic incident detector, a reproducible three-scenario fault benchmark, and bounded evidence-grounded diagnosis with a configurable LLM provider. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for verified acceptance results. Policy-controlled remediation and matched approach comparisons remain future work. Real-model performance is unmeasured until explicit provider credentials and a call budget are configured.

## Run on Windows

From this folder with Python 3.12, Docker Desktop (Linux containers) and Docker Compose:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pytest -q
docker compose up --build -d --wait --wait-timeout 180
.\.venv\Scripts\python.exe scripts/smoke.py
docker compose ps
```

Linux/macOS: use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows Python path. Docker commands are the same.

API: http://127.0.0.1:18080/docs. Gateway liveness: `/healthz`; full dependency readiness: `/readyz`. Only gateway is published, on loopback only. Order/payment remain on the Compose network.

`POST /orders` accepts `{"item_id":"demo","quantity":2}`. The synthetic catalogue charges 1000 cents per item and creates a simulated payment receipt. No real payment, persistence or production authentication is provided. Requests create fresh IDs; POSTs are not retried because idempotency has not been implemented.

For logs: `docker compose logs --tail 100`. To stop only this project's containers without deleting them: `docker compose stop`.

## Run in Kubernetes (Day 2)

From the same project directory:

```powershell
.\.venv\Scripts\python.exe scripts/k8s.py install-kind
.\.venv\Scripts\python.exe scripts/k8s.py setup
.\.venv\Scripts\python.exe scripts/k8s.py deploy
.\.venv\Scripts\python.exe scripts/k8s.py verify
.\.venv\Scripts\python.exe scripts/k8s.py recovery
.\.venv\Scripts\python.exe scripts/k8s.py recovery --execute
```

The last command deliberately stops the isolated payment container and verifies
native recovery. Omit `--execute` for a dry run. It does not delete a Pod or perform
a manual restart. Evidence is saved in `evidence/day2/`. Use
`python scripts/k8s.py port-forward` to reach the Kubernetes gateway at
http://127.0.0.1:18081/docs; the Compose gateway stays on 18080.

See [Kubernetes architecture and runbook](docs/KUBERNETES.md) for prerequisites,
probe semantics, safeguards, troubleshooting, limitations, and interview concepts.
The scripts always use a project-local kubeconfig and the dedicated `safeheal-dev`
cluster/namespace. Applications have no Kubernetes API token or RoleBinding.

## Design and learning

- Three processes expose partial failure and inter-service HTTP, unlike one in-process application.
- Liveness answers whether a process responds; readiness checks its dependency chain. Dependency failures should not trigger liveness restart cascades.
- Bounded HTTP timeouts prevent indefinite waits. The gateway has a longer timeout than the order service.
- Integer cents avoid floating-point monetary arithmetic; all payments are synthetic.
- Structured request logs propagate a correlation ID; basic OpenTelemetry spans link the gateway, order and payment calls.
- Tests use HTTPX transport mocks for repeatable failure paths; a separate live smoke test exercises actual networking.
- A shared app factory keeps Day 1 small; separate modules can follow when service behaviour grows.

Interview question: Why can restarting a healthy gateway make a payment outage worse? Explain cascading failure, readiness versus liveness, and retry amplification.

## Research objective

Compare native Kubernetes recovery, deterministic rule-based recovery and evidence-grounded LLM assistance under matched failures. No claim of AI superiority is made until measured. This is a portfolio/research project, not an admission guarantee.

See ROADMAP.md, ARCHITECTURE.md, EXPERIMENTS.md and WORKLOG.md. The original user specification is retained in docs/MASTER_SPEC.txt.

Official implementation references: https://fastapi.tiangolo.com/tutorial/testing/ and https://docs.docker.com/compose/how-tos/startup-order/.


## Observability (Day 3)

Prometheus metrics, correlated JSON logs, basic OpenTelemetry distributed spans and an
8-panel provisioned Grafana dashboard are implemented. See [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)
for deployment, loopback access, the actual-traffic acceptance verifier and research limitations.
The optional developer fault check uses the existing guarded payment-container-stop procedure.

## Deterministic incident detector (Day 4)

Run `python scripts/detect.py serve` in the project environment while the local Prometheus forward is active. The read-only API is at `http://127.0.0.1:18082/docs`; SQLite evidence defaults to `.local/incidents.sqlite3`. No LLM or cluster-write access is used. Rules, thresholds, lifecycle, correlation, bounded collection, tests and current acceptance limits are in [docs/INCIDENT_DETECTION.md](docs/INCIDENT_DETECTION.md).

## Fault injection and benchmark harness (Day 5)

```powershell
.\.venv\Scripts\python.exe scripts/benchmark.py run
.\.venv\Scripts\python.exe scripts/benchmark.py run --execute --backend kubernetes --repeats 2 --baseline-seconds 30
```

The first command prints the seeded plan without touching the cluster. After deploying the current image, the second executes two repetitions each of a payment process crash, HTTP 500 responses and bounded added latency. Every trial persists independent ground-truth labels, real HTTP samples, raw Prometheus observations, rule incidents, native recovery evidence and timestamped results under `evidence/day5/`. Failed attempts remain available; the run stops before injecting another fault after an unsuccessful trial.

See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for prerequisites, exact workload and reset conditions, timestamp definitions, summaries and interpretation. The rule detector observes the experiments without executing recovery. Application fault expiration and native Kubernetes recovery have separate attribution.

Initial acceptance passed in [CI39774736343](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39774736343): six real Kubernetes trials, two per scenario, with stored raw evidence and verified final health. Read the [initial benchmark results](evidence/day5/README.md) for individual detection/recovery timings, recovery attribution, audit and limitations.


## Evidence-grounded diagnosis (Day 6)

```text
python scripts/diagnose.py --output .local/day6-replay.json benchmark evidence/day5/ci-39774736343/run-03a9072a24f8
python scripts/diagnose.py incident --database .local/incidents.sqlite3 --incident-id INCIDENT_ID
```

The default provider is disabled, so these commands need no model credentials. Enable an explicit OpenAI-compatible endpoint/model and call budget only when intended. The agent accepts only grounded hypotheses with matching evidence IDs, adds uncertainty and conservative confidence handling, and falls back on provider failure. It exposes no recovery actions. [Provider setup, schema, limits and live-test instructions](docs/AI_DIAGNOSIS.md); [retained acceptance evidence](evidence/day6/README.md). Mocked and fallback replay passed all six stored trials; real-model performance remains unmeasured.
