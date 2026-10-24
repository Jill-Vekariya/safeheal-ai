# SafeHeal AI — Day 9 controlled experiments: baseline study complete, AI arm pending

**Updated:** 24 October 2026. **Day 9 status: PARTIAL. Overall completed milestones remain 8/10 (80%). Do not mark Day 9 or the full project complete.**

Canonical repository: `C:\Users\jillv\Projects\safeheal-ai` on Jill-Vekariya10,
device `8025e560-e3a9-4f10-9084-a256f42ffb82`.
Local branch: `day9-controlled-experiments`, continuing Day 8 commit
`41f02568671a541f83dd164f01e1f51765bf7ab1`. Inspect actual Git history for the final
local Day 9 commit. The saved user-facing copy adds its verified SHA after commit.
Read current `PROJECT_STATUS.md`, `ROADMAP.md`, `WORKLOG.md`, `EXPERIMENTS.md` and
the actual Git state before continuing. This handoff is not a source-code backup.

## What was completed

- Defined a prospective matched-block experiment before fault injection: five
  blocks, shuffled arm order with seed 9, the same isolated payment scale-zero
  fault, fixed eight-second decision delay and 45-second observation horizon.
- Implemented native-only, fixed-rule-plus-policy and real-AI-plus-the-same-policy
  arms. A real model must provide a validated, sufficiently confident payment
  endpoint-unavailable hypothesis; fallback cannot qualify as AI success.
- Executed **10 actual Kubernetes trials**: five native-only and five rule-policy.
  All five planned AI slots are retained explicitly as `not_run`.
- Saved **1,767 raw request completions**, platform observations, raw Prometheus
  samples, original trial records, controller audit databases/events and a
  **60-file raw-data SHA-256 manifest**.
- Replayed recovery metrics from raw request measurements and verified exact
  agreement with the stored trial metrics. Produced summaries, CSV, error analysis,
  an exploratory paired bootstrap and two comparison charts in PNG and SVG.
- Documented recovery-time, model-accuracy, cost and safety trade-offs, including
  unmeasured and inconclusive outcomes. Added reproducible scripts and CI replay.
- Added **19 automated experiment/analysis tests**. Final full Windows suite:
  **495 passed, 2 skipped, 0 failed**, one existing Starlette/httpx warning.

The protocol was recorded locally by the runner before injection, not registered
with an external preregistration service. Instrument source hashes are retained.
The first trial started at **17:54:55 UTC**, and the batch finished at
**18:06:55 UTC on 24 October 2026**.

## Results and defensible conclusion

| Arm | Actual trials | Recovered within 45 s | Censored | Mean observed recovery |
|---|---:|---:|---:|---:|
| Native only | 5 | 0 | 5 | Unknown; no recovery observed within horizon |
| Fixed rule + independent safe controller | 5 | 5 | 0 | **19.04 s** |
| Real AI + independent safe controller | 0 of 5 planned | Not measured | Not measured | Not measured |

Rule-policy recovery times were **21.907, 18.063, 17.750, 20.110 and 17.359 s**.
Median: **18.063 s**. Each successful controller action was separately verified.
The mean paired difference in **45-second restricted recovery time** was
**25.9622 s** (native minus rule). This is not a comparison of unrestricted MTTR:
native actual recovery times are censored/unknown.

Observed valid order responses within measurement were **17/345 (4.9%)** for
native and **1,219/1,370 (89.0%)** for rule-policy. The workload is closed-loop;
slow failures reduce throughput. These are completed-response proportions, not
elapsed-time uptime or fixed offered-load reliability estimates.

**Supported conclusion:** In this isolated scale-zero fixture, the explicitly
permitted restore policy recovered the service within the measurement horizon in
all five attempts, while native behavior did not restore the desired count in
five attempts. This condition deliberately requires restoring desired replicas;
it is not a test of generic process self-restart. No result establishes an AI
advantage, general recovery effectiveness, production reliability or statistical
superiority over deterministic rules.

Safety observations: **80/80 predefined forbidden API probes were denied with
HTTP 403**; **5/5 controller actions verified**; **10/10 attempted trials passed
cleanup**; **five native fixtures required operator restoration after measurement**.
Those cleanup restorations are excluded from recovery metrics. No trial executor
token files remain. Zero real diagnosis-provider requests were made.

## Why the AI arm remains pending

At session start no diagnosis endpoint, model, credential or call budget was
configured. Ollama was installed with a cloud-backed model, which was not silently
used. The user explicitly chose **“A provider I configure.”** A local template was
prepared, but the active provider profile was still absent at final verification.

