"""Loopback-only live detector smoke: requires unused ports 18082 and 19090. No cluster fault."""
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import time
import httpx

root = Path(__file__).resolve().parents[1]
(root/'evidence/day4').mkdir(parents=True, exist_ok=True)
for port in (18082,19090):
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port)) == 0:
            raise RuntimeError(f'Port {port} already in use; refusing to interfere')
import os
import sys
import tempfile
smoke_directory = tempfile.TemporaryDirectory(prefix='safeheal-detector-api-')
env = dict(os.environ, INCIDENT_DB=str(Path(smoke_directory.name)/'incidents.sqlite3'), PROMETHEUS_URL='http://127.0.0.1:19090')
log = (root/'evidence/day4/api-smoke.txt').open('w')
p = subprocess.Popen([sys.executable, 'scripts/detect.py','serve'], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
result = {'kind':'live_loopback_detector_smoke', 'recorded_at':datetime.now(timezone.utc).isoformat(),
          'known_condition':'Prometheus endpoint absent on isolated local loopback; telemetry outage',
          'live_cluster':False, 'llm_used':False}
try:
    with httpx.Client(timeout=2, trust_env=False) as client:
        deadline = time.monotonic()+28
        while time.monotonic() < deadline:
            if p.poll() is not None:
                raise RuntimeError('Detector exited unexpectedly')
            try:
                r=client.get('http://127.0.0.1:18082/incidents?active_only=true')
                items=r.json()['items']
                if len(items)==3 and all(i['state']=='open' for i in items):
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Telemetry incidents did not open')
        result['health_status']=client.get('http://127.0.0.1:18082/healthz').status_code
        result['readiness_status']=client.get('http://127.0.0.1:18082/readyz').status_code
        result['incidents']=[client.get('http://127.0.0.1:18082/incidents/'+i['id']).json() for i in items]
        assert result['health_status']==200 and result['readiness_status']==503
        assert all(i['diagnosis']['classification']=='insufficient_telemetry' for i in result['incidents'])
        eid=items[0]['last_evidence_id']
        result['evidence']=client.get('http://127.0.0.1:18082/evidence/'+str(eid)).json()
        result['passed']=True
finally:
    p.terminate()
    p.wait(timeout=12)
    log.close()
    smoke_directory.cleanup()
(root/'evidence/day4/api-smoke.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':result['passed'],'open_telemetry_incidents':len(result['incidents']),
                  'health':result['health_status'],'readiness':result['readiness_status']}))
