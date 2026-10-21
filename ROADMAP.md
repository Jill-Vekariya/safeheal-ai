# SafeHeal AI — 10-day execution plan

Days are work milestones, not a promise that unfinished gates are complete on a calendar date. Progress uses 10 equally weighted daily gates; partial task counts are reported separately.

**Verified progress: Days 1–3 complete, 3/10 gates (30%), as of 2026-10-21 Asia/Kolkata. Next: Day 4 deterministic detector.** Day 3 evidence is in `evidence/day3/`; see PROJECT_STATUS.md and docs/OBSERVABILITY.md for actual results.

| Day | Implementation tasks | Acceptance evidence |
|---|---|---|
| 1 | Inspect environment; create gateway/order/payment; health/readiness; Dockerfile/Compose; tests; documentation/progress; private GitHub baseline | Running three-service stack; health and order smoke pass; tests pass; authorized private repository and verified pushed commit |
| 2 | Install kind if missing; create dedicated local cluster; deployments/services; probes; namespace/RBAC foundations; deploy scripts | All services ready; approved controlled process failure recovers natively; recovery recorded |
| 3 | Prometheus request/error/latency metrics; JSON logs; Grafana; OpenTelemetry if feasible | Real load visible in dashboards; trace correlation verified if added |
| 4 | Detector; thresholds/windows; incident state machine; SQLite; evidence timestamps; deterministic diagnosis | Known failures detected without LLM; false-alert and transition tests pass |
| 5 | Scoped fault injection; ground-truth labels; experiment runner; native/rule baselines | At least three reproducible scenarios, raw trial records and reset verification |
| 6 | Configurable provider; bounded read-only tools; structured diagnoses; evidence attribution; uncertainty and fallback | Benchmark diagnoses attributable to actual evidence; mock tests and real-provider tests distinguished |
| 7 | Typed allowlisted recovery; independent policies; approval/dry run; least-privilege executor; audit; health verification | Permitted recovery succeeds in isolated cluster; forbidden actions rejected; safety tests pass |
| 8 | Misleading/incomplete/stale evidence; provider outage; duplicate incidents; unsupported claims | Documented failure handling and before/after robustness measurements |
| 9 | Matched A/B/C trials; at least five repetitions per scenario/approach if feasible; statistics; charts; error analysis | Raw data, scripts, confidence intervals and honest limitations support conclusions |
| 10 | End-to-end verification; CI; report; reproducibility; demo; resume/SOP narrative; 15–20 interview questions | Reviewer can clone, run core experiment, inspect evidence and understand limitations |

## Working rule

At session start: read PROJECT_STATUS.md, WORKLOG.md, actual git state and test evidence. At session end: verify changed behaviour, update records, commit/push only when authorized and state the exact next task.

## Completion rule

100% means all 10 gates passed with evidence and final deliverables reviewed. It does not mean admission, novelty or production readiness. If scope changes, document it explicitly and retain the original requirements; never silently remove unmet tasks to reach 100%.

## Deferred dependencies and choices

Private repository baseline and scoped kind setup are complete. Reuse the existing `safeheal-dev` cluster after checking its current state. Select an LLM/provider and budget before paid calls in Day 6. Keep GitHub private unless the user approves public visibility. Do not install system-wide components or delete/reset resources without the required authorization.
