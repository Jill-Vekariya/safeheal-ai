# SafeHeal AI — portable project status

**Snapshot:** 2026-10-21, Asia/Kolkata (verification timestamps below are UTC). **Version:** 4 (in progress). **Phase:** DAY 3 IN PROGRESS. Live observability acceptance pending.

## Read this first in a new chat

The user wants this file to preserve continuity even if earlier chats are deleted. Read the entire file, inspect the actual project and WORKLOG.md, then continue from the next incomplete task. Do not start again or assume an unchecked item is complete. This file describes the project; it does not contain all its source code. Use the existing local folder or private GitHub repository to access current code. The earlier SafeHeal_AI_Day1.zip and Day 2 in-progress status are historical snapshots.

User objective: build SafeHeal AI, a trustworthy self-healing distributed-systems platform powered by an evidence-grounded LLM agent, as a rigorous portfolio/research project supporting a Georgia Tech on-campus MS CS/AI application for Fall 2028. User profile in supplied specification: BTech expected July 2028, CGPA 8.75/10, research ongoing. Never claim admission is guaranteed or experimental gains are proven without measurements.

## Day 3 implementation checkpoint

User authorized the complete Day 3 observability checklist and commits on 2026-10-21.
The computer was initially offline, then reconnected. The canonical checkout was clean at
`a4ce10a5e5eb201e5a11cfefe971eb5d7419785e`, matched private remote main; all three original Pods were healthy.
Implemented bounded Prometheus counters/histograms, JSON request logs, OpenTelemetry W3C
server/client tracing with JSON span export, digest-pinned Prometheus/Grafana manifests,
eight provisioned operational panels, acceptance scripts, tests and the observability runbook.
Tests: 51 passed with one existing dependency deprecation warning. The first monitoring
image-import attempt failed because Docker's partially pulled multi-platform archive lacked
other-platform content. Deployment now lets kubelet resolve the pinned image directly.
Live monitoring deployment/traffic acceptance and final commit/CI remain pending. Gate 3 is not complete.

## Progress at this snapshot

- Day 1 checklist: **13 of 13 tasks complete (100%)**.
- Day 2 checklist: **9 of 9 tasks complete (100%)**. All core services run in kind, and a deliberately terminated payment container recovered through native Kubernetes mechanisms.
- Full daily acceptance gates: **2 of 10 complete (20%)**. This is a strict gate count, not an estimate of effort already spent. **The whole project is NOT complete.**
- Kubernetes deployment, service discovery, probes and a native container-restart acceptance check are verified. AI integration, the rule controller, observability stack and controlled research benchmarks remain unfinished.
- Verified Day 2 implementation commit: `43abb2318280ff455ad9ab56e9359af9f5531eed` on `main`, matched to the remote before collecting local evidence. This status and evidence are maintained in a subsequent documentation commit; inspect `git log -1` and `git ls-remote origin refs/heads/main` for the latest documentation SHA.
- GitHub URL: https://github.com/Jill-Vekariya/safeheal-ai — **private**, verified through GitHub CLI. Origin: `https://github.com/Jill-Vekariya/safeheal-ai.git`.

## Current environment and artifacts

| Item | Verified value |
|---|---|
| Development computer | Jill-Vekariya10, Windows, online during this session |
| Desktop Commander device ID | 8025e560-e3a9-4f10-9084-a256f42ffb82; recheck connection next session |
| Canonical working directory | `C:\Users\jillv\Projects\safeheal-ai` |
| Python | Python 3.12 used in project-local `.venv`; Python 3.13 also installed |
| Git | 2.55.0.windows.5 |
| Docker engine / Compose | 29.8.2 / v5.5.1 |
| Hardware | 12 logical processors, approximately 16 GiB RAM |
| GitHub CLI | Authenticated account `Jill-Vekariya` |
| Git author | Repo-local `Jill-Vekariya`, `195921415+Jill-Vekariya@users.noreply.github.com`, based on authenticated GitHub login/ID |
| kind / kubectl / Kubernetes | Project-local `.tools/kind.exe` v0.33.0 / client v1.36.1 / server v1.36.4 |
| Cluster / context / namespace | `safeheal-dev` / `kind-safeheal-dev` / `safeheal-dev` |
| Node / runtime | `safeheal-dev-control-plane`, single Ready node; containerd 2.3.4 |
| Kubernetes configuration | Explicit project `.local/kubeconfig`; loopback API; private ownership labels `safeheal.ai/project=safeheal-ai` and `safeheal.ai/environment=local-test` |
| Local API docs | Compose: `http://127.0.0.1:18080/docs`; Kubernetes: `http://127.0.0.1:18081/docs` only while `python scripts/k8s.py port-forward` runs |
| Container state | Kubernetes gateway/order/payment all 1/1 Ready; payment restart count 1, upstream counts 0 after the recorded test. Compose remains healthy. Recheck later. |
| Source backup | Current source/status in the private GitHub repository; earlier `SafeHeal_AI_Day1.zip` is a pre-publication snapshot with older status |

