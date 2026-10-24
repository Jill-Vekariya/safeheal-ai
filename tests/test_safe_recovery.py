from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from services.recovery.controller import (ACTION, CATALOG, Controller, Denied, Journal,
                                           digest, template_digest)
from services.recovery.kubernetes import DEPLOYMENT_PATH, KubernetesAPI


def request(name="req-1"):
    return {"schema_version": "day7-recovery-v1", "request_id": name,
            "incident_id": "incident-1", "action": ACTION}


def deployment():
    return {"kind": "Deployment", "apiVersion": "apps/v1",
            "metadata": {"name": "payment", "namespace": "safeheal-dev", "uid": "deployment-uid",
                         "resourceVersion": "42", "generation": 3,
                         "labels": {"app.kubernetes.io/name": "payment", "app.kubernetes.io/part-of": "safeheal-ai"}},
            "spec": {"replicas": 0, "template": {"spec": {"containers": [{"name": "payment", "image": "pinned"}]}}},
            "status": {}}


class API:
    def __init__(self):
        self.d = deployment()
        self.writes = []
        self.reads = 0
        self.fail_write = False
        self.ready = True
        self.change_after_write = False

    def deployment(self):
        self.reads += 1
        result = deepcopy(self.d)
        if self.writes and self.change_after_write:
            result["metadata"]["uid"] = "replaced"
        if self.writes and self.ready:
            result["status"] = {"observedGeneration": 4, "updatedReplicas": 1,
                                "readyReplicas": 1, "availableReplicas": 1, "replicas": 1}
        return result

    def scale(self):
        return {"metadata": deepcopy(self.d["metadata"]), "spec": {"replicas": self.d["spec"]["replicas"]}}

    def restore(self, patch):
        self.writes.append(deepcopy(patch))
        if self.fail_write:
            raise TimeoutError("SECRET TOKEN must not leak")
        self.d["spec"]["replicas"] = 1
        self.d["metadata"]["generation"] = 4


class Clock:
    def __init__(self):
        self.t = 10000.

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


@pytest.fixture
def setup(tmp_path):
    api, clock, journal = API(), Clock(), Journal(tmp_path / "audit.sqlite3")
    controller = Controller(api, journal, {"deployment_uid": "deployment-uid", "template_sha256": template_digest(api.d)},
                            autonomous_enabled=True, clock=clock.now, monotonic=clock.now,
                            sleep=clock.sleep, verification_seconds=5)
    yield controller, api, journal, clock
    journal.close()


def events(journal):
    return [json.loads(r[0]) for r in journal.db.execute("SELECT body FROM audit ORDER BY seq")]


def test_dry_run_has_no_write_or_consumed_claim(setup):
    c, api, j, _ = setup
    assert c.run(request())["status"] == "dry_run"
    assert not api.writes
    assert not j.db.execute("SELECT * FROM runs").fetchall()
    assert events(j)[0]["mode"] == "dry-run"
    j.verify()


def test_autonomous_verifies_three_observations_and_exact_patch(setup):
    c, api, j, _ = setup
    result = c.run(request(), mode="autonomous")
    assert result["status"] == "verified" and len(result["observations"]) == 3
    assert len(api.writes) == 1
    assert api.writes[0] == [
        {"op": "test", "path": "/metadata/uid", "value": "deployment-uid"},
        {"op": "test", "path": "/metadata/resourceVersion", "value": "42"},
        {"op": "test", "path": "/spec", "value": {"replicas": 0}},
        {"op": "add", "path": "/spec/replicas", "value": 1}]
    assert [e["code"] for e in events(j)] == ["permitted", "intent_durably_recorded", "api_acknowledged", "recovery_verified"]
    assert j.db.execute("SELECT state FROM runs").fetchone()[0] == "verified"


