# Day 5 initial benchmark evidence

## Verified outcome

Six Kubernetes trials completed successfully: two repetitions each of payment process crash, HTTP 500 and added latency. All six had verified ground truth, eligible rule observations, a detected incident, restored business behavior, and verified cleanup. Final service health and harness shutdown passed. The machine-readable acceptance result is `true`.

- Source: [`31f2af628e70487f1cd0098403bd3ab2304a4d46`](https://github.com/Jill-Vekariya/safeheal-ai/commit/31f2af628e70487f1cd0098403bd3ab2304a4d46).
- CI: [39774736343](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39774736343), both jobs successful.
- Actual benchmark interval: 2026-10-22 12:05:12.009502–12:22:41.030610 UTC.
- Dataset: [`ci-39774736343/run-03a9072a24f8`](ci-39774736343/run-03a9072a24f8).
- Summary: [JSON](ci-39774736343/run-03a9072a24f8/summary.json) and [CSV](ci-39774736343/run-03a9072a24f8/summary.csv); [audit](ci-39774736343/run-03a9072a24f8/audit.json).
- Environment: fresh Linux CI kind cluster; kind v0.33.0, kubectl v1.37.1, Kubernetes v1.36.4. The development PC's existing cluster was not the execution environment.

## Individual results

Rows follow the seeded execution order. Every duration below starts at the host `injection_requested_at`; it includes command and observation overhead. Business recovery is the end of the sustained healthy-response window, not the first successful request.

| Trial | Scenario / repeat | Rule detection (s) | Sustained business recovery (s) | Observed native Ready (s) | Recovery attribution |
|---|---|---:|---:|---:|---|
| `d5-01-http_5xx-d6b754b6` | http_5xx / 1 | 27.130 | 93.040 | N/A | `fault_expiry` |
| `d5-02-process_crash-41c49801` | process_crash / 1 | 17.172 | 32.429 | 34.317 | `native_kubernetes` |
| `d5-03-process_crash-d3a98bd4` | process_crash / 2 | 12.033 | 51.740 | 50.340 | `native_kubernetes` |
| `d5-04-latency-f3613d30` | latency / 2 | 32.187 | 92.979 | N/A | `fault_expiry` |
| `d5-05-latency-caab66e3` | latency / 1 | 32.321 | 93.064 | N/A | `fault_expiry` |
| `d5-06-http_5xx-bea84ddf` | http_5xx / 2 | 32.103 | 93.107 | N/A | `fault_expiry` |

All six detector outcomes were `detected`; no benchmark attempt in this batch failed, was ineligible, or was censored. Earlier Windows test/setup failures remain separate engineering records and were not converted into benchmark trials.

### Recorded event timestamps

All times are UTC on 2026-10-22, rounded to milliseconds for this table. Full precision and injection acknowledgement, observed effect, removal, first healthy response, final platform and trial-finish timestamps remain in each `trial.json`.

| Sequence | Injection requested | First qualifying incident opened | Sustained business recovery |
|---|---|---|---|
| 1 | 12:05:49.211 | 12:06:16.341 | 12:07:22.250 |
| 2 | 12:09:06.399 | 12:09:23.571 | 12:09:38.828 |
| 3 | 12:11:08.808 | 12:11:20.841 | 12:12:00.548 |
| 4 | 12:13:35.859 | 12:14:08.046 | 12:15:08.838 |
| 5 | 12:16:42.854 | 12:17:15.176 | 12:18:15.918 |
| 6 | 12:19:50.261 | 12:20:22.364 | 12:21:23.368 |

## Protocol and recovery attribution

The predeclared plan uses seed 5, two repetitions, a 30-second minimum baseline, 15 seconds of continuously clean eligible telemetry, at least 20 recent healthy requests, four closed-loop request workers, a 0.2-second delay after completion, and five-second detector polling. HTTP 500 and 1.25-second payment latency faults have 90-second leases. There is one scoped CRI stop for each process-crash trial and no automatic fault retry. A normal repeated run uses the same plan and records its own timing variation.

Ground truth is written before mutation and independently verified through the fault identity/direct response or immutable container termination identity, plus observed gateway impact. The unchanged Day 4 detector has no access to fault labels and performs no recovery action. The full protocol and exact eligibility, matching, baseline, censoring and finalization rules are in [docs/BENCHMARKS.md](../../docs/BENCHMARKS.md).

Both crashes retained payment Pod UID `163ff0e6-8161-4daf-a4ca-d1ec11514aa3`, replaced the container, and increased restart count from 2 to 3 and then 3 to 4. Each old container's recorded termination matched the injected container, with exit 137. Gateway/order identities and restart counts remained stable, although their readiness temporarily dropped during both crashes. These records establish restart after forced exit; the earlier liveness events in the run predate these injections. The two earlier payment restarts belonged to preceding CI acceptance checks; the benchmark does not reset Kubernetes restart history between trials.

For HTTP and latency faults the payment container identity and restart count stayed unchanged, and its probes remained healthy in recorded platform observations. Business recovery followed lease expiration. Those four trials do not demonstrate Kubernetes repairing an application-level failure. `rule_executed_recovery` is false in all six records.

Sustained business recovery requires at least three consecutive valid HTTP 201 confirmed 2000-cent order responses, each below 0.5 seconds, spanning at least two seconds after the last affected response. Native Ready is a separately sampled platform observation; it can appear later than the first or sustained successful traffic. The run also waits for qualifying rule incidents to resolve and verifies final Service-DNS health and an end-to-end order.

## What the rule baseline established

The rules observed a qualifying incident in each of these six trials, with first-open delays from 12.033 to 32.321 seconds. First diagnoses classified crash symptoms as service/metrics unavailability, HTTP faults as server error spikes, and added latency as request latency degradation.

Detection is distinct from root-cause localization. The first qualifying matched diagnosis pointed to the injected payment service in only three of the six records (both crash trials and one latency trial); the other first diagnoses described gateway/order symptoms. `suspected_root_service` was null in all six first diagnoses. This descriptive target-match count is not a validated root-cause accuracy estimate, and no population false-positive or false-negative rate is inferred.

In both HTTP trials, payment first produced a `telemetry_unavailable` incident, which is excluded from matched fault detection. Its own `high_error_rate` incident opened about 77.1 seconds after injection; the earlier order/gateway symptom alerts supply the reported 27.130/32.103-second detection intervals. The raw evidence retains this metric-family warmup limitation.

This is an initial small engineering benchmark of native behavior with a concurrent rule observer. It contains no matched A/B/C intervention comparison, rule recovery executor, LLM diagnosis, production reliability estimate, or claimed improvement in MTTR. The two repetitions share a cluster and restart history, and the closed-loop workload issues fewer requests during slower responses.

## Retained data and audit

The dataset retains 15,180 individual gateway request records, 212 telemetry snapshots, six detector SQLite databases, platform observations, ground-truth trial records, source/runtime hashes, environment and rule configuration, the plan, and final run health/shutdown evidence. At run level, `summary.json` and `summary.csv` include all six attempts. Console logs and GitHub workflow metadata are retained in the parent CI directory.

All 39 downloaded benchmark artifact files matched the retained originals by SHA-256. Summary replay from the stored run/trial records reproduced the JSON content and CSV bytes. Every request count, status count and valid-response count agreed with its raw JSONL; all six SQLite integrity checks returned `ok`. `audit.json` contains the replay flags, trial measurements and file SHA-256 hashes. Git attributes preserve raw benchmark bytes across Windows and Linux checkouts.

To recompute a summary without changing the original artifact's formatting, copy the run directory to a new path and use:

```text
python scripts/benchmark.py summarize <copied-run-directory>
```

To execute another isolated-cluster batch after the prerequisites in the runbook:

```text
python scripts/benchmark.py run
python scripts/benchmark.py run --execute --backend kubernetes --repeats 2 --baseline-seconds 30
```

The first command is a plan-only dry run. Every executed batch receives a new run directory. A failed trial stops the batch and remains stored.

## Other retained Day 5 verification

- Canonical Linux CI suite: 289 passed, one existing dependency warning; workflow log retained with the CI dataset.
- Canonical Windows suite: 288 passed, one skipped symlink test (missing Windows creation privilege), one existing warning; [transcript](windows-final-tests.txt).
- Initial Windows 16-failure transcript and intermediate test pass remain retained. Fixes corrected platform path handling and mocked Linux-container path fixtures.
- [Docker port state](docker-port-before-repair.json): the existing Windows kind node's internal API responded, but its configured loopback API binding had no active published mapping. Scoped node restart/network reconnection did not restore it. No cluster deletion or global Docker restart was performed. Local Windows Kubernetes reruns remain blocked until that host mapping is restored.
