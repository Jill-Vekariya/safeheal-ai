# Architecture

## Implemented application data plane

The gateway forwards validated orders to the order service. The order service creates an order ID, calculates a fixed synthetic price, calls payment and verifies the returned receipt. The payment service issues a simulated receipt. Each runs in its own container using the same app factory selected with SERVICE_ROLE.

HTTP POST operations have no retries. Order/payment data is not persisted. A request ID is propagated in headers and JSON request logs. These IDs are correlation identifiers, not authenticated caller identities.

## Planned control plane (not implemented)

Telemetry collectors -> deterministic incident detection -> bounded evidence aggregation -> rule or LLM diagnosis -> independent policy validation -> typed recovery executor -> health verification -> incident history.

The control plane will be separate from the monitored application. No model will receive arbitrary shell execution or unrestricted Kubernetes credentials. Policies will enforce an action allowlist, namespace/target scope, approval mode, rate limits, duplicate suppression and audit records.

## Trade-offs

Compose proves the application baseline before Kubernetes adds orchestration complexity. A shared service factory reduces boilerplate; services remain independently deployed. Recursive readiness is suitable for this small dependency chain but can amplify probes in a larger graph, where cached/local readiness decisions should be evaluated.

Day 2 adds a dedicated kind cluster, Kubernetes Deployments/Services/probes, and a guarded native container recovery demonstration. An incident detector, AI agent and policy-controlled executor remain separate acceptance gates.


## Kubernetes orchestration

Each service has one Deployment and a ClusterIP Service in `safeheal-dev`.
CoreDNS provides service names; the kubelet manages container lifecycle and probes.
Deployment/ReplicaSet controllers maintain Pod count, while the kubelet restarts
containers within existing Pods under `restartPolicy: Always`.

The single kind node shares control-plane and application workloads on the developer
machine. It demonstrates real process and HTTP boundaries but not node-level high
availability. Each workload has resource requests/limits, a non-root user, dropped
capabilities, read-only root filesystem, bounded temporary storage and no API token.
No network policy enforcement or public ingress is configured.

[Day 2 architecture, diagram, deployment and recovery runbook](docs/KUBERNETES.md)
contains the full implementation, exact commands and limitations.


## Observability extension

Each service exposes bounded request/status counters and duration histograms to a local
Prometheus instance. Grafana queries Prometheus through a provisioned datasource. W3C trace
context links manual OpenTelemetry server/client spans, exported as JSON container logs.
Request logs carry the same request, trace and span IDs. No external telemetry sink or model
call is involved. See docs/OBSERVABILITY.md for precise semantics, resource limits and verification.

## Day 4 detector boundary

The standalone incident service reads only three fixed Prometheus matrix queries. Pure deterministic verdicts feed a transactional SQLite lifecycle and rule-based diagnosis controller. A loopback-only GET API exposes incidents and evidence. This service cannot execute recovery or access Kubernetes credentials. Fixed dependency topology can correlate upstream server errors with a suspected downstream outage while preserving both evidence references. See docs/INCIDENT_DETECTION.md.
