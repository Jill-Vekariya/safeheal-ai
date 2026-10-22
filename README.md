# SafeHeal AI

An isolated research testbed for evidence-grounded AI diagnosis and policy-controlled recovery of distributed services.

**Current scope:** Synthetic gateway/order/payment services, scoped Kubernetes deployment, Prometheus/Grafana observability, a deterministic incident detector, and a reproducible three-scenario fault benchmark. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for verified acceptance results. AI diagnosis, policy-controlled remediation and matched approach comparisons remain future work.

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
