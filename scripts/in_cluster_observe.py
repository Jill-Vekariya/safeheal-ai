"""Runs inside our existing gateway container; stdlib only; no fault capabilities."""
from collections import Counter
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(url, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def api(url):
    status, body = fetch(url)
    if status != 200:
        raise RuntimeError(f"Unexpected HTTP {status} from {url}")
    return json.loads(body)


mode = os.environ["OBS_MODE"]
if mode == "traffic":
    trial = os.environ["OBS_TRIAL"]
    target = os.environ["OBS_TARGET"]
    observations = []
    started = time.monotonic()
    index = 0
    while time.monotonic() - started < 45:
        rid = f"{trial}-{index}"
        payload = {"item_id": "telemetry-demo", "quantity": 0 if index % 5 == 4 else 2}
        at = time.time()
        request_started = time.monotonic()
        try:
            status, body = fetch(target + "/orders", payload, {"x-request-id": rid})
            data = json.loads(body)
            if status == 201:
                assert data["amount_cents"] == 2000 and data["status"] == "confirmed"
            result = {"status": status}
        except (OSError, ValueError) as exc:
            result = {"transport_error": type(exc).__name__}
        observations.append({"request_id": rid, "at_unix": at,
                             "elapsed_s": time.monotonic() - started,
                             "duration_s": time.monotonic() - request_started, **result})
        index += 1
        time.sleep(.4)
    print(json.dumps({"target": target, "elapsed_s": time.monotonic() - started,
                      "status_counts": dict(Counter(str(o.get('status', 'transport_error')) for o in observations)),
                      "observations": observations}))
elif mode == "collect":
    expressions = json.loads(os.environ["OBS_QUERIES"])
    result = {"targets": api("http://prometheus:9090/api/v1/targets"), "queries": {}}
    for name, expression in expressions.items():
        result["queries"][name] = api("http://prometheus:9090/api/v1/query?" + urllib.parse.urlencode({"query": expression}))
    result["grafana_health"] = api("http://grafana:3000/api/health")
    result["dashboard"] = api("http://grafana:3000/api/dashboards/uid/safeheal-operations")
    # Ask Grafana's configured datasource to execute the same query used by a panel.
    result["grafana_query"] = api("http://grafana:3000/api/datasources/proxy/uid/safeheal-prometheus/api/v1/query?" +
        urllib.parse.urlencode({"query": "sum by(service)(safeheal_http_requests_total)"}))
    print(json.dumps(result))
else:
    raise RuntimeError("Unknown mode")
