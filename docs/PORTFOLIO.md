# Portfolio language grounded in the implementation

Use only statements that you can explain and substantiate. Adapt the wording to your actual contribution and acknowledge implementation assistance where your application or institution asks for it. Do not claim independently authored work you cannot defend.

## Resume bullets

- Built a three-service Kubernetes incident-response prototype with Prometheus evidence, structured read-only diagnosis and an independent recovery controller enforcing one explicitly enrolled scale transition through named-resource RBAC and admission policy.
- Developed safety tests for stale/misleading evidence, duplicate notifications, unsafe proposals, approval/replay controls and ambiguous write outcomes; retained raw incident data and reproducible numerical analysis rather than reporting unsupported AI performance gains.
- Designed a seeded native/rule/AI experiment with sustained business-recovery checks, right-censoring, operator-cleanup separation and hash-verified raw data; measured five fixed-rule recoveries in five original scale-zero trials, with a 19.04-second observed mean.

The third bullet describes only the original baseline cohort. The full project report contains the separate larger-model timeout study and the newer CPU study, where the rule recovered in 5/5 trials and the AI path in 2/5. These are distinct configurations and hosts. Do not present 19.04 seconds as a general production MTTR or claim a percentage speedup against censored native observations.

## Concise statement-of-purpose project narrative

In SafeHeal AI, I explored how an incident assistant can remain useful when its diagnosis is uncertain. I built a small Kubernetes application and separated normalized evidence, model hypotheses and recovery authority. A deterministic controller, scoped service account and admission policy permit only one enrolled state transition, while durable claims prevent blind retries after ambiguous writes. Controlled experiments and retained failure cases taught me to distinguish business recovery from readiness, symptom agreement from causal diagnosis, and censored observations from measured recovery times. The project sharpened my interest in dependable intelligent systems: I want to investigate how calibrated uncertainty, verification and evaluation design can make AI-assisted operations easier to trust and audit.

This is a project narrative, not a claim of faculty collaboration, publication, academic novelty or admission likelihood. Add program-specific academic fit only after checking the current official program/faculty sources.

## Twenty interview questions and answers

1. **What is the actual research question?** Whether model ranking improves a fixed symptom-to-action pipeline when both use the same independent controller, and what latency/failure costs it adds. A single permitted action makes the model's possible benefit small; that is a useful baseline.
2. **Why does native recovery not restore replicas?** Kubernetes reconciles toward desired state. Desired zero is a valid configuration, so native behavior should preserve zero. This fixture tests an explicit restoration policy, not ordinary container restart quality.
3. **What can the model execute?** Nothing directly. It returns bounded diagnosis data. Candidate indices expand only into evidence-supported hypotheses. A fixed bridge may construct one typed proposal; authority comes from operator enrollment and controller policy.
4. **Why are schema validation and RBAC both necessary?** Schema validation rejects malformed proposals but is not an authorization boundary. RBAC limits API operations and named resources, while admission independently limits old/new replica values.
5. **What stops a time-of-check/time-of-use race?** Live identity/spec checks plus an atomic JSON Patch test of UID, resource version and scale spec. A changed precondition fails instead of blindly overwriting it.
6. **Why no write retries?** A timeout can occur after the API accepted the write. Claim-before-write and a durable uncertain/running state avoid a second execution without reconciliation.
7. **How does approval work?** It is operator-issued, expiring, single-use and bound to a specific request and live spec/generation. Model-supplied approval or mode fields cannot confer authority.
8. **What is verified after recovery?** Three consecutive readiness observations for the expected generation and exact replicas. A separate operator harness checks Service routing and confirmed business orders; readiness alone is insufficient.
9. **Why did a Service check once fail after controller success?** Readiness can precede route propagation. The harness now waits with bounded GET-only checks before one unretried order POST. The earlier failure is retained as failed.
10. **How is evidence freshness measured?** Actual sample timestamps matter, not only envelope collection time. Stale, future, malformed and unsupported evidence is excluded or rejected before provider invocation.
11. **How do you handle prompt injection in logs?** Normalize bounded evidence and remove arbitrary prose/labels before model use; treat evidence as data and validate every reference independently. This is defense in depth, not proof against all injection.
12. **What does confidence mean?** A subjective model score capped by validation, not a calibrated probability. A threshold controls this experimental bridge; calibration needs independent labeled evaluation.
13. **What happens when the provider is unavailable?** The bounded transport consumes the attempted call, does not retry, emits a fixed secret-free failure code and produces abstention/low-confidence fallback. Fallback does not qualify as an AI recovery success.
14. **How do duplicate incidents behave?** Durable notification claims deduplicate IDs and evidence across restarts/concurrency. Collisions, persistence failures and uncertain interrupted processing fail closed rather than calling repeatedly.
15. **Why report restricted recovery time?** Native trials may not recover before the observation horizon. Their actual time is unknown; min(T,H) supports a declared limited comparison without inventing a measured MTTR of H.
16. **What is wrong with response success percentage as uptime?** The workload is closed-loop. Slow failures produce fewer completions, so completed-response percentages are request weighted, not elapsed-time availability or fixed-load reliability.
17. **What can five matched blocks establish?** Descriptive behavior in this lab and exploratory paired resampling. Shared caches, telemetry carryover, order and host contention prevent population-level precision claims.
18. **Is the audit tamper-proof?** No. Hash chaining detects accidental corruption and local append controls prevent ordinary updates, but an OS administrator can rewrite the database and hashes. External append-only storage is future work.
19. **Why are fresh journals used in repeated trials?** The operator creates separate experimental episodes so retained audits are not deleted and production controller limits stay unchanged. Continuous-production rate limiting across episode resets is not evaluated; the model cannot reset journals.
20. **What would you improve first?** Add benign and ambiguous held-out controls, more independently policy-addressable faults, replicated hosts, calibrated uncertainty, external audit anchoring and protected enrollment. Add actions only after specifying independent permissions, invariants and verification.
