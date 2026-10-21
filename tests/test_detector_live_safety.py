import json
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import verify_detector_live as live


def owned():
    return {"metadata": {"name": "payment", "namespace": "safeheal-dev", "uid": "owned-uid",
                         "labels": {"app.kubernetes.io/name": "payment", "app.kubernetes.io/part-of": "safeheal-ai"}},
            "spec": {"selector": {"app.kubernetes.io/name": "payment", "app.kubernetes.io/part-of": "safeheal-ai"}}}


@pytest.mark.parametrize("field,value", [("namespace", "production"), ("name", "foreign"), ("uid", "")])
def test_foreign_or_ambiguous_service_rejected(field, value):
    service = owned()
    service["metadata"][field] = value
    with pytest.raises(RuntimeError):
        live.service_identity(service)


def test_existing_unexpected_selector_is_never_replaced():
    service = owned()
    service["spec"]["selector"]["user-owned"] = "preserve"
    with pytest.raises(RuntimeError, match="selector"):
        live.service_identity(service)


def test_selector_patch_checks_uid_and_exact_prior_selector(monkeypatch):
    calls = []
    def kubectl(*args):
        calls.append(args)
        return '{}'
    monkeypatch.setattr(live.lab, "kubectl", kubectl)
    live.patch_selector("uid", {"a": "b"}, {"a": "c"})
    call = calls[0]
    assert call[:5] == ("-n", "safeheal-dev", "patch", "service", "payment")
    patch = json.loads(call[call.index("-p")+1])
    assert patch == [{"op":"test","path":"/metadata/uid","value":"uid"},
                     {"op":"test","path":"/spec/selector","value":{"a":"b"}},
                     {"op":"replace","path":"/spec/selector","value":{"a":"c"}}]


def test_fresh_connection_ground_truth_does_not_require_keepalive_failure():
    record = {"fault_applied_at": "2026-10-21T12:00:00+00:00", "restored_at": "2026-10-21T12:00:25+00:00",
              "traffic": {"observations": [{"status":201,"fresh_payment_at":1792583990.,"fresh_payment_status":201},
                                           {"status":201,"fresh_payment_at":1792584010.,"fresh_payment_status":"transport_error"}]}}
    assert live.validate_traffic(record)["fresh_payment_failures_during_fault"] == 1


def test_unrelated_transport_failure_cannot_establish_fault_ground_truth():
    record = {"fault_applied_at": "2026-10-21T12:00:00+00:00", "restored_at": "2026-10-21T12:00:25+00:00",
              "traffic": {"observations": [{"status":201,"fresh_payment_at":1792583990.,"fresh_payment_status":201},
                                           {"status":201,"fresh_payment_at":1792583995.,"fresh_payment_status":"transport_error"}]}}
    with pytest.raises(RuntimeError, match="fresh-connection"):
        live.validate_traffic(record)


@pytest.mark.parametrize("cid", ["abc", "a"*63, "a"*64+";echo unsafe"])
def test_pause_command_rejects_non_runtime_container_ids(cid):
    import verify_detector_pause as pause
    with pytest.raises(RuntimeError, match="container ID"):
        pause.pause_command(cid)


def test_pause_command_uses_exact_dedicated_node_and_separate_id_argument():
    import verify_detector_pause as pause
    cid = "a"*64
    command = pause.pause_command(cid)
    assert command[:5] == ["docker","exec","safeheal-dev-control-plane","sh","-c"]
    assert command[-1] == cid and cid not in command[5]
    assert 'sleep 35' in command[5] and 'trap resume_task' in command[5]
