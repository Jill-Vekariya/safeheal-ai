# Day 6 diagnosis acceptance

2026-10-23; canonical base e04a5069d2cfa6142b44bb85b16b27a2dc91efab. Protocol and interpretation: ../../docs/AI_DIAGNOSIS.md.

| Check | Observed result |
|---|---|
| Windows full suite | 337 passed, 2 skipped, 0 failed; one existing dependency warning |
| Mocked configurable HTTP provider | 6/6 grounded; 6/6 target and observable-class agreement |
| Disabled-provider deterministic fallback | 6/6 grounded; 6/6 target and observable-class agreement |
| CLI replay | Passed, no credentials/network/model calls |
| Day 5 evidence | Unchanged from canonical base |
| Real provider | Not called; credentials/model/budget opt-in unavailable |

The skipped tests require Windows symlink privilege and explicit real-model configuration respectively. The initial failed integrity test and correction are retained in initial-test-failure.json. windows-tests.txt is the final complete suite output. acceptance.json contains source hashes, mode-specific counts and limitations. mocked-model-replay.json and fallback-replay.json contain complete diagnoses, evidence IDs/hashes, source artifact hashes and post-diagnosis ground-truth comparison for all six attempts.

`llm_diagnoses: 6` in the mocked report means six validated responses passed the LLM transport path **using httpx.MockTransport**, not six real model generations. The top-level model_execution field records this explicitly. There were no paid calls, new injections or recovery actions. These are retrospective development-data engineering checks, not held-out accuracy, online diagnosis latency, evidence of the injection mechanism, or an AI improvement result. Full gates: 6/10; Days 7–10 remain incomplete.

The Git commit containing executable changes is a local source checkpoint. Automatic approval review rejected the combined commit/private-push command as an unapproved GitHub disclosure. Local commit proceeds separately; no Day 6 push or remote CI result is claimed. PROJECT_STATUS.md records the publication boundary. Existing source/lock files were preserved except the listed Day 6 additions and documentation/workflow integration.
