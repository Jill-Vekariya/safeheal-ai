(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SafeHealDemo = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const scenarios = {
    replica_loss: { name: 'Payment replica loss', tag: 'Recovery path', icon: '01', description: 'Payment is scaled to zero. Diagnose the downstream errors and preview the one enrolled recovery action.', target: 'payment', provider: 'validated_fixture', freshness: true, outcome: 'recovered', latency: 1240, error: 38.4 },
    provider_timeout: { name: 'Diagnosis provider timeout', tag: 'Fallback', icon: '02', description: 'A provider times out. A deterministic fallback can describe symptoms, but cannot qualify for this recovery path.', target: 'payment', provider: 'timeout', freshness: true, outcome: 'fallback', latency: 1240, error: 38.4 },
    unsupported_target: { name: 'Out-of-scope target', tag: 'Policy denial', icon: '03', description: 'Gateway evidence is valid, but the gateway is outside the payment-only recovery enrollment.', target: 'gateway', provider: 'validated_fixture', freshness: true, outcome: 'denied', latency: 890, error: 24.1 },
    stale_evidence: { name: 'Stale evidence', tag: 'Evidence denial', icon: '04', description: 'The telemetry window is stale. The demo refuses to treat it as support for a recovery action.', target: 'payment', provider: 'validated_fixture', freshness: false, outcome: 'denied', latency: 1240, error: 38.4 },
    readiness_failure: { name: 'Readiness stays unhealthy', tag: 'Verification failure', icon: '05', description: 'A simulated patch is acknowledged, but payment does not become ready. No recovery is claimed.', target: 'payment', provider: 'validated_fixture', freshness: true, outcome: 'verification_failed', latency: 1240, error: 38.4 },
    ambiguous_response: { name: 'Ambiguous write response', tag: 'Manual review', icon: '06', description: 'The simulated write response is lost. The outcome is unknown and the controller does not retry.', target: 'payment', provider: 'validated_fixture', freshness: true, outcome: 'ambiguous', latency: 1240, error: 38.4 }
  };
  const terminal = new Set(['dry_run', 'recovered', 'denied', 'fallback', 'verification_failed', 'ambiguous']);
  function createRun(key = 'replica_loss') {
    if (!Object.hasOwn(scenarios, key)) throw new Error('Unknown demo scenario');
    const scenario = scenarios[key];
    return { scenario: key, phase: 'idle', step: 0, dryRun: true, approved: false, writes: 0, seconds: 0, events: [], diagnosis: null, policy: null, metrics: { latency: 82, error: 0.2, ready: 1 }, scenarioData: { ...scenario } };
  }
  function event(run, kind, title, detail) {
    run.events.push({ seq: run.events.length + 1, simulated_time: 'T+' + String(run.seconds).padStart(2, '0') + 's', kind, title, detail });
  }
  function advance(run) {
    if (terminal.has(run.phase)) return run;
    const scenario = run.scenarioData;
    run.seconds += 2;
    if (run.phase === 'idle') {
      run.phase = 'detected'; run.step = 1;
      run.metrics = { latency: scenario.latency, error: scenario.error, ready: scenario.target === 'payment' ? 0 : 1 };
      event(run, 'warning', 'Incident detected', scenario.target + ' unavailable in synthetic telemetry. No live endpoint was contacted.');
    } else if (run.phase === 'detected') {
      run.step = 2;
      if (!scenario.freshness) {
        run.phase = 'denied'; run.policy = 'stale_evidence';
        event(run, 'denied', 'Evidence rejected', 'Freshness check failed. No diagnosis or write is authorized.');
      } else {
        run.phase = 'diagnosed';
        run.diagnosis = { service: scenario.target, observable_class: 'endpoint_unavailable', provider: scenario.provider === 'timeout' ? 'deterministic_fallback' : 'scripted_demo_fixture', status: scenario.provider === 'timeout' ? 'provider_timeout' : 'validated_fixture', execution_allowed: false, evidence_ids: ['EV-001', 'EV-002'] };
        event(run, scenario.provider === 'timeout' ? 'warning' : 'info', scenario.provider === 'timeout' ? 'Provider timeout · fallback' : 'Diagnosis fixture validated', scenario.provider === 'timeout' ? 'Fixed timeout code retained; fallback is not a successful model diagnosis.' : scenario.target + '/endpoint_unavailable. The diagnosis grants no execution authority.');
      }
    } else if (run.phase === 'diagnosed') {
      run.step = 3;
      if (scenario.provider === 'timeout') {
        run.phase = 'fallback'; run.policy = 'unqualified_diagnosis';
        event(run, 'denied', 'Recovery withheld', 'Fallback does not satisfy the validated-model requirement of this illustrated recovery path.');
      } else if (scenario.target !== 'payment') {
        run.phase = 'denied'; run.policy = 'target_not_enrolled';
        event(run, 'denied', 'Policy denied target', 'Only safeheal-dev/payment and restore_payment_replica are enrolled.');
      } else {
        run.phase = 'policy_checked'; run.policy = 'eligible';
        event(run, 'info', 'Independent policy checks passed', 'Illustrative enrollment, identity/version, budget, single-flight and 0→1 checks pass for this fixture.');
      }
    } else if (run.phase === 'policy_checked') {
      run.step = 4;
      if (run.dryRun) {
        run.phase = 'dry_run';
        event(run, 'info', 'Dry run complete · zero writes', 'Preview: restore_payment_replica, safeheal-dev/payment, replicas 0→1. Approval is required to simulate execution.');
      } else if (!run.approved) {
        run.phase = 'denied'; run.policy = 'approval_missing';
        event(run, 'denied', 'Approval missing', 'No simulated write attempted.');
      } else {
        run.phase = 'applying'; run.writes += 1;
        event(run, 'info', 'One simulated conditional patch', 'Illustrated JSON Patch tests identity and version, then replaces replicas with 1. No network request is made.');
      }
    } else if (run.phase === 'applying') {
      if (scenario.outcome === 'ambiguous') {
        run.phase = 'ambiguous';
        event(run, 'denied', 'Write outcome unknown · no retry', 'The response is ambiguous. Stop and require operator reconciliation; no success is claimed.');
      } else {
        run.phase = 'verifying'; run.step = 5;
        event(run, 'info', 'Verifying readiness and business health', 'A write acknowledgment is not recovery. Evaluate the next synthetic readiness and order checks.');
      }
    } else if (run.phase === 'verifying') {
      run.step = 6;
      if (scenario.outcome === 'verification_failed') {
        run.phase = 'verification_failed';
        event(run, 'denied', 'Verification failed', 'Payment readiness remains false. Business recovery is unverified.');
      } else {
        run.phase = 'recovered'; run.metrics = { latency: 91, error: 0.3, ready: 1 };
        event(run, 'success', 'Simulated recovery verified', 'Both readiness and a synthetic order check passed. This is an illustrative result, not measured project performance.');
      }
    }
    return run;
  }
  function approveSimulation(run) {
    if (run.phase !== 'dry_run' || run.policy !== 'eligible' || run.writes !== 0) return false;
    run.dryRun = false; run.approved = true; run.phase = 'policy_checked';
    event(run, 'info', 'Operator approved simulation', 'Approval applies only to this browser-local fixture run.');
    return true;
  }
  function exportRun(run) {
    return { schema_version: 1, simulation: true, live_network_requests: 0, metrics_are_illustrative: true, elapsed_time_is_scripted: true, source_context: 'SafeHeal AI main 97c9aedeace35bb9e7a639ffe129f93237383afc; docs/SAFE_RECOVERY.md and services/recovery/controller.py inspected on 29 October 2026. Simplified browser fixtures, not an execution of the Python controller.', ...JSON.parse(JSON.stringify(run)) };
  }
  return { scenarios, createRun, advance, approveSimulation, exportRun, isTerminal: run => terminal.has(run.phase) };
});
