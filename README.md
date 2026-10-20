# SafeHeal AI

An isolated research testbed for evidence-grounded AI diagnosis and policy-controlled recovery of distributed services.

**Current scope:** Synthetic gateway/order/payment application with a scoped kind deployment and native Kubernetes recovery demonstration. See PROJECT_STATUS.md for verified acceptance results. AI diagnosis and controlled benchmark comparisons remain future work.

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
- Structured request logs propagate a correlation ID. This is not distributed tracing yet.
- Tests use HTTPX transport mocks for repeatable failure paths; a separate live smoke test exercises actual networking.
- A shared app factory keeps Day 1 small; separate modules can follow when service behaviour grows.

Interview question: Why can restarting a healthy gateway make a payment outage worse? Explain cascading failure, readiness versus liveness, and retry amplification.

## Research objective

Compare native Kubernetes recovery, deterministic rule-based recovery and evidence-grounded LLM assistance under matched failures. No claim of AI superiority is made until measured. This is a portfolio/research project, not an admission guarantee.

See ROADMAP.md, ARCHITECTURE.md, EXPERIMENTS.md and WORKLOG.md. The original user specification is retained in docs/MASTER_SPEC.txt.

Official implementation references: https://fastapi.tiangolo.com/tutorial/testing/ and https://docs.docker.com/compose/how-tos/startup-order/.
