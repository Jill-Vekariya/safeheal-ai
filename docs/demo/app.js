(function () {
  'use strict';
  const Demo = window.SafeHealDemo;
  const $ = id => document.getElementById(id);
  const phases = ['Detect', 'Diagnose', 'Policy', 'Execute', 'Verify', 'Outcome'];
  let run = Demo.createRun(), timer = null, toastTimer = null, view = 'overview';
  const select = $('scenario-select');
  for (const [key, scenario] of Object.entries(Demo.scenarios)) {
    const option = document.createElement('option'); option.value = key; option.textContent = scenario.name; select.append(option);
  }
  function stop() { if (timer !== null) clearInterval(timer); timer = null; }
  function text(id, value) { $(id).textContent = value; }
  function el(tag, className, content) { const node = document.createElement(tag); if (className) node.className = className; if (content !== undefined) node.textContent = content; return node; }
  function notify(message) { clearTimeout(toastTimer); text('toast', message); $('toast').classList.add('visible'); toastTimer = setTimeout(() => $('toast').classList.remove('visible'), 3500); }
  function setView(next) {
    if (!['overview', 'evidence', 'audit'].includes(next)) return;
    view = next;
    for (const name of ['overview', 'evidence', 'audit']) $(name + '-view').hidden = name !== next;
    document.querySelectorAll('.nav-item').forEach(button => { button.classList.toggle('active', button.dataset.view === next); if (button.dataset.view === next) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
    text('breadcrumb-current', {overview:'Overview',evidence:'Evidence explorer',audit:'Audit trail'}[next]);
  }
  function stateDetails() {
    if (run.phase === 'idle') return ['Healthy', 'All three services available', 'healthy'];
    if (run.phase === 'recovered') return ['Recovered', 'Simulated health checks passed', 'healthy'];
    if (run.phase === 'verification_failed') return ['Unverified', 'Readiness check did not pass', 'danger'];
    if (run.phase === 'ambiguous') return ['Unknown', 'Operator reconciliation required', 'danger'];
    if (['denied', 'fallback'].includes(run.phase)) return ['Withheld', 'Recovery was not authorized', 'danger'];
    if (run.phase === 'dry_run') return ['Dry run', 'Action previewed · zero writes', 'warning'];
    return ['Degraded', 'Synthetic incident in progress', 'warning'];
  }
  function setNode(id, state, label) { const node = $(id); node.className = 'service-node' + (state ? ' ' + state : ''); node.querySelector('.node-state').replaceChildren(el('i'), document.createTextNode(' ' + label)); }
  function renderTopology() {
    const bad = run.phase !== 'idle' && run.phase !== 'recovered';
    const gateway = bad && run.scenarioData.target === 'gateway';
    setNode('node-gateway', gateway ? 'error' : '', gateway ? 'Unavailable' : 'Healthy');
    setNode('node-order', bad && !gateway ? 'warning' : '', bad && !gateway ? '5xx errors' : 'Healthy');
    setNode('node-payment', bad && !gateway ? 'error' : '', bad && !gateway ? 'Unavailable' : 'Healthy');
    $('payment-connector').classList.toggle('broken', bad && !gateway);
    text('replica-info', 'payment: ' + run.metrics.ready + ' / 1 ready' + (bad && !gateway && run.writes ? ' · desired 1' : ''));
    const last = run.events.at(-1);
    text('signal-title', last ? last.title : 'A quiet system. A controlled experiment.');
    text('signal-detail', last ? last.detail : 'Run a scenario to see how evidence becomes a recovery decision.');
  }
  function spark(id, type) {
    const bad = run.phase !== 'idle';
    const recovered = run.phase === 'recovered';
    const points = !bad ? '0,23 10,22 20,24 30,20 40,21 50,23 60,20 70,22 80,21 90,22 100,19 110,21' : recovered ? '0,22 10,23 20,20 30,5 40,4 50,5 60,8 70,19 80,21 90,22 100,22 110,23' : '0,24 10,23 20,24 30,21 40,23 50,8 60,5 70,7 80,3 90,6 100,4 110,5';
    const svg = $(id); svg.replaceChildren();
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('points', points); line.setAttribute('fill', 'none'); line.setAttribute('stroke', bad && !recovered ? type === 'error' ? '#ee8f89' : '#edba73' : '#a0e8c4'); line.setAttribute('stroke-width', '1.5'); svg.append(line);
  }
  function renderPolicy() {
    const evaluated = run.step >= 3 && run.policy === 'eligible';
    const denial = ['denied','fallback'].includes(run.phase);
    const checks = [
      ['Fresh, supported evidence', run.step >= 2 && run.scenarioData.freshness, run.policy === 'stale_evidence'],
      ['Qualified diagnosis', !!run.diagnosis && run.diagnosis.status === 'validated_fixture', run.policy === 'unqualified_diagnosis'],
      ['Target & action enrolled', evaluated, run.policy === 'target_not_enrolled'],
      ['Identity, version & write budget', evaluated, false],
      ['Operator approval', run.approved, run.policy === 'approval_missing']
    ];
    const container = $('policy-checks'); container.replaceChildren();
    for (const [label, pass, fail] of checks) { const row = el('div', 'policy-check' + (fail ? ' fail' : pass ? ' pass' : '')); row.append(el('span', 'check-icon', fail ? '×' : pass ? '✓' : '·'), el('span', '', label), el('span', '', fail ? 'DENIED' : pass ? 'PASS' : 'PENDING')); container.append(row); }
    const badge = $('decision-badge');
    badge.textContent = ({idle:'STANDBY',detected:'COLLECTING',diagnosed:'EVALUATING',policy_checked:'ELIGIBLE',dry_run:'DRY RUN',applying:'APPROVED',verifying:'VERIFYING',recovered:'VERIFIED',denied:'DENIED',fallback:'WITHHELD',verification_failed:'FAILED',ambiguous:'UNKNOWN'})[run.phase];
    badge.className = 'outline-pill' + (denial || ['verification_failed','ambiguous'].includes(run.phase) ? ' danger' : ['recovered','dry_run'].includes(run.phase) ? ' success' : '');
    $('approve-button').disabled = run.phase !== 'dry_run';
    const captions = {dry_run:'Zero writes so far. Review to continue the simulation.',recovered:'Readiness and synthetic order checks passed.',denied:'Action blocked. No simulated write was attempted.',fallback:'Fallback is not a qualifying model diagnosis.',verification_failed:'Write acknowledged. Recovery remains unverified.',ambiguous:'One attempt. Unknown outcome. No retry.'};
    text('decision-caption', captions[run.phase] || (run.approved ? 'Operator approved this browser-local simulation.' : 'Run the scenario to evaluate this action.'));
  }
  function renderJourney() {
    const container = $('journey'); container.replaceChildren();
    phases.forEach((label, index) => { const num = index + 1; const li = el('li', num < run.step ? 'done' : num === run.step ? 'current' : ''); li.append(el('span','step-number', num < run.step ? '✓' : String(num).padStart(2,'0')), el('span','',label)); container.append(li); });
    const last = run.events.at(-1); $('event-preview').replaceChildren(el('span','event-dot'),el('span','',last ? last.simulated_time + ' · ' + last.title : 'Ready when you are. Choose a scenario and run the simulation.'));
    text('journey-description', run.phase === 'dry_run' ? 'Dry run complete. Approval is the next boundary.' : 'Every decision leaves a trace.');
    text('elapsed-label', run.seconds ? 'T+' + run.seconds + 's · SCRIPTED' : 'SCRIPTED TIMELINE');
  }
  function renderDiagnosis() {
    const container = $('diagnosis-content'); container.replaceChildren();
    text('diagnosis-mode', run.diagnosis ? run.diagnosis.provider === 'deterministic_fallback' ? 'FALLBACK' : 'SCRIPTED FIXTURE' : run.phase === 'denied' ? 'WITHHELD' : 'WAITING');
    if (!run.diagnosis) {
      container.append(el('p','insight-empty',run.policy === 'stale_evidence' ? 'The evidence freshness check failed. Diagnosis is withheld; no recovery request is formed.' : 'The diagnosis appears here after fresh telemetry is validated. It can inform a recovery request; it cannot execute one.'));
    } else {
      container.append(el('div','insight-class',run.diagnosis.service + ' / endpoint_unavailable'),el('p','insight-description',run.diagnosis.provider === 'deterministic_fallback' ? 'The provider timed out. A deterministic fallback reports the symptom; recovery qualification is withheld.' : 'The scripted diagnosis references fresh endpoint and downstream error evidence. An observed symptom does not prove its physical cause.'));
      const chips = el('div','evidence-chips'); for (const id of run.diagnosis.evidence_ids) { const chip = el('button','evidence-chip',id + ' ↗'); chip.addEventListener('click',()=>setView('evidence')); chips.append(chip); } container.append(chips);
      const flag = el('div','execution-flag','execution_allowed: '); flag.append(el('b','','false')); container.append(flag);
    }
    text('diagnosis-json',JSON.stringify(run.diagnosis || {status:run.policy === 'stale_evidence' ? 'withheld_stale_evidence' : 'not_yet_evaluated',execution_allowed:false},null,2));
  }
  function renderEvidence() {
    const active = run.phase !== 'idle', stale = !run.scenarioData.freshness;
    const entries = [
      ['EV-001','Endpoint availability',active ? run.scenarioData.target + ' endpoint unavailable in the selected fixture.' : 'All three synthetic endpoints respond successfully.','probe{service="' + run.scenarioData.target + '"} = ' + (active ? '0' : '1')],
      ['EV-002','Downstream request failures','Synthetic order errors rise during dependency loss. A downstream symptom alone does not identify the underlying cause.','order_5xx_percent = ' + (active ? run.scenarioData.error : run.metrics.error)],
      ['EV-003','Payment desired / ready replicas','Replica counts are illustrated from the fixture. Identity and version checks are simulated policy inputs.','desired=' + (active && run.scenarioData.target === 'payment' ? 0 : 1) + ', ready=' + (active && run.scenarioData.target === 'payment' ? 0 : 1)],
      ['EV-004','Evidence freshness','The freshness result is a predefined scenario input, not a live timestamp or cluster check.',stale && active ? 'freshness = rejected (stale fixture)' : 'freshness = within fixture window']
    ];
    $('evidence-list').replaceChildren();
    for (const [id,title,detail,query] of entries) { const card = el('article','evidence-card'); const body = el('div'); body.append(el('h3','',title),el('p','',detail),el('code','',query)); card.append(el('span','evidence-id',id),body,el('span','outline-pill',stale && active ? 'STALE FIXTURE' : 'SYNTHETIC')); $('evidence-list').append(card); }
  }
  function renderAudit() {
    document.querySelectorAll('.audit-count').forEach(node => node.textContent = String(run.events.length));
    const summary = $('audit-summary'); summary.replaceChildren();
    for (const [value,label] of [[run.events.length,'events'],[run.writes,'simulated write attempts'],[0,'live requests']]) { const item = el('span'); item.append(el('b','',String(value)),document.createTextNode(label)); summary.append(item); }
    const body = $('audit-rows'); body.replaceChildren();
    for (const event of run.events) { const row = el('tr'); const title = el('td'); title.append(el('span','event-kind ' + event.kind),document.createTextNode(event.title)); row.append(el('td','','#' + String(event.seq).padStart(3,'0')),el('td','',event.simulated_time),title,el('td','',event.detail)); body.append(row); }
    $('audit-empty').hidden = run.events.length > 0; $('audit-rows').closest('.audit-table-wrap').hidden = run.events.length === 0;
  }
  function render() {
    text('scenario-help',run.scenarioData.description);
    const [label,detail,color] = stateDetails(); text('system-state',label); $('system-state').className = 'metric-value ' + color; $('system-state').style.color = color === 'danger' ? 'var(--red)' : color === 'warning' ? 'var(--amber)' : '';
    $('system-detail').replaceChildren(el('span','tiny-dot'),document.createTextNode(detail));
    text('latency-value',run.metrics.latency.toLocaleString('en-US')); text('error-value',run.metrics.error.toFixed(1)); text('write-value',run.writes);
    text('write-detail', run.writes ? 'One illustrated attempt · no real writes' : 'Dry run enabled by default');
    spark('latency-spark','latency');spark('error-spark','error');renderTopology();renderPolicy();renderJourney();renderDiagnosis();renderEvidence();renderAudit();
    $('run-button').classList.toggle('running',timer !== null);
    $('run-button').replaceChildren(el('span','',timer !== null ? 'Ⅱ' : '▶'),document.createTextNode(timer !== null ? 'Pause' : run.phase === 'idle' ? 'Run simulation' : Demo.isTerminal(run) ? 'Replay scenario' : 'Continue'));
    $('step-button').disabled = Demo.isTerminal(run) || timer !== null;
    text('live-status',label + '. ' + (run.events.at(-1)?.title || 'Ready to simulate.'));
  }
  function tick() { Demo.advance(run); if (Demo.isTerminal(run)) stop(); render(); }
  function play() { if (timer !== null) { stop(); render(); return; } if (Demo.isTerminal(run)) run = Demo.createRun(select.value); timer = setInterval(tick,1100); tick(); }
  function reset() { stop(); run = Demo.createRun(select.value); $('approval-dialog').close(); $('approval-consent').checked = false; $('confirm-approval').disabled = true; render(); }
  $('run-button').addEventListener('click',play); $('reset-button').addEventListener('click',reset); $('step-button').addEventListener('click',tick); select.addEventListener('change',reset);
  document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>setView(button.dataset.view)));
  document.querySelectorAll('[data-close]').forEach(button=>button.addEventListener('click',()=>$(button.dataset.close).close()));
  for (const id of ['about-button','walkthrough-button']) $(id).addEventListener('click',()=>{stop();render();$('info-dialog').showModal();});
  $('approve-button').addEventListener('click',()=>{if(run.phase !== 'dry_run')return; stop();$('approval-consent').checked=false;$('confirm-approval').disabled=true;$('approval-dialog').showModal();});
  $('approval-consent').addEventListener('change',()=>{$('confirm-approval').disabled=!$('approval-consent').checked;});
  $('confirm-approval').addEventListener('click',()=>{if(!$('approval-consent').checked || !Demo.approveSimulation(run))return; $('approval-dialog').close(); timer=setInterval(tick,1100);tick();});
  document.querySelectorAll('.export-button').forEach(button=>button.addEventListener('click',()=>{const json=JSON.stringify(Demo.exportRun(run),null,2)+'\n';const url=URL.createObjectURL(new Blob([json],{type:'application/json'}));const link=el('a');link.href=url;link.download='safeheal-demo-'+run.scenario+'.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('Simulation trace exported as JSON.');}));
  document.querySelector('.brand').addEventListener('click', event => { event.preventDefault(); setView('overview'); });
  window.addEventListener('pagehide',stop);
  render();
})();
