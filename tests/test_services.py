import httpx
import pytest
from fastapi.testclient import TestClient
from services.app import create_app


@pytest.mark.parametrize("role", ["gateway", "order", "payment"])
def test_liveness_does_not_call_dependencies(role):
    def unexpected(request):
        raise AssertionError("Liveness must not call dependencies")
    with TestClient(create_app(role, "http://dependency" if role != "payment" else None,
                               httpx.MockTransport(unexpected))) as client:
        assert client.get("/healthz").json() == {"status": "ok", "service": role}


def test_payment_validation_and_receipt():
    with TestClient(create_app("payment")) as client:
        assert client.get("/readyz").status_code == 200
        result = client.post("/payments", json={"order_id": "test", "amount_cents": 1000})
        assert result.status_code == 201
        assert result.json()["status"] == "simulated_paid"
        assert client.post("/payments", json={"order_id": "test", "amount_cents": -1}).status_code == 422


@pytest.mark.parametrize("quantity", [0, -1, 101, True, 1.5, "2"])
def test_invalid_orders_rejected_before_downstream(quantity):
    with TestClient(create_app("gateway", "http://unused")) as client:
        assert client.post("/orders", json={"item_id": "demo", "quantity": quantity}).status_code == 422


@pytest.mark.parametrize("role", ["gateway", "order"])
@pytest.mark.parametrize("failure,expected", [("timeout", 504), ("connection", 503),
                                              ("http", 503), ("malformed", 503)])
def test_downstream_failures_fail_closed(role, failure, expected):
    calls = []
    def fail(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("test timeout", request=request)
        if failure == "connection":
            raise httpx.ConnectError("test connection", request=request)
        return httpx.Response(500 if failure == "http" else 200, json={"unexpected": True})
    with TestClient(create_app(role, "http://dependency", httpx.MockTransport(fail))) as client:
        assert client.post("/orders", json={"item_id": "demo", "quantity": 1}).status_code == expected
    assert len(calls) == 1  # No unsafe automatic POST retries.


def test_order_success_and_correlation():
    import json
    def pay(request):
        assert request.headers["x-request-id"] == "trial-001"
        body = json.loads(request.content)
        return httpx.Response(201, json={**body, "payment_id": "fake", "status": "simulated_paid"})
    with TestClient(create_app("order", "http://payment", httpx.MockTransport(pay))) as client:
        result = client.post("/orders", json={"item_id": "demo", "quantity": 2},
                             headers={"x-request-id": "trial-001"})
        assert result.status_code == 201
        assert result.json()["amount_cents"] == 2000
        assert result.headers["x-request-id"] == "trial-001"


@pytest.mark.parametrize("body,expected", [({"status": "ready"}, 200), ({"status": "down"}, 503)])
def test_readiness_checks_dependency(body, expected):
    with TestClient(create_app("gateway", "http://order",
                               httpx.MockTransport(lambda r: httpx.Response(200, json=body)))) as client:
        assert client.get("/readyz").status_code == expected


def test_mismatched_payment_is_rejected():
    def wrong(request):
        return httpx.Response(201, json={"order_id": "wrong", "amount_cents": 1000,
                                       "payment_id": "fake", "status": "simulated_paid"})
    with TestClient(create_app("order", "http://payment", httpx.MockTransport(wrong))) as client:
        assert client.post("/orders", json={"item_id": "demo", "quantity": 1}).status_code == 503
