# SafeHeal AI — Live demo

[Working demo](https://jill-vekariya.github.io/safeheal-ai/) — the public, hosted browser simulation for [Jill-Vekariya/safeheal-ai](https://github.com/Jill-Vekariya/safeheal-ai).

Run `python -m http.server 8080 --directory docs/demo` from this directory, then open http://localhost:8080. Or open `docs/demo/index.html` directly. No installation, API key, model, database, or Kubernetes cluster is needed.

Run the meaningful state-transition checks with Node 20 or later:

```sh
node --test tests/demo_engine.test.cjs
node --check docs/demo/app.js
```

## Demonstration

1. Start **Payment replica loss**. The workflow stops at a zero-write dry run.
2. Inspect the diagnosis, frozen incident evidence, and audit events.
3. Review the action and explicitly approve the **simulation**.
4. See one simulated attempt and separate readiness/business verification.
5. Try timeout, out-of-scope target, stale evidence, readiness failure, and ambiguous-response scenarios. Acknowledged writes, verified readiness, and business recovery are different outcomes.
6. Export JSON to retain a run. Reset or reload discards in-memory state.

All metrics, chart values, diagnoses, time offsets, verification results, and audit events are synthetic. There are no real model requests, telemetry requests, cluster writes, persistent approvals, or durable audit records. The browser code is not a security boundary or a substitute for the Python recovery controller. It simplifies the full controller; its identity/version/budget checks are scripted fixture outcomes.

## Provenance and scope

Checked against `safeheal-ai` main revision `97c9aedeace35bb9e7a639ffe129f93237383afc` on 29 October 2026, especially `docs/SAFE_RECOVERY.md`, `services/recovery/controller.py`, and `services/diagnosis/provider.py`. The project model does not execute actions. Its independent controller permits only `restore_payment_replica` for the enrolled `safeheal-dev/payment` deployment, replicas 0→1. Its historical studies and limitations remain separate from this visual demo.

This implementation used AI assistance. No independent human implementation, production usage, model quality, comparative performance gain, or completion of the portfolio's deployment stage is claimed. No license was selected or changed.

## Published working demo

[Open Working demo](https://jill-vekariya.github.io/safeheal-ai/). GitHub Pages serves only the static simulation assets from the dedicated gh-pages branch.

The application source is in docs/demo on main. The published branch is a selected snapshot: later source changes must be copied to that branch and its Pages build verified before claiming an updated deployment.

The browser simulation does not expose the Python services, SQL endpoints, provider credentials, a database, or a Kubernetes cluster. The private preview is a separate deployment.

To remove public hosting, disable Pages through a separately authorized repository-settings action. Local previews stop when their HTTP server stops. Keep historical experiment data and ownership disclosures intact.
