# SafeHeal AI: end-to-end demo

**Result: PASS**

Source commit: cbdce4d780925212c96d470bdc7a3de8627c926f

| Stage | Outcome |
|---|---|
| runtime | success |
| checks | success |
| replay | success |
| diagnosis | success |
| cluster | success |
| services | success |
| native | success |
| autonomous | success |
| approval | success |
| observability | success |
| detector | success |
| final services | success |

## Fresh recovery evidence

| Mode | Trial | Verified | Audit events |
|---|---|---|---:|
| approval | d7-approval-389dd2fe49 | True | 9 |
| autonomous | d7-autonomous-5dbb1f289d | True | 7 |

Each successful trial includes eight forbidden API denials, a server dry-run denial from zero,
dry-run, approval checks where applicable, three Ready observations, one confirmed business order,
replay denial, source hashes and read-only audit-chain verification.

The diagnosis stage replays retained evidence with deterministic fallback; it is separate from
the fresh operator-created recovery fixtures. No live model or provider key is used.
All five real local-model requests in the retained study timed out; AI benefit is unproven.

Download the safeheal-demo-evidence artifact for result.json, replay outputs and raw trial records.
