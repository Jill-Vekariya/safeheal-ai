# Broader controlled comparison

The prior controlled experiment measures only desired replicas set to zero.
Stage 4 adds HTTP 5xx and latency negative controls using the existing guarded,
expiring application-fault adapter. These faults do not expand the independent
controller's allowlisted scale-from-zero authority. A diagnosis is a proposal;
RBAC, admission, target identity and controller validation still decide execution.

```bash
python scripts/controlled_suite.py
python -m pytest tests/test_controlled_suite.py tests/test_controlled_suite_runtime.py tests/test_controlled_experiments.py -q
```

The default plan contains 27 slots: three faults, three arms and three repeats.
Ordering is seeded; reports remain separate by fault. Every planned slot remains
in the denominator after a technical failure or batch stop. Censored observations
use restricted time; they are never presented as observed recovery times.
The exploratory bootstrap resamples repetition blocks within a fault. With two
or three blocks, its interval provides very limited evidence.

An operator-approved bounded demonstration is prepared as:

```bash
python scripts/controlled_suite.py --execute --lab safeheal-day7 --repeats 2 --horizon 30 --output .local/stage4/run-001
```

It uses the existing `safeheal-day7` lab, twelve native/rule trials and six
explicitly unrun AI slots, at most two concurrent synthetic workload requests,
15-second expiring application faults and 30-second observation horizons.
Scale-zero restoration is guarded by deployment UID/template and an exact
zero-or-one replica check. Expiring faults use identity-bound cleanup. Cleanup
failure stops the batch and preserves the failure. Cleanup is outside the timed
comparison. Expiry or operator cleanup is never credited as policy recovery.

**PARTIALLY VERIFIED:** deterministic adapter tests exercise both added fault
paths, latency impact, absence of recovery permission, and retained cleanup
failures. The local full suite passed 572 tests with one explicit live-model skip.
**BLOCKED:** automatic approval review refused live fault injection against the
already-running Kubernetes lab; explicit approval is required before that run.
That existing-lab command remains unrun. The publication follow-up instead runs
the same twelve native/rule slots in the Kubernetes CI job's fresh disposable
`safeheal-dev` cluster, with `--lab safeheal-dev`. The job refuses any pre-existing
named cluster before setup. The previous running workstation lab is not used.
CI retains the full declared protocol, all eighteen slots (including six unrun
model slots), attempted outcomes, cleanup failures and source hashes. Check the
exact-head CI result before claiming this comparison passed. Live execution now
requires an explicit supported `--lab`; plan mode remains read-only.

No broader real-model recovery comparison or effectiveness improvement is claimed.
The suite deliberately cannot silently enable a configured provider profile.

This is AI-assisted implementation. No independent user implementation, human
review, production usage, new CI run or live model outcome is claimed.
