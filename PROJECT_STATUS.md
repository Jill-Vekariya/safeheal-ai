# SafeHeal AI — portable project status

**Snapshot:** 2026-10-21, Asia/Kolkata (verification timestamps below are UTC). **Version:** 4.1. **Phase:** DAY 3 COMPLETE. Next: Day 4 deterministic detector.

## CI timeout correction after Day 3 completion

The later documentation/evidence commit `10d8415150860c62ba41168a4793a36dbfc3072d`
passed unit tests but its fresh-cluster recovery check failed in [run 39588507641](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39588507641).
`crictl` returned a runtime RPC `DeadlineExceeded` at its default **2-second** client deadline;
the log did not establish a verified recovery outcome. The observability step was consequently skipped.
This does not invalidate the earlier completed local observability acceptance or passing implementation CI.

Corrected the developer recovery script to use an explicit **30-second CRI client timeout**, within its
existing 45-second outer command bound. The separate container kill grace remains **0 seconds**;
there is still one scoped stop request, no automatic retry, the same ownership guards/lock and the same
required recovery assertions. `crictl` 1.36.0 local help verified the two distinct timeout meanings.
The corrected code passed **51 tests** and a new local dry-run/native recovery check, including the same
Pod/new container/increased restart count, stable upstream containers and three healthy order checks.
Evidence: `evidence/day3/tests-rpc-timeout-fix.txt`, `evidence/day2/recovery-20261021T110508-9fb946.json`.
The original failed CI record and run metadata are preserved under `evidence/day3/ci-failure-*`.

The complete CI suite is rerun by the correction commit. At the time this source document was written,
that new run was pending; inspect the latest GitHub Actions run/current HEAD before claiming the
latest commit is green. The portable handoff can append the final verified publication result.
Day 3 remains 9/9; full gates remain 3/10 (30%). No new research benchmark claim is made.

## Read this first in a new chat

The user wants this file to preserve continuity even if earlier chats are deleted. Read the entire file, inspect the actual project and WORKLOG.md, then continue from the next incomplete task. Do not start again or assume an unchecked item is complete. This file describes the project; it does not contain all its source code. Use the existing local folder or private GitHub repository to access current code. The earlier SafeHeal_AI_Day1.zip and Day 2 in-progress status are historical snapshots.

User objective: build SafeHeal AI, a trustworthy self-healing distributed-systems platform powered by an evidence-grounded LLM agent, as a rigorous portfolio/research project supporting a Georgia Tech on-campus MS CS/AI application for Fall 2028. User profile in supplied specification: BTech expected July 2028, CGPA 8.75/10, research ongoing. Never claim admission is guaranteed or experimental gains are proven without measurements.

## Progress at this snapshot

- Day 1 checklist: **13 of 13 tasks complete (100%)**.
- Day 2 checklist: **9 of 9 tasks complete (100%)**. All core services run in kind, and a deliberately terminated payment container recovered through native Kubernetes mechanisms.
- Day 3 checklist: **9 of 9 tasks complete (100%)**; live traffic, monitoring, logs and basic distributed tracing verified.
- Full daily acceptance gates: **3 of 10 complete (30%)**. This is a strict gate count, not an estimate of effort already spent. **The whole project is NOT complete.**
- Kubernetes deployment, service discovery, probes and a native container-restart acceptance check are verified. Observability is now verified. AI integration, the rule controller, safe recovery executor and controlled research benchmarks remain unfinished.
- Verified Day 3 implementation commit: `9b5fec7d517dd46b68eb65a9442335fcb4c77560` on `main`; source checkout was clean at the start of live acceptance. Both CI jobs passed [run 39587430249](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39587430249). Final evidence/status documentation is committed subsequently; verify the latest tip with `git log -1` and `git ls-remote origin refs/heads/main`.
- Historical Day 2 implementation commit: `43abb2318280ff455ad9ab56e9359af9f5531eed` on `main`, matched to the remote before collecting local evidence. This status and evidence are maintained in a subsequent documentation commit; inspect `git log -1` and `git ls-remote origin refs/heads/main` for the latest documentation SHA.
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
| Container state | All five Kubernetes Deployments Ready/Available after Day 3; payment restart count 2 and gateway/order 0 after the Day 3 fault and subsequent timeout-fix recovery check. Compose is an older Day 2 stack and was not changed/reverified in Day 3. Recheck next session. |
| Monitoring | Prometheus 3.15.0; Grafana 13.2.4; digest-pinned manifests in `infrastructure/observability` |
| Python telemetry | prometheus-client 0.26.0; OpenTelemetry SDK/API 1.45.1; exact lock retained |
| Grafana | `http://127.0.0.1:13000/d/safeheal-operations`, on development PC while its forward is running; HTTP health 200 verified |
| Prometheus | `http://127.0.0.1:19090`, on development PC while its forward is running; readiness HTTP 200 verified |
| Trace storage | Basic W3C/OpenTelemetry SERVER/CLIENT spans exported to JSON container logs; no trace UI/backend |
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

## Day 3 checklist

