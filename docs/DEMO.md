# SafeHeal AI: end-to-end GitHub demo

[Run the demo in GitHub Actions](https://github.com/Jill-Vekariya/safeheal-ai/actions/workflows/demo.yml) · [Research report](RESEARCH_REPORT.md) · [Recovery contract](SAFE_RECOVERY.md)

## Earlier verified reference run

[Open the successful demo](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40145365194) · [Rendered result summary](../evidence/demo/ci-40145365194/summary.md) · [Download artifact](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40145365194/artifacts/12580581966) · [Permanent archive](../evidence/demo/ci-40145365194/artifacts.zip)

The run at 9f6e268d2b5daad8caaff87e1c2e6c8b457d74de passed all twelve required stages and both fresh recovery modes. Its downloaded manifest and audit chains verified; raw logs and artifact hashes are retained under evidence/demo/ci-40145365194. Linux tests: 537 passed, 1 opt-in skip. Windows: 536 passed, 2 existing skips. [Full normal CI](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40145364797) also passed.

The first demo (40145170673) retains its actual successful workflow and delivery verification separately. Explicit inclusion of the selected report paths was then added and verified in the reference run above. No original trial outcome was replaced.

Show a real synthetic order, a controlled lab failure, independently authorized recovery and a confirmed order after recovery. The GitHub run also replays diagnosis and the controlled experiments, checks raw-data integrity and verifies audit chains.

## Current verified two-job demonstration

[Verified current run](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40206671248) completed both jobs at fd809cae41b60c62b59bd2fc2e2377f5d487b163. The original demo job verifies fresh native/autonomous/approval recovery and labels its historical diagnosis replay as fallback. The independent model-study job runs all fifteen matched trials with real loopback CPU inference, validates raw metrics/audits, checks final health and removes its owned model container. Both retain failed or incomplete outcomes. Allow roughly 30-45 minutes for a fresh run, including image/model pulls and 15 real observation windows.

Download both safeheal-demo-evidence and real-cpu-model-study. The latter includes protocol, every raw trial, usage where reported, model/weight digests, warmup metadata, numerical findings and verification. See [current study](../evidence/public-release/CPU_STUDY.md). The two job reports have distinct scopes; the standard demo summary alone is not proof of the model study.

## One-click demonstration

1. Open **Actions → End-to-end safe recovery demo** in this public repository.
2. Select **Run workflow**, choose **main**, and start the run.
3. Open the run and expand the numbered stages below. Allow time for image pulls, cluster setup and the real observation windows.
4. Open the run's **Summary**: it reports PASS only when all required stages and both fresh recovery trials passed.
5. Download **safeheal-demo-evidence** and **real-cpu-model-study** from **Artifacts**. It contains a machine-readable result, summary, file hashes, diagnosis/robustness/raw-measurement replays, fresh acceptance records and audit databases. GitHub retains this download for 14 days; retained reference runs are archived separately in this repository.

Repository write access is needed to start a manual run. See [GitHub's manual workflow instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). No provider key, model selection, cluster URL or shell-command input is requested.

## What appears on screen

| Stage | What actually runs | Evidence to show |
|---|---|---|
| 1. Tests | Application, evidence validation, provider failures, duplicate notifications and recovery safety tests | Pytest result in the stage log |
| 2. Reproduction | All retained cohorts and exact-source robustness comparison | Replay JSON; synthetic 27/36 → 36/36, labelled development evidence |
| 3. Diagnosis | Deterministic fallback replay of six retained benchmark incidents | Grounded diagnoses and explicit fallback in diagnosis.json |
| 4. Healthy application | Fresh Docker-kind cluster, gateway/order/payment Deployments, Service DNS and HTTP checks | Ready services and a confirmed synthetic order |
| 5. Native recovery | Guarded payment-container failure and Kubernetes recovery | Native acceptance record |
| 6. Autonomous recovery | Real executor token, policy-readiness gate, forbidden calls, scale-zero fixture, dry-run and operator-enabled controller | New autonomous acceptance record; verified result |
| 7. Approval recovery | A second fixture, unapproved denial, expiring operator approval, recovery and replay denial | New approval acceptance record; verified result |
| 8. Observability and detection | Actual traffic, Prometheus, dashboards, traces and a bounded payment-task failure | Observability and deterministic detector evidence |
| 9. Final business verification | Service DNS, health/readiness and another confirmed order | Final service checks |
| 10. Summary and audit | Only trials created after this run began; source hashes, three consecutive Ready observations and audit-chain integrity | result.json, summary.md and manifest.json |

The diagnosis replay uses historical evidence; the two recovery fixtures are freshly created by the trusted operator harness. They are distinct episodes. The standard demo job makes no live-LLM closed-loop performance claim; the separate model-study job retains its own measured outcomes. The model receives no shell, cluster credential or approval authority. The independent action remains only the enrolled payment Deployment's desired-replica change **0 → 1**.

A failed or missing step, a failed business check, operator restoration, an invalid audit or a missing mode produces **FAIL / INCOMPLETE**. Old trials cannot qualify as fresh success. Failed artifacts remain available for investigation.

## Four-minute presentation

Prepare a completed run before presenting. Executing the full workflow takes longer than the four-minute walkthrough.

| Time | Show | Explain |
|---|---|---|
| 0:00–0:30 | README and this page | “SafeHeal separates fallible diagnosis from independently authorized recovery.” |
| 0:30–1:00 | Tests, reproduction and diagnosis stages | “Evidence must be fresh, attributable and supported. Fallback and mocked engineering tests are labelled.” |
| 1:00–1:40 | Healthy application and native recovery logs | “Three real services communicate through Kubernetes DNS. A confirmed order verifies the business path.” |
| 1:40–2:40 | Autonomous and approval acceptance records | “Eight forbidden calls are denied in each mode. Dry-run performs no action. Operator approval, conditional writes and admission bound the one permitted transition.” |
| 2:40–3:15 | Summary, audit events and final order | “Recovery needs three consecutive Ready observations and a separate confirmed business order. Replays are denied and cleanup is checked.” |
| 3:15–4:00 | Charts and limitations below | “The rule restored this deliberately policy-addressable fault. The earlier larger-model requests timed out; the new CPU study records its actual outcomes separately. General AI benefit and reliability remain unproven.” |

## Results to explain honestly

| Separate study | Native | Fixed rule + independent policy | AI arm |
|---|---|---|---|
| Original, 45-second horizon | 0/5 within horizon; actual recovery time unknown | 5/5; observed mean 19.0378 s | Five slots explicitly not run without a provider |
| Local-model, 90-second horizon | 0/5 within horizon; actual recovery time unknown | 5/5; observed mean 30.5436 s | Five actual requests timed out; no validated output or AI recovery |
| Fresh Linux CPU model, 90-second horizon | 0/5 within horizon | 5/5; observed mean 14.107 s | 2/5 recovered; four validated diagnoses, one invalid provider response; observed-only mean 14.836 s |

Do not pool the cohorts or label the horizon as observed MTTR. The demo's recovery checks are engineering evidence, not additional randomized study trials.

![Separate 90-second local-model cohort](../evidence/day9/analysis-local/recovery_comparison.png)

[Raw local-model cohort](../evidence/day9/run-local-20261025) · [Analysis and limitations](../evidence/day9/analysis-local/FINDINGS.md) · [Original cohort findings](../evidence/day9/analysis/FINDINGS.md)

## Copy-paste local demonstration

### Fast offline review

From an installed checkout, choose a new output directory:

~~~powershell
.\.venv\Scripts\python.exe scripts/reproduce.py --output .local/demo-review-01
.\.venv\Scripts\python.exe scripts/compare_robustness.py --output-dir .local/demo-robustness-01
.\.venv\Scripts\python.exe scripts/diagnose.py --output .local/demo-diagnosis-01.json benchmark evidence/day5/ci-39774736343/run-03a9072a24f8
~~~

Show the exit status and replay JSON. This route needs no Docker or provider. On Linux/macOS, use .venv/bin/python.

### Existing verified Windows lab

Use the canonical checkout and healthy safeheal-day7 lab:

~~~powershell
Set-Location C:\Users\jillv\Projects\safeheal-ai
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode autonomous
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode approval
~~~

The first command is read-only preflight. Each execute command intentionally creates one guarded scale-zero fixture, invokes the separate credential-limited controller, verifies a confirmed order and records cleanup. The returned trial ID locates evidence/day7/<trial-id>/acceptance.json and audit.sqlite3. Keep every outcome.

### Fresh machine: Windows PowerShell (x86_64)

Prerequisites: repository access, Git, Python 3.12, Docker using Linux containers, and kubectl. The setup installs pinned project-local kind and creates only the dedicated project cluster.

~~~powershell
git clone https://github.com/Jill-Vekariya/safeheal-ai.git
Set-Location safeheal-ai
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe scripts/k8s.py install-kind
.\.venv\Scripts\python.exe scripts/k8s.py setup
.\.venv\Scripts\python.exe scripts/k8s.py deploy
.\.venv\Scripts\python.exe scripts/k8s.py verify
.\.venv\Scripts\python.exe scripts/verify_recovery.py
.\.venv\Scripts\python.exe scripts/verify_recovery.py --execute --mode autonomous
.\.venv\Scripts\python.exe scripts/verify_recovery.py --execute --mode approval
~~~

### Fresh machine: Linux (x86_64)

Use the same Git/Docker/kubectl prerequisites:

~~~bash
git clone https://github.com/Jill-Vekariya/safeheal-ai.git
cd safeheal-ai
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python scripts/k8s.py install-kind
.venv/bin/python scripts/k8s.py setup
.venv/bin/python scripts/k8s.py deploy
.venv/bin/python scripts/k8s.py verify
.venv/bin/python scripts/verify_recovery.py
.venv/bin/python scripts/verify_recovery.py --execute --mode autonomous
.venv/bin/python scripts/verify_recovery.py --execute --mode approval
~~~

See [reproduction](REPRODUCIBILITY.md) for the full observability, detector and matched-study protocol. Never expose the operator fixture harness as a model tool. Keep token files and kubeconfigs off screen and out of Git. Investigate a running/uncertain claim using [SAFE_RECOVERY.md](SAFE_RECOVERY.md); no automatic write retry or override exists.
