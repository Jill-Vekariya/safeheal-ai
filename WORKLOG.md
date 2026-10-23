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

## 2026-10-21 — Day 3 acceptance and completion

Committed implementation `9b5fec7d517dd46b68eb65a9442335fcb4c77560` and pushed to private main; remote SHA matched.
CI run 39587430249 passed both unit and live-kind jobs, including observability acceptance on a fresh Linux cluster.
Rebuilt/redeployed the exact committed source and reused the existing Windows kind cluster. Final monitoring rollouts passed.

Resolved remaining setup issues: Prometheus rejected `--web.enable-admin-api=false`; removed the flag, leaving the default disabled.
Grafana image transfer was interrupted by unexpected EOF; selected the Linux amd64 child manifest, loaded the cached image and
verified rollout. Earlier rollout waits failed during download/startup, and a corrected wait passed. These are setup failures,
not experiment trials. No cluster recreation, Pod deletion or unrelated-project change was needed.

Ran `python scripts/observe.py verify --native-fault`: PASS. Trial `day3-c56cd5922e10`, clean source checkout, 2026-10-21T10:53:00.097837+00:00 to
2026-10-21T10:53:57.942991+00:00 UTC. Actual gateway diagnostic workload: 108 requests in 45.352 s, 80 HTTP 201 / 21 HTTP 422 / 7 HTTP 503.
All three Prometheus targets UP; all expressions behind eight Grafana panels populated; Grafana datasource proxy returned all services.
Verified correlated successful JSON logs, matching 503 request/trace IDs at gateway and order, and five linked SERVER/CLIENT spans
for `day3-c56cd5922e10-0` / trace `343fa893514c31296812ada4604de8d9`. Previous payment logs retained early spans across the restart.
Native trial `day2-native-478183e561ad` passed same-Pod kubelet restart, stable upstream identities and three post-recovery order checks.
Final Service-DNS, health/readiness and synthetic-order checks passed. Raw evidence lives under evidence/day3 and the referenced Day 2-format recovery JSON.

All five Deployments are Ready. Started loopback-only Grafana port 13000 and Prometheus port 19090 forwards; both health URLs returned 200.
These forwards are temporary processes on the development PC. Updated PROJECT_STATUS.md version 4, ROADMAP.md and EXPERIMENTS.md to
Day 3 complete / full gates 3 of 10 (30%). Final evidence/status documentation is committed separately from implementation.
No benchmark MTTR, diagnostic score, overhead comparison, AI improvement or admission claim is made. Next: Day 4 deterministic detector.

## 2026-10-21 — CI runtime-client timeout correction

When the user asked whether everything was on GitHub, confirmed local/remote main matched `10d8415`,
clean working tree and PRIVATE visibility. The subsequent Actions run 39588507641 had failed in the
Day 2 native recovery step: StopContainer RPC exceeded crictl's default two-second client deadline.
Unit tests passed; observability acceptance was skipped. Retrieved and retained the original failed
trial as `evidence/day3/ci-failure-recovery-20261021T110016-45fd40.json` and run metadata as
`evidence/day3/ci-failure-39588507641.json`. No verified CI recovery success was inferred from the timeout.

User explicitly requested making the run successful. Verified installed crictl 1.36.0 help: global
`--timeout` controls runtime-client timeout, while `stop --timeout` controls kill grace. Added only
`--timeout=30s` before `stop`, retaining zero-second kill grace, existing 45-second host subprocess
bound, one-shot injection/no retries, target ownership validation, fault lock and recovery assertions.

Corrected code: 51 tests passed / one existing warning in 15.21 s, saved tests-rpc-timeout-fix.txt.
Dry run passed; actual local native recovery passed, raw record `evidence/day2/recovery-20261021T110508-9fb946.json`.
Same payment Pod/new container/restart count increased 1 -> 2; upstream containers stable; three healthy
order checks passed. Documentation and experiment register updated. Correction commit reruns the full
GitHub suite; final run state is verified after publication rather than assuming the timeout increase succeeded.

## 2026-10-21 — Day 4 offline implementation checkpoint (Asia/Kolkata)

User requested the incident service, deterministic rules, correlation, lifecycle, timestamped evidence, rule diagnosis, tests and a commit. Read the entire supplied Day 3 portable handoff. Desktop Commander listed Jill-Vekariya10 offline. Direct private Git access could not authenticate; GitHub plugin discovery confirmed it was not connected (recently suggested already, so no duplicate suggestion). No credential request or public publishing was attempted.

Found prior Day 3 source copies in the shared workspace; the latest includes observability and the crictl timeout fix but no Git metadata. Copied it into this session's workspace and created an isolated snapshot baseline, recording every baseline tracked-file SHA-256 in evidence/day4/source-provenance.json. This history is explicitly separate from canonical main; no remote verification, canonical modification or existing-cluster action is claimed.

Implemented a separate FastAPI polling service under services/incidents: three bounded GET-only Prometheus matrix reads, actual source-time freshness and conservative non-extrapolated counter increments; four versioned rules with sample minima and hysteresis; persistent pending/open/recovering/resolved lifecycle; transactional SQLite evidence/verdict/history/diagnoses; active fingerprint uniqueness/replay guards; topology-based suspected dependency links with evidence references. No model/executor/Kubernetes-write dependency exists. Added local run and synthetic verification commands, full runbook and README/architecture references. Existing Day 3 service code and runtime dependency lock are unchanged.

Verification: project-local Python 3.12 virtual environment installed the existing exact requirements.lock. Initial full suite had 101 passes and one trace-export failure because this host sets parentbased_traceidratio sampling at 0.01. Corrected only the trace tests to select parentbased_always_on; failure summary retained. Full suite then passed 107 tests, one existing Starlette/HTTPX warning; 56 additional detector/integration tests. Actual order FastAPI 503 responses and real exported metrics feed the detector in an integration test; transport/scrape timestamps are simulated. Synthetic scenarios confirm four deterministic failure classes with pending -> open -> recovering -> resolved and evidence/diagnosis. Raw results are retained in evidence/day4.

Canonical checklist remains: reconnect computer or GitHub, inspect current instructions/HEAD/worktree/private visibility, reconcile/apply patch, run full tests and actual Prometheus/kind detector acceptance, then canonical commit/private push/CI verification. The isolated implementation commit and archive manifest preserve completed work. Overall full gates remain 3/10; Day 4 live gate is in progress. No Day 5 fault benchmark, provider call, automated recovery or research effectiveness claim was made.


Day 4 loopback service smoke also passed: started the actual detector as an isolated local process with no Prometheus listener, observed three open `telemetry_unavailable` incidents through real HTTP GET requests, health 200 and readiness 503, read their diagnoses/evidence, then stopped only that process. Raw record: `evidence/day4/api-smoke.json`; console: `evidence/day4/api-smoke.txt`. This verifies real detector execution and telemetry-outage detection, not business-fault detection in the existing kind cluster. Reproduce only with unused local ports 18082/19090 using `python scripts/verify_detector_api.py`.

## 2026-10-21 — Day 4 reconnection and canonical integration

User reported the computer connected. Jill-Vekariya10 was online; canonical working tree was clean, local/remote main both matched bc06bf52efe19db592932b824de5da864c8b8c8d and repository visibility remained PRIVATE. No parent/nested AGENTS.md appeared in the checked locations. All five Deployments were 1/1 Ready. Latest Day 3 CI run 39589628381 was completed/success. Applied the isolated implementation patch only after a successful canonical `git apply --check`.

The first Windows suite reported 106 passes and one failure in the existing latency observation test: Windows woke a requested 30 ms sleep early and the observed interval was 23.98 ms. Retained the full process transcript in evidence/day4/windows-initial-tests.txt. Changed only that test to wait until a monotonic deadline; the production middleware is unchanged. Subsequent suites passed. Added developer-harness safety/ground-truth tests, bringing the suite to 118 tests.

