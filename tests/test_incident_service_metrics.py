"""Actual FastAPI error responses -> exported Day 3 metrics -> detector.

TestClient transport and scrape timestamps are simulated; this is not live kind/Prometheus acceptance.
"""
import httpx
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from services.app import create_app
from services.incidents.controller import Controller
from services.incidents.telemetry import QUERIES, SERVICES, decode


def test_real_order_failure_metrics_open_deterministic_incident(tmp_path):
    at = 1_800_000_000.
    rows = {name: {} for name in QUERIES}
    def add(name, labels, sample_at, value):
        key = tuple(sorted(labels.items()))
        row = rows[name].setdefault(key, {"metric": labels, "values": []})
        row["values"].append([sample_at, str(value)])
    fail = httpx.MockTransport(lambda r: httpx.Response(500, json={"detail": "labelled dependency failure"}))
    with TestClient(create_app("order", "http://payment", fail)) as client:
        # Initialize the bounded metric label set, then observe increments after that baseline.
        assert client.post("/orders", json={"item_id": "demo", "quantity": 1}).status_code == 503
        c = Controller(tmp_path/"real-metrics.db")
        for t in range(0, 31, 5):
            if t:
                for _ in range(20):
                    assert client.post("/orders", json={"item_id": "demo", "quantity": 1}).status_code == 503
            for service in SERVICES:
                add("up", {"job": "safeheal", "instance": service+":8000"}, at+t, 1.)
            for family in text_string_to_metric_families(client.get("/metrics").text):
                for sample in family.samples:
                    name = {"safeheal_http_requests_total": "requests", "safeheal_http_request_duration_seconds_bucket": "buckets"}.get(sample.name)
                    if name:
                        labels = {**sample.labels, "job": "safeheal", "instance": "order:8000"}
                        add(name, labels, at+t, sample.value)
            raw = {name: {"status": "success", "data": {"resultType": "matrix", "result": list(series.values())}}
                   for name, series in rows.items()}
            c.ingest(decode(raw, {}, at+t))
        items = c.list_incidents()
        error = next(i for i in items if i["service"] == "order" and i["rule"] == "high_error_rate")
        assert error["state"] == "open"
        diagnosis = c.detail(error["id"])["diagnosis"]
        assert diagnosis["classification"] == "server_error_spike" and diagnosis["controller"] == "deterministic"
        evidence = c.evidence(error["last_evidence_id"])
        assert evidence["services"]["order"]["requests"] == 120
        assert evidence["services"]["order"]["errors"] == 120
        assert not evidence["services"]["order"]["problems"]
        c.close()
