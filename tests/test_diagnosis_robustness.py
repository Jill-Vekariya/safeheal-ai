"""Adversarial development cases, durable deduplication, and failure boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from scripts.evaluate_robustness import (T0, MARKER, Model, cases, diagnosis_case,
                                          http_model, make_bundle, notification_case)
from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.evidence import Bundle, encoded, validate_bundle
from services.diagnosis.notifications import NotificationPipeline
from services.diagnosis.replay import grounded


def event(notice="notice-1", incident="incident-1", at=T0):
    return {"schema_version":"day8-notification-v1", "notification_id":notice,
            "incident_id":incident, "observed_at":at}


@pytest.mark.parametrize("case", cases(), ids=lambda c:c["name"])
def test_frozen_adversarial_diagnosis_cases(case):
    result = diagnosis_case(case)
    assert result["passed"], result["checks"]


@pytest.mark.parametrize("kind", ["repeated_notification", "different_ids_same_evidence", "stale_notification"])
def test_frozen_notification_cases(kind):
    result = notification_case("after",kind)
    assert result["passed"], result["checks"]


@pytest.fixture
def setup(tmp_path):
    model = Model("normal")
    pipeline = NotificationPipeline(DiagnosisAgent(model),tmp_path/"inbox.sqlite3",clock=lambda:T0)
    yield pipeline,model
    pipeline.close()


@pytest.mark.parametrize("change", [
    {"command":"kubectl delete namespace"}, {"approved":True}, {"mode":"autonomous"},
    {"notification_id":"../../credential"}, {"incident_id":"bad\nlog"},
    {"observed_at":T0+1}, {"observed_at":T0-61}, {"observed_at":True},
    {"schema_version":"wrong"}, {"action":"restore_payment_replica"},
])
def test_invalid_notification_is_audited_without_provider_or_execution(setup, change):
    pipeline,model = setup
    result = pipeline.handle({**event(),**change},make_bundle("fault"))
    assert result["status"] == "rejected" and not result["execution_allowed"]
    assert model.calls == 0
    assert pipeline.db.execute("SELECT COUNT(*) FROM inbox").fetchone()[0] == 0
    assert pipeline.db.execute("SELECT decision FROM notification_audit").fetchone()[0] == "rejected"
    assert MARKER not in encoded(result)


def test_duplicate_notification_survives_restart_and_reordered_evidence(tmp_path):
    model = Model("normal")
    path = tmp_path/"inbox.sqlite3"
    p = NotificationPipeline(DiagnosisAgent(model),path,clock=lambda:T0)
    assert p.handle(event(),make_bundle("fault"))["status"] == "diagnosed"
    p.close()
    p = NotificationPipeline(DiagnosisAgent(model),path,clock=lambda:T0)
    try:
        assert p.handle(event(),make_bundle("fault"))["reason"] == "duplicate_notification"
        reordered = make_bundle("fault")
        reordered.records.reverse()
        assert p.handle(event("new-id"),reordered)["reason"] == "duplicate_evidence"
        assert model.calls == 1
    finally:
        p.close()


def test_conflicting_duplicate_id_cannot_retarget_an_incident(setup):
    p,m = setup
    p.handle(event(),make_bundle("fault"))
    result = p.handle(event(incident="different-incident"),make_bundle("fault"))
    assert result["status"] == "rejected" and result["reason"] == "notification_id_collision"
    assert m.calls == 1


def test_new_evidence_or_independent_incident_is_not_suppressed(setup):
    p,m = setup
    p.handle(event(),make_bundle("fault"))
    assert p.handle(event("notice-2","incident-2"),make_bundle("fault"))["status"] == "diagnosed"
    assert p.handle(event("notice-3"),make_bundle("labels"))["status"] == "diagnosed"
    assert m.calls == 3


def test_provider_outage_is_reported_and_duplicate_does_not_retry(tmp_path):
    model = http_model("timeout")
    p = NotificationPipeline(DiagnosisAgent(model),tmp_path/"inbox.sqlite3",clock=lambda:T0)
    try:
        result = p.handle(event(),make_bundle("fault"))
        assert result["diagnosis"]["provider_status"] == "provider_timeout"
        assert result["diagnosis"]["status"] == "low_confidence" and grounded(result["diagnosis"])
        assert p.handle(event("notice-2"),make_bundle("fault"))["status"] == "suppressed"
        assert model.calls == 1
    finally:
        p.close()


def test_durable_claim_exists_before_provider_call(setup):
    p,m = setup
    original = m.propose
    def propose(bundle):
        with sqlite3.connect(p.db.execute("PRAGMA database_list").fetchone()[2]) as db:
            assert db.execute("SELECT state FROM episodes").fetchone()[0] == "pending"
            assert db.execute("SELECT reason FROM notification_audit").fetchone()[0] == "intent_durably_recorded"
        return original(bundle)
    m.propose = propose
    assert p.handle(event(),make_bundle("fault"))["status"] == "diagnosed"


def test_two_concurrent_consumers_make_one_provider_call(tmp_path):
    path = tmp_path/"inbox.sqlite3"
    p = NotificationPipeline(DiagnosisAgent(),path,clock=lambda:T0)
    p.close()
    barrier = threading.Barrier(2)
    model = Model("normal")
    def worker():
        p = NotificationPipeline(DiagnosisAgent(model),path,clock=lambda:T0)
        try:
            barrier.wait(timeout=5)
            return p.handle(event(),make_bundle("fault"))["status"]
        finally:
            p.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:worker(),range(2)))
    assert sorted(results) == ["diagnosed","suppressed"] and model.calls == 1


def test_crash_after_claim_never_causes_an_automatic_retry(tmp_path):
    class Crashes:
        def diagnose(self,bundle):
            raise KeyboardInterrupt()
    path = tmp_path/"inbox.sqlite3"
    p = NotificationPipeline(Crashes(),path,clock=lambda:T0)
    with pytest.raises(KeyboardInterrupt):
        p.handle(event(),make_bundle("fault"))
    p.close()
    model = Model("normal")
    p = NotificationPipeline(DiagnosisAgent(model),path,clock=lambda:T0)
    try:
        assert p.handle(event("notice-2"),make_bundle("fault"))["status"] == "suppressed"
        assert model.calls == 0
        assert p.db.execute("SELECT state FROM episodes").fetchone()[0] == "pending"
    finally:
        p.close()


def test_unwritable_journal_prevents_provider_call(setup):
    p,m = setup
    p.db.execute("PRAGMA query_only=ON")
    result = p.handle(event(),make_bundle("fault"))
    assert result["status"] == "rejected" and m.calls == 0


def test_post_call_persistence_failure_does_not_return_unrecorded_success(setup):
    p,m = setup
    original = p.agent.diagnose
    def fail_persistence(bundle):
        result = original(bundle)
        p.db.execute("PRAGMA query_only=ON")
        return result
    p.agent.diagnose = fail_persistence
    result = p.handle(event(),make_bundle("fault"))
    assert result["reason"] == "result_persistence_failed" and result["diagnosis"] is None
    p.db.execute("PRAGMA query_only=OFF")
    assert p.handle(event("notice-2"),make_bundle("fault"))["status"] == "suppressed"
    assert m.calls == 1


def test_capacity_limit_and_backward_clock_fail_closed(setup,monkeypatch):
    p,m = setup
    p.clock = lambda:T0-1
    assert p.handle(event(),make_bundle("fault"))["status"] == "rejected"
    p.clock = lambda:T0
    monkeypatch.setattr("services.diagnosis.notifications.MAX_EVENTS",0)
    assert p.handle(event(),make_bundle("fault"))["status"] == "rejected"
    assert m.calls == 0


@pytest.mark.parametrize("mutate", [
    lambda b:b.issues.append(MARKER),
    lambda b:b.records.append(b.records[0]),
    lambda b:setattr(b,"latest_telemetry",T0+1),
    lambda b:b.records[0].values.update(message=MARKER),
    lambda b:b.records[0].values.update(errors=1),
    lambda b:setattr(b,"records",[replace(b.records[0],source="log")]),
    lambda b:setattr(b,"records",[replace(b.records[0],supports=("OOMKilled",))]),
    lambda b:setattr(b,"as_of",float("nan")),
    lambda b:setattr(b,"as_of","2027-01-15T08:00:00+00:00"),
    lambda b:setattr(b,"latest_telemetry",True),
])
def test_invalid_bundle_never_reaches_provider_or_free_text_output(mutate):
    b,m = make_bundle("fault"),Model("normal")
    mutate(b)
    result = DiagnosisAgent(m).diagnose(b)
    assert result["provider_status"] == "invalid_evidence"
    assert result["status"] == "insufficient_evidence" and not result["hypotheses"]
    assert m.calls == 0 and MARKER not in encoded(result)


def test_detached_provider_cannot_mutate_callers_input():
    b = make_bundle("fault")
    original = encoded(b.document())
    result = DiagnosisAgent(Model("mutates")).diagnose(b)
    assert encoded(b.document()) == original and grounded(result)


@pytest.mark.parametrize("exception", [RuntimeError(MARKER), OSError(MARKER), KeyError(MARKER), AttributeError(MARKER)])
def test_unexpected_adapter_failure_is_secret_free_and_unretried(exception):
    class Fails:
        calls = 0
        def propose(self,bundle):
            self.calls += 1
            raise exception
    model = Fails()
    result = DiagnosisAgent(model).diagnose(make_bundle("fault"))
    assert result["provider_status"] == "provider_unavailable" and result["status"] == "low_confidence"
    assert model.calls == 1 and MARKER not in encoded(result) and grounded(result)


def test_notification_cli_deduplicates_without_modifying_incident_store(tmp_path,monkeypatch):
    from scripts.diagnose import main
    from services.incidents.controller import Controller
    from services.incidents.telemetry import decode
    from services.diagnosis.tools import IncidentTools
    from scripts.evaluate_robustness import raw_metrics
    monkeypatch.setenv("SAFEHEAL_LLM_PROVIDER","disabled")
    now = time.time()
    database = tmp_path/"incidents.sqlite3"
    controller = Controller(database)
    for dt in (-15,-10,-5,0):
        at = now+dt
        controller.ingest(decode(raw_metrics(at),{},at))
    controller.close()
    reader = IncidentTools(database)
    incident = next(i for i in reader.list_incidents() if i["service"] == "payment")
    reader.close()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    notice = tmp_path/"event.json"
    notice.write_text(json.dumps(event(incident=incident["id"],at=now)))
    journal = tmp_path/"notifications.sqlite3"
    args = ["notification","--database",str(database),"--event",str(notice),"--journal",str(journal)]
    assert main(args) == main(args) == 0
    with sqlite3.connect(journal) as db:
        assert db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM notification_audit WHERE decision='diagnosed'").fetchone()[0] == 1
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_notification_cli_rejects_unknown_authority_fields(tmp_path,monkeypatch):
    from scripts.diagnose import main
    monkeypatch.setenv("SAFEHEAL_LLM_PROVIDER","disabled")
    notice = tmp_path/"event.json"
    notice.write_text(json.dumps({**event(at=time.time()),"command":MARKER}))
    journal = tmp_path/"notifications.sqlite3"
    assert main(["notification","--database",str(tmp_path/"missing.db"),"--event",str(notice),"--journal",str(journal)]) == 2
    assert not journal.exists()


def test_paired_evaluator_uses_identical_cases_and_exact_baseline(tmp_path):
    from scripts.compare_robustness import BASELINE,compare
    result = compare(BASELINE,tmp_path/"paired")
    assert result["before"]["passed"] == 27 and result["after"]["passed"] == 36
    assert result["baseline_source_verified_against_git"] and result["identical_evaluator"]
    assert len(result["improved_cases"]) == 9 and not result["regressed_cases"]
    with pytest.raises(FileExistsError):
        compare(BASELINE,tmp_path/"paired")
