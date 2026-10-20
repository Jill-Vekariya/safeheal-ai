"""Run through kubectl exec stdin: real DNS, Services, and HTTP boundaries."""
import json
import os
import socket
import urllib.request


def main():
    request_id = os.environ.get("CHECK_REQUEST_ID", "day2-check")
    result = {"request_id": request_id, "dns": {}, "health": {}}
    for role in ("gateway", "order", "payment"):
        fqdn = f"{role}.safeheal-dev.svc.cluster.local"
        result["dns"][role] = {"short": socket.gethostbyname(role),
                               "fqdn": socket.gethostbyname(fqdn)}
        assert result["dns"][role]["short"] == result["dns"][role]["fqdn"]
        result["health"][role] = {}
        for endpoint, expected in (("healthz", "ok"), ("readyz", "ready")):
            with urllib.request.urlopen(f"http://{role}:8000/{endpoint}", timeout=8) as response:
                body = json.load(response)
                assert response.status == 200 and body == {"status": expected, "service": role}
                result["health"][role][endpoint] = body
    request = urllib.request.Request(
        "http://gateway:8000/orders",
        data=json.dumps({"item_id": "day2-demo", "quantity": 2}).encode(),
        headers={"Content-Type": "application/json", "X-Request-ID": request_id})
    with urllib.request.urlopen(request, timeout=8) as response:
        order = json.load(response)
        assert response.status == 201 and response.headers["X-Request-ID"] == request_id
        assert order["status"] == "confirmed" and order["amount_cents"] == 2000
        assert order["item_id"] == "day2-demo" and order["quantity"] == 2
        assert order["order_id"] and order["payment_id"]
        result["order"] = order
        result["http_status"] = response.status
    result["passed"] = True
    print(json.dumps(result))


if __name__ == "__main__":
    main()
