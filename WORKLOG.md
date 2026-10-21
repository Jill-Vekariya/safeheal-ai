# Worklog

## 2026-10-20 — Day 1 initial session (Asia/Kolkata)

Read the full user specification and request for portable progress. Inspected Desktop Commander computer Jill-Vekariya10; Python 3.12/3.13, Git, Docker Desktop/Compose and GitHub CLI present. Confirmed authenticated GitHub account Jill-Vekariya; no accessible safeheal-ai repository. Found no existing safeheal-ai folder under Projects and created it. No applicable AGENTS.md was found in the checked parent locations.

Docker engine was initially stopped. `docker desktop start` succeeded; engine version 29.8.2 verified. No system-wide dependency installation or configuration change was made. Python dependencies installed only into the new `.venv`; Docker built the project image and launched its dedicated Compose network/containers.

Created pyproject.toml, services/app.py, services/__init__.py, tests/test_services.py, Dockerfile, compose.yaml, requirements.lock, .gitignore, .dockerignore, .env.example, scripts/smoke.py and .github/workflows/tests.yml. Created README.md, ARCHITECTURE.md, ROADMAP.md, EXPERIMENTS.md, PROJECT_STATUS.md, this worklog, docs/MASTER_SPEC.txt and evidence/day1-tests.txt. Local bootstrap JSON files are temporary transfer aids excluded from Git and the archive.

Implemented synthetic order/payment flow, request validation, health/readiness, timeout/error mapping, receipt validation, correlation IDs and JSON request logs. Chose a shared service factory for a manageable Day 1 codebase; separate containers preserve real HTTP boundaries. No model API, real payment, Kubernetes fault or automatic recovery action was run.

Commands/outcomes:

- `py -3.12 -m venv .venv`: succeeded.
- `.\.venv\Scripts\python.exe -m pip install -e '.[dev]'`: succeeded; exact versions captured in requirements.lock.
- `.\.venv\Scripts\python.exe -m pytest -q`: 22 passed, 1 Starlette/HTTPX deprecation warning, 11.77 seconds.
- `docker compose config --quiet`: exit 0.
- `docker compose up --build -d --wait --wait-timeout 180`: images built and all healthy; PowerShell stderr/Tee wrapper exited 1. Verified directly with `docker compose up -d --wait --wait-timeout 60`: exit 0.
- `.\.venv\Scripts\python.exe scripts/smoke.py`: health/readiness 200, order 201 with 2000 cents; SMOKE PASS, exit 0.
- `docker compose ps`: three healthy containers, only gateway published to loopback port 18080.
- `git init -b main`: succeeded. No configured Git author; no commit/push attempted.

Issues resolved: created destination directory before remote file transfer after an initial ENOENT; started Docker engine; distinguished PowerShell stderr handling from actual Docker state via a direct successful verification.

Open items: user authorization for private GitHub creation/push, confirmed commit author identity, initial commit, remote verification and CI. All Days 2–10 remain open. Containers left running for the user to inspect. See README for the scoped stop command.

No experimental findings yet. Latest verified commit: none.


## 2026-10-20 — Day 1 completion follow-up

User said “day 1 complete” after the private-repository/commit authorization request; proceeded to finish the specified baseline. Queried authenticated GitHub login and account ID, configured repo-local author name and GitHub noreply email; no global Git settings changed.

Staged the 20 project files explicitly, checked staged whitespace and committed baseline `9b75e000492162de9528bb18a5ffbc7219875262`. Created `Jill-Vekariya/safeheal-ai` as private, pushed main, and verified private visibility and matching local/remote SHA. GitHub Actions run 39399733684 completed successfully, including installation and pytest on Ubuntu/Python 3.12. Rechecked all three local containers: healthy.

Updated PROJECT_STATUS.md to version 2: Day 1 13/13, full acceptance gates 1/10 (10%), next Day 2. Updated ROADMAP.md; excluded only the transient local Compose build transcript via .gitignore (summary evidence remains tracked). No application code changes or new research results in this follow-up. Documentation checkpoint is committed separately from the tested implementation baseline.

Day 1 blockers resolved. Remaining project work: Days 2–10. Next action: scoped kind/Kubernetes preparation and service deployment.

## 2026-10-20 to 2026-10-21 — Day 2 Kubernetes completion

The user authorized Day 2 implementation, native recovery testing, documentation, tested commits and a completion status file, using Desktop Commander. Reused the canonical Windows checkout and left unrelated Docker projects intact. Installed checksum-verified kind v0.33.0 into `.tools`, used kubectl v1.36.1, and created the single-node `safeheal-dev` cluster with pinned Kubernetes v1.36.4 image. All cluster commands use `.local/kubeconfig` and context `kind-safeheal-dev`; the default kubeconfig was not changed.