## Day 1 checklist

1. [x] Inspect development computer, software, hardware and GitHub login.
2. [x] Identify/create a new project workspace without overwriting an existing project.
3. [x] Create Python package/repository structure and project-local virtual environment.
4. [x] Implement independently deployed FastAPI gateway, order and simulated payment services.
5. [x] Implement process liveness and dependency-aware readiness endpoints.
6. [x] Add input validation, bounded HTTP calls, correlation IDs and response checks.
7. [x] Create Dockerfile, Compose stack and exact installed dependency snapshot.
8. [x] Run automated tests: 22 passed, 0 failed, 1 dependency deprecation warning.
9. [x] Build/start containers and verify live health/readiness and end-to-end order flow.
10. [x] Create README, architecture, 10-day roadmap, experiment protocol, worklog and portable status.
11. [x] Initialize local Git branch `main`, add CI and verify successful GitHub Actions execution.
12. [x] Configure repository-local GitHub identity and create/verify initial source commit.
13. [x] User instructed completion after the authorization request; create private GitHub repository, push baseline and verify visibility, remote SHA and passing CI.

## Day 2 checklist

1. [x] Install pinned, checksum-verified kind locally and create a dedicated local cluster.
2. [x] Create namespace, ServiceAccount, Deployments, ClusterIP Services and Kustomize manifests.
3. [x] Build/load the application image and deploy all three core services successfully.
4. [x] Configure startup, readiness and liveness probes for each service.
5. [x] Verify short/FQDN service discovery, health/readiness and gateway -> order -> payment HTTP communication.
6. [x] Deliberately terminate payment and verify a native kubelet container restart and restored orders.
7. [x] Document Kubernetes architecture, probe choices, recovery attribution and limitations.
8. [x] Add scoped install/setup/deploy/verify/recovery/status/port-forward scripts and safety tests.
9. [x] Commit and push tested implementation to private GitHub; unit and live kind CI both pass.

## Day 2 verification and evidence

- Unit/safety suite: **40 passed, 1 existing Starlette/HTTPX deprecation warning**. Raw final test output: `evidence/day2/tests.txt`. The 18 added safety tests cover target/context/ownership checks, dry-run behaviour and concurrent-fault locking.
- All three Deployments report 1/1 Ready/Available, using image tag `safeheal-ai:sha256-34edfc9c74355d5b`.
- Service IPs: gateway `10.96.56.205`, order `10.96.23.37`, payment `10.96.88.201`. Both short names and FQDNs resolve to the actual ClusterIPs. These addresses are observations, not configuration values to hard-code.
- `scripts/k8s.py verify`: PASS at 2026-10-20 22:31:02 UTC. Health/readiness passed for every service; an end-to-end order returned HTTP 201, quantity 2, amount 2000 cents, status `confirmed`. Request ID `day2-676251f8cc50` appears in successful POST logs from all three services.
- Discovery/HTTP/raw cluster evidence: `evidence/day2/verification-20261020T223105-a896d6.json`.
- `scripts/k8s.py recovery` completed a dry run, followed by the authorized `recovery --execute`: **PASS**. Trial `day2-native-d15965119813`; raw record `evidence/day2/recovery-20261020T223144-4257ee.json`.
- Fault requested at `2026-10-20T22:31:44.979649+00:00`; previous payment container terminated with exit code **137**, reason `Error`, at 22:31:45 UTC.
- Payment Pod `payment-844c7c8bd-n6mmh` retained UID `7ee64010-5f44-46a0-90ff-36a8ea2ed4b8`; restart count **0 -> 1**. The CRI container ID changed from `02834e3d09ae...` to `5d9cee0a5340...`. The kubelet restarted it under `restartPolicy: Always`; the script did not delete a Pod or manually restart a service.
- Payment first observed Ready after **6.391 s**. Gateway/order retained their UIDs and restart counts. Three subsequent health/readiness/DNS/order checks succeeded, with two-second gaps; each order returned HTTP 201 and 2000 cents.
- Final checks finished at `2026-10-20T22:31:58.821720+00:00`, **13.844 s** after the stop request. This host-observed interval includes polling, CLI/API overhead and verification checks; it is **not service downtime or benchmark MTTR**.
- The JSON records retain source commit, file hashes, environment versions, Pod identities and observations. Only the first verification began with a clean working tree; the recovery record also lists the newly generated, untracked evidence directory.
- This establishes native recovery for one container-stop scenario. It does not establish liveness-threshold behaviour, Pod replacement, node failure tolerance, zero downtime or an AI benefit.

