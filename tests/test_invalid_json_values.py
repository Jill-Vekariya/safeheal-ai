import pytest
from fastapi.testclient import TestClient

from services.app import create_app


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_payment_returns_validation_error(number):
    with TestClient(create_app("payment")) as client:
        response = client.post(
            "/payments",
            content='{"order_id":"private-input", "amount_cents":' + number + "}",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "amount_cents"]
    assert "input" not in response.json()["detail"][0]