1. [x] Integrate Prometheus metrics into gateway, order and payment using separate per-app registries.
2. [x] Add request counts, separate 4xx/5xx outcomes, error-rate queries and latency histograms.
3. [x] Add structured JSON request/error logs with UTC timestamps and correlation identifiers.
4. [x] Add and verify basic distributed tracing: W3C propagation, SERVER/CLIENT spans and parentage.
5. [x] Configure scoped Prometheus and Grafana with immutable image digests and local-only forwarding.
6. [x] Provision eight useful operational dashboard panels and a working Prometheus datasource.
7. [x] Verify telemetry using actual traffic and an authorized scoped native payment-container interruption.
8. [x] Document the pipeline, commands, measurement semantics, resource limits and limitations.
9. [x] Commit/push implementation to the private repository and verify passing unit/live-kind CI; retain evidence.

## Day 3 verification and evidence

- Unit/safety/trace suite: **51 passed**, one pre-existing Starlette/HTTPX deprecation warning, 25.71 s; `evidence/day3/tests.txt`.
- Implementation: `9b5fec7d517dd46b68eb65a9442335fcb4c77560`. Local HEAD matched private remote main. The live acceptance record reports an initially **clean working tree** and records additional observability file hashes.
- Raw acceptance: `evidence/day3/observability-20261021T105300-day3-c56cd5922e10.json`, **PASS**.
- Acceptance ran from `2026-10-21T10:53:00.097837+00:00` to `2026-10-21T10:53:57.942991+00:00` (UTC).
- Gateway diagnostic workload: **108 actual HTTP requests** over **45.352 s**: **80 HTTP 201**, **21 HTTP 422**, **7 HTTP 503**. No transport errors were recorded. Successful orders were checked for confirmed status and 2000 cents. These are workload observations, not production availability or research benchmarks.
- Diagnostic traffic used the validated gateway Pod IP so readiness withdrawal did not hide application errors. Baseline/final checks separately passed through Service DNS, health/readiness and end-to-end order flow.
- Prometheus: **3/3 scrape targets UP**. All nine expressions behind the eight Grafana panels returned data. Server-error counters showed **7** for gateway and **7** for order: the same seven failed gateway requests propagated through the dependency chain, not fourteen independent incidents. Histograms and request/status counters populated from actual calls.
- Grafana **13.2.4**: health/database passed; eight-panel provisioned dashboard retrieved; Grafana's actual datasource proxy returned all three services. Loopback forwarded Grafana and Prometheus health endpoints both returned HTTP 200.
- Structured logs correlate all three services on successful request `day3-c56cd5922e10-0`. Failure request IDs/trace IDs also match between gateway and order; e.g. `day3-c56cd5922e10-28`, HTTP 503, trace `2d3766018fe3320286b2d83f69912235`.
- Basic distributed tracing: **five distinct linked spans** for request `day3-c56cd5922e10-0`, common trace ID `343fa893514c31296812ada4604de8d9`. Verified chain: gateway SERVER -> gateway CLIENT -> order SERVER -> order CLIENT -> payment SERVER. Previous payment-container logs preserved early spans across the deliberate restart.
- Native fault trial `day2-native-478183e561ad`: **PASS**, `evidence/day2/recovery-20261021T105312-78fdbe.json`. Guarded payment-container stop; kubelet restarted it in the same Pod, increased restart count and changed container ID; upstream containers remained stable; three subsequent healthy order checks passed. No manual restart or Pod deletion was used.
- CI [run 39587430249](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39587430249): **completed / success**, both `test` and `kubernetes` jobs. The fresh Linux kind job reproduced service checks, native recovery and non-fault observability acceptance. Metadata: `evidence/day3/implementation-ci.json`.
- Packaging/startup issues resolved: partial multi-platform archive could not be imported into kind; normal kubelet digest pull used instead. Prometheus rejected an explicit false-valued flag; omitted it (admin API remains disabled by default). Grafana download suffered an unexpected EOF and startup/provisioning took time; pinned its Linux amd64 manifest, loaded the cached image, and verified the final rollout. One earlier rollout wait exceeded its deadline before the corrected rollout succeeded. These were setup failures, not failed research trials.
- Day 3 blockers: **none**. All five Deployments finished Ready/Available. Local viewing forwards were left running; they must be restarted if the device/session stops.

### Day 3 implementation choices and limits

Application metrics exclude `/healthz`, `/readyz` and `/metrics`; otherwise probe traffic could dilute the error denominator. Labels use service, normalized method, route template and status class. Request IDs, trace IDs, raw paths, query strings and payloads do not become labels. Duration histograms use seconds and cover the existing two/three-second dependency timeouts. Quantiles are bucket estimates. Undefined zero-traffic percentages are not zero-error claims.

Request logs carry UTC timestamp, validated request ID, route/method, status, elapsed time, exception type and trace/span IDs. W3C context propagates through real HTTP boundaries. The basic OpenTelemetry exporter writes spans as JSON logs; **no Tempo/Jaeger/collector, persistent trace store or Grafana tracing UI** was added. Synchronous span logging overhead has not been benchmarked.