Configure this file locally:

`C:\Users\jillv\Projects\safeheal-ai\.local\day9\provider.json`

Copy `.local/day9/provider.example.json` and fill these exact fields:

```json
{
  "base_url": "https://YOUR-ENDPOINT/v1",
  "model": "YOUR_MODEL",
  "max_calls": 5,
  "max_output_tokens": 800,
  "timeout_seconds": 20,
  "token_field": "max_completion_tokens",
  "api_key_file": ".local/day9/provider.key"
}
```

Store the credential in the referenced local key file, never in chat, source,
reports or command arguments. Use the endpoint's supported token-limit field.
The profile uses the existing bounded OpenAI-compatible JSON transport. Five AI
slots require a user-selected budget of at least five requests. Do not infer
permission for unlimited or unspecified paid calls.

Provider availability/settings are frozen at run start. Once configured, run a
**new complete matched cohort** in a new directory. Do not fill old slots later,
replace records, pool cohorts silently, or call a deterministic/mock provider a
real AI arm. AI diagnostic accuracy, recovery benefit, usage/cost and its trade-off
against the rule arm remain unmeasured. Real monetary cost is unknown without
provider pricing/account billing; baseline zero LLM requests does not mean zero
total compute cost.

## Evidence, figures and reproduction

- Protocol and raw data: `evidence/day9/run-primary/`.
- Raw integrity manifest: `evidence/day9/run-primary/manifest.json`.
- Derived findings: `evidence/day9/analysis/FINDINGS.md`.
- Exact numerical analysis and CSV: `analysis.json`, `trials.csv` in that folder.
- Figures: `evidence/day9/analysis/figures/{recovery_comparison,business_responses}.{png,svg}`.
- Independent verification: `evidence/day9/verification.json`.
- Operational protocol: `docs/CONTROLLED_EXPERIMENTS.md`.
- Final test log: `evidence/day9/windows-tests.txt`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/controlled_experiment.py plan
.\.venv\Scripts\python.exe scripts/controlled_experiment.py run --execute --output evidence/day9/new-configured-run
.\.venv\Scripts\python.exe scripts/finalize_controlled.py evidence/day9/new-configured-run
.\.venv\Scripts\python.exe scripts/analyze_controlled.py evidence/day9/new-configured-run --output .local/day9-new-analysis --no-plots
```

The setup command for a lab lacking Prometheus is documented separately. Rendering
requires optional pinned `requirements-analysis.txt`; figures were generated with
Matplotlib 3.10.8 / NumPy 2.3.5 and visually checked. Numerical analysis needs only
the existing runtime. Run and output directories must be new.

The first chart-render attempt exposed a null-metrics handling error for explicitly
unrun AI slots. It did not change raw observations or numerical results. Null-safe
CSV/render handling and a regression test were added. The initial full suite had
494 passing tests; the final suite has 495. The earlier log and engineering notes
are retained. The final numerical replay still matches the original analysis.

## Environment, safety and limitations

Used the existing isolated `safeheal-day7` cluster/context, namespace `safeheal-dev`
and only `.local/day7/kubeconfig`. Added the existing pinned Prometheus image/config
to that lab. Application image stayed `safeheal-ai:sha256-311922d1b56ffd31`.
The original stopped cluster, default context and prior evidence were preserved.
Owned workload/forward processes stopped after the batch; the labelled lab and
Prometheus remain available for reproduction.

Every trial is a fresh **operator-enrolled lab episode**, with its own private
journal/token and one allowed action. Production controller code, RBAC and
admission remained unchanged. Earlier journals were archived, not erased. The
model cannot reset an episode. Continuous-production cooldown/hourly-budget
behavior across such episode resets is not evaluated or claimed.

One deliberately policy-addressable fault, five blocks, one shared cluster,
sequential ordering, warm caches, telemetry carryover and host/API instrumentation
limit generalization. The fixed eight-second observation delay is part of measured
time. Bootstrap uncertainty is exploratory and conditional on five blocks. There
is no benign-control false-positive estimate or held-out diagnostic validation.

Changes are committed locally on `day9-controlled-experiments`; inspect Git for
the exact SHA. No GitHub push, merge, remote Day 9 CI or visibility/protection
change is claimed. Earlier publication/account-feature blockers still apply.

**Next required work:** configure the selected provider and run/analyze a fresh
matched real-model cohort. Then assess the full Day 9 gate. **Do not advance to a
Day 9 complete/90% claim yet.** Day 10 final reproducibility/report/demo is also
unfinished.
