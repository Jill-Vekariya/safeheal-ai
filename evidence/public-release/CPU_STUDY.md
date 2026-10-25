# Public CPU study results

## Public CPU model study - verified implementation

A fresh isolated Linux GitHub runner completed five randomized matched blocks and all 15 planned scale-zero trials with the predeclared 90-second horizon. Its exact implementation source is `fd809cae41b60c62b59bd2fc2e2377f5d487b163`. The separate standard demo and normal CI passed at that source: Linux 559 passed, 1 opt-in skip; Windows 558 passed, 2 expected skips.

| Arm | Attempts | Recovered / 5 | Censored | Observed mean (s) | Restricted mean (s) |
|---|---:|---:|---:|---:|---:|
| native | 5 | 0 | 5 | Not measured | 90.000 |
| rule_policy | 5 | 5 | 0 | 14.107 | 14.107 |
| ai_policy | 5 | 2 | 3 | 14.836 | 59.934 |

The AI arm made 5 real local CPU-model requests, with provider statuses {"provider_invalid_response": 1, "validated": 4}. It recorded 2 independently controller-verified recoveries and 2 sustained business recoveries within the horizon. Reported token usage was {"input_tokens": 2106, "output_tokens": 134}; failed requests may consume compute without returning usage. Actual monetary compute cost is unknown.

All 15 cleanup checks passed, all 120 forbidden probes returned HTTP 403, and 28 audit events verified. The model had no Kubernetes credential, shell tool, approval power or action authority. The runner pinned the official Ollama image and base model digest, served inference only on loopback, disabled cloud inference, capped it at two CPUs and 1536 MiB, and warmed the model outside measurement. Model metadata confirms CPU residency.

Full evidence validation precedes compact candidate projection, and expanded selected hypotheses are checked independently. This ranks deterministic evidence-supported candidates; it is not unrestricted root-cause discovery. Confidence is uncalibrated. The same independent one-action policy constrains rule and AI arms.

The two Windows CPU attempts remain incomplete: six of fifteen attempted before interruption, then nine of fifteen before a cleanup rollout timeout. The latter preserves eight passed cleanups, one failed cleanup and six unrun slots; a later independent healthy-order check does not change that failure. The original 45-second baseline and larger-model timeout cohort remain unchanged. No attempt was replaced or resumed, and differing hosts, horizons, runtimes or prompt formats are not pooled.

Six retrospective development incidents also produced six grounded, target-matched and observable-class-matched real-model diagnoses without fallback. Those are development checks, not held-out accuracy. One policy-addressable scenario, five shared-host blocks, warm state, telemetry windows, closed-loop workload and host contention limit generalization. Observed-only means exclude censored observations; the horizon is not observed MTTR. No general AI superiority, calibrated diagnostic accuracy, production safety rate or universal recovery gain is established. CPU/memory fault coverage, held-out benign controls, multi-host replication and external audit anchoring remain future research.

Raw measurements: `evidence/day9/run-ci-cpu-40206671248`. Full findings and charts: `evidence/day9/analysis-ci-cpu-40206671248`. Permanent CI archives and source/runtime provenance: `evidence/public-release/ci-40206671248` and `ci-40206669554`.
