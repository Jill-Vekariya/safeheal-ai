import asyncio
import json
import logging
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from services.app import create_app


def samples(client, name):
    return [s for family in text_string_to_metric_families(client.get("/metrics").text)
            for s in family.samples if s.name == name]


def test_success_validation_and_probe_exclusion():
    with TestClient(create_app("payment")) as c:
        for path in ("/healthz", "/readyz", "/metrics"):
            assert c.get(path).status_code == 200
        assert samples(c, "safeheal_http_requests_total") == []
        assert c.post("/payments", json={"order_id": "a", "amount_cents": 1000}).status_code == 201
        assert c.post("/payments", json={"order_id": "a", "amount_cents": -1}).status_code == 422
        counts = samples(c, "safeheal_http_requests_total")
        assert {(s.labels["status_class"], s.value) for s in counts} == {("2xx", 1), ("4xx", 1)}
        assert sum(s.value for s in samples(c, "safeheal_http_request_duration_seconds_count")) == 2
        assert samples(c, "safeheal_http_requests_in_progress")[0].value == 0
        assert "text/plain" in c.get("/metrics").headers["content-type"]


@pytest.mark.parametrize("timeout,status", [(False, 503), (True, 504)])
def test_real_dependency_failures_are_5xx(timeout, status):
    def unavailable(request):
        if timeout:
            raise httpx.ReadTimeout("test", request=request)
        return httpx.Response(500)
    with TestClient(create_app("gateway", "http://order", httpx.MockTransport(unavailable))) as c:
        assert c.post("/orders", json={"item_id": "demo", "quantity": 1}).status_code == status
        count = samples(c, "safeheal_http_requests_total")[0]
        assert count.labels == {"service": "gateway", "method": "POST", "route": "/orders", "status_class": "5xx"}
        assert count.value == 1


def test_unhandled_exception_recorded_and_gauge_released(caplog):
    app = create_app("payment")
    @app.get("/explode")
    def explode():
        raise RuntimeError("must not appear in telemetry")
    with TestClient(app, raise_server_exceptions=False) as c, caplog.at_level(logging.INFO, logger="safeheal.requests"):
        assert c.get("/explode", headers={"x-request-id": "failure-1"}).status_code == 500
        assert samples(c, "safeheal_http_requests_total")[0].labels["status_class"] == "5xx"
        assert samples(c, "safeheal_http_requests_in_progress")[0].value == 0
    event = json.loads(next(r.message for r in caplog.records if r.name == "safeheal.requests"))
    assert event["exception_type"] == "RuntimeError"
    assert event["request_id"] == "failure-1"
    assert "must not appear" not in json.dumps(event)


def test_bounded_labels_and_json_log_correlation(caplog):
    app = create_app("payment")
    @app.get("/lookup/{item}")
    def lookup(item: str):
        return {"ok": True}
    with TestClient(app) as c, caplog.at_level(logging.INFO, logger="safeheal.requests"):
        for i in range(20):
            assert c.get(f"/lookup/user-{i}?secret=hidden", headers={"x-request-id": f"id-{i}"}).status_code == 200
            assert c.request(f"CUSTOM{i}", f"/missing-{i}").status_code == 404
        counts = samples(c, "safeheal_http_requests_total")
        assert len(counts) == 2
        assert {s.labels["route"] for s in counts} == {"/lookup/{item}", "__unmatched__"}
        assert {s.labels["method"] for s in counts} == {"GET", "OTHER"}
        payload = c.get("/metrics").text
        assert "id-19" not in payload and "user-19" not in payload and "missing-19" not in payload
        response = c.get("/healthz", headers={"x-request-id": "bad/value"})
        assert response.headers["x-request-id"] != "bad/value"
    events = [json.loads(r.message) for r in caplog.records if r.name == "safeheal.requests"]
    assert any(e["request_id"] == "id-19" and e["timestamp"].endswith("+00:00") for e in events)
    assert "hidden" not in json.dumps(events)


def test_latency_observes_completed_work_and_independent_registries():
    app = create_app("payment")
    @app.get("/delayed")
    async def delayed():
        deadline = time.perf_counter() + .03
        # Windows event-loop clock resolution can wake a short sleep early.
        while time.perf_counter() < deadline:
            await asyncio.sleep(.005)
        return {"ok": True}
    with TestClient(app) as a, TestClient(create_app("payment")) as b:
        assert a.get("/delayed").status_code == 200
        assert samples(a, "safeheal_http_request_duration_seconds_sum")[0].value >= .025
        assert samples(b, "safeheal_http_requests_total") == []
