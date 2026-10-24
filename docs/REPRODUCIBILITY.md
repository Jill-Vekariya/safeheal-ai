# Reviewer reproduction guide

The fastest route is an offline numerical replay of retained raw data. It needs Python 3.12 and the pinned project dependencies; it does not call a provider or need Docker. A fresh live run additionally needs Docker Linux containers, kubectl, the pinned project-local kind binary, an isolated project cluster and an explicitly selected model. Timing and stochastic model output are not guaranteed to be identical.

## 1. Clean checkout and offline checks

```powershell
git clone https://github.com/Jill-Vekariya/safeheal-ai.git
Set-Location safeheal-ai
# Check out the exact final tested commit identified in PROJECT_STATUS.md.
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/reproduce.py --output .local/reviewer-replay
```

On Linux/macOS use `python3.12`, `.venv/bin/python` and the equivalent paths. Use a new replay output directory on each invocation. The reproduction command verifies the final artifact inventory, each raw-data manifest, the declared historical instrument bytes, numerical agreement with stored analysis and SQLite audit chains in read-only mode. Historical instruments are retained under evidence/final/instruments; later cleanup hardening is distinguished from as-run source. It writes only the selected output directory. Byte integrity is not proof of scientific validity; inspect the report's limitations as well.

The suite's real-provider test is intentionally opt-in, and Windows may skip a symlink test without creation privilege. The default suite uses mocks for provider behavior. A green default suite is not a real-model evaluation. Actual local-model results belong to the retained live cohort.

Optional chart regeneration (separate plotting environment is acceptable):

```powershell
python -m pip install -r requirements-analysis.txt
python scripts/analyze_controlled.py --render-analysis evidence/day9/analysis/analysis.json --output .local/baseline-figures
```

## 2. Start a new lab on an otherwise clean machine

Read docs/KUBERNETES.md and docs/SAFE_RECOVERY.md first. Do not reuse a production cluster or its credentials. The ordinary project setup uses a dedicated `safeheal-dev` kind cluster and project-local kubeconfig:

```powershell
.\.venv\Scripts\python.exe scripts/k8s.py install-kind
.\.venv\Scripts\python.exe scripts/k8s.py setup
.\.venv\Scripts\python.exe scripts/k8s.py deploy
.\.venv\Scripts\python.exe scripts/k8s.py verify
.\.venv\Scripts\python.exe scripts/verify_recovery.py
.\.venv\Scripts\python.exe scripts/verify_recovery.py --execute --mode approval
```

`setup` creates only the dedicated project lab. Deployment builds the application image from checked-out source and loads it into kind. The final `--execute` command intentionally introduces the guarded scale-zero fixture and checks the independent controller. Keep the returned evidence, including cleanup and failed outcomes. It uses no model.

The historical Windows machine has a separately enrolled `safeheal-day7` lab because its original API port is reserved by Windows. Do not reproduce that workaround on a clean host unless needed. Its explicit kubeconfig is `.local/day7/kubeconfig`; `--lab safeheal-day7` selects it. The old stopped cluster was preserved.

## 3. Fresh matched study on the existing Windows lab

The controlled runner is deliberately pinned to `safeheal-day7`. It does not silently repoint to arbitrary kubeconfigs. On a clean host, provision that separate pinned kind lab with the existing guarded helpers, then install/verify its policy using the acceptance harness:

```powershell
.\.venv\Scripts\python.exe scripts/k8s.py install-kind
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'scripts'); import verify_recovery as r; r.configure_lab('safeheal-day7'); r.lab.setup(); r.lab.deploy(); r.lab.verify()"
.\.venv\Scripts\python.exe scripts/verify_recovery.py --lab safeheal-day7 --execute --mode approval
```

The explicit helper selection fixes the dedicated name, node, context and local kubeconfig before calling setup/deploy/verify. It creates only that project lab and builds from checked-out source. The acceptance harness installs the named recovery RBAC/admission resources and retains a real fixture trial. Do not edit constants to target a production cluster.

Install/run Ollama, then download the explicit local weights and copy the tracked example into the ignored operator configuration:

```powershell
ollama pull qwen2.5:1.5b-instruct-q4_K_M
New-Item -ItemType Directory -Force .local/day9
Copy-Item examples/provider.local.json .local/day9/provider-local.json
```

Configure an ignored local provider profile as described in CONTROLLED_EXPERIMENTS.md. The final local study uses Ollama at `http://127.0.0.1:11434/v1` with `qwen2.5:1.5b-instruct-q4_K_M`, key-file string empty, max five calls, max 800 output tokens and 30-second timeout. Compare the installed model digest against `evidence/day9/local-model-environment.json`. If an upstream tag resolves to a different digest, record it as a new configuration and do not call the result an exact model repeat. Downloading model weights is an external network action; inference for this selected model runs locally. A cloud-backed Ollama tag is a different destination and is not an equivalent local reproduction.

```powershell
.\.venv\Scripts\python.exe scripts/controlled_experiment.py plan --horizon 90
.\.venv\Scripts\python.exe scripts/controlled_experiment.py setup --execute
.\.venv\Scripts\python.exe scripts/controlled_experiment.py run --execute --horizon 90 --provider-profile .local/day9/provider-local.json --output evidence/day9/new-local-run
.\.venv\Scripts\python.exe scripts/finalize_controlled.py evidence/day9/new-local-run
.\.venv\Scripts\python.exe scripts/analyze_controlled.py evidence/day9/new-local-run --output .local/new-local-analysis --no-plots
```

Every arm in this new cohort uses the declared 90-second horizon; do not pool its times with the earlier 45-second baseline cohort. Use a new output directory and keep all attempted slots. The model sees normalized telemetry only. Fresh operator-managed journal episodes do not establish continuous-production cooldown behavior.

## Failure investigation

An audit claim left running or uncertain blocks writes. Inspect the live identity/generation, saved request, audit history and actual business state before manual reconciliation. There is no automatic override/retry. A failed business check is not success merely because the Deployment became Ready. Operator cleanup is labelled and excluded from recovery time.

Dependency downloads, Docker image pulls, model availability and CI runners depend on external services. Existing evidence can be replayed without them. No production SLO, billing estimate or population-level safety claim follows from these checks.