## Day 1 historical verification

- `.\.venv\Scripts\python.exe -m pytest -q`: **22 passed, 1 warning in 11.77 seconds**.
- Warning: Starlette reports that its HTTPX TestClient path is deprecated and recommends httpx2. Tests pass; migration has not been performed.
- `docker compose config --quiet`: exit 0.
- Initial image build and startup reached healthy state, but the PowerShell stderr-to-Tee wrapper reported exit 1. A direct follow-up `docker compose up -d --wait --wait-timeout 60` returned **compose_up_exit=0**, confirming startup.
- `scripts/smoke.py`: **SMOKE PASS**, exit 0; gateway `/healthz` and `/readyz` both HTTP 200; `POST /orders` HTTP 201, quantity 2, amount 2000 cents, status `confirmed`, correlation ID `day1-smoke`.
- Actual smoke order ID: `a764b8a5-6e27-4c4f-9cd6-c54829a61072`.
- `docker compose ps`: all three service containers healthy. Only gateway exposed, bound to `127.0.0.1:18080`.
- Tests cover liveness independence, validation, simulated payments, dependency errors/timeouts, malformed responses, receipt mismatch, readiness and correlation propagation. These are engineering checks, not research benchmark trials.

## GitHub verification

- Authenticated account: Jill-Vekariya, account ID 195921415.
- Repository visibility reverified **PRIVATE** on 2026-10-21 local time.
- Day 1 baseline `9b75e000492162de9528bb18a5ffbc7219875262` passed run 39399733684.
- Day 2 implementation `43abb2318280ff455ad9ab56e9359af9f5531eed` passed GitHub Actions run **39470648959**: unit tests and actual Linux kind setup, deployment, DNS/HTTP verification and native recovery all succeeded.
- Run URL: https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39470648959
- CI metadata: `evidence/day2/implementation-ci.json`. CI uploads its raw Kubernetes JSON as a seven-day artifact; committed local JSON preserves the Windows acceptance evidence independently.
- Earlier Day 2 implementation `cf769a7` failed kind bootstrap in run 39469746459. The kubelet rejected a reserved `app.kubernetes.io/part-of` node-registration label. Replaced it with private `safeheal.ai/*` node labels; corrected local setup and CI passed. Only our newly created, empty failed kind node was recreated; existing Docker projects were left intact.
- A tool credit interruption and an offline device delayed local verification. Work resumed after the user reported the device online; no offline execution was claimed.
- Day 2 blockers: **none**. Existing non-failing Starlette deprecation warning remains a maintenance item.

## Implemented design

Gateway -> order -> payment over HTTP, with one shared application factory selected by SERVICE_ROLE. Each container runs as non-root with dropped capabilities and a read-only root filesystem. Payment creates synthetic receipts only. No external money movement or API credentials are used.

All items have a synthetic fixed price of 1000 cents. Order/payment records are not persisted. POST calls are not retried because idempotency is not implemented. Structured request logging exists; Prometheus dashboards and OpenTelemetry tracing do not yet exist. Gateway HTTP timeout is 3 seconds; order timeout is 2 seconds. Liveness does not call dependencies; readiness checks the dependency chain.

Kubernetes uses one replica per service, internal port 8000, ClusterIP DNS routing, a restricted Pod Security namespace and a token-free ServiceAccount with no RoleBinding. Each container requests 100m CPU/128Mi memory, limits 500m/256Mi, runs as UID 10001 with read-only root, dropped capabilities and RuntimeDefault seccomp. `/healthz` supplies startup/liveness; `/readyz` supplies readiness. See `docs/KUBERNETES.md` for the diagram, timings and commands.

The single-node lab has no high availability, public ingress, enforced NetworkPolicy, metrics stack or production recovery controller. The developer fault script uses privileged Docker access to the kind node and must not become an unrestricted LLM tool. Full least-privilege recovery policies remain Day 7 work.

## Exact next action

**Continue with Day 3: observability. Days 1 and 2 are complete.**

