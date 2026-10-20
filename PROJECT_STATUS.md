# SafeHeal AI — portable project status

**Snapshot:** 2026-10-20, Asia/Kolkata. **Version:** 1. **Phase:** Day 1, working local baseline; GitHub foundation pending.

## Read this first in a new chat

The user wants this file to preserve continuity even if earlier chats are deleted. Read the entire file, inspect the actual project and WORKLOG.md, then continue from the next incomplete task. Do not start again or assume an unchecked item is complete. This file describes the project; it does not contain all its source code. Use the existing local folder, the accompanying SafeHeal_AI_Day1.zip, or an authorized GitHub repository to access code.

User objective: build SafeHeal AI, a trustworthy self-healing distributed-systems platform powered by an evidence-grounded LLM agent, as a rigorous portfolio/research project supporting a Georgia Tech on-campus MS CS/AI application for Fall 2028. User profile in supplied specification: BTech expected July 2028, CGPA 8.75/10, research ongoing. Never claim admission is guaranteed or experimental gains are proven without measurements.

## Progress at this snapshot

- Day 1 checklist: **11 of 13 tasks complete (84.6%)**.
- Full daily acceptance gates: **0 of 10 complete (0%)** because Day 1 also requires a verified pushed GitHub baseline. This is a strict gate count, not an estimate of effort already spent.
- Day 1 application runs successfully. **The whole project is NOT complete.**
- No AI integration, Kubernetes deployment, automatic recovery or research experiments have been completed.
- Latest verified Git commit: **none**. Git was initialized on branch `main`; no commit or remote exists yet.
- GitHub URL: **not created**. Proposed private repository: `Jill-Vekariya/safeheal-ai`. Read-only lookup found no accessible repository under that name.

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
| Git author | `git config --get user.name` and `user.email` returned no configured values |
| kind | Not found on PATH; Day 2 prerequisite |
| Local API docs | `http://127.0.0.1:18080/docs` on the development computer |
| Container state | gateway, order and payment running and healthy at verification time; recheck later |
| Archive | `SafeHeal_AI_Day1.zip`; includes source, documentation, lockfile, evidence and this status |

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
11. [x] Initialize local Git branch `main` and add a CI workflow file (workflow not executed on GitHub).
12. [ ] Confirm Git author identity and create/verify the initial source commit.
13. [ ] Obtain explicit authorization to create private GitHub repository, push baseline, verify remote commit and CI.

## Verified tests and actual results

- `.\.venv\Scripts\python.exe -m pytest -q`: **22 passed, 1 warning in 11.77 seconds**.
- Warning: Starlette reports that its HTTPX TestClient path is deprecated and recommends httpx2. Tests pass; migration has not been performed.
- `docker compose config --quiet`: exit 0.
- Initial image build and startup reached healthy state, but the PowerShell stderr-to-Tee wrapper reported exit 1. A direct follow-up `docker compose up -d --wait --wait-timeout 60` returned **compose_up_exit=0**, confirming startup.
- `scripts/smoke.py`: **SMOKE PASS**, exit 0; gateway `/healthz` and `/readyz` both HTTP 200; `POST /orders` HTTP 201, quantity 2, amount 2000 cents, status `confirmed`, correlation ID `day1-smoke`.
- Actual smoke order ID: `a764b8a5-6e27-4c4f-9cd6-c54829a61072`.
- `docker compose ps`: all three service containers healthy. Only gateway exposed, bound to `127.0.0.1:18080`.
- Tests cover liveness independence, validation, simulated payments, dependency errors/timeouts, malformed responses, receipt mismatch, readiness and correlation propagation. These are engineering checks, not research benchmark trials.

## Implemented design

Gateway -> order -> payment over HTTP, with one shared application factory selected by SERVICE_ROLE. Each container runs as non-root with dropped capabilities and a read-only root filesystem. Payment creates synthetic receipts only. No external money movement or API credentials are used.

All items have a synthetic fixed price of 1000 cents. Order/payment records are not persisted. POST calls are not retried because idempotency is not implemented. Structured request logging exists; Prometheus dashboards and OpenTelemetry tracing do not yet exist. Gateway HTTP timeout is 3 seconds; order timeout is 2 seconds. Liveness does not call dependencies; readiness checks the dependency chain.

## Exact next action

Ask the user to authorize creation/push of **private** `Jill-Vekariya/safeheal-ai` and confirm the Git commit identity (GitHub profile name and verified GitHub noreply email is an option; retrieve it through authenticated GitHub access rather than inventing an address). This authorization is specifically required by sections 9, 11, 12 and 14 of the supplied master specification.

After authorization:

1. Reconnect to the listed computer and read the actual folder, this file, WORKLOG.md and `git status`.
2. Configure author identity **only in this repository**, using confirmed details.
3. Review/stage source, docs and evidence; exclude `.venv`, local secrets and bootstrap transfer JSON.
4. Commit the verified Day 1 baseline; record its SHA. Create the private repository and push using authenticated GitHub CLI; verify visibility, remote SHA and CI.
5. Update this status and worklog, supply an updated status download, and mark the Day 1 gate complete only when its acceptance evidence exists.
6. Begin Day 2: verify/install kind as authorized, create a designated local test cluster, deploy services with liveness/readiness probes, and test native recovery under controlled conditions.

Do not ask for passwords or tokens in chat. Use existing authenticated tools or secure connection flows. If the computer is offline, say so and use the archive for inspection; do not claim remote execution.

## Remaining 10-day roadmap / acceptance gates

| Gate | Status | Required outcome |
|---|---|---|
| Day 1: foundation | In progress | Tested running microservices AND working private GitHub baseline |
| Day 2: Kubernetes | Not started | kind cluster, deployments/services/probes, service discovery and observed native crash recovery |
| Day 3: observability | Not started | Real Prometheus error/latency/request metrics, JSON logs, Grafana; tracing if feasible |
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

Final deliverables still required: working controller, observability, rule baseline, AI diagnosis, safety/executor/verification, Kubernetes manifests, fault harness, raw datasets, analysis charts, research report, demo, achievement-based resume/SOP text and 15–20 interview questions. Day 1 source/tests/docs are foundational parts of these deliverables, not their completion.

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
