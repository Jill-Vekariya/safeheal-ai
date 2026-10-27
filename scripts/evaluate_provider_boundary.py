"""Frozen synthetic transport fixtures; no network, model inference or cluster calls."""
import argparse
import builtins
from contextlib import ExitStack
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluate_robustness import raw_metrics, T0
from services.diagnosis.agent import DiagnosisAgent
from services.diagnosis.evidence import Aggregator, encoded
from services.diagnosis.notifications import NotificationPipeline
from services.diagnosis.provider import JsonProvider, ProviderConfig
from services.diagnosis.replay import grounded
import services.diagnosis.provider as provider_module
import services.recovery.kubernetes as kubernetes_module
from services.recovery.kubernetes import KubernetesAPI
import httpx

CASES = [
    ("valid_hypotheses", "validated"), ("valid_candidate", "validated"),
    ("malformed_json", "provider_invalid_response"),
    ("unsupported_evidence", "model_output_rejected"),
    ("action_request", "model_output_rejected"),
    ("tool_call", "provider_invalid_response"), ("abstain", "model_abstained"),
    ("timeout", "provider_timeout"), ("connection_error", "provider_unavailable"),
    ("http_503", "provider_http_error"),
    ("response_oversize", "provider_response_too_large"),
    ("compressed_valid", "provider_unsupported_encoding"),
    ("slow_trickle", "provider_timeout"),
    ("output_budget", "provider_output_budget_exceeded"),
    ("duplicate_json_keys", "provider_invalid_response"),
    ("call_budget", "call_budget_exhausted"),
    ("kubernetes_valid", "accepted"),
    ("kubernetes_oversize", "kubernetes_response_too_large"),
    ("kubernetes_compressed", "kubernetes_response_encoding"),
]


class Stream(httpx.SyncByteStream):
    def __init__(self, body, chunk_size=16384):
        self.body, self.chunk_size, self.chunks, self.closed = body, chunk_size, 0, False

    def __iter__(self):
        for offset in range(0, len(self.body), self.chunk_size):
            self.chunks += 1
            yield self.body[offset:offset+self.chunk_size]

    def close(self):
        self.closed = True