Added kind config and Kustomize manifests for namespace, token-free ServiceAccount, three Deployments and three ClusterIP Services. Added startup/readiness/liveness probes, resource requests/limits, non-root restricted security settings and an in-memory temporary directory. Added `scripts/k8s.py`, `scripts/in_cluster_check.py`, 18 safety tests, the Kubernetes architecture/runbook, README/architecture updates and a GitHub Actions live-kind job. `.tools` and `.local` are excluded from Git and Docker builds.

Initial kind bootstrap failed because our config used the reserved `app.kubernetes.io/part-of` label in kubelet node-registration flags. The diagnostic journal showed the rejected label. Corrected node ownership labels to `safeheal.ai/*`, retained failed bootstrap diagnostics and streamed build/load progress. Recreated only the verified empty failed kind node created during this task. Corrected setup reached Ready and deploy built/loaded `safeheal-ai:sha256-34edfc9c74355d5b`; all Deployments became 1/1 Ready. No application change was required.

Committed/pushed implementation `cf769a7aa9c523afef129cdad3f9ff966f1fc9b5`; its kind CI failed at the label issue. Fix `43abb2318280ff455ad9ab56e9359af9f5531eed` passed run 39470648959, including unit tests and Linux kind deployment, discovery and native recovery. Private visibility and matching remote SHA were rechecked. A tool credit interruption and later offline computer delayed local acceptance verification; resumed after the user reported the device online. Existing deployed services were healthy, so no cluster recreation was needed on reconnection.

Final Windows checks on 2026-10-21 local time (UTC records dated 2026-10-20):

- Unit/safety suite: **40 passed, 1 existing dependency warning in 16.06 s**, exit 0; saved `evidence/day2/tests.txt`.
- Discovery/HTTP check: **PASS**, exit 0. Short names and FQDNs matched ClusterIPs, all health/readiness checks passed, an order returned HTTP 201 / 2000 cents / confirmed, and matching POST logs existed in all three services. Raw record: `evidence/day2/verification-20261020T223105-a896d6.json`.
- Recovery dry run: passed target checks without injecting a fault.
- Executed trial `day2-native-d15965119813`: stopped exactly the validated payment CRI container. Exit 137 was observed; kubelet replaced the container inside the same Pod UID. Restart count rose 0 -> 1; gateway/order UIDs and restart counts stayed unchanged.
- Payment first observed Ready after 6.391 s. Three following DNS/health/readiness/order checks passed with two-second gaps. End-to-final-check interval 13.844 s includes API/CLI/poll/check overhead and is not benchmark MTTR. Raw record: `evidence/day2/recovery-20261020T223144-4257ee.json`.
- Saved implementation CI metadata in `evidence/day2/implementation-ci.json`.

Updated PROJECT_STATUS.md to version 3, Day 2 9/9 and full gates 2/10 (20%); updated ROADMAP.md and EXPERIMENTS.md. Evidence and completion documentation are committed separately from the tested implementation. The cluster and existing Compose stack remain running for inspection. Day 2 has no blockers; next is Day 3 observability. This proves a native container restart, not liveness-failure thresholds, Pod replacement, high availability or AI effectiveness.


## 2026-10-21 — Day 3 implementation checkpoint

User requested Day 3 observability and an updated portable status. Computer was initially offline;
reconnected after the user reported it online. Canonical checkout clean and local/remote HEAD matched
`a4ce10a5e5eb201e5a11cfefe971eb5d7419785e`; private visibility confirmed; all services Ready in the existing cluster.
No newer work or parent AGENTS.md was found. Reused the cluster without recreation.

Added per-app Prometheus registries and ASGI request/status/duration metrics; bounded labels and
probe exclusions; correlated JSON logs including failures; OpenTelemetry manual server/client spans
with W3C propagation and local JSON span export. Added digest-pinned monitoring manifests,
eight provisioned Grafana panels, guarded deployment and actual-traffic verification scripts,
unit/safety/trace tests, CI extension and docs/OBSERVABILITY.md. New packages installed only in
project .venv; exact installed versions captured in requirements.lock.

Tests: 51 passed, one existing Starlette warning. All app Deployments rolled out successfully.
Initial kind image import of the Prometheus multi-platform digest failed because Docker's local
archive lacked other-platform content. No monitoring resources had been applied. Replaced this
preload step with normal kubelet pull by immutable digest; no cluster recreation or unrelated changes.
Live monitoring acceptance is pending at this implementation checkpoint. Research findings remain none.
