"""Guarded prospective scale-zero experiments. Default plan never mutates the cluster."""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"scripts"))
import k8s as lab
import verify_recovery as recovery
from benchmark import Workload, Journal as MeasurementJournal
from benchmark_kubernetes import KubernetesBackend, _free_port
from controlled_core import protocol, rule_support, ai_support, metrics, summarize, encoded
from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.evidence import Aggregator
from services.diagnosis.provider import JsonProvider, ProviderConfig
from services.incidents.telemetry import Collector
from services.recovery.controller import ACTION, Journal, template_digest
from services.recovery.kubernetes import KubernetesAPI

PROFILE = ROOT/".local/day9/provider.json"


def provider_profile(path):
    if not path.exists():
        return None, {"configured":False,"reason":"provider_profile_missing"}
    cfg = json.loads(path.read_text(encoding="utf-8"))
    required = {"base_url","model","max_calls","max_output_tokens","timeout_seconds","token_field","api_key_file"}
    if set(cfg) != required:
        raise ValueError("Provider profile must contain the exact documented fields")
    key_file = cfg.pop("api_key_file")
    if not isinstance(key_file, str):
        raise ValueError("Provider key file must be a path string or empty for a keyless loopback endpoint")
    key_path = Path(key_file) if key_file else None
    if key_path and not key_path.is_absolute():
        key_path = ROOT/key_path
    key = key_path.read_text(encoding="utf-8").strip() if key_path else ""
    provider = JsonProvider(ProviderConfig(provider="openai-compatible",api_key=key,**cfg))
    return provider, {"configured":True, **cfg, "credential_present":bool(key)}


def setup_prometheus():
    lab.guard_cluster()
    resources = json.loads((ROOT/"infrastructure/observability/resources.json").read_text())["items"]
    resources = [r for r in resources if r["metadata"]["name"]=="prometheus"]
    cm = {"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"safeheal-prometheus","namespace":lab.NAMESPACE,"labels":lab.LABELS},
          "data":{"prometheus.yml":(ROOT/"infrastructure/observability/prometheus.yml").read_text()}}
    resources.append(cm)
    for r in resources:
        current = lab.kubectl("-n",lab.NAMESPACE,"get",r["kind"],r["metadata"]["name"],"--ignore-not-found","-o","json")
        if current.strip():
            lab.guard_labels(json.loads(current),r["metadata"]["name"])
    manifest = json.dumps({"apiVersion":"v1","kind":"List","items":resources})
    lab.kubectl("apply","--dry-run=server","-f","-",stdin=manifest)
    print(lab.kubectl("apply","-f","-",stdin=manifest))
    print(lab.kubectl("-n",lab.NAMESPACE,"rollout","status","deployment/prometheus","--timeout=180s",timeout=190))


def enroll(private, baseline):
    recovery.private_directory(private)
    view = json.loads(lab.kubectl("config","view","--minify","--raw","-o","json"))["clusters"][0]["cluster"]
    (private/"ca.crt").write_bytes(base64.b64decode(view["certificate-authority-data"]))
    (private/"executor.token").write_text(lab.kubectl("-n",lab.NAMESPACE,"create","token","safeheal-recovery","--duration=10m").strip())
    cfg = {"server":view["server"],"ca_file":str(private/"ca.crt"),"token_file":str(private/"executor.token"),
           "journal":str(private/"audit.sqlite3"),"autonomous_enabled":True,
           "enrollment":{"deployment_uid":baseline["metadata"]["uid"],"template_sha256":template_digest(baseline)}}
    recovery.save(private/"controller.json",cfg)
    return KubernetesAPI(view["server"],cfg["ca_file"],cfg["token_file"])