def fixture(name, expected, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    agg = Aggregator(T0)
    agg.snapshot({"at": T0, "raw": raw_metrics()})
    bundle = agg.finish()
    proposal = {"hypotheses": [{**bundle.candidates()[0], "confidence": .7}]}
    if name == "valid_candidate":
        proposal = {"selections": [{"candidate_index": 0, "confidence": .7}]}
    elif name == "unsupported_evidence":
        proposal["hypotheses"][0]["evidence_refs"] = ["ev-nonexistent"]
    elif name == "action_request":
        proposal["actions"] = ["delete namespace"]
    elif name == "abstain":
        proposal = {"hypotheses": []}
    body = json.dumps({"choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps(proposal), **({"tool_calls": ["synthetic"]} if name == "tool_call" else {})}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 801 if name == "output_budget" else 20}}).encode()
    limit = 262144 if name.startswith("kubernetes_") else 65536
    if name.startswith("kubernetes_"):
        body = b'{"ok":true}'
    if name in ("response_oversize", "kubernetes_oversize"):
        body = b"x" * (limit + 16384)
    elif name == "malformed_json":
        body = b"{"
    elif name == "duplicate_json_keys":
        body = b'{"choices":[],"choices":[]}'
    compressed = name in ("compressed_valid", "kubernetes_compressed")
    if compressed:
        body = gzip.compress(body)
    stream = Stream(body, 8 if name == "slow_trickle" else 16384)
    calls, observed_headers = [], []

    def handler(request):
        if name.startswith("kubernetes_"):
            assert request.method == "GET" and request.url.path == kubernetes_module.DEPLOYMENT_PATH
        calls.append(1)
        observed_headers.append(request.headers.get("accept-encoding"))
        if name == "timeout":
            raise httpx.ReadTimeout("fixture-secret")
        if name == "connection_error":
            raise httpx.ConnectError("fixture-secret")
        return httpx.Response(503 if name == "http_503" else 200, stream=stream,
                              headers={"Content-Encoding": "gzip"} if compressed else {})

    class Accumulator(builtins.bytearray):
        maximum = 0
        def extend(self, chunk):
            super().extend(chunk)
            type(self).maximum = max(type(self).maximum, len(self))

    with ExitStack() as stack:
        module = kubernetes_module if name.startswith("kubernetes_") else provider_module
        stack.enter_context(patch.object(module, "bytearray", Accumulator, create=True))
        if name.startswith("kubernetes_"):
            stack.enter_context(patch.object(kubernetes_module.ssl, "create_default_context", lambda **kwargs: True))
            token = directory / "synthetic-token"
            token.write_text("synthetic-executor-token")
            api = KubernetesAPI("https://127.0.0.1:6443", "test-only-ca", token,
                                transport=httpx.MockTransport(handler))
            try:
                try:
                    value = api.deployment()
                    status = "accepted" if value == {"ok": True} else "unexpected_result"
                except Exception as exc:
                    status = str(exc)
            finally:
                api.close()
            persisted, duplicate_suppressed, safe = True, True, True
        else:
            cfg = ProviderConfig(provider="openai-compatible", base_url="http://127.0.0.1:9999/v1",
                                 model="synthetic-fixture-not-a-model", max_calls=1,
                                 selection_mode="candidate_index" if name == "valid_candidate" else "hypotheses")
            provider = JsonProvider(cfg, transport=httpx.MockTransport(handler))
            if name == "slow_trickle":
                clock = iter([0, 0, 31])
                stack.enter_context(patch.object(provider_module.time, "monotonic", lambda: next(clock, 31)))
            if name == "call_budget":
                provider.propose(bundle)
            journal = directory / "notifications.sqlite3"
            pipeline = NotificationPipeline(DiagnosisAgent(provider), journal, clock=lambda: T0)
            event = {"schema_version": "day8-notification-v1", "notification_id": "notice-1",
                     "incident_id": "incident-1", "observed_at": T0}
            try:
                result = pipeline.handle(event, bundle)
                diagnosis = result["diagnosis"]
                status = diagnosis["provider_status"]
                before_duplicate = len(calls)
                duplicate = pipeline.handle(event, bundle)
                duplicate_suppressed = duplicate["status"] == "suppressed" and len(calls) == before_duplicate
                stored = pipeline.db.execute("SELECT result FROM episodes").fetchone()[0]
                persisted = stored == encoded(diagnosis)
                safe = diagnosis["execution_allowed"] is False
                if diagnosis["hypotheses"]:
                    safe = safe and grounded(diagnosis)
                if expected == "validated":
                    safe = safe and diagnosis["source"] == "llm"
            finally:
                pipeline.close()
        closed = stream.closed if name not in ("timeout", "connection_error") else True
        checks = {"expected_status": status == expected, "accumulator_bounded": Accumulator.maximum <= limit,
                  "stream_closed": closed, "one_request_at_most": len(calls) <= 1,
                  "failure_redacted": "fixture-secret" not in status, "execution_denied_or_read_only": safe,
                  "result_persisted": persisted, "duplicate_suppressed": duplicate_suppressed,
                  "compressed_unread": not compressed or stream.chunks == 0}
    if name.startswith("kubernetes_"):
        checks.pop("result_persisted")
        checks.pop("duplicate_suppressed")
    return {"name": name, "expected": expected, "actual_status": status, "checks": checks,
            "passed": all(checks.values()), "http_requests": len(calls), "stream_chunks": stream.chunks,
            "max_accumulator_bytes": Accumulator.maximum, "accumulator_limit": limit,
            "identity_encoding_requested": observed_headers == ["identity"],
            "journal": "notifications.sqlite3" if not name.startswith("kubernetes_") else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", choices=["baseline", "treatment"], required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases_hash = hashlib.sha256(json.dumps(CASES).encode()).hexdigest()
    rows = []
    for name, expected in CASES:
        try:
            row = fixture(name, expected, args.output / name)
        except Exception as exc:
            row = {"name": name, "passed": False, "harness_error": type(exc).__name__, "error": str(exc)}
        rows.append(row)
        (args.output / "trials.json").write_text(json.dumps(rows, indent=2))
    source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in [ROOT/"services/diagnosis", ROOT/"services/recovery"] for p in sorted(folder.glob("*.py"))}
    report = {"arm": args.arm, "case_manifest_sha256": cases_hash,
              "evaluator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source_sha256": source, "planned": len(CASES), "attempted": len(rows),
              "passed": sum(r["passed"] for r in rows), "failed": sum(not r["passed"] for r in rows),
              "harness_errors": sum("harness_error" in r for r in rows), "trials": rows,
              "scope": "19 purposive synthetic development fixtures; zero real model calls and zero cluster writes."}
    (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ("trials", "source_sha256")}, indent=2))
    return 1 if report["harness_errors"] or args.arm == "treatment" and report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
