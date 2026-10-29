const {test} = require('node:test');
const assert = require('node:assert/strict');
const demo = require('../docs/demo/engine.js');
function finish(run) { for(let n=0;!demo.isTerminal(run)&&n<20;n++)demo.advance(run);assert.equal(demo.isTerminal(run),true);return run; }
test('every scenario starts with dry run, no approval and no write authority',()=>{
  for(const key of Object.keys(demo.scenarios)){const run=demo.createRun(key);assert.equal(run.dryRun,true);assert.equal(run.approved,false);assert.equal(run.writes,0);assert.equal(demo.approveSimulation(run),false);}
});
test('all scenarios reach an explicit terminal outcome without user approval and zero writes',()=>{
  for(const key of Object.keys(demo.scenarios)){const run=finish(demo.createRun(key));assert.equal(run.writes,0);assert.notEqual(run.phase,'recovered');if(run.diagnosis)assert.equal(run.diagnosis.execution_allowed,false);}
});
test('eligible recovery requires dry-run review and explicit approval before exactly one attempt',()=>{
  const run=finish(demo.createRun());assert.equal(run.phase,'dry_run');assert.equal(run.metrics.ready,0);assert.equal(demo.approveSimulation(run),true);finish(run);assert.equal(run.phase,'recovered');assert.equal(run.writes,1);assert.equal(run.metrics.ready,1);assert.equal(run.diagnosis.execution_allowed,false);const events=run.events.length;demo.advance(run);assert.equal(run.events.length,events);assert.equal(demo.approveSimulation(run),false);
});
test('turning off dry run without approval cannot write',()=>{const run=demo.createRun();run.dryRun=false;finish(run);assert.equal(run.phase,'denied');assert.equal(run.policy,'approval_missing');assert.equal(run.writes,0);});
test('stale evidence, unsupported target and fallback cannot be approved',()=>{
  for(const key of ['stale_evidence','unsupported_target','provider_timeout']){const run=finish(demo.createRun(key));assert.equal(demo.approveSimulation(run),false);assert.equal(run.writes,0);assert.notEqual(run.policy,'eligible');}
});
test('acknowledged simulated write does not imply successful recovery',()=>{const run=finish(demo.createRun('readiness_failure'));demo.approveSimulation(run);finish(run);assert.equal(run.writes,1);assert.equal(run.phase,'verification_failed');assert.equal(run.metrics.ready,0);});
test('ambiguous outcome remains unknown without a second write',()=>{const run=finish(demo.createRun('ambiguous_response'));demo.approveSimulation(run);finish(run);assert.equal(run.phase,'ambiguous');assert.equal(run.writes,1);for(let i=0;i<20;i++)demo.advance(run);assert.equal(run.writes,1);assert.equal(run.phase,'ambiguous');});
test('exports retain failure events, scripted timing and explicit simulation provenance',()=>{const run=finish(demo.createRun('provider_timeout'));const data=demo.exportRun(run);assert.equal(data.simulation,true);assert.equal(data.live_network_requests,0);assert.equal(data.metrics_are_illustrative,true);assert.equal(data.elapsed_time_is_scripted,true);assert.equal(data.phase,'fallback');assert.ok(data.events.some(e=>e.title.includes('timeout')));data.events.length=0;assert.ok(run.events.length>0);});
test('unknown scenario cannot enter a run',()=>{assert.throws(()=>demo.createRun('__proto__'));assert.throws(()=>demo.createRun('arbitrary_target'));});