The first routing acceptance trial day4-live-463536f6246c detected and resolved a real payment scrape outage and restored the exact Service selector; final DNS/health/order and stable Pod/container checks passed. Its overall acceptance remained FAILED because the harness also required gateway 5xx responses. Those were absent: established internal HTTP keep-alive connections continued serving orders after Service endpoint withdrawal. The raw failed record remains unchanged.

After adding direct fresh payment connection probes, routing trial day4-live-b54f1ad56622 FAILED its incident-opening assertion because Prometheus also retained a working existing connection: all payment `up` samples stayed 1. The Service was restored in finally; a separate `scripts/k8s.py verify` passed (evidence/day2/verification-20261021T163453-1a78ec.json). No rule threshold was lowered to relabel this unobservable condition as detected. Both failed routing records are retained and demonstrate a scrape/connection observability limitation, not controlled research false-negative rates.

Added a separate fixed payment-task pause harness with the existing cluster/namespace/CRI identity guards, exact container-ID validation, fault lock, node-side timed resume, bounded containerd command/connect timeouts and recovery assertions. Verified installed ctr pause/resume help and timeout semantics before execution. This is a privileged developer fault harness; the detector modules contain no cluster-tool calls. This check does not prove operating-system privilege separation. Native Kubernetes liveness may restart payment during the pause; the detector does not remediate it. CI now reproduces this observable fault with real Prometheus and preserves Day 4 evidence.


## Day 4 final local engineering acceptance — PASS

Trial `day4-pause-670cd6f0b91f` passed from 2026-10-21T16:41:02.324443 to 16:43:49.611107 UTC. Fixed identity-checked payment task pause; node-side pause/resume command completed with exit 0. Actual Prometheus observations opened payment scrape outage, gateway/order latency and gateway/order 5xx incidents. All five completed pending -> open -> recovering -> resolved; error incidents carried suspected-payment correlation links and evidence IDs. Actual gateway workload: 250 responses, 187 x 201 / 63 x 503. Final fresh DNS/health/readiness/order checks passed (confirmed, 2000 cents). Payment retained its Pod UID with native restart count 2 -> 3; upstream identities/counts stayed unchanged (0 -> 0). Detector remediation/model calls: none. Runtime source hashes, raw query matrices and failed checks are retained in evidence/day4.

Final Windows suite: 118 passed / one existing dependency warning in 28.26 s, evidence/day4/windows-tests.txt. Linux suite: 118 passed. Expanded CI installs the existing locked runtime, forwards Prometheus locally, executes the guarded dry run and observable task-pause check in fresh kind, and uploads Day 4 evidence. Canonical implementation/docs/evidence are committed privately; publication SHA/CI is verified after commit and appended to the portable completion copy. Day 4 checklist 8/8; full gates 4/10 (40%). Next: Day 5 controlled fault runner/ground truth/native and rule-diagnosis baselines. No controlled benchmark, MTTR, model benefit or OS privilege-separation claim is made.


Automatic approval review rejected a combined commit/default-main push command before execution, stating that exact default-branch publication was not clearly authorized. No main push occurred. Continued with the materially safer alternative: a separate day4-incident-baseline branch and reviewable private publication. Main remains at the verified Day 3 tip until a separately authorized merge. The requested implementation, tests and commit are completed on that review branch; CI is checked there.


## CI warm-up baseline correction

Initial branch CI run 39638639803 (76d78187619e45da87fbe85601e37c822e13b860) passed the unit job and failed the new live acceptance **before fault injection**. Raw CI trial day4-pause-3416e684d4a5 had two baseline polls: the first recorded incomplete warm-up telemetry; the second had all targets UP, eligible zero-error traffic, no telemetry problems, and that transient incident already resolved without opening. The harness incorrectly rejected any historical incident. Failure logs, metadata and raw trial remain under evidence/day4.

Changed only harness readiness: require eligible current telemetry and no active incidents; resolved warm-up history remains visible and no longer blocks a healthy baseline. Active incidents still block acceptance. Added two regression tests; suite now 120 tests, rules/thresholds/state machine unchanged. No fault is automatically retried after ambiguous injection. The corrected commit runs the full CI suite again; its final result is verified after private review-branch publication. A console Unicode error while printing the downloaded log was a retrieval-display issue; the UTF-8 failure file and downloaded raw JSON were already retained.