Prometheus/Grafana run non-root in the existing restricted namespace, with no ServiceAccount token and no new API permissions. Static Service scrape targets support the current **one replica per service** only. Monitoring uses capped resources, ephemeral storage and a 24-hour/256 MB Prometheus block-retention setting; WAL/head overhead is additional. Recreated monitoring Pods lose live data, while Git configuration and committed JSON evidence remain. No public ingress was created. Grafana has anonymous Viewer access only inside this local lab. See `docs/OBSERVABILITY.md` for deployment and interpretation.

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

- Day 2 completion/evidence commit: [`a4ce10a5e5eb201e5a11cfefe971eb5d7419785e`](https://github.com/Jill-Vekariya/safeheal-ai/commit/a4ce10a5e5eb201e5a11cfefe971eb5d7419785e). Push succeeded; local HEAD matched remote `main`, and the working tree was clean.
- Final commit CI: [run 39509354163](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39509354163) **completed / success** for both `test` and `kubernetes` jobs. The latter created a fresh cluster and verified deployment, discovery, HTTP communication and native container recovery.
- This portable copy adds the final publication results to the canonical `PROJECT_STATUS.md` committed with the evidence. All three local services were rechecked after the push and remained 1/1 Ready.

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

All items have a synthetic fixed price of 1000 cents. Order/payment records are not persisted. POST calls are not retried because idempotency is not implemented. Prometheus request/status/duration metrics, correlated JSON logs, an eight-panel Grafana dashboard and basic OpenTelemetry distributed spans now exist; see the Day 3 section and runbook. Gateway HTTP timeout is 3 seconds; order timeout is 2 seconds. Liveness does not call dependencies; readiness checks the dependency chain.

Kubernetes uses one replica per service, internal port 8000, ClusterIP DNS routing, a restricted Pod Security namespace and a token-free ServiceAccount with no RoleBinding. Each container requests 100m CPU/128Mi memory, limits 500m/256Mi, runs as UID 10001 with read-only root, dropped capabilities and RuntimeDefault seccomp. `/healthz` supplies startup/liveness; `/readyz` supplies readiness. See `docs/KUBERNETES.md` for the diagram, timings and commands.

The single-node lab has no high availability, public ingress, enforced NetworkPolicy or production recovery controller. The Day 3 monitoring stack is a local lab configuration, not production observability. The developer fault script uses privileged Docker access to the kind node and must not become an unrestricted LLM tool. Full least-privilege recovery policies remain Day 7 work.

## Exact next action

**Continue with Day 4: deterministic detector. Days 1–3 are complete.**

1. Reconnect to Jill-Vekariya10; read current PROJECT_STATUS.md, WORKLOG.md, ROADMAP.md and actual git state. Do not reset or overwrite newer work. Check the latest local/remote SHA and private visibility.
2. Check Docker and the existing `safeheal-dev` cluster; verify all five Deployments. Restart local Grafana/Prometheus forwards when needed. Reuse the cluster.
3. Define deterministic thresholds/windows, minimum sample counts and stale/missing-telemetry handling using the real Prometheus schema. Keep insufficient evidence distinct from healthy state.
4. Implement an incident lifecycle with timestamps, deduplication and SQLite persistence. Add bounded read-only evidence collection and rule-based diagnosis with explicit evidence references.
5. Test normal, faulty, transient, stale/missing and duplicate conditions. Verify against scoped real-service scenarios. Do not yet give a detector arbitrary shell or cluster-write access.
6. Update status/worklog/experiment register; retain failed checks and raw evidence; commit/push authorized tested changes. Mark Day 4 complete only when its acceptance gate passes.

The user explicitly authorized Day 2 implementation, the local Kubernetes restart demonstration, commits/pushes and continued work through Desktop Commander. The user also explicitly authorized the full Day 3 observability checklist, actual service verification and commits. These completed actions need no repeated permission. Keep the repository private. Public publishing, destructive changes outside the scoped test and significant paid calls still require the appropriate authorization.

Do not ask for passwords or tokens in chat. If the computer is offline, report it and use the authorized repository for inspection; never claim remote execution that did not occur.

## Remaining 10-day roadmap / acceptance gates

| Gate | Status | Required outcome |
|---|---|---|
| Day 1: foundation | COMPLETE | Tested running microservices AND working private GitHub baseline |
| Day 2: Kubernetes | COMPLETE | kind cluster, deployments/services/probes, service discovery and recorded native container recovery |
| Day 3: observability | COMPLETE | Real Prometheus error/latency/request metrics, JSON logs, Grafana; tracing if feasible |
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

Final deliverables still required: working controller, rule baseline, AI diagnosis, safety/executor/verification, broader fault harness, controlled-trial datasets, analysis charts, research report, demo, achievement-based resume/SOP text and 15–20 interview questions. Kubernetes manifests, scoped native-recovery demonstrations and verified observability now exist; Days 1–3 form the foundation for the remaining deliverables.

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
