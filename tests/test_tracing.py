import json
import logging

import httpx
from fastapi.testclient import TestClient

from services.app import create_app


def test_w3c_server_to_client_propagation_and_json_export(caplog):
    trace_id = "0af7651916cd43dd8448eb211c80319c"
    parent_id = "b7ad6b7169203331"
    outbound = []
    def pay(request):
        outbound.append(request.headers["traceparent"])
        return httpx.Response(201, json={**json.loads(request.content), "payment_id": "fake", "status": "simulated_paid"})
    with caplog.at_level(logging.INFO, logger="safeheal.traces"):
        with TestClient(create_app("order", "http://payment", httpx.MockTransport(pay))) as c:
            assert c.post("/orders", json={"item_id": "demo", "quantity": 1}, headers={
                "x-request-id": "trace-test", "traceparent": f"00-{trace_id}-{parent_id}-01"}).status_code == 201
    spans = [json.loads(r.message) for r in caplog.records if r.name == "safeheal.traces"]
    assert len(spans) == 2 and {s["trace_id"] for s in spans} == {trace_id}
    server = next(s for s in spans if s["kind"] == "SERVER")
    client = next(s for s in spans if s["kind"] == "CLIENT")
    assert server["parent_span_id"] == parent_id
    assert client["parent_span_id"] == server["span_id"]
    assert outbound == [f"00-{trace_id}-{client['span_id']}-01"]
    assert all(s["attributes"]["request_id"] == "trace-test" for s in spans)
    assert all(s["end_time_unix_nano"] >= s["start_time_unix_nano"] for s in spans)


def test_invalid_traceparent_is_replaced_and_probes_do_not_export_spans(caplog):
    with caplog.at_level(logging.INFO, logger="safeheal.traces"):
        with TestClient(create_app("payment")) as c:
            for path in ("/healthz", "/readyz", "/metrics"):
                c.get(path)
            c.post("/payments", json={"order_id": "a", "amount_cents": 1}, headers={"traceparent": "bad-parent"})
    spans = [json.loads(r.message) for r in caplog.records if r.name == "safeheal.traces"]
    assert len(spans) == 1 and spans[0]["parent_span_id"] is None
    assert len(spans[0]["trace_id"]) == 32 and int(spans[0]["trace_id"], 16) != 0
