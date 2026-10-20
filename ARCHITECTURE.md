# Architecture

## Implemented Day 1 data plane

The gateway forwards validated orders to the order service. The order service creates an order ID, calculates a fixed synthetic price, calls payment and verifies the returned receipt. The payment service issues a simulated receipt. Each runs in its own container using the same app factory selected with SERVICE_ROLE.

HTTP POST operations have no retries. Order/payment data is not persisted. A request ID is propagated in headers and JSON request logs. These IDs are correlation identifiers, not authenticated caller identities.

## Planned control plane (not implemented)

Telemetry collectors -> deterministic incident detection -> bounded evidence aggregation -> rule or LLM diagnosis -> independent policy validation -> typed recovery executor -> health verification -> incident history.

The control plane will be separate from the monitored application. No model will receive arbitrary shell execution or unrestricted Kubernetes credentials. Policies will enforce an action allowlist, namespace/target scope, approval mode, rate limits, duplicate suppression and audit records.

## Trade-offs

Compose proves the application baseline before Kubernetes adds orchestration complexity. A shared service factory reduces boilerplate; services remain independently deployed. Recursive readiness is suitable for this small dependency chain but can amplify probes in a larger graph, where cached/local readiness decisions should be evaluated.

Day 1 is not fault injection, an incident detector, an AI agent or an automatic recovery platform. Those are separate acceptance gates.
