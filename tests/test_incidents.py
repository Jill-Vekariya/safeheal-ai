"""Faults and telemetry failures are deliberately labelled; no model access exists."""
import copy
import json
import math
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from services.incidents.app import create_app
from services.incidents.controller import Controller
from services.incidents.rules import evaluate
from services.incidents.telemetry import (BUCKETS, MAX_BYTES, QUERIES, SERVICES, Collector,
                                         ServiceEvidence, Snapshot, decode, delta)

T0 = 1_800_000_000.


def snapshot(t=0, **changes):
    services = {s: ServiceEvidence(True, T0+t, 100., 0., .05, T0+t) for s in SERVICES}
    for service, values in changes.items():
        for key, value in values.items():
            setattr(services[service], key, value)
    return Snapshot(T0+t, services)


def verdict(data, rule, service="payment"):
    return next(v for v in evaluate(data) if v.service == service and v.rule == rule)


def incident(c, rule, service="payment"):
    return next(i for i in c.list_incidents() if i["service"] == service and i["rule"] == rule)


def matrix(rows):
    return {"status": "success", "data": {"resultType": "matrix", "result": rows}}


def raw_metrics(at=T0, down=False, errors=0, slow=False):
    raw = {k: matrix([]) for k in QUERIES}
    for service in SERVICES:
        common = {"job": "safeheal", "instance": service+":8000"}
        times = (at-10, at-5, at)
        raw["up"]["data"]["result"].append({"metric": common, "values": [[t, "0" if down and service == "payment" else "1"] for t in times]})
        labels = {**common, "service": service, "route": "/orders", "method": "POST"}
        for status, count in (("2xx", 40-errors), ("5xx", errors)):
            raw["requests"]["data"]["result"].append({"metric": {**labels, "status_class": status},
                "values": [[t, str(i*count/2)] for i, t in enumerate(times)]})
        for bound in BUCKETS:
            total = 40 if bound >= (2. if slow else .05) else 0
            raw["buckets"]["data"]["result"].append({"metric": {**labels, "status_class": "2xx", "le": "+Inf" if math.isinf(bound) else str(bound)},
                "values": [[t, str(i*total/2)] for i, t in enumerate(times)]})
    return raw


@pytest.mark.parametrize("rule,changes", [
    ("scrape_unavailable", {"up": False}),
    ("high_error_rate", {"errors": 20.}),
    ("high_latency", {"p95": 1.}),
    ("telemetry_unavailable", {"up": None, "problems": ["up:missing"]}),
])
def test_each_known_failure_opens_and_recovers_without_model(tmp_path, rule, changes):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10, 15):
        c.ingest(snapshot(t, payment=changes))
    item = incident(c, rule)
    assert item["state"] == "open"
    detail = c.detail(item["id"])
    assert detail["diagnosis"]["controller"] == "deterministic"
    for ref in detail["diagnosis"]["evidence_refs"]:
        assert c.evidence(ref["evidence_id"]) is not None
    for t in (20, 25, 30, 35):
        c.ingest(snapshot(t))
    recovered = incident(c, rule)
    assert recovered["state"] == "resolved" and recovered["resolution"] == "recovered"
    assert recovered["opened_at"] and recovered["resolved_at"]
    final_diagnosis = c.detail(item["id"])["diagnosis"]
    assert final_diagnosis["classification"] == "recovered"
    assert final_diagnosis["evidence_refs"][0]["evidence_id"] == recovered["last_evidence_id"]
    states = [row["state"] for row in reversed(c.detail(item["id"])["transitions"])]
    assert states == ["pending", "open", "recovering", "resolved"]
    c.close()