def trial(slot,plan,folder,backend,provider):
    folder.mkdir(parents=True,exist_ok=False)
    row = {**slot,"trial_id":folder.name,"attempted":False,"status":"not_run","provider_calls":0}
    if slot["arm"]=="ai_policy" and provider is None:
        row["reason"]="real_provider_not_configured"
        recovery.save(folder/"trial.json",row)
        return row
    before = lab.kjson("-n",lab.NAMESPACE,"get","deployment","payment")
    lab.require(before["spec"]["replicas"]==1 and before.get("status",{}).get("readyReplicas")==1,"Unhealthy trial baseline")
    baseline_check={"trial_id":row["trial_id"]}
    lab.wait_for_service_routes(baseline_check,timeout=60)
    private=ROOT/".local/day9"/row["trial_id"]
    api=enroll(private,before)
    workload=None; platform=None; faulted=False; started=time.monotonic()
    try:
        row["denied_access"]=recovery.forbidden_checks(api)
        workload=Workload(backend,row["trial_id"],started,folder,{"request_interval_seconds":.2,"concurrency":2})
        platform=MeasurementJournal(folder/"platform.jsonl")
        platform.write({"at":lab.utc(),"elapsed":time.monotonic()-started,"deployment":before})
        workload.start()
        time.sleep(2)
        row.update(attempted=True,status="running",baseline=before,started_at=lab.utc(),baseline_check=baseline_check)
        row["injection_elapsed"]=time.monotonic()-started
        row["injection_requested_at"]=lab.utc()
        recovery.save(folder/"trial.json",row)  # Durable intent before operator fixture.
        faulted=True
        patch=[{"op":"test","path":"/metadata/uid","value":before["metadata"]["uid"]},
               {"op":"test","path":"/spec/replicas","value":1},{"op":"replace","path":"/spec/replicas","value":0}]
        lab.kubectl("-n",lab.NAMESPACE,"patch","deployment","payment","--type=json","-p",json.dumps(patch))
        deadline=started+row["injection_elapsed"]+plan["horizon_seconds"]
        next_collect=started+row["injection_elapsed"]+plan["decision_delay_seconds"]
        while time.monotonic()<next_collect:
            d=api.deployment()
            platform.write({"at":lab.utc(),"elapsed":time.monotonic()-started,"deployment":d})
            row["injection_verified"]=d["metadata"]["uid"]==before["metadata"]["uid"] and d["spec"]["replicas"]==0
            if row["injection_verified"] and d.get("status",{}).get("replicas",0)==0:
                row["zero_replicas_observed_at"]=lab.utc()
            row["effect_verified"]=any(not s["valid_response"] and s["started_elapsed_seconds"]>=row["injection_elapsed"] for s in workload.rows())
            time.sleep(min(.5,max(0,next_collect-time.monotonic())))
        lab.require(row.get("injection_verified") and row.get("effect_verified") and row.get("zero_replicas_observed_at"),"Fault/effect was not verified before decision")
        snapshot=Collector(backend.prometheus_url).collect().document()
        recovery.save(folder/"telemetry.json",snapshot)
        agg=Aggregator(snapshot["at"]); agg.snapshot(snapshot); bundle=agg.finish()
        row["decision_started_elapsed"]=time.monotonic()-started
        permit=False
        if slot["arm"]=="rule_policy":
            permit=rule_support(bundle)
            row["decision"]={"source":"deterministic_rule","supported":permit}
        elif slot["arm"]=="ai_policy":
            calls=provider.calls; usage=deepcopy(provider.usage); model_started=time.monotonic()
            diagnosis=DiagnosisAgent(provider).diagnose(bundle)
            row["model_elapsed_seconds"]=time.monotonic()-model_started
            row["provider_calls"]=provider.calls-calls
            row["provider_usage"]={k:provider.usage[k]-usage[k] for k in usage}
            row["diagnosis"]=diagnosis
            permit=ai_support(diagnosis)
            row["decision"]={"source":diagnosis["source"],"supported":permit}
        else:
            row["decision"]={"source":"native_no_intervention","supported":False}
        row["decision_finished_elapsed"]=time.monotonic()-started
        # Ground truth attaches after the decision; it is never part of the bundle.
        row["ground_truth"]={"service":"payment","fault":"desired_replicas_zero","observable_class":"endpoint_unavailable",
                             "mechanism":"operator_scale_fixture","injection_verified":row["injection_verified"],"effect_verified":row["effect_verified"]}
        if permit:
            request={"schema_version":"day7-recovery-v1","request_id":row["trial_id"],"incident_id":"observed-endpoint-outage","action":ACTION}
            recovery.save(private/"proposal.json",request)
            remaining=deadline-time.monotonic()
            lab.require(remaining>1,"No horizon remains for a policy request")
            row["action_requested_elapsed"]=time.monotonic()-started
            process=subprocess.run([sys.executable,str(ROOT/"scripts/recover.py"),"run","--config",str(private/"controller.json"),
                 "--request",str(private/"proposal.json"),"--mode","autonomous"],capture_output=True,text=True,cwd=ROOT,timeout=remaining)
            row["controller_result"]=json.loads(process.stdout)
            row["controller_exit_code"]=process.returncode
            row["controller_finished_elapsed"]=time.monotonic()-started
        # Stop observation at the same declared horizon in every arm, regardless of recovery.
        while time.monotonic()<deadline:
            time.sleep(min(.5,max(0,deadline-time.monotonic())))
        row["observation_elapsed_end"]=time.monotonic()-started
        row["status"]="observed"
    except Exception as exc:
        row["status"]="technical_failure"
        row["error_type"]=type(exc).__name__
        row["observation_elapsed_end"]=time.monotonic()-started
    finally:
        try:
            if workload:
                try:
                    workload.close()
                    row["metrics"]=metrics(row,workload.rows(),plan["horizon_seconds"])
                except Exception as exc:
                    row.update(status="technical_failure",workload_error_type=type(exc).__name__)
                    row["metrics"]={"eligible":False,"recovery_seconds":None,"restricted_seconds":None,"censored":None}
            if faulted:
                try:
                    d=api.deployment()
                    lab.require(d["metadata"]["uid"]==before["metadata"]["uid"] and template_digest(d)==template_digest(before),"Cleanup identity mismatch")
                    if d["spec"]["replicas"]==0:
                        patch=[{"op":"test","path":"/metadata/uid","value":before["metadata"]["uid"]},
                               {"op":"test","path":"/spec/replicas","value":0},{"op":"replace","path":"/spec/replicas","value":1}]
                        lab.kubectl("-n",lab.NAMESPACE,"patch","deployment","payment","--type=json","-p",json.dumps(patch))
                        row["operator_cleanup_restore"]=True
                    lab.kubectl("-n",lab.NAMESPACE,"rollout","status","deployment/payment","--timeout=120s",timeout=130)
                    lab.wait_for_service_routes(row,timeout=60)
                    row["cleanup_passed"]=True
                    platform.write({"at":lab.utc(),"elapsed":time.monotonic()-started,"deployment":api.deployment(),"phase":"after_measurement_cleanup"})
                except Exception as exc:
                    row.update(status="technical_failure",cleanup_passed=False,cleanup_error_type=type(exc).__name__)
                    raise
        finally:
            if platform:
                platform.close()
            api.close()
            try:
                if (private/"audit.sqlite3").exists():
                    j=Journal(private/"audit.sqlite3")
                    try:
                        j.verify()
                        with sqlite3.connect(folder/"audit.sqlite3") as dest:
                            j.db.backup(dest)
                        recovery.save(folder/"audit.json",[json.loads(r[0]) for r in j.db.execute("SELECT body FROM audit ORDER BY seq")])
                    finally:
                        j.close()
            finally:
                (private/"executor.token").unlink(missing_ok=True)
                row["finished_at"]=lab.utc()
                recovery.save(folder/"trial.json",row)
    return row