## 2026-10-21 - Day 4 GitHub pull-request completion

User requested completing the GitHub compare/pull-request banner. Verified a clean canonical day4-incident-baseline checkout, private repository, remote branch at 87e2ec25e9264fe0d48b3e5fae97c39762dc03e4, and no divergence from the Day 3 base (main behind by the two intended Day 4 commits). Both jobs in CI run 39640164313 succeeded, including real Kubernetes/Prometheus acceptance. Created PR #1: https://github.com/Jill-Vekariya/safeheal-ai/pull/1.

Updated the current handoff to link the review/merge record and distinguish historical pending-publication notes. This checkpoint changes documentation only. PR and subsequent main checks establish final integration status; do not infer success from a queued run. No new local fault or model call was performed. Full project gates remain 4/10; Day 5 is next.


## 2026-10-21 - Bound Service-readiness settling after native recovery

User requested successful GitHub checks. Latest candidate 0498156 had green push/PR runs, but inspection found older PR run 39646024404 failed in native recovery: after the scoped container stop/restart and Pod Ready waits, the first Service HTTP probe failed with connection refused. Retained the original run metadata/log and recovery-20261021T174308-4dbb2d.json under evidence/day4. Passing later runs do not erase that failure or prove absence of a readiness propagation race.

Added a 90-second, monotonic, read-only settling phase that checks DNS, healthz and readyz through actual Service addresses. Each attempt shares one bounded subprocess budget across Pod lookup and exec, capped at 30 seconds or the remaining overall deadline. Failed attempts remain in the raw recovery record; persistent unavailability fails closed. After settling, all existing Pod/container identity checks and three unretried full order checks remain mandatory. Fault injection remains one validated CRI stop, with no retry. Runtime application code, detector rules, and workflow acceptance steps are unchanged.

Eight regression cases cover GET-only versus normal one-POST mode, transient readiness failures, persistent timeout, malformed/unconfirmed probe responses, shared timeout accounting, and failure of the final order check without retry or false success. Windows full suite: 128 passed, one existing warning; evidence/day4/windows-readiness-tests.txt. Full Linux and fresh-kind acceptance are checked after the correction is pushed through PR #1. No additional fault was injected into the user's existing local cluster. Main merge still depends on explicit authorization after the earlier automatic approval rejection.

Text console transcripts normalize line endings and trailing whitespace for Git review; the downloaded raw failure JSON is preserved unchanged.


## 2026-10-22 — Day 5 implementation and verification checkpoint

Read the portable Day 4 handoff and preserved its scope, private repository and review-branch publication policy. The development PC initially appeared offline, so authored changes against the saved Day 4 snapshot without overwriting canonical history. After reconnection, verified private visibility, clean main at 156da54a5de4ddf4977676ebf7ce29310089fb0f, merged Day 4 PR #1 and successful CI39651662574. Created day5-fault-benchmark; applied only the reviewed patch after git apply --check. A broad canonical source export was rejected by automatic approval review; continued with targeted file comparisons and direct canonical tests instead.

Implemented bounded expiring application faults plus one-shot identity-checked CRI stop, seeded repeated experiment plans, before-injection ground-truth checkpoints, real gateway/payment samples, concurrent read-only rule observation, raw Prometheus data, SQLite incidents, platform state/events, recovery attribution and durable summaries. Final acceptance reconciles drained request samples, final platform identity and final eligible/resolved telemetry; successful run health/shutdown are required too. Linux local-process execution is separately labelled and cannot satisfy the Kubernetes gate. No model or rule recovery executor was added; Day 4 thresholds are unchanged.

