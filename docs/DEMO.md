# Four-minute SafeHeal AI demonstration

Prepare dependencies and the retained evidence before recording. Use offline replay for a predictable demonstration. A live fault takes additional setup and runs only through the guarded operator harness. Do not expose that harness as a model tool.

| Time | Screen/action | Spoken explanation |
|---|---|---|
| 0:00–0:35 | README and architecture in RESEARCH_REPORT.md | “SafeHeal is a three-service synthetic application. I studied whether a bounded model diagnosis adds value beyond a fixed rule when a separate controller controls recovery authority.” |
| 0:35–1:15 | services/diagnosis/agent.py and docs/AI_ROBUSTNESS.md | “The model ranks hypotheses supported by normalized evidence. Stale evidence, unsupported references, malformed output and unsafe fields cannot grant authority. Fallback remains low confidence. The fixed development robustness cases improved from 27 of 36 to 36 of 36; this is not held-out model accuracy.” |
| 1:15–2:00 | infrastructure/recovery/policy.yaml and services/recovery/controller.py | “There is one permitted action: restore this enrolled payment Deployment from zero to one replica. The model has no token or shell. Conditional live-state checks, a dedicated named-resource Role and API-server admission constrain the write. Ambiguous outcomes block retries.” |
| 2:00–2:50 | Run the offline reproduction command; inspect a trial, requests.jsonl and audit.json | “Measurements are replayed from raw business requests, and the integrity manifest is checked. Cleanup occurs after observation and does not count as recovery. Failed and censored outcomes remain visible.” |
| 2:50–3:35 | Retained charts and FINDINGS.md for each cohort | “The original fixed-rule cohort recovered five of five scale-zero fixtures; native behavior was censored in all five. Native Kubernetes is expected to preserve desired zero. Inspect the separately retained local-model results rather than assuming an AI advantage.” |
| 3:35–4:00 | Report limitations and future work | “This demonstrates bounded recovery engineering. It does not establish general root-cause accuracy, production safety or AI superiority. Next I would add benign controls, held-out ambiguous cases and independent multi-host trials.” |

## Offline command

```powershell
.\.venv\Scripts\python.exe scripts/reproduce.py --output .local/demo-replay
```

Choose a new output directory each time. Show the command's exit status and generated JSON. Never display `.local` credentials, token files, a raw kubeconfig or authorization headers on screen.

## Optional live controller demonstration

Only after the isolated lab is healthy and enrolled:

```powershell
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode approval
```

The first command is read-only preflight. The second intentionally creates a scale-zero lab fixture and checks dry-run, approval denial/grant, recovery verification and replay denial. It is an operator acceptance test, not model-triggered fault injection. Inspect its saved acceptance record and cleanup outcome; do not replace a failed recording with a claim that it passed.