def test_transient_is_recorded_but_never_opened(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    c.ingest(snapshot(payment={"up": False}))
    c.ingest(snapshot(5))
    item = incident(c, "scrape_unavailable")
    assert item["state"] == "resolved" and item["resolution"] == "transient" and item["opened_at"] is None


def test_normal_traffic_and_validation_errors_are_not_incidents(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10, 15, 20):
        c.ingest(decode(raw_metrics(T0+t), {}, T0+t))
    assert c.list_incidents() == []
    raw = raw_metrics()
    for row in raw["requests"]["data"]["result"]:
        row["metric"]["status_class"] = "4xx" if row["metric"]["status_class"] == "2xx" else "5xx"
    assert verdict(decode(raw, {}, T0), "high_error_rate").decision == "clear"


@pytest.mark.parametrize("value,expected", [(19.99, "unknown"), (20., "alert")])
def test_minimum_observed_requests(value, expected):
    assert verdict(snapshot(payment={"requests": value, "errors": value}), "high_error_rate").decision == expected


@pytest.mark.parametrize("errors,expected", [(5, "clear"), (5.001, "hold"), (19.999, "hold"), (20, "alert")])
def test_error_threshold_hysteresis(errors, expected):
    assert verdict(snapshot(payment={"errors": errors}), "high_error_rate").decision == expected


@pytest.mark.parametrize("p95,expected", [(.5, "clear"), (.501, "hold"), (.999, "hold"), (1, "alert")])
def test_latency_threshold_hysteresis(p95, expected):
    assert verdict(snapshot(payment={"p95": p95}), "high_latency").decision == expected


def test_missing_evidence_never_means_healthy_or_resolved(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10, 15):
        c.ingest(snapshot(t, payment={"errors": 30.}))
    c.ingest(snapshot(20))
    assert incident(c, "high_error_rate")["state"] == "recovering"
    c.ingest(snapshot(25, payment={"requests": None, "errors": None}))
    item = incident(c, "high_error_rate")
    assert item["state"] == "open" and item["resolved_at"] is None
    assert c.detail(item["id"])["diagnosis"]["classification"] == "insufficient_current_evidence"
    for t in (30, 35, 40):
        c.ingest(snapshot(t))
    assert incident(c, "high_error_rate")["state"] == "recovering"
    c.ingest(snapshot(45))
    assert incident(c, "high_error_rate")["state"] == "resolved"


def test_unknown_and_poll_gaps_reset_pending_hold(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    c.ingest(snapshot(payment={"errors": 30.}))
    c.ingest(snapshot(10, payment={"requests": 0.}))
    c.ingest(snapshot(15, payment={"errors": 30.}))
    c.ingest(snapshot(20, payment={"errors": 30.}))
    assert incident(c, "high_error_rate")["state"] == "pending"
    c.ingest(snapshot(100, payment={"errors": 30.}))
    assert incident(c, "high_error_rate")["state"] == "pending"
    for t in (105, 110, 115):
        c.ingest(snapshot(t, payment={"errors": 30.}))
    assert incident(c, "high_error_rate")["state"] == "open"


def test_hysteresis_breaks_recovery_and_recurrence_uses_same_id(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10, 15):
        c.ingest(snapshot(t, payment={"errors": 30.}))
    first = incident(c, "high_error_rate")["id"]
    c.ingest(snapshot(20))
    c.ingest(snapshot(25, payment={"errors": 10.}))
    assert incident(c, "high_error_rate")["state"] == "open"
    c.ingest(snapshot(30, payment={"errors": 30.}))
    assert incident(c, "high_error_rate")["id"] == first
    for t in (35, 40, 45, 50):
        c.ingest(snapshot(t))
    c.ingest(snapshot(55, payment={"errors": 30.}))
    assert len([i for i in c.list_incidents() if i["rule"] == "high_error_rate"]) == 2


def test_restart_persistence_duplicates_and_out_of_order(tmp_path):
    path = tmp_path/"incidents.db"
    c = Controller(path)
    data = snapshot(payment={"up": False})
    eid = c.ingest(data)
    assert c.ingest(data) == eid
    c.close()
    c = Controller(path)
    for t in (5, 10):
        c.ingest(snapshot(t, payment={"up": False}))
    assert incident(c, "scrape_unavailable")["state"] == "open"
    with pytest.raises(ValueError, match="Out-of-order"):
        c.ingest(snapshot(5))
    assert c.evidence(eid)["at"] == T0
    assert len(c.list_incidents()) == 1


def test_repeated_scrape_does_not_mature_hold(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10):
        c.ingest(snapshot(t, payment={"up": False, "up_at": T0}))
    assert incident(c, "scrape_unavailable")["state"] == "pending"


def test_concurrent_duplicate_ingestion_is_atomic(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    data, results = snapshot(payment={"up": False}), []
    threads = [threading.Thread(target=lambda: results.append(c.ingest(data))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(results) == 8 and len(set(results)) == 1 and len(c.list_incidents()) == 1


def test_dependency_correlation_is_evidence_backed_and_not_a_proven_cause(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in (0, 5, 10, 15):
        c.ingest(snapshot(t, payment={"up": False}, gateway={"errors": 30.}, order={"errors": 30.}))
    root = incident(c, "scrape_unavailable")
    for service in ("gateway", "order"):
        item = c.detail(incident(c, "high_error_rate", service)["id"])
        diagnosis = item["diagnosis"]
        assert diagnosis["classification"] == "suspected_dependency_unavailable"
        assert diagnosis["suspected_root_service"] == "payment"
        assert len(diagnosis["evidence_refs"]) == 2
        assert item["correlations"][-1]["root_id"] == root["id"]
    assert c.detail(root["id"])["diagnosis"]["classification"] == "service_or_metrics_endpoint_unavailable"


def test_no_unrelated_or_old_correlation(tmp_path):
    c = Controller(tmp_path/"incidents.db")
    for t in range(0, 85, 5):
        c.ingest(snapshot(t, payment={"up": False}))
    for t in (85, 90, 95, 100):
        c.ingest(snapshot(t, payment={"up": False}, gateway={"errors": 30.}))
    item = c.detail(incident(c, "high_error_rate", "gateway")["id"])
    assert item["diagnosis"]["classification"] == "server_error_spike" and item["correlations"] == []


@pytest.mark.parametrize("mode", ["stale", "missing", "nan", "future", "duplicate", "wrong_target", "partial", "bad_type"])
def test_untrusted_up_is_unknown_not_application_failure(mode):
    raw = raw_metrics()
    row = raw["up"]["data"]["result"][-1]
    if mode == "stale":
        row["values"] = [[T0-30, "0"]]
    elif mode == "missing":
        raw["up"]["data"]["result"].pop()
    elif mode == "nan":
        row["values"][-1][1] = "NaN"
    elif mode == "future":
        row["values"][-1][0] += 1
    elif mode == "duplicate":
        raw["up"]["data"]["result"].append(copy.deepcopy(row))
    elif mode == "wrong_target":
        row["metric"]["instance"] = "foreign:8000"
    elif mode == "partial":
        raw["up"]["warnings"] = ["partial result"]
    else:
        raw["up"]["data"]["resultType"] = "vector"
    data = decode(raw, {}, T0)
    assert verdict(data, "scrape_unavailable").decision == "unknown"
    assert verdict(data, "telemetry_unavailable").decision == "alert"
    assert verdict(data, "high_error_rate").decision == "unknown"


def test_counter_resets_and_real_histogram_quantile():
    assert delta([(0, 100), (5, 4), (10, 10)]) == 10
    data = decode(raw_metrics(errors=12, slow=True), {}, T0)
    assert data.services["payment"].requests == 40
    assert data.services["payment"].errors == 12
    assert data.services["payment"].p95 == pytest.approx(1.95)
    assert verdict(data, "high_error_rate").decision == "alert"
    assert verdict(data, "high_latency").decision == "alert"


@pytest.mark.parametrize("mode", ["empty", "stale", "incomplete", "unaligned", "count_mismatch"])
def test_incomplete_histogram_never_clears_latency(mode):
    raw = raw_metrics()
    rows = raw["buckets"]["data"]["result"]
    if mode == "empty":
        raw["buckets"]["data"]["result"] = []
    elif mode == "stale":
        rows[-1]["values"] = [[T0-30, "0"]]
    elif mode == "incomplete":
        rows.pop()
    elif mode == "unaligned":
        rows[-1]["values"] = rows[-1]["values"][1:]
    else:
        rows[-1]["values"][-1][1] = "100"
    data = decode(raw, {}, T0)
    assert verdict(data, "high_latency").decision == "unknown"
    assert verdict(data, "telemetry_unavailable").decision == "alert"


def test_no_traffic_is_unknown_performance_not_missing_scrape():
    raw = raw_metrics()
    raw["requests"] = raw["buckets"] = matrix([])
    data = decode(raw, {}, T0)
    assert verdict(data, "high_error_rate").decision == "unknown"
    assert verdict(data, "high_latency").decision == "unknown"
    assert verdict(data, "scrape_unavailable").decision == "clear"
    assert verdict(data, "telemetry_unavailable").decision == "clear"


def test_collector_uses_only_bounded_gets_and_exact_queries():
    raw, calls = raw_metrics(), []
    def respond(request):
        calls.append(request)
        assert request.method == "GET" and request.url.path == "/api/v1/query"
        name = next(k for k, v in QUERIES.items() if v == request.url.params["query"])
        assert request.url.params["time"] == str(T0) and request.url.params["timeout"] == "1s"
        return httpx.Response(200, json=raw[name])
    data = Collector(transport=httpx.MockTransport(respond)).collect(T0)
    assert data.services["payment"].requests == 40 and len(calls) == 3


@pytest.mark.parametrize("url", ["https://example.com", "http://169.254.169.254", "http://user:secret@localhost:19090", "http://localhost:19090/other"])
def test_collector_refuses_arbitrary_urls(url):
    with pytest.raises(ValueError):
        Collector(url)


@pytest.mark.parametrize("mode", ["timeout", "redirect", "oversized", "non_json", "http500"])
def test_collector_failures_are_evidence_not_healthy(mode):
    def respond(request):
        if mode == "timeout":
            raise httpx.ReadTimeout("synthetic", request=request)
        if mode == "redirect":
            return httpx.Response(302, headers={"Location": "http://foreign"})
        if mode == "oversized":
            return httpx.Response(200, content=b"x"*(MAX_BYTES+1))
        return httpx.Response(500 if mode == "http500" else 200, content=b"invalid")
    data = Collector(transport=httpx.MockTransport(respond)).collect(T0)
    assert len(data.errors) == 3
    assert verdict(data, "telemetry_unavailable").decision == "alert"
    assert verdict(data, "scrape_unavailable").decision == "unknown"


def test_full_collector_controller_api_path(tmp_path):
    raw = raw_metrics(errors=12)
    def respond(request):
        name = next(k for k,v in QUERIES.items() if v == request.url.params["query"])
        return httpx.Response(200, json=raw[name])
    collector = Collector(transport=httpx.MockTransport(respond))
    app = create_app(tmp_path/"api.db", collector, poll=False)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        for t in (0, 5, 10, 15):
            raw = raw_metrics(T0+t, errors=12)
            app.state.controller.ingest(collector.collect(T0+t))
        items = client.get("/incidents?active_only=true").json()["items"]
        assert len(items) == 3 and all(i["state"] == "open" for i in items)
        item = client.get("/incidents/"+items[0]["id"]).json()
        assert item["diagnosis"]["classification"] == "server_error_spike"
        assert client.get("/evidence/"+str(item["last_evidence_id"])).status_code == 200
        assert client.get("/incidents/missing").status_code == 404
        assert client.get("/evidence/999").status_code == 404
        assert client.get("/incidents?limit=101").status_code == 422
        assert client.post("/incidents").status_code == 405


def test_api_poller_runs_and_shuts_down_cleanly(tmp_path):
    import time
    class Source:
        def collect(self):
            return snapshot(time.time()-T0)
    app = create_app(tmp_path/"poll.db", Source())
    with TestClient(app) as client:
        deadline = time.monotonic()+2
        while client.get("/readyz").status_code != 200 and time.monotonic() < deadline:
            time.sleep(.01)
        assert client.get("/readyz").status_code == 200


def test_transaction_rolls_back_evidence_and_incidents_together(tmp_path, monkeypatch):
    c = Controller(tmp_path/"atomic.db")
    original = c._diagnose
    def fail(*args):
        raise RuntimeError("synthetic diagnosis failure")
    monkeypatch.setattr(c, "_diagnose", fail)
    data = snapshot(payment={"up": False})
    with pytest.raises(RuntimeError):
        c.ingest(data)
    assert c.list_incidents() == [] and c.evidence(1) is None
    monkeypatch.setattr(c, "_diagnose", original)
    assert c.ingest(data) == 1


def test_separate_connections_deduplicate_and_preserve_state(tmp_path):
    c1, c2 = Controller(tmp_path/"shared.db"), Controller(tmp_path/"shared.db")
    data = snapshot(payment={"up": False})
    eid = c1.ingest(data)
    assert c2.ingest(data) == eid
    c2.ingest(snapshot(5, payment={"up": False}))
    c1.ingest(snapshot(10, payment={"up": False}))
    assert len(c1.list_incidents()) == 1 and c2.list_incidents()[0]["state"] == "open"
    c1.close()
    c2.close()


def test_gap_breaks_recovery_after_process_restart(tmp_path):
    path = tmp_path/"gap.db"
    c = Controller(path)
    for t in (0, 5, 10):
        c.ingest(snapshot(t, payment={"up": False}))
    c.ingest(snapshot(15))
    c.close()
    c = Controller(path)
    c.ingest(snapshot(60))
    assert incident(c, "scrape_unavailable")["state"] == "recovering"
    c.ingest(snapshot(65))
    assert incident(c, "scrape_unavailable")["state"] == "recovering"
    for t in (70, 75):
        c.ingest(snapshot(t))
    assert incident(c, "scrape_unavailable")["state"] == "resolved"


def test_histogram_schema_matches_existing_service():
    from services.observability import BUCKETS as service_buckets
    assert BUCKETS[:-1] == service_buckets
