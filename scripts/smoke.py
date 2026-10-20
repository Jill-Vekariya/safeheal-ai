"""Live HTTP verification; no fault injection and no real payments."""
import json
import sys
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:18080"
for endpoint in ("/healthz", "/readyz"):
    with urllib.request.urlopen(base + endpoint, timeout=10) as response:
        assert response.status == 200
        print(endpoint, response.read().decode())
request = urllib.request.Request(base + "/orders",
    data=json.dumps({"item_id": "demo", "quantity": 2}).encode(),
    headers={"Content-Type": "application/json", "X-Request-ID": "day1-smoke"})
with urllib.request.urlopen(request, timeout=10) as response:
    data = json.load(response)
    assert response.status == 201
    assert data["status"] == "confirmed" and data["amount_cents"] == 2000
    assert response.headers["X-Request-ID"] == "day1-smoke"
    print("order", json.dumps(data))
print("SMOKE PASS")
