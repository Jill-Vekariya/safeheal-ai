# SafeHeal AI — Recovery Lab demo

Interactive browser-local prototype for [Jill-Vekariya/safeheal-ai](https://github.com/Jill-Vekariya/safeheal-ai).

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

## GitHub Pages handoff

The demo is static and can be served by GitHub Pages or any static host. The dedicated CI workflow validates it but does not change Pages settings or publish a GitHub Pages site. Enabling Pages or merging this branch requires the owner’s separate authorization under the portfolio plan. Serve only this directory; do not expose project databases, credentials, raw traces, or SQL/provider endpoints.

A private hosted preview is supplied in the pull request. The preview and this folder use the same five UI assets. To remove the demo, revert its commit; stop the optional local HTTP server to tear down a local preview.