Canonical first Windows suite:16 failed/257 passed/1 skipped; full transcript retained. Corrected platform-absolute default path and mocked Linux path rendering only, then 274 passed/1 skipped. After finalization-race regression coverage, canonical suite:288 passed/1 skipped/one existing dependency warning in37.35s. The Windows symlink creation test is skipped for unavailable privileges; Linux exercises it. Isolated older Linux source:268 passed/one warning in2.63s. Real local-process startup smoke had previously passed but is not Kubernetes fault evidence.

Docker Desktop was stopped at reconnection. Starting it exposed a pre-existing node publishing problem: internal API live, expected kind identity, configured loopback6443 binding, but Docker's active published mapping empty. Saved the node network/binding state; attempted scoped node restart and same-network reconnection preserving original IPv4/IPv6 addresses. All operations target only safeheal-dev-control-plane. Live acceptance and final publication are pending this checkpoint; failed setup is not counted as a fault trial. CI includes a six-trial seeded benchmark with raw artifact retention and a45-minute job bound.

## 2026-10-22 — Day 5 live benchmark acceptance and retained results

Implementation commit 31f2af628e70487f1cd0098403bd3ab2304a4d46 was pushed to the private day5-fault-benchmark review branch. Full CI39774736343 passed both jobs. Linux canonical suite: 289 passed, one existing warning in 3.85 seconds; Windows canonical suite remains 288 passed, one privilege-related skip and one warning. The workflow also passed deployment, discovery/HTTP, native recovery, observability and the earlier Day 4 detector acceptance before the new benchmark.

Actual benchmark run-03a9072a24f8 executed from 12:05:12.009502 to 12:22:41.030610 UTC. All six trials completed successfully with independent verified ground truth and eligible matched rule detections: two HTTP 500, two process-crash and two latency trials in seeded order. Final service health and owned-forward shutdown passed. Both crashes show same Pod/new container/exit 137 and restart counts 2→3→4, with stable upstream identities. HTTP/latency leases expired normally with no container restart. The rule observer executed no recovery action.

Downloaded the original CI artifact into a separate staging folder and retained the complete benchmark run plus CI metadata/logs under evidence/day5/ci-39774736343. Summary replay matched JSON content and CSV bytes; 15,180 request rows and 212 telemetry snapshots were reconciled, and all six SQLite integrity checks passed. Original artifact files were independently compared by SHA-256 with the retained copy. An initial read-only SQLite inspection created only empty WAL/shared-memory auxiliaries; these audit-created files are removed after checking they were absent from the original, and the final integrity audit uses immutable read-only access. Raw downloaded evidence is preserved.

Individual times, wall-clock timestamps, native-versus-expiry attribution, first-diagnosis limitations and reproduction commands are recorded in evidence/day5/README.md and EXPERIMENTS.md. No benchmark attempt in this batch failed or was censored. Earlier Windows test failures and local Docker publishing setup failures remain preserved as engineering evidence. Detection in six trials does not establish general root-cause accuracy, population error rates, production reliability or an A/B/C improvement.

The Windows kind node's internal API remained live but Docker's host API mapping stayed empty after scoped restart/network repair; no cluster deletion or global Docker restart was used. Windows live fault trials were not performed. Successful actual Kubernetes acceptance comes from the fresh Linux CI cluster.

Updated the current project status, experiment register, roadmap, README and evidence index for Day 5 completion: 8/8 tasks; full gates 5/10 (50%). This following commit retains data/documentation and raw-byte Git attributes; executable source and CI workflow remain identical to the tested implementation. Private review-branch publication is verified after commit; no main merge, model call or recovery executor is part of this checkpoint. Next is Day 6 bounded read-only AI diagnosis, with provider/budget selection before significant paid calls.

## 2026-10-22 ? Final Day 5 verification and local environment repair

Reconnected the canonical PC and confirmed CI39780164487 for evidence commit0b1e4cb succeeded in both jobs, with 289 Linux tests and six further benchmark trials. Retained full workflow metadata/logs. Rechecked all39 initial dataset hashes and all six databases; replay matched JSON content/CSV bytes. Current Windows tests:288 passed, one privilege-related skip, one warning. Empty audit-created WAL/shared-memory auxiliaries were archived in ignored local storage after empty-WAL checks; final reads used immutable mode.

The original kind API port49693 refused connections and Windows denied binding it. Created the owned, restricted safeheal-dev-api-proxy container, publishing127.0.0.1:18082 and forwarding TLS without credential mounts; updated only project kubeconfig endpoint after certificate-verified readiness succeeded. Original mapping remains unresolved; proxy restores access without cluster recreation/global Docker reset.

Normal docker build failed at Docker Hub metadata resolution. Exact dependency/package metadata hashes matched the cached immutable image, so built a separate offline source-refresh image, loaded it into the same kind node, server-validated current manifests and deployed safeheal-ai:sha256-311922d1b56ffd31. All three rollouts and DNS/health/readiness/order/correlation checks passed. Benchmark preflight and all10 deployed payment source hashes matched current checkout. Failed preflight/build and successful repair/deployment provenance are separately retained. No local fault batch was performed during repair.

Updated status, experiment register, roadmap and final verification note. Publication is documentation/evidence only on the private Day5 branch with [skip ci]; executable implementation remains identical to successful full CI39780164487. The final pushed hash and clean tree are verified separately after commit. Day5 complete; Day6 next.


## Day 6 implementation and verification — 2026-10-23

Implemented configurable disabled-by-default JSON provider, fixed read-only incident/telemetry tools, bounded evidence normalization, strict cited hypotheses, confidence/abstention/fallback handling and independent ground-truth scoring. Source/tests: services/diagnosis, scripts/diagnose.py, tests/test_diagnosis*.py. Protocol: docs/AI_DIAGNOSIS.md.

Replayed all six original Day 5 Kubernetes trials using telemetry/platform observations only, with a fixed first-observation +105s cutoff. Ground truth is read after each diagnosis. Mocked HTTP transport and deterministic fallback each obtained 6/6 grounded, target-matched and observable-class-matched outputs. Reports and input SHA-256 hashes are retained under evidence/day6. No new fault trials, real-model calls, recovery execution, held-out accuracy estimate, or comparative AI-benefit claim is made. Original Day 5 artifacts remained unchanged.

Windows final full suite: 337 passed, 2 skipped, 0 failed; one existing dependency warning. The skips are symlink privilege and unavailable real-model opt-in/credentials. Initial targeted run: 42 passed, one failed, one skipped; it exposed that the scorer checked only cited record hashes. Corrected to verify every bundled record, and retained the failure description. Additional malformed JSON, oversized confidence and corrupt-database handling passed. CLI benchmark replay passed. Final test log and acceptance manifest are retained.

Canonical private review branch day6-ai-diagnosis begins at e04a506. No main merge. CI publication/final result is checked after push. PC connected; Docker engine stopped, so no local cluster operation was attempted. Next: independent Day 7 safe-recovery controls; real-provider quality remains unmeasured until an explicit model/call budget and credentials are available.

Publication boundary: automatic approval review rejected the combined local commit/private push as an unapproved disclosure to GitHub. The rejected terminal command did not run. Local commit is explicitly authorized and is completed separately; no push or Day 6 CI run is claimed. Remote publication requires explicit approval.


## Day 6 delivery and repository-state recheck - 2026-10-23

Implementation remains 33b27a43b18f808474e9778ce432aebc789d69e0. All retained source hashes match; both six-trial reports pass grounding recheck. Credentials remain unavailable. GitHub main remains Day 4 at156da54; Day5 branch e04a506 and PR2 are published, Day6 is local only. ADMIN access does not enable branch protection on this private repository plan: GitHub returns403 requiring an eligible upgrade or public visibility. Neither purchase nor visibility change was performed. The proposed docs/MAIN_BRANCH_PROTECTION.json is not applied or enforced. Automatic approval review rejected the source/documentation/benchmark-evidence push again after broad user authorization, requiring explicit destination-and-payload authorization; do not bypass it. No Day6 remote CI or main integration is claimed. See PROJECT_STATUS_Day6_2026-10-23.md and evidence/day6/publication-blockers.json.
