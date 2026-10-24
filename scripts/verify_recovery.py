"""Operator-only lab enrollment/acceptance. Not imported by model/controller.

Default: read-only preflight. --execute installs narrowly scoped access controls,
introduces a payment replicas=0 fixture, and invokes the independent controller.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import k8s as lab
from services.recovery.controller import ACTION, Journal, template_digest
from services.recovery.kubernetes import KubernetesAPI, DEPLOYMENT_PATH


def configure_lab(name):
    if name == "safeheal-day7":
        lab.CLUSTER = name
        lab.CONTEXT = "kind-" + name
        lab.NODE = name + "-control-plane"
        lab.KUBECONFIG = lab.ROOT / ".local/day7/kubeconfig"


def save(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def private_directory(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    if sys.platform == "win32":
        # Restrict to the current operator; no token in process arguments/output.
        import getpass
        lab.run(["icacls", path, "/inheritance:r", "/grant:r", getpass.getuser()+":(OI)(CI)F"])
    else:
        path.chmod(0o700)


def cli(config, raw, *, operation="run", mode="dry-run", ok=True):
    request_file = Path(config).parent / "proposal.json"
    save(request_file, raw)
    process = subprocess.run([sys.executable, str(lab.ROOT/"scripts/recover.py"), operation,
        "--config", str(config), "--request", str(request_file), "--mode", mode],
        cwd=lab.ROOT, capture_output=True, text=True, timeout=140)
    lab.require((process.returncode == 0) == ok, "Unexpected independent controller exit: " + process.stdout[-1000:])
    return json.loads(process.stdout)


def forbidden_checks(api, *, zero=False):
    results = []
    checks = [
        ("GET", "/api/v1/namespaces/safeheal-dev/secrets", None),
        ("GET", "/api/v1/namespaces/safeheal-dev/pods", None),
        ("POST", "/api/v1/namespaces/safeheal-dev/pods/payment/exec?dryRun=All", None),
        ("DELETE", DEPLOYMENT_PATH+"?dryRun=All", None),
        ("PATCH", DEPLOYMENT_PATH+"?dryRun=All", {"spec": {"replicas": 2}}),
        ("PATCH", DEPLOYMENT_PATH.replace("payment", "order")+"/scale?dryRun=All", {"spec": {"replicas": 1}}),
        ("GET", DEPLOYMENT_PATH.replace("safeheal-dev", "default"), None),
        ("PATCH", DEPLOYMENT_PATH+"/scale?dryRun=All", {"spec": {"replicas": 2}}),
    ]
    if zero:
        checks = checks[-1:]
    for method, path, body in checks:
        token = api.token_file.read_text().strip()
        with api.client.stream(method, api.server+path,
                headers={"Authorization": "Bearer "+token, "Content-Type": "application/merge-patch+json"},
                json=body) as response:
            record = {"method": method, "path": path, "status_code": response.status_code}
            results.append(record)
            lab.require(response.status_code == 403, "Least privilege/admission check failed: " + str(record))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--lab", choices=("safeheal-dev", "safeheal-day7"), default="safeheal-dev")
    parser.add_argument("--mode", choices=("autonomous", "approval"), default="autonomous")
    args = parser.parse_args()
    configure_lab(args.lab)
    lab.guard_cluster()
    before = lab.kjson("-n", lab.NAMESPACE, "get", "deployment", "payment")
    lab.require(before["spec"]["replicas"] == 1 and before.get("status", {}).get("readyReplicas") == 1,
                "Expected healthy payment baseline with one replica")
    lab.guard_labels(lab.kjson("get", "namespace", lab.NAMESPACE), "namespace")
    if not args.execute:
        print(json.dumps({"status": "dry_run", "cluster": lab.CLUSTER, "context": lab.CONTEXT,
                          "action": ACTION, "fault": "payment replicas 1 -> 0", "controller_mode": args.mode}))
        return
    with lab.recovery_lock():
        trial_id = "d7-" + args.mode + "-" + uuid4().hex[:10]
        evidence = lab.ROOT / "evidence/day7" / trial_id
        evidence.mkdir(parents=True, exist_ok=False)
        record = {"trial_id": trial_id, "started_at": lab.utc(), "passed": False,
                  "lab": lab.CLUSTER, "context": lab.CONTEXT, "namespace": lab.NAMESPACE,
                  "controller_mode": args.mode, "llm_calls": 0,
                  "baseline_uid": before["metadata"]["uid"], "baseline_spec_sha256": template_digest(before)}
        api = None
        faulted = False
        private = lab.ROOT / ".local/day7" / trial_id
        try:
            policy = lab.ROOT / "infrastructure/recovery/policy.yaml"
            # Refuse to overwrite resources with these reserved names if unowned.
            for kind, name, namespaced in [
                ("serviceaccount", "safeheal-recovery", True), ("role", "safeheal-recovery", True),
                ("rolebinding", "safeheal-recovery", True),
                ("validatingadmissionpolicy", "safeheal-recovery-scale", False),
                ("validatingadmissionpolicybinding", "safeheal-recovery-scale", False)]:
                prefix = ("-n", lab.NAMESPACE) if namespaced else ()
                current = lab.kubectl(*prefix, "get", kind, name, "--ignore-not-found", "-o", "json")
                if current.strip():
                    lab.require(json.loads(current)["metadata"].get("labels", {}).get("app.kubernetes.io/part-of") == "safeheal-ai",
                                "Reserved recovery resource is not project-owned")
            lab.kubectl("apply", "--dry-run=server", "-f", policy)
            lab.kubectl("apply", "-f", policy)
            private_directory(private)
            config_view = json.loads(lab.kubectl("config", "view", "--minify", "--raw", "-o", "json"))
            cluster = config_view["clusters"][0]["cluster"]
            ca = private / "ca.crt"
            ca.write_bytes(base64.b64decode(cluster["certificate-authority-data"]))
            token_file = private / "executor.token"
            token_file.write_text(lab.kubectl("-n", lab.NAMESPACE, "create", "token", "safeheal-recovery", "--duration=10m").strip())
            if sys.platform != "win32":
                token_file.chmod(0o600)
            config = private / "controller.json"
            enrollment = {"deployment_uid": before["metadata"]["uid"], "template_sha256": template_digest(before)}
            save(config, {"server": cluster["server"], "ca_file": str(ca), "token_file": str(token_file),
                          "journal": str(private/"audit.sqlite3"), "enrollment": enrollment,
                          "autonomous_enabled": args.mode == "autonomous"})
            api = KubernetesAPI(cluster["server"], ca, token_file)
            # Real token checks: no admin impersonation and no model credentials.
            record["denied_access"] = forbidden_checks(api)
            raw = {"schema_version": "day7-recovery-v1", "request_id": trial_id,
                   "incident_id": "scale-zero-fixture", "action": ACTION}
            record["rejected_proposal"] = cli(config, {**raw, "command": "kubectl delete namespace"}, ok=False)
            record["fault_intent_at"] = lab.utc()
            save(evidence/"acceptance.json", record)
            # Developer fixture uses admin credentials; recovery never receives them.
            patch = [{"op": "test", "path": "/metadata/uid", "value": before["metadata"]["uid"]},
                     {"op": "test", "path": "/spec/replicas", "value": 1},
                     {"op": "replace", "path": "/spec/replicas", "value": 0}]
            faulted = True
            lab.kubectl("-n", lab.NAMESPACE, "patch", "deployment", "payment", "--type=json", "-p", json.dumps(patch))
            deadline = time.monotonic()+60
            while time.monotonic() < deadline:
                d = api.deployment()
                if d["spec"]["replicas"] == 0 and d.get("status", {}).get("replicas", 0) == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Scale-zero fixture never settled")
            record["zero_observed_at"] = lab.utc()
            record["scale_before_recovery"] = api.scale()
            record["admission_denied_from_zero"] = forbidden_checks(api, zero=True)
            record["dry_run"] = cli(config, raw)
            lab.require(api.scale()["spec"].get("replicas", 0) == 0, "Dry run changed replicas")
            if args.mode == "approval":
                record["unapproved_denial"] = cli(config, raw, mode="approval", ok=False)
                record["approval"] = cli(config, raw, operation="approve")
            record["controller_result"] = cli(config, raw, mode=args.mode)
            lab.require(record["controller_result"]["status"] == "verified", "Recovery was not verified")
            record["replay_denial"] = cli(config, raw, mode=args.mode, ok=False)
            record["after"] = api.deployment()
            lab.require(record["after"]["metadata"]["uid"] == before["metadata"]["uid"] and
                        template_digest(record["after"]) == template_digest(before), "Deployment identity/spec changed")
            # Separate operator business check through Service DNS; no exec right in recovery token.
            # Kubernetes Ready may precede Service endpoint propagation. Reuse the
            # existing bounded GET-only route wait; never retry the order POST.
            lab.wait_for_service_routes(record, timeout=60)
            record["business_check"] = lab.check_services(trial_id)
            lab.require(record["business_check"].get("passed") is True, "Business check failed")
            record["passed"] = True
        except Exception as exc:
            record["error"] = type(exc).__name__ + ": " + str(exc)[:1500]
            raise
        finally:
            if api:
                api.close()
            # Cleanup only this fixture, using operator rights; distinguish it from controller success.
            if faulted:
                try:
                    d = lab.kjson("-n", lab.NAMESPACE, "get", "deployment", "payment")
                    lab.require(d["metadata"]["uid"] == before["metadata"]["uid"] and
                                template_digest(d) == template_digest(before), "Cleanup identity mismatch")
                    if d["spec"]["replicas"] == 0:
                        lab.kubectl("-n", lab.NAMESPACE, "scale", "deployment/payment", "--current-replicas=0", "--replicas=1")
                        record["operator_cleanup_restore"] = True
                    lab.kubectl("-n", lab.NAMESPACE, "rollout", "status", "deployment/payment", "--timeout=120s", timeout=130)
                    record["cleanup_passed"] = True
                except Exception as exc:
                    record["cleanup_passed"] = False
                    record["cleanup_error_type"] = type(exc).__name__
                    record["passed"] = False
            if (private/"audit.sqlite3").exists():
                j = Journal(private/"audit.sqlite3")
                try:
                    j.verify()
                    save(evidence/"audit.json", [json.loads(row[0]) for row in j.db.execute("SELECT body FROM audit ORDER BY seq")])
                    j.db.backup(__import__("sqlite3").connect(evidence/"audit.sqlite3"))
                finally:
                    j.close()
            # Revoke locally held access; the short-lived server token expires without refresh.
            if (private/"executor.token").exists():
                (private/"executor.token").unlink()
            record["finished_at"] = lab.utc()
            record["source_sha256"] = {str(p.relative_to(lab.ROOT)).replace("\\", "/"):
                hashlib.sha256(p.read_bytes()).hexdigest() for p in
                [*sorted((lab.ROOT/"services/recovery").glob("*.py")),
                 lab.ROOT/"scripts/recover.py", Path(__file__), policy]}
            save(evidence/"acceptance.json", record)
        lab.require(record["passed"] and record.get("cleanup_passed"), "Acceptance or cleanup failed")
        print(json.dumps({"passed": True, "evidence": str(evidence), "trial_id": trial_id}))


if __name__ == "__main__":
    main()