1. Reconnect to the development computer; inspect PROJECT_STATUS.md, WORKLOG.md, `git status`, current HEAD and remote before making changes. Do not reset or overwrite newer work.
2. Check Docker and `python scripts/k8s.py status`; reuse the existing dedicated cluster. Do not recreate it merely to resume work.
3. Add real request/error/latency metrics to the services with bounded label cardinality and an appropriate histogram.
4. Deploy a scoped Prometheus/Grafana setup with reproducible configuration and local-only access; account for the host's resource limits.
5. Generate real synthetic traffic, demonstrate populated dashboards and correlate failures with existing request IDs/logs. Add OpenTelemetry tracing if feasible and verify its actual propagation if included.
6. Run meaningful tests and save real observability evidence. Do not mark Day 3 complete until its acceptance gate is demonstrated.
7. Update the status/worklog/experiment register, commit/push the authorized changes and provide the next portable status snapshot.

The user explicitly authorized Day 2 implementation, the local Kubernetes restart demonstration, commits/pushes and continued work through Desktop Commander. These completed actions need no repeated permission. Keep the repository private. Public publishing, destructive changes outside the scoped test and significant paid calls still require the appropriate authorization.

Do not ask for passwords or tokens in chat. If the computer is offline, report it and use the authorized repository for inspection; never claim remote execution that did not occur.

## Remaining 10-day roadmap / acceptance gates

| Gate | Status | Required outcome |
|---|---|---|
| Day 1: foundation | COMPLETE | Tested running microservices AND working private GitHub baseline |
| Day 2: Kubernetes | COMPLETE | kind cluster, deployments/services/probes, service discovery and recorded native container recovery |
| Day 3: observability | IN PROGRESS | Real Prometheus error/latency/request metrics, JSON logs, Grafana; tracing if feasible |
| Day 4: deterministic detector | Not started | Rules, incident lifecycle, timestamps/evidence, SQLite and rule diagnosis with tests |
| Day 5: fault benchmark | Not started | At least three repeatable scoped faults, ground truth, native/rule trials and raw records |
| Day 6: AI diagnosis | Not started | Provider integration, bounded read-only tools, structured hypotheses, evidence references, uncertainty and fallback |
| Day 7: safe recovery | Not started | Allowlisted operations, independent policies, approval/dry-run, RBAC, audit and verified recovery |
| Day 8: robustness | Not started | Stale/misleading/missing evidence, provider outage, duplicates and safety/failure tests |
| Day 9: experiments | Not started | Comparable A/B/C trials, raw data, uncertainty estimates, charts, negative results and limitations |
| Day 10: finalization | Not started | Reproducibility, end-to-end checks, CI, report, demo, resume/SOP narrative and interview preparation |

Use ROADMAP.md for the execution plan. Work days are milestones, not automatic calendar-based completion.

## Research protocol and final scope

Research question: can evidence-grounded LLM assistance improve incident diagnosis and safe recovery compared with deterministic approaches?

Compare A: native Kubernetes recovery, B: rule-based incident controller, C: AI-assisted diagnosis with the same independent safety gate. Plan process crash, HTTP 500 spike, latency, resource saturation, faulty deployment/configuration; cascading dependency outage is optional. Aim for at least five repeats per scenario/approach if resources allow. Record detection latency, diagnostic accuracy, recovery time/success, false positives/negatives, unsafe proposals/executions, token usage/cost and overhead. Separate diagnostic success from service recovery; retain failed trials. Never fabricate findings.

Final deliverables still required: working controller, observability, rule baseline, AI diagnosis, safety/executor/verification, broader fault harness, controlled-trial datasets, analysis charts, research report, demo, achievement-based resume/SOP text and 15–20 interview questions. Kubernetes manifests and one scoped native-recovery demonstration now exist; Days 1–2 form the foundation for the remaining deliverables.

## Safety and continuity requirements

- Fault injection and recovery only in the designated isolated local test cluster/namespace.
- No arbitrary LLM-generated shell commands, unrestricted cluster permissions or bypassing policy.
- Default dry-run initially; approval for higher-risk actions; typed allowlist, rate limiting, duplicate/concurrency protection, timeouts, audit and health verification.
- No destructive repository/resource operations, public publishing or significant paid calls without required authorization.
- Keep repository private by default. Never commit secrets.
- Explain important design choices, failure modes and verification while implementing; no invented test/deployment output.
- At every session end update PROJECT_STATUS.md, WORKLOG.md and EXPERIMENTS.md, including exact completed/remaining work, blockers, tests, latest verified commit and next step.

## What “whole project complete” means

Mark `PROJECT COMPLETE` only after all 10 acceptance gates pass and the final deliverables are verified. Full-gate completion percentage = completed gates / 10 * 100. Report partially completed task checklists separately. A plan, a status file, mocked-model success or an unverified claim is not completion. When scope changes, record the approved change and its limitations explicitly.
