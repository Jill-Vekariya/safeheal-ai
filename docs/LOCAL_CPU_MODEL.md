# Run the bounded local CPU model

The optional CPU profile uses local Qwen2.5 0.5B weights, a 4096-token context and two inference threads. It selects numbered supported candidates instead of generating evidence identifiers. Full evidence validation occurs before projection, and the expanded hypothesis is independently checked afterward. Model indices cannot create an action, credential, approval, target or evidence record. Unsupported selections and provider failures remain explicit fallback or abstention.

The default provider remains disabled. The existing full-hypothesis JSON transport remains the default output mode for existing configurations. Candidate-index prompts have an explicit version and are retained in source.

## Prepare the local runtime

Run from the repository with Ollama installed:

```powershell
ollama pull qwen2.5:0.5b-instruct-q4_K_M
ollama create safeheal-qwen-cpu -f examples/Modelfile.cpu
Copy-Item examples/provider.cpu.json .local/day9/provider-cpu.json
```

The download uses the external model registry; inference for this model uses loopback. Record the resolved model digest when reproducing, because upstream tags can change. No cloud-backed model is an equivalent local run.

## Read-only retrospective diagnosis

The following is an explicit maximum of six local diagnosis requests on retained development observations. It makes no recovery call.

```powershell
$env:SAFEHEAL_LLM_PROVIDER='openai-compatible'
$env:SAFEHEAL_LLM_BASE_URL='http://127.0.0.1:11434/v1'
$env:SAFEHEAL_LLM_MODEL='safeheal-qwen-cpu'
$env:SAFEHEAL_LLM_SELECTION_MODE='candidate_index'
$env:SAFEHEAL_LLM_MAX_CALLS='6'
$env:SAFEHEAL_LLM_MAX_OUTPUT_TOKENS='256'
$env:SAFEHEAL_LLM_TOKEN_FIELD='max_tokens'
$env:SAFEHEAL_LLM_TIMEOUT_SECONDS='30'
.\.venv\Scripts\python.exe scripts/diagnose.py --output .local/new-real-diagnosis.json benchmark evidence/day5/ci-39774736343/run-03a9072a24f8
```

Use a new output path. Inspect llm_diagnoses separately from fallback counts, grounding, target agreement and observable-class agreement. A zero exit code alone does not establish real-model success or diagnostic accuracy. Do not use historical evidence to authorize a current recovery.

## Prospective matched local study

Use the existing enrolled safeheal-day7 lab and its explicit project kubeconfig. The operator harness introduces a lab-only fault; it must never be a model tool. It records the protocol and actual source hashes before injection. A fresh five-block cohort uses one real local request per AI slot, at most 256 output tokens, the same 30-second provider timeout, and the same independent policy as the rule arm.

```powershell
.\.venv\Scripts\python.exe scripts/controlled_experiment.py plan --horizon 90
.\.venv\Scripts\python.exe scripts/controlled_experiment.py run --execute --horizon 90 --provider-profile .local/day9/provider-cpu.json --output evidence/day9/new-cpu-run
.\.venv\Scripts\python.exe scripts/finalize_controlled.py evidence/day9/new-cpu-run
.\.venv\Scripts\python.exe scripts/analyze_controlled.py evidence/day9/new-cpu-run --output .local/new-cpu-analysis --no-plots
```

Choose a new cohort and analysis directory. Keep every attempted, failed, censored or unrun slot. Do not pool this profile with the original 45-second cohort or the larger-model 90-second cohort. Model confidence is uncalibrated; a supported symptom is not proof of the initiating fault. Resource limits, warm state, compact selection and shared-host contention limit generalization.


## Isolated Linux CI study

Run the existing End-to-end safe recovery demo workflow. Its separate model-study job creates a fresh safeheal-day7 lab, serves a checksum-pinned official Ollama image only on loopback with two CPUs and a 1536 MiB memory cap, checks the base weight digest from examples/ollama-runtime.json, and warms the model before measurement. It uses no provider credential or cloud inference. The model has no cluster credential or shell tool.

The job attempts five randomized matched blocks with the unchanged 90-second horizon, one model request per AI slot and the same independent policy as the rule arm. It retains partial raw data on failures. scripts/verify_model_study.py independently replays metrics and audits; success requires all 15 trials and cleanups, 120 forbidden probes denied, five real model requests, and at least one controller-verified and business-observed AI recovery. Success does not require suppressing abstentions or censored outcomes and does not establish superiority. The owned model container is removed; no global Docker reset occurs. Download real-cpu-model-study from that run.

The two Windows CPU studies are incomplete and retained separately in analysis-cpu-interrupted and analysis-cpu-rollout-failure. The latter records a cleanup timeout. A subsequent read-only business-path check passed; it does not retroactively change the failed cleanup.


Verified reference: [CI run 40206671248](https://github.com/Jill-Vekariya/safeheal-ai/actions/runs/40206671248), [current results](../evidence/public-release/CPU_STUDY.md), and [all raw outcomes](../evidence/day9/run-ci-cpu-40206671248).
