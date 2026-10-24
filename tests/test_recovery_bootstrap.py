"""Admission rollout must not expose an executable configuration prematurely."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from scripts.verify_recovery import enroll_executor, wait_for_admission

DENIAL={"kind":"Status","apiVersion":"v1","reason":"Forbidden","code":403,
        "message":"ValidatingAdmissionPolicy 'safeheal-recovery-scale' denied request: SafeHeal recovery permits only payment replicas 0 to 1 in safeheal-dev"}


class Clock:
    def __init__(self):self.at=0.
    def now(self):return self.at
    def sleep(self,seconds):self.at+=seconds


def setup_api(tmp_path,handler):
    token=tmp_path/"probe.token";token.write_text("fixture-token")
    client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False,follow_redirects=False)
    return SimpleNamespace(server="https://127.0.0.1:6443",token_file=token,client=client)


def check_request(request):
    assert request.method=="PATCH" and request.url.query==b"dryRun=All"
    assert request.url.path=="/apis/apps/v1/namespaces/safeheal-dev/deployments/payment/scale"
    assert json.loads(request.content)=={"spec":{"replicas":2}}
    assert request.headers["authorization"]=="Bearer fixture-token"


def test_executable_config_appears_only_after_two_policy_denials(tmp_path):
    config=tmp_path/"controller.json";calls=[];clock=Clock();record={}
    def handler(request):
        check_request(request);assert not config.exists();calls.append(request)
        return httpx.Response(200,json={"kind":"Scale"}) if len(calls)==1 else httpx.Response(403,json=DENIAL)
    api=setup_api(tmp_path,handler)
    try:
        enroll_executor(api,config,{"autonomous_enabled":True},record,timeout=2,monotonic=clock.now,sleep=clock.sleep)
    finally:api.client.close()
    assert len(calls)==3 and record["admission_ready"]
    assert [a["status_code"] for a in record["admission_readiness"]]==[200,403,403]
    assert json.loads(config.read_text())=={"autonomous_enabled":True}


def test_intervening_acceptance_resets_consecutive_enforcement_observations(tmp_path):
    replies=iter([403,200,403,403]);calls=[];clock=Clock();record={}
    def handler(request):
        check_request(request);calls.append(request);code=next(replies)
        return httpx.Response(code,json=DENIAL if code==403 else {})
    api=setup_api(tmp_path,handler)
    try:wait_for_admission(api,record,timeout=2,monotonic=clock.now,sleep=clock.sleep)
    finally:api.client.close()
    assert len(calls)==4 and record["admission_ready"]


@pytest.mark.parametrize("reply",[
    (200,{"kind":"Scale"}),
    (403,{"reason":"Forbidden","code":403,"message":"RBAC: cannot patch resource"}),
    (403,{"reason":"Forbidden","code":403,"message":"safeheal-recovery-scale evaluation error"}),
    (401,{"message":"Unauthorized"}),
])
def test_absent_or_unproven_enforcement_times_out_without_releasing_config(tmp_path,reply):
    clock=Clock();record={};config=tmp_path/"controller.json";calls=[]
    def handler(request):
        check_request(request);calls.append(request)
        return httpx.Response(reply[0],json=reply[1])
    api=setup_api(tmp_path,handler)
    try:
        with pytest.raises(RuntimeError,match="did not become ready"):
            enroll_executor(api,config,{"autonomous_enabled":True},record,timeout=1,monotonic=clock.now,sleep=clock.sleep)
    finally:api.client.close()
    assert not config.exists() and not record["admission_ready"] and 1 <= len(calls) <= 5


def test_transport_errors_do_not_leak_details_or_release_config(tmp_path):
    clock=Clock();record={};config=tmp_path/"controller.json"
    def handler(request):
        check_request(request)
        raise httpx.ReadTimeout("SECRET must not enter the record",request=request)
    api=setup_api(tmp_path,handler)
    try:
        with pytest.raises(RuntimeError,match="did not become ready"):
            enroll_executor(api,config,{},record,timeout=1,monotonic=clock.now,sleep=clock.sleep)
    finally:api.client.close()
    assert not config.exists() and "SECRET" not in json.dumps(record)


def test_oversized_probe_response_fails_closed(tmp_path):
    record={};clock=Clock();config=tmp_path/"controller.json"
    api=setup_api(tmp_path,lambda request:httpx.Response(403,content=b"x"*65537))
    try:
        with pytest.raises(RuntimeError,match="response bounds"):
            enroll_executor(api,config,{},record,timeout=1,monotonic=clock.now,sleep=clock.sleep)
    finally:api.client.close()
    assert not config.exists() and not record["admission_ready"]


def test_existing_config_cannot_be_silently_overwritten(tmp_path):
    config=tmp_path/"controller.json";config.write_text("existing")
    api=setup_api(tmp_path,lambda request:pytest.fail("Must stop before probe"))
    try:
        with pytest.raises(RuntimeError,match="already exists"):
            enroll_executor(api,config,{}, {})
    finally:api.client.close()
    assert config.read_text()=="existing"


@pytest.mark.parametrize("timeout",[0,61,True,float("inf")])
def test_unbounded_or_invalid_probe_timeout_is_rejected(tmp_path,timeout):
    api=setup_api(tmp_path,lambda request:pytest.fail("Invalid budget must not call API"))
    try:
        with pytest.raises(ValueError):wait_for_admission(api,{},timeout=timeout)
    finally:api.client.close()
