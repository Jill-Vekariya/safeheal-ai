# SafeHeal AI — portable project status

**Snapshot:** 2026-10-22 UTC. **Version:** 6.1. **Phase:** DAY 5 COMPLETE — initial reproducible fault benchmark. **Next:** Day 6 evidence-grounded AI diagnosis.

## Current Day 5 completion

**Acceptance passed: three real Kubernetes failure scenarios, each executed successfully twice, with stored experimental results. Day 5 checklist: 8/8. Overall daily gates: 5/10 (50%).**

Canonical implementation commit [31f2af628e70487f1cd0098403bd3ab2304a4d46](https://github.com/Jill-Vekariya/safeheal-ai/commit/31f2af628e70487f1cd0098403bd3ab2304a4d46) passed both jobs in [CI run 39774736343](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39774736343). The actual six-trial run completed on 2026-10-22 from 12:05:12 to 12:22:41 UTC. Results, raw data, workflow logs and the replay audit are retained under [evidence/day5](evidence/day5/README.md), dataset `ci-39774736343/run-03a9072a24f8`.

Implemented seeded process-crash, HTTP 500 and 1.25-second added-latency scenarios; independent ground truth before mutation; an experiment runner with real workload and Prometheus capture; unchanged rule-baseline observation; timestamped detection, native-ready and sustained business recovery; reset/cleanup verification; and JSON/CSV summaries. See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for the exact protocol and repeat commands.

All six executions passed, all six had eligible matched rule detections, and final health/shutdown passed. Crash business-recovery intervals were 32.429 and 51.740 seconds; Kubernetes restarted the same Pod's payment container. HTTP faults recovered in 93.040 and 93.107 seconds, and latency faults in 93.064 and 92.979 seconds, after their 90-second leases expired. These intervals start at the host injection request and include sampling/tooling overhead. The rule detector performed no recovery action. Initial matched diagnoses localized payment in three of six records; detection is not proof of root-cause accuracy. This is not an A/B/C improvement study.

The preserved dataset contains 15,180 request records, 212 telemetry snapshots and six detector SQLite databases, plus platform/identity evidence and source/configuration hashes. Summary replay matched JSON content and CSV bytes; raw workload counts agreed and all six database integrity checks passed. Canonical Linux CI: **289 passed**, one existing warning. Canonical Windows: **288 passed, 1 skipped**, one existing warning; the skipped symlink test needs unavailable Windows creation privilege. Initial Windows failures and their correction evidence remain retained.

Publication uses the private `day5-fault-benchmark` review branch. Day 4 PR #1 was already merged; canonical main was verified at `156da54a5de4ddf4977676ebf7ce29310089fb0f` with successful CI39651662574 before Day 5. This evidence/status checkpoint follows the tested implementation; inspect branch HEAD and its Actions status for the subsequent documentation/data commit. No main merge is performed in Day 5.

**Remaining environment issue:** the existing Windows kind node's internal API is live but Docker's active loopback API mapping is missing. Scoped node restart and network reconnection did not restore it. No cluster deletion or global Docker restart was used. The successful Day 5 live dataset comes from a fresh Linux CI kind cluster; local Windows Kubernetes reruns require restoration of that host mapping. The historical Day 1–4 sections below preserve earlier evidence and point-in-time publication notes.

## Historical Day 4 delivery checkpoint

Day 4 delivery is tracked in [pull request #1](https://github.com/Jill-Vekariya/safeheal-ai/pull/1). The reviewed implementation is `87e2ec25e9264fe0d48b3e5fae97c39762dc03e4`; both jobs passed [CI run 39640164313](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39640164313). Windows and Linux suites passed 120 tests. The PR runs the full suite again, including the real Kubernetes/Prometheus fault acceptance; use the PR's current checks and merge record for its final integration status.

The user requested reliable successful GitHub checks. An earlier PR run (39646024404) failed after native recovery when the first HTTP probe received connection refused despite Pod Ready. The original failed log, run metadata, and raw recovery JSON are retained under evidence/day4. The recovery harness now uses a bounded 90-second GET-only Service-readiness wait, followed by the unchanged identity assertions and three unretried end-to-end order checks. The CRI stop remains one-shot; detector behavior and thresholds are unchanged. Windows verification: **128 passed**, one existing dependency warning, in evidence/day4/windows-readiness-tests.txt. PR #1 reruns the full Linux/Kubernetes suite; check its latest commit and results before claiming final CI success. The repository remains private. Earlier publication/merge notes below are historical checkpoints.

Full acceptance gates remain **4/10 (40%)**. Days 5-10 are incomplete. Next: controlled fault benchmark, not additional Day 4 implementation. Recheck remote main, the latest Actions run and the local checkout before starting the next day.

## Historical Day 4 completion

The computer reconnected, canonical working tree was clean and local/remote main both matched `bc06bf52efe19db592932b824de5da864c8b8c8d`. Private visibility and all five healthy Deployments were verified. The offline Day 4 patch applied only after `git apply --check`; canonical Git history was preserved. The earlier isolated commit `0dc5ff6` is a historical delivery checkpoint, not the canonical Day 4 commit. Automatic approval review rejected direct publication to default main. Day 4 is committed on `day4-incident-baseline` for private branch publication/review, preserving main at the Day 3 tip. Inspect current `git log -1`, the review branch and Actions for the publication SHA/result; the portable completion copy appends final verification.

**Day 4 checklist: 8/8 implemented and verified.**

1. [x] Separate incident detection polling service and read-only FastAPI API.
2. [x] Deterministic scrape, 5xx-rate, latency and telemetry-availability rules with windows/minima/hysteresis.
3. [x] Evidence-backed suspected dependency correlation on the fixed service topology.
4. [x] Persistent pending/open/recovering/resolved transitions, deduplication and restart handling.
5. [x] SQLite timestamps, raw telemetry, verdicts, history, diagnosis and evidence references.
6. [x] Basic rule diagnosis without a model/provider or recovery executor.
7. [x] 120 passing tests plus actual Prometheus/HTTP fault acceptance; failed attempts retained.
8. [x] Reviewed source/docs/evidence committed in canonical history; GitHub integration and current checks are tracked in PR #1.

Live acceptance `day4-pause-670cd6f0b91f`: **PASS**, 2026-10-21 16:41:02.324443 to 16:43:49.611107 UTC. One identity-checked payment container task was paused with fixed timed resumption. The detector opened **five incidents**: payment scrape outage; gateway/order latency; gateway/order 5xx rates. All five followed pending -> open -> recovering -> resolved. Upstream error incidents had suspected-payment dependency links with evidence references. Raw record: `evidence/day4/day4-pause-670cd6f0b91f.json`.

Actual gateway workload: **250 HTTP responses: 187 x 201 and 63 x 503**. Final fresh DNS/health/readiness/order checks passed (confirmed, 2000 cents). Payment retained its Pod UID and was restarted natively, count **2 -> 3**; gateway/order retained identities and counts **0 -> 0**. The detector executed no remediation and used no LLM. The developer harness has host/cluster credentials; OS privilege separation is not established by this check. This is engineering acceptance, not benchmark MTTR, diagnostic accuracy, false-positive rates or an AI improvement.

Windows after the CI harness correction: **120 passed**, one existing Starlette/HTTPX warning; `evidence/day4/windows-tests.txt`. Linux suite also passed 120. Two test-environment issues were corrected only in tests: inherited 1% trace sampling and a Windows short-sleep timing assumption. Initial failures remain recorded. The initial CI run 39638639803 passed unit tests but rejected an already-resolved transient telemetry warm-up record before fault injection. The corrected harness waits for current eligible telemetry with no **active** incidents; detector rules/thresholds are unchanged. Failed CI logs, run metadata and raw JSON are retained. Verify the corrected CI result after publication.

Two Service-selector trials remain **FAILED** in their original JSON: one scrape incident was detected/recovered but gateway keep-alive connections prevented expected 5xx; in the second, Prometheus kept a working connection and no scrape outage was observable. Thresholds were not lowered to turn these into successes. See WORKLOG.md and EXPERIMENTS.md.

**Overall acceptance gates: 4/10 (40%).** Days 5–10 remain incomplete. The safe recovery executor, model integration, controlled research benchmarks and final report are not implemented. `docs/INCIDENT_DETECTION.md` documents the service, exact thresholds, operations, limitations and reproducible guarded live check. The CI Kubernetes job now runs that check against real Prometheus in a fresh isolated cluster and uploads its evidence.

## Historical CI timeout correction after Day 3 completion

The later documentation/evidence commit `10d8415150860c62ba41168a4793a36dbfc3072d`
passed unit tests but its fresh-cluster recovery check failed in [run 39588507641](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39588507641).
`crictl` returned a runtime RPC `DeadlineExceeded` at its default **2-second** client deadline;
the log did not establish a verified recovery outcome. The observability step was consequently skipped.
This does not invalidate the earlier completed local observability acceptance or passing implementation CI.

Corrected the developer recovery script to use an explicit **30-second CRI client timeout**, within its
existing 45-second outer command bound. The separate container kill grace remains **0 seconds**;
there is still one scoped stop request, no automatic retry, the same ownership guards/lock and the same
required recovery assertions. `crictl` 1.36.0 local help verified the two distinct timeout meanings.
The corrected code passed **51 tests** and a new local dry-run/native recovery check, including the same
Pod/new container/increased restart count, stable upstream containers and three healthy order checks.
Evidence: `evidence/day3/tests-rpc-timeout-fix.txt`, `evidence/day2/recovery-20261021T110508-9fb946.json`.
The original failed CI record and run metadata are preserved under `evidence/day3/ci-failure-*`.

The complete CI suite is rerun by the correction commit. At the time this source document was written,
that new run was pending; inspect the latest GitHub Actions run/current HEAD before claiming the
latest commit is green. The portable handoff can append the final verified publication result.
Day 3 remains 9/9; full gates remain 3/10 (30%). No new research benchmark claim is made.

## Read this first in a new chat

The user wants this file to preserve continuity even if earlier chats are deleted. Read the entire file, inspect the actual project and WORKLOG.md, then continue from the next incomplete task. Do not start again or assume an unchecked item is complete. This file describes the project; it does not contain all its source code. Use the existing local folder or private GitHub repository to access current code. The earlier SafeHeal_AI_Day1.zip and Day 2 in-progress status are historical snapshots.

User objective: build SafeHeal AI, a trustworthy self-healing distributed-systems platform powered by an evidence-grounded LLM agent, as a rigorous portfolio/research project supporting a Georgia Tech on-campus MS CS/AI application for Fall 2028. User profile in supplied specification: BTech expected July 2028, CGPA 8.75/10, research ongoing. Never claim admission is guaranteed or experimental gains are proven without measurements.

## Progress at this snapshot

- Day 1: **13/13 tasks complete** — three services, tests and private GitHub baseline.
- Day 2: **9/9 tasks complete** — scoped kind cluster, discovery, probes and native recovery.
- Day 3: **9/9 tasks complete** — real traffic, Prometheus/Grafana, logs and basic distributed tracing.
- Day 4: **8/8 tasks complete** — deterministic detection/diagnosis without an LLM; PR #1 merged.
- Day 5: **8/8 tasks complete** — three reproducible fault scenarios, six real Kubernetes trials, stored ground truth/raw data, recovery attribution and private commits.
- Full daily acceptance gates: **5 of 10 complete (50%)**. This is a strict gate count, not an estimate of effort. **The whole project is not complete.**
- AI diagnosis/provider integration, the safe recovery executor, robustness evaluation, matched A/B/C research experiments and final deliverables remain unfinished.
- Verified Day 5 implementation: `31f2af628e70487f1cd0098403bd3ab2304a4d46`; [successful full CI39774736343](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39774736343).
- Current private development branch: `day5-fault-benchmark`. Main at the start of Day 5: `156da54a5de4ddf4977676ebf7ce29310089fb0f`. Verify current local/remote tips before continuing; do not replace canonical history with an older offline source snapshot.
- GitHub: https://github.com/Jill-Vekariya/safeheal-ai — private, reverified before Day 5 publication. Origin: `https://github.com/Jill-Vekariya/safeheal-ai.git`.

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
| Git author | Repo-local `Jill-Vekariya`, `195921415+Jill-Vekariya@users.noreply.github.com`, based on authenticated GitHub login/ID |
| kind / kubectl / Kubernetes | Project-local `.tools/kind.exe` v0.33.0 / client v1.36.1 / server v1.36.4 |
| Cluster / context / namespace | `safeheal-dev` / `kind-safeheal-dev` / `safeheal-dev` |
| Node / runtime | Existing `safeheal-dev-control-plane` running; internal API live, host-published API mapping missing. Historical runtime containerd 2.3.4; recheck after mapping recovery. |
| Kubernetes configuration | Explicit project `.local/kubeconfig`; loopback API; private ownership labels `safeheal.ai/project=safeheal-ai` and `safeheal.ai/environment=local-test` |
| Local API docs | Compose: `http://127.0.0.1:18080/docs`; Kubernetes: `http://127.0.0.1:18081/docs` only while `python scripts/k8s.py port-forward` runs |
| Container state | Fresh CI cluster passed final Day 5 Service-DNS/health/order checks; payment restart count 4, gateway/order 0. Existing Windows cluster was not externally reverified because its API mapping is unavailable. Compose is older and was not changed. |
| Monitoring | Prometheus 3.15.0; Grafana 13.2.4; digest-pinned manifests in `infrastructure/observability` |
| Python telemetry | prometheus-client 0.26.0; OpenTelemetry SDK/API 1.45.1; exact lock retained |
| Grafana | Historical local address `http://127.0.0.1:13000/d/safeheal-operations`; requires a working API/forward. Not reverified on Windows during Day 5. |
| Prometheus | `http://127.0.0.1:19090` when a project-owned forward is active. Real telemetry verified in Day 5 CI; Windows forward access is not currently verified. |
| Trace storage | Basic W3C/OpenTelemetry SERVER/CLIENT spans exported to JSON container logs; no trace UI/backend |
| Source backup | Current source/status in the private GitHub repository; earlier `SafeHeal_AI_Day1.zip` is a pre-publication snapshot with older status |

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
11. [x] Initialize local Git branch `main`, add CI and verify successful GitHub Actions execution.
12. [x] Configure repository-local GitHub identity and create/verify initial source commit.
13. [x] User instructed completion after the authorization request; create private GitHub repository, push baseline and verify visibility, remote SHA and passing CI.

## Day 2 checklist

1. [x] Install pinned, checksum-verified kind locally and create a dedicated local cluster.
2. [x] Create namespace, ServiceAccount, Deployments, ClusterIP Services and Kustomize manifests.
3. [x] Build/load the application image and deploy all three core services successfully.
4. [x] Configure startup, readiness and liveness probes for each service.
5. [x] Verify short/FQDN service discovery, health/readiness and gateway -> order -> payment HTTP communication.
6. [x] Deliberately terminate payment and verify a native kubelet container restart and restored orders.
7. [x] Document Kubernetes architecture, probe choices, recovery attribution and limitations.
8. [x] Add scoped install/setup/deploy/verify/recovery/status/port-forward scripts and safety tests.
9. [x] Commit and push tested implementation to private GitHub; unit and live kind CI both pass.

## Day 3 checklist

1. [x] Integrate Prometheus metrics into gateway, order and payment using separate per-app registries.
2. [x] Add request counts, separate 4xx/5xx outcomes, error-rate queries and latency histograms.
3. [x] Add structured JSON request/error logs with UTC timestamps and correlation identifiers.
4. [x] Add and verify basic distributed tracing: W3C propagation, SERVER/CLIENT spans and parentage.
5. [x] Configure scoped Prometheus and Grafana with immutable image digests and local-only forwarding.
6. [x] Provision eight useful operational dashboard panels and a working Prometheus datasource.
7. [x] Verify telemetry using actual traffic and an authorized scoped native payment-container interruption.
8. [x] Document the pipeline, commands, measurement semantics, resource limits and limitations.
9. [x] Commit/push implementation to the private repository and verify passing unit/live-kind CI; retain evidence.

## Day 3 verification and evidence

- Unit/safety/trace suite: **51 passed**, one pre-existing Starlette/HTTPX deprecation warning, 25.71 s; `evidence/day3/tests.txt`.
- Implementation: `9b5fec7d517dd46b68eb65a9442335fcb4c77560`. Local HEAD matched private remote main. The live acceptance record reports an initially **clean working tree** and records additional observability file hashes.
- Raw acceptance: `evidence/day3/observability-20261021T105300-day3-c56cd5922e10.json`, **PASS**.
- Acceptance ran from `2026-10-21T10:53:00.097837+00:00` to `2026-10-21T10:53:57.942991+00:00` (UTC).
- Gateway diagnostic workload: **108 actual HTTP requests** over **45.352 s**: **80 HTTP 201**, **21 HTTP 422**, **7 HTTP 503**. No transport errors were recorded. Successful orders were checked for confirmed status and 2000 cents. These are workload observations, not production availability or research benchmarks.
- Diagnostic traffic used the validated gateway Pod IP so readiness withdrawal did not hide application errors. Baseline/final checks separately passed through Service DNS, health/readiness and end-to-end order flow.
- Prometheus: **3/3 scrape targets UP**. All nine expressions behind the eight Grafana panels returned data. Server-error counters showed **7** for gateway and **7** for order: the same seven failed gateway requests propagated through the dependency chain, not fourteen independent incidents. Histograms and request/status counters populated from actual calls.
- Grafana **13.2.4**: health/database passed; eight-panel provisioned dashboard retrieved; Grafana's actual datasource proxy returned all three services. Loopback forwarded Grafana and Prometheus health endpoints both returned HTTP 200.
- Structured logs correlate all three services on successful request `day3-c56cd5922e10-0`. Failure request IDs/trace IDs also match between gateway and order; e.g. `day3-c56cd5922e10-28`, HTTP 503, trace `2d3766018fe3320286b2d83f69912235`.
- Basic distributed tracing: **five distinct linked spans** for request `day3-c56cd5922e10-0`, common trace ID `343fa893514c31296812ada4604de8d9`. Verified chain: gateway SERVER -> gateway CLIENT -> order SERVER -> order CLIENT -> payment SERVER. Previous payment-container logs preserved early spans across the deliberate restart.
- Native fault trial `day2-native-478183e561ad`: **PASS**, `evidence/day2/recovery-20261021T105312-78fdbe.json`. Guarded payment-container stop; kubelet restarted it in the same Pod, increased restart count and changed container ID; upstream containers remained stable; three subsequent healthy order checks passed. No manual restart or Pod deletion was used.
- CI [run 39587430249](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39587430249): **completed / success**, both `test` and `kubernetes` jobs. The fresh Linux kind job reproduced service checks, native recovery and non-fault observability acceptance. Metadata: `evidence/day3/implementation-ci.json`.
- Packaging/startup issues resolved: partial multi-platform archive could not be imported into kind; normal kubelet digest pull used instead. Prometheus rejected an explicit false-valued flag; omitted it (admin API remains disabled by default). Grafana download suffered an unexpected EOF and startup/provisioning took time; pinned its Linux amd64 manifest, loaded the cached image, and verified the final rollout. One earlier rollout wait exceeded its deadline before the corrected rollout succeeded. These were setup failures, not failed research trials.
- Day 3 blockers: **none**. All five Deployments finished Ready/Available. Local viewing forwards were left running; they must be restarted if the device/session stops.

### Day 3 implementation choices and limits

Application metrics exclude `/healthz`, `/readyz` and `/metrics`; otherwise probe traffic could dilute the error denominator. Labels use service, normalized method, route template and status class. Request IDs, trace IDs, raw paths, query strings and payloads do not become labels. Duration histograms use seconds and cover the existing two/three-second dependency timeouts. Quantiles are bucket estimates. Undefined zero-traffic percentages are not zero-error claims.

Request logs carry UTC timestamp, validated request ID, route/method, status, elapsed time, exception type and trace/span IDs. W3C context propagates through real HTTP boundaries. The basic OpenTelemetry exporter writes spans as JSON logs; **no Tempo/Jaeger/collector, persistent trace store or Grafana tracing UI** was added. Synchronous span logging overhead has not been benchmarked.

Prometheus/Grafana run non-root in the existing restricted namespace, with no ServiceAccount token and no new API permissions. Static Service scrape targets support the current **one replica per service** only. Monitoring uses capped resources, ephemeral storage and a 24-hour/256 MB Prometheus block-retention setting; WAL/head overhead is additional. Recreated monitoring Pods lose live data, while Git configuration and committed JSON evidence remain. No public ingress was created. Grafana has anonymous Viewer access only inside this local lab. See `docs/OBSERVABILITY.md` for deployment and interpretation.

## Day 2 verification and evidence

- Unit/safety suite: **40 passed, 1 existing Starlette/HTTPX deprecation warning**. Raw final test output: `evidence/day2/tests.txt`. The 18 added safety tests cover target/context/ownership checks, dry-run behaviour and concurrent-fault locking.
- All three Deployments report 1/1 Ready/Available, using image tag `safeheal-ai:sha256-34edfc9c74355d5b`.
- Service IPs: gateway `10.96.56.205`, order `10.96.23.37`, payment `10.96.88.201`. Both short names and FQDNs resolve to the actual ClusterIPs. These addresses are observations, not configuration values to hard-code.
- `scripts/k8s.py verify`: PASS at 2026-10-20 22:31:02 UTC. Health/readiness passed for every service; an end-to-end order returned HTTP 201, quantity 2, amount 2000 cents, status `confirmed`. Request ID `day2-676251f8cc50` appears in successful POST logs from all three services.
- Discovery/HTTP/raw cluster evidence: `evidence/day2/verification-20261020T223105-a896d6.json`.
- `scripts/k8s.py recovery` completed a dry run, followed by the authorized `recovery --execute`: **PASS**. Trial `day2-native-d15965119813`; raw record `evidence/day2/recovery-20261020T223144-4257ee.json`.
- Fault requested at `2026-10-20T22:31:44.979649+00:00`; previous payment container terminated with exit code **137**, reason `Error`, at 22:31:45 UTC.
- Payment Pod `payment-844c7c8bd-n6mmh` retained UID `7ee64010-5f44-46a0-90ff-36a8ea2ed4b8`; restart count **0 -> 1**. The CRI container ID changed from `02834e3d09ae...` to `5d9cee0a5340...`. The kubelet restarted it under `restartPolicy: Always`; the script did not delete a Pod or manually restart a service.
- Payment first observed Ready after **6.391 s**. Gateway/order retained their UIDs and restart counts. Three subsequent health/readiness/DNS/order checks succeeded, with two-second gaps; each order returned HTTP 201 and 2000 cents.
- Final checks finished at `2026-10-20T22:31:58.821720+00:00`, **13.844 s** after the stop request. This host-observed interval includes polling, CLI/API overhead and verification checks; it is **not service downtime or benchmark MTTR**.
- The JSON records retain source commit, file hashes, environment versions, Pod identities and observations. Only the first verification began with a clean working tree; the recovery record also lists the newly generated, untracked evidence directory.
- This establishes native recovery for one container-stop scenario. It does not establish liveness-threshold behaviour, Pod replacement, node failure tolerance, zero downtime or an AI benefit.

## Day 1 historical verification

- `.\.venv\Scripts\python.exe -m pytest -q`: **22 passed, 1 warning in 11.77 seconds**.
- Warning: Starlette reports that its HTTPX TestClient path is deprecated and recommends httpx2. Tests pass; migration has not been performed.
- `docker compose config --quiet`: exit 0.
- Initial image build and startup reached healthy state, but the PowerShell stderr-to-Tee wrapper reported exit 1. A direct follow-up `docker compose up -d --wait --wait-timeout 60` returned **compose_up_exit=0**, confirming startup.
- `scripts/smoke.py`: **SMOKE PASS**, exit 0; gateway `/healthz` and `/readyz` both HTTP 200; `POST /orders` HTTP 201, quantity 2, amount 2000 cents, status `confirmed`, correlation ID `day1-smoke`.
- Actual smoke order ID: `a764b8a5-6e27-4c4f-9cd6-c54829a61072`.
- `docker compose ps`: all three service containers healthy. Only gateway exposed, bound to `127.0.0.1:18080`.
- Tests cover liveness independence, validation, simulated payments, dependency errors/timeouts, malformed responses, receipt mismatch, readiness and correlation propagation. These are engineering checks, not research benchmark trials.

## GitHub verification

- Day 2 completion/evidence commit: [`a4ce10a5e5eb201e5a11cfefe971eb5d7419785e`](https://github.com/Jill-Vekariya/safeheal-ai/commit/a4ce10a5e5eb201e5a11cfefe971eb5d7419785e). Push succeeded; local HEAD matched remote `main`, and the working tree was clean.
- Final commit CI: [run 39509354163](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39509354163) **completed / success** for both `test` and `kubernetes` jobs. The latter created a fresh cluster and verified deployment, discovery, HTTP communication and native container recovery.
- This portable copy adds the final publication results to the canonical `PROJECT_STATUS.md` committed with the evidence. All three local services were rechecked after the push and remained 1/1 Ready.

- Authenticated account: Jill-Vekariya, account ID 195921415.
- Repository visibility reverified **PRIVATE** on 2026-10-21 local time.
- Day 1 baseline `9b75e000492162de9528bb18a5ffbc7219875262` passed run 39399733684.
- Day 2 implementation `43abb2318280ff455ad9ab56e9359af9f5531eed` passed GitHub Actions run **39470648959**: unit tests and actual Linux kind setup, deployment, DNS/HTTP verification and native recovery all succeeded.
- Run URL: https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39470648959
- CI metadata: `evidence/day2/implementation-ci.json`. CI uploads its raw Kubernetes JSON as a seven-day artifact; committed local JSON preserves the Windows acceptance evidence independently.
- Earlier Day 2 implementation `cf769a7` failed kind bootstrap in run 39469746459. The kubelet rejected a reserved `app.kubernetes.io/part-of` node-registration label. Replaced it with private `safeheal.ai/*` node labels; corrected local setup and CI passed. Only our newly created, empty failed kind node was recreated; existing Docker projects were left intact.
- A tool credit interruption and an offline device delayed local verification. Work resumed after the user reported the device online; no offline execution was claimed.
- Day 2 blockers: **none**. Existing non-failing Starlette deprecation warning remains a maintenance item.

## Implemented design

Gateway -> order -> payment over HTTP, with one shared application factory selected by SERVICE_ROLE. Each container runs as non-root with dropped capabilities and a read-only root filesystem. Payment creates synthetic receipts only. No external money movement or API credentials are used.

All items have a synthetic fixed price of 1000 cents. Order/payment records are not persisted. POST calls are not retried because idempotency is not implemented. Prometheus request/status/duration metrics, correlated JSON logs, an eight-panel Grafana dashboard and basic OpenTelemetry distributed spans now exist; see the Day 3 section and runbook. Gateway HTTP timeout is 3 seconds; order timeout is 2 seconds. Liveness does not call dependencies; readiness checks the dependency chain.

Kubernetes uses one replica per service, internal port 8000, ClusterIP DNS routing, a restricted Pod Security namespace and a token-free ServiceAccount with no RoleBinding. Each container requests 100m CPU/128Mi memory, limits 500m/256Mi, runs as UID 10001 with read-only root, dropped capabilities and RuntimeDefault seccomp. `/healthz` supplies startup/liveness; `/readyz` supplies readiness. See `docs/KUBERNETES.md` for the diagram, timings and commands.

The single-node lab has no high availability, public ingress, enforced NetworkPolicy or production recovery controller. The Day 3 monitoring stack is a local lab configuration, not production observability. The developer fault script uses privileged Docker access to the kind node and must not become an unrestricted LLM tool. Full least-privilege recovery policies remain Day 7 work.

## Exact next action

**Continue with Day 6: bounded, evidence-grounded AI diagnosis. Days 1–5 are complete.**

1. Read this status, WORKLOG.md, ROADMAP.md, docs/BENCHMARKS.md and the retained Day 5 dataset. Recheck canonical Git status/HEAD, the private review branch and latest CI; preserve newer work and historical failures.
2. Add a configurable provider interface, structured hypotheses, evidence references, uncertainty and deterministic fallback. Keep diagnosis read-only, bounded and separate from ground-truth labels and fault controls.
3. Use the retained six-trial evidence to exercise diagnosis with honest distinctions between mock tests, replayed data and actual paid-provider execution. Select the provider/model and budget before significant paid calls.
4. Before a new Windows live trial, restore/verify the missing Docker host API mapping without resetting unrelated resources. Fresh CI already establishes Day 5 Kubernetes acceptance. Reuse the existing lab after checking state.
5. Recovery execution, policy/RBAC/approval enforcement and action verification remain Day 7; matched A/B/C comparisons and broader repeated experiments remain Day 9. Do not infer AI benefit or detector-caused recovery from Day 5.
6. Update status/worklog/experiment records and commit/push tested changes on the private review branch under existing authorization. Main merge/public visibility or destructive operations outside the isolated test scope need the appropriate authorization.

Existing authorization covers scoped local-test work, tested commits and private pushes. Do not request passwords or tokens in chat.

## Remaining 10-day roadmap / acceptance gates

| Gate | Status | Required outcome |
|---|---|---|
| Day 1: foundation | COMPLETE | Tested running microservices AND working private GitHub baseline |
| Day 2: Kubernetes | COMPLETE | kind cluster, deployments/services/probes, service discovery and recorded native container recovery |
| Day 3: observability | COMPLETE | Real Prometheus error/latency/request metrics, JSON logs, Grafana; tracing if feasible |
| Day 4: deterministic detector | COMPLETE | Rules, SQLite lifecycle/evidence, diagnosis/correlation and real Prometheus/task-failure acceptance; PR #1 merged |
| Day 5: fault benchmark | COMPLETE | Three repeatable faults, two successful Kubernetes executions each, independent labels, native/rule observations, raw records and replay audit |
| Day 6: AI diagnosis | Not started | Provider integration, bounded read-only tools, structured hypotheses, evidence references, uncertainty and fallback |
| Day 7: safe recovery | Not started | Allowlisted operations, independent policies, approval/dry-run, RBAC, audit and verified recovery |
| Day 8: robustness | Not started | Stale/misleading/missing evidence, provider outage, duplicates and safety/failure tests |
| Day 9: experiments | Not started | Comparable A/B/C trials, raw data, uncertainty estimates, charts, negative results and limitations |
| Day 10: finalization | Not started | Reproducibility, end-to-end checks, CI, report, demo, resume/SOP narrative and interview preparation |

Use ROADMAP.md for the execution plan. Work days are milestones, not automatic calendar-based completion.

## Research protocol and final scope

Research question: can evidence-grounded LLM assistance improve incident diagnosis and safe recovery compared with deterministic approaches?

Compare A: native Kubernetes recovery, B: rule-based incident controller, C: AI-assisted diagnosis with the same independent safety gate. Plan process crash, HTTP 500 spike, latency, resource saturation, faulty deployment/configuration; cascading dependency outage is optional. Aim for at least five repeats per scenario/approach if resources allow. Record detection latency, diagnostic accuracy, recovery time/success, false positives/negatives, unsafe proposals/executions, token usage/cost and overhead. Separate diagnostic success from service recovery; retain failed trials. Never fabricate findings.

Final deliverables still required: AI diagnosis, safety/executor/verification, robustness evaluation, broader matched-trial datasets, analysis charts, research report, demo, achievement-based resume/SOP text and 15–20 interview questions. Services, Kubernetes, observability, the deterministic rule baseline and an initial three-scenario benchmark now exist; Days 1–5 form the verified foundation.

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


Day 4 loopback service smoke also passed: started the actual detector as an isolated local process with no Prometheus listener, observed three open `telemetry_unavailable` incidents through real HTTP GET requests, health 200 and readiness 503, read their diagnoses/evidence, then stopped only that process. Raw record: `evidence/day4/api-smoke.json`; console: `evidence/day4/api-smoke.txt`. This verifies real detector execution and telemetry-outage detection, not business-fault detection in the existing kind cluster. Reproduce only with unused local ports 18082/19090 using `python scripts/verify_detector_api.py`.