# SafeHeal AI ? Day 5 final verification

**Status: DAY 5 COMPLETE, 8/8 tasks; project progress 5/10 gates (50%).** Verification date: 22 October 2026. This final record supersedes the earlier connection-blocked verification note.

## Verified outcomes

| Check | Result |
|---|---|
| Three reproducible Kubernetes fault scenarios | Process crash, HTTP 500, latency; two successful trials each in the retained initial dataset |
| Independent ground truth, detection and recovery | All six retained trials verified |
| Original artifact integrity | All 39 SHA-256 hashes matched again after local repair |
| Raw records | 15,180 gateway requests; 212 telemetry snapshots; six detector databases |
| Database integrity and summary replay | All six databases passed; replay matched JSON content and CSV bytes |
| Current Windows unit suite | 288 passed, one privilege-related skip, one existing dependency warning |
| Final full CI for evidence commit 0b1e4cb9b344a41415cbc1789038920dd35c695d | Run 39780164487: both jobs successful; Linux suite 289 passed |
| Final CI live checks | Deployment, native recovery, observability, deterministic detector and six repeated benchmark trials passed |
| Local Kubernetes API | Restored via TLS passthrough on https://127.0.0.1:18082 |
| Current local application | Deployed image safeheal-ai:sha256-311922d1b56ffd31; all three rollouts passed |
| Local business verification | DNS, health/readiness, synthetic order and correlated service logs passed |
| Local benchmark preflight | Passed; explicit local-test fault opt-in, source match and no active fault lease |
| All deployed payment Python files | All 10 source hashes matched the checkout |
| Repository visibility | Private; publication remains on day5-fault-benchmark |

The second CI run's logs also record six successful trials. Its logs/metadata are retained separately; the original six-trial dataset remains the reported initial benchmark and was not overwritten or pooled with later runs. No additional fault trial was executed as part of the local repair.

## Local repair and build details

Docker's original kind API mapping on port 49693 remained absent, and Windows refused binding that port. The workaround uses the separately labelled container safeheal-dev-api-proxy on the existing kind network and publishes only 127.0.0.1:18082. It forwards raw TLS to safeheal-dev-control-plane:6443. Kubernetes still verifies certificates and client authentication.

Only the project-local .local/kubeconfig endpoint was updated; credentials and the user's default context were unchanged. A local backup is .local/kubeconfig.before-api-proxy. No kubeconfig or credential file is committed. The proxy has no mounts, a read-only filesystem, dropped capabilities, no-new-privileges, and resource/concurrency limits. Its configuration and exact relay source are retained in evidence/day5/local-repair.

The normal Docker build failed while Docker Hub resolved python:3.12-slim. A local source-refresh image was instead built from the existing immutable application image after exact requirements.lock and pyproject.toml hash equality was checked. The refreshed image replaced /app/services with current source. The fallback Dockerfile and provenance are retained. This local fallback is distinct from the normal Dockerfile build that passed in fresh CI. A future normal rebuild requires registry access.

The proxy restores local access; it does not repair Docker's original mapping. Keep it running for local work. If it is stopped, start only this known project container and recheck the scoped API before proceeding. Do not recreate the cluster or reset unrelated Docker resources automatically. Running kind setup can export the old endpoint again; inspect the project endpoint before reusing setup.

## Evidence and publication

- Accepted dataset: evidence/day5/ci-39774736343/run-03a9072a24f8
- Final full CI metadata/logs: evidence/day5/ci-39780164487
- Repair, deployment, source checks and verification: evidence/day5/local-repair
- End-to-end local verification: evidence/day2/verification-20261022T131742-68c7dd.json
- Benchmark protocol: docs/BENCHMARKS.md

The independent read-only SQLite audit created empty WAL/shared-memory auxiliaries. Their empty WALs were checked and the auxiliaries moved outside tracked evidence. Final database checks used immutable read-only mode; original benchmark bytes still match the retained audit.

The final publication update contains documentation and evidence only. Application source, tests, infrastructure, dependency lock and CI workflow remain unchanged from the successful full CI. It uses a documentation-only commit with [skip ci] to avoid rerunning the identical 23-minute live suite. Do not claim a new full CI run for this documentation commit; run 39780164487 validates its unchanged implementation.

## Continue tomorrow

Read the updated PROJECT_STATUS_Day5_Complete.md handoff, then canonical PROJECT_STATUS.md, WORKLOG.md, EXPERIMENTS.md and actual Git state. Day 5 has no pending acceptance item. Begin Day 6 bounded, read-only AI diagnosis after selecting the provider and an explicit call/token/cost budget before paid calls.

Keep diagnosis separate from execution. Day 7 safety execution and Day 9 controlled A/B/C comparisons remain future work. Two repetitions and symptom detections do not establish root-cause accuracy, production reliability or AI benefit. No main merge or public publication was performed.

Repository: https://github.com/Jill-Vekariya/safeheal-ai/tree/day5-fault-benchmark

Successful full CI: https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/39780164487