def run(plan,folder,profile):
    folder.mkdir(parents=True,exist_ok=False)
    provider,metadata=provider_profile(profile)
    plan["provider"]=metadata
    plan["source_sha256"]={str(p.relative_to(ROOT)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [Path(__file__),ROOT/"scripts/controlled_core.py",*sorted((ROOT/"services/diagnosis").glob("*.py")),*sorted((ROOT/"services/recovery").glob("*.py"))]}
    recovery.save(folder/"protocol.json",plan)
    lab.guard_cluster()
    backend=KubernetesBackend(folder)
    gateway=lab.pod_for("gateway")["metadata"]["name"]
    rows=[]
    with lab.recovery_lock():
        try:
            backend.gateway_url=backend._forward("gateway","pod/"+gateway,_free_port(),8000,"gateway")
            backend.prometheus_url=backend._forward("prometheus","service/prometheus",_free_port(19090),9090)
            for _ in range(12):
                s=Collector(backend.prometheus_url).collect()
                if all(e.up is True for e in s.services.values()):
                    break
                time.sleep(2)
            else:
                raise RuntimeError("Fresh Prometheus baseline unavailable")
            for i,slot in enumerate(plan["slots"],1):
                name=f"d9-{i:02d}-{slot['arm']}-{uuid4().hex[:6]}"
                try:
                    row=trial(slot,plan,folder/name,backend,provider)
                except BaseException:
                    path=folder/name/"trial.json"
                    row=json.loads(path.read_text()) if path.exists() else {**slot,"trial_id":name,"attempted":False,"status":"technical_failure","reason":"trial_setup_or_cleanup_failed"}
                    rows.append(row)
                    recovery.save(folder/name/"trial.json",row)
                    raise
                rows.append(row)
                recovery.save(folder/"summary.json",summarize(rows))
                print(json.dumps({"trial":name,"status":row["status"],"metrics":row.get("metrics"),"reason":row.get("reason")}),flush=True)
        finally:
            backend.close()
            recovery.save(folder/"summary.json",summarize(rows))
            recovery.save(folder/"run.json",{"attempted_slots":len(rows),"planned_slots":len(plan["slots"]),"finished_at":lab.utc(),"completed":len(rows)==len(plan["slots"])})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("plan","setup","run"),nargs="?",default="plan")
    parser.add_argument("--execute",action="store_true")
    parser.add_argument("--repeats",type=int,default=5)
    parser.add_argument("--seed",type=int,default=9)
    parser.add_argument("--horizon",type=int,default=45)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--provider-profile",type=Path,default=PROFILE)
    args=parser.parse_args()
    recovery.configure_lab("safeheal-day7")
    p=protocol(args.repeats,args.seed,args.horizon)
    if not args.execute or args.action=="plan":
        print(json.dumps(p,indent=2)); return
    if args.action=="setup":
        setup_prometheus(); return
    folder=args.output or ROOT/"evidence/day9"/("run-"+uuid4().hex[:10])
    run(p,folder,args.provider_profile)


if __name__=="__main__":
    main()