@pytest.mark.parametrize("change", [
    {"action": "kubectl delete namespace"}, {"command": "rm -rf /"}, {"namespace": "prod"},
    {"replicas": 999}, {"mode": "autonomous"}, {"approved": True}, {"request_id": "x\nadmin"},
    {"incident_id": "../../etc"}, {"schema_version": "wrong"}, {"action": [ACTION]},
    {"action": "restore_payment_replica; id"}, {"execution_allowed": True}, {"confidence": 1.0},
])
def test_untrusted_proposal_cannot_grant_authority(setup, change):
    c, api, j, _ = setup
    raw = {**request(), **change}
    with pytest.raises(Denied):
        c.run(raw, mode="autonomous")
    assert not api.writes and api.reads == 0
    assert events(j)[-1]["stage"] == "denial"
    assert "rm -rf" not in str(events(j))


@pytest.mark.parametrize("mutate", [
    lambda d: d["metadata"].update(uid="foreign"),
    lambda d: d["metadata"].update(namespace="production"),
    lambda d: d["metadata"].update(deletionTimestamp="now"),
    lambda d: d["metadata"]["labels"].update({"app.kubernetes.io/part-of": "foreign"}),
    lambda d: d["spec"]["template"]["spec"]["containers"][0].update(image="changed"),
    lambda d: d["spec"].update(replicas=1),
    lambda d: d["spec"].update(replicas=True),
    lambda d: d["spec"].update(replicas=2),
])
def test_independent_live_preconditions(setup, mutate):
    c, api, _, _ = setup
    mutate(api.d)
    with pytest.raises(Denied):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_autonomy_disabled_and_approval_required(setup):
    c, api, _, _ = setup
    c.autonomous_enabled = False
    for mode in ("autonomous", "approval"):
        with pytest.raises(Denied):
            c.run(request(), mode=mode)
    assert not api.writes


def test_approval_is_bound_single_use_and_durable(setup):
    c, api, j, _ = setup
    c.approve(request())
    assert c.run(request(), mode="approval")["status"] == "verified"
    api.d = deployment()
    with pytest.raises(Denied, match="request_already_claimed"):
        c.run(request(), mode="approval")
    assert len(api.writes) == 1
    assert j.db.execute("SELECT used FROM approvals").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["expired", "generation", "incident", "different_request"])
def test_stale_or_mismatched_approval_fails(setup, change):
    c, api, _, clock = setup
    c.approve(request())
    raw = request()
    if change == "expired":
        clock.t += 180
    elif change == "generation":
        api.d["metadata"]["generation"] += 1
    elif change == "incident":
        raw["incident_id"] = "different"
    else:
        raw["request_id"] = "different"
    with pytest.raises(Denied, match="approval_missing_stale_or_used"):
        c.run(raw, mode="approval")
    assert not api.writes


@pytest.mark.parametrize("failure", ["timeout", "not_ready", "uid_changed"])
def test_failure_is_never_success_or_retried_and_blocks_followup(setup, failure):
    c, api, j, clock = setup
    api.fail_write = failure == "timeout"
    api.ready = failure != "not_ready"
    api.change_after_write = failure == "uid_changed"
    with pytest.raises(Denied):
        c.run(request(), mode="autonomous")
    assert len(api.writes) == 1
    assert "SECRET" not in str(events(j))
    assert j.db.execute("SELECT state FROM runs").fetchone()[0] == "uncertain"
    clock.t += 3601
    api.d = deployment()
    api.change_after_write = False
    with pytest.raises(Denied, match="unresolved_execution"):
        c.run(request("second"), mode="autonomous")
    assert len(api.writes) == 1


def test_replay_survives_controller_restart(setup):
    c, api, j, _ = setup
    c.run(request(), mode="autonomous")
    api.d = deployment()
    reopened = Journal(j.path)
    c.journal = reopened
    try:
        with pytest.raises(Denied, match="request_already_claimed"):
            c.run(request(), mode="autonomous")
    finally:
        reopened.close()


