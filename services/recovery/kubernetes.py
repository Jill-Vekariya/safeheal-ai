"""Fixed HTTPS endpoints with a dedicated token; no kubectl, shell, or kubeconfig.

Credentials/configuration are trusted operator inputs, never proposal fields.
"""
import json
from pathlib import Path
import ssl
import time
from urllib.parse import urlsplit

import httpx

from services.recovery.controller import Denied, require

DEPLOYMENT_PATH = "/apis/apps/v1/namespaces/safeheal-dev/deployments/payment"


class KubernetesAPI:
    def __init__(self, server, ca_file, token_file, *, transport=None):
        url = urlsplit(server)
        require(url.scheme == "https" and url.hostname in ("127.0.0.1", "localhost", "::1") and
                not url.username and not url.password and not url.query and not url.fragment and
                url.path in ("", "/"), "api_must_be_local_https")
        self.server = server.rstrip("/")
        self.token_file = Path(token_file)
        self.client = httpx.Client(verify=ssl.create_default_context(cafile=str(ca_file)),
                                   timeout=httpx.Timeout(5), follow_redirects=False,
                                   trust_env=False, transport=transport)

    def close(self):
        self.client.close()

    def _request(self, method, path, patch=None):
        token = self.token_file.read_text(encoding="utf-8").strip()
        require(0 < len(token) <= 16384 and not any(c.isspace() for c in token), "invalid_executor_token")
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "Accept-Encoding": "identity"}
        if patch is not None:
            headers["Content-Type"] = "application/json-patch+json"
        try:
            deadline = time.monotonic() + 10
            with self.client.stream(method, self.server+path, headers=headers, json=patch) as response:
                require(response.status_code == 200, "kubernetes_request_rejected")
                require(response.headers.get("content-encoding", "identity").strip().lower() == "identity",
                        "kubernetes_response_encoding")
                content = bytearray()
                for chunk in response.iter_bytes():
                    require(time.monotonic() < deadline, "kubernetes_response_deadline")
                    require(len(content) + len(chunk) <= 262144, "kubernetes_response_too_large")
                    content.extend(chunk)
                result = json.loads(content)
                require(isinstance(result, dict), "invalid_kubernetes_response")
                return result
        except (httpx.HTTPError, OSError, ValueError):
            raise Denied("kubernetes_transport_failure") from None

    def deployment(self):
        return self._request("GET", DEPLOYMENT_PATH)

    def scale(self):
        return self._request("GET", DEPLOYMENT_PATH + "/scale")

    def restore(self, patch):
        return self._request("PATCH", DEPLOYMENT_PATH + "/scale", patch)