def test_claim_exists_before_remote_write(setup):
    c, api, j, _ = setup
    original = api.restore
    def assert_durable(patch):
        with sqlite3.connect(j.path) as db:
            assert db.execute("SELECT state FROM runs").fetchone()[0] == "running"
            assert "intent_durably_recorded" in db.execute("SELECT body FROM audit ORDER BY seq DESC LIMIT 1").fetchone()[0]
        original(patch)
    api.restore = assert_durable
    c.run(request(), mode="autonomous")


def test_cooldown_hourly_budget_and_backward_clock(setup):
    c, api, _, clock = setup
    for index in range(3):
        api.d, api.writes = deployment(), []
        c.run(request(f"r{index}"), mode="autonomous")
        api.d = deployment()
        with pytest.raises(Denied, match="recovery_rate_limited"):
            c.run(request(f"fast{index}"), mode="autonomous")
        clock.t += 301
    with pytest.raises(Denied, match="recovery_rate_limited"):
        c.run(request("fourth"), mode="autonomous")


def test_single_flight_survives_crash(setup):
    c, api, j, _ = setup
    j.db.execute("INSERT INTO runs VALUES ('crashed',0,'running')")
    with pytest.raises(Denied, match="unresolved_execution"):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_audit_unavailable_prevents_write(setup, monkeypatch):
    c, api, j, _ = setup
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(j, "event", fail)
    with pytest.raises(OSError):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_audit_append_only_and_corruption_blocks_execution(setup):
    c, api, j, _ = setup
    c.run(request())
    with pytest.raises(sqlite3.IntegrityError):
        j.db.execute("DELETE FROM audit")
    j.db.execute("DROP TRIGGER audit_no_update")
    j.db.execute("UPDATE audit SET body='corrupt'")
    with pytest.raises(Denied, match="audit_integrity_failure"):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_scale_race_is_rejected(setup):
    c, api, _, _ = setup
    old = api.scale
    def race():
        s = old()
        s["metadata"]["uid"] = "new-uid"
        return s
    api.scale = race
    with pytest.raises(Denied, match="scale_precondition_changed"):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_spec_change_between_deployment_and_scale_reads_is_rejected(setup):
    c, api, _, _ = setup
    original = api.scale
    def raced_version():
        value = original()
        value["metadata"]["resourceVersion"] = "43"
        return value
    api.scale = raced_version
    with pytest.raises(Denied, match="scale_precondition_changed"):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_stale_ready_status_never_verifies(setup):
    c, api, _, _ = setup
    original = api.deployment
    def stale():
        d = original()
        if api.writes:
            d["status"]["observedGeneration"] = 3
        return d
    api.deployment = stale
    with pytest.raises(Denied, match="verification_timeout"):
        c.run(request(), mode="autonomous")


def test_status_version_race_allows_only_bounded_read_resampling(setup):
    c, api, _, _ = setup
    original = api.scale
    calls = []
    def race_once():
        value = original()
        calls.append(1)
        if len(calls) == 1:
            value["metadata"]["resourceVersion"] = "43"
        return value
    api.scale = race_once
    assert c.run(request(), mode="autonomous")["status"] == "verified"
    assert len(calls) == 2 and len(api.writes) == 1


def test_continuous_status_churn_is_bounded(setup):
    c, api, _, _ = setup
    original = api.scale
    calls = []
    def churn():
        value = original()
        calls.append(1)
        value["metadata"]["resourceVersion"] = "43"
        return value
    api.scale = churn
    with pytest.raises(Denied, match="scale_precondition_changed"):
        c.run(request(), mode="autonomous")
    assert len(calls) == 3 and not api.writes


def test_real_scale_json_omits_zero_replicas(setup):
    c, api, _, _ = setup
    original = api.scale
    def omitted_zero():
        value = original()
        value["spec"] = {}
        return value
    api.scale = omitted_zero
    assert c.run(request(), mode="autonomous")["status"] == "verified"
    assert api.writes[0][2] == {"op": "test", "path": "/spec", "value": {}}


@pytest.mark.parametrize("spec", [{"replicas": True}, {"replicas": 2}, {"replicas": 0, "other": 1}])
def test_scale_spec_is_exact_and_typed(setup, spec):
    c, api, _, _ = setup
    original = api.scale
    def bad():
        value = original()
        value["spec"] = spec
        return value
    api.scale = bad
    with pytest.raises(Denied, match="scale_precondition_changed"):
        c.run(request(), mode="autonomous")
    assert not api.writes


def test_external_generation_change_cannot_be_attributed_to_recovery(setup):
    c, api, _, _ = setup
    original = api.deployment
    def changed():
        d = original()
        if api.writes:
            d["metadata"]["generation"] += 1
        return d
    api.deployment = changed
    with pytest.raises(Denied, match="verification_generation_changed"):
        c.run(request(), mode="autonomous")


def test_backward_wall_clock_fails_closed(setup):
    c, api, _, clock = setup
    c.run(request(), mode="autonomous")
    clock.t -= 500
    api.d = deployment()
    with pytest.raises(Denied, match="recovery_rate_limited"):
        c.run(request("new"), mode="autonomous")


def test_approval_denial_is_audited(setup):
    c, api, j, _ = setup
    with pytest.raises(Denied):
        c.approve({**request(), "approved": True})
    assert events(j)[-1]["stage"] == "approval_denial"
    assert not api.writes


def test_catalog_is_immutable():
    with pytest.raises(TypeError):
        CATALOG[ACTION]["to_replicas"] = 100


@pytest.mark.parametrize("url", ["http://127.0.0.1", "https://production", "https://127.0.0.1.evil", "https://user@localhost", "https://localhost/path", "https://localhost/?a=b"])
def test_transport_rejects_nonlocal_or_ambiguous_endpoint(url):
    with pytest.raises(Denied):
        KubernetesAPI(url, "unused", "unused")


def transport_api(tmp_path, monkeypatch, handler):
    import ssl
    # Only the test transport bypasses CA loading. Production always verifies TLS.
    monkeypatch.setattr(ssl, "create_default_context", lambda **kwargs: True)
    token = tmp_path / "token"
    token.write_text("private-executor-token")
    return KubernetesAPI("https://127.0.0.1:6443", "test-ca", token,
                         transport=httpx.MockTransport(handler))


def test_transport_only_fixed_paths_and_json_patch(tmp_path, monkeypatch):
    seen = []
    def handler(req):
        seen.append((req.method, req.url.path))
        assert req.headers["Authorization"] == "Bearer private-executor-token"
        return httpx.Response(200, json={"ok": True})
    api = transport_api(tmp_path, monkeypatch, handler)
    try:
        api.deployment(); api.scale(); api.restore([])
        assert seen == [("GET", DEPLOYMENT_PATH), ("GET", DEPLOYMENT_PATH+"/scale"), ("PATCH", DEPLOYMENT_PATH+"/scale")]
    finally:
        api.close()


@pytest.mark.parametrize("status,size", [(302, 0), (401, 0), (403, 0), (409, 0), (500, 0), (200, 262145)])
def test_transport_rejection_is_bounded_secret_free_and_unretried(tmp_path, monkeypatch, status, size):
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(status, content=b"x" * size if size else b"SECRET server body")
    api = transport_api(tmp_path, monkeypatch, handler)
    try:
        with pytest.raises(Denied) as exc:
            api.restore([])
        assert "SECRET" not in str(exc.value) and len(calls) == 1
    finally:
        api.close()


def test_proposal_file_rejects_duplicate_keys_and_oversize(tmp_path):
    spec = importlib.util.spec_from_file_location("recover_cli", Path(__file__).parents[1]/"scripts/recover.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    p = tmp_path / "request.json"
    for raw in ('{"action":"a","action":"b"}', 'x'*8193, '{"x":NaN}'):
        p.write_text(raw)
        with pytest.raises(Denied):
            cli.read_request(p)
