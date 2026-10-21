"""Per-process metrics and bounded, correlated JSON logs; no telemetry leaves the lab."""
from datetime import datetime, timezone
from contextlib import nullcontext
from opentelemetry.trace import SpanKind, Status, StatusCode
from services.tracing import propagator
import json
import logging
import time
from uuid import uuid4

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

logger = logging.getLogger("safeheal.requests")
METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CONNECT"})
EXCLUDED = frozenset({"/metrics", "/healthz", "/readyz"})
BUCKETS = (.005, .01, .025, .05, .1, .25, .5, 1., 2., 3., 5., 10.)


class Metrics:
    def __init__(self):
        # Factories/tests may create several apps in one process. Never share global collectors.
        self.registry = CollectorRegistry()
        labels = ("service", "method", "route", "status_class")
        self.requests = Counter("safeheal_http_requests_total", "Completed application requests", labels,
                                registry=self.registry)
        self.duration = Histogram("safeheal_http_request_duration_seconds", "Full ASGI request duration",
                                  labels, buckets=BUCKETS, registry=self.registry)
        self.inflight = Gauge("safeheal_http_requests_in_progress", "Active application requests",
                              ("service",), registry=self.registry)


class ObservabilityMiddleware:
    def __init__(self, app, role, metrics, tracer):
        self.app, self.role, self.metrics, self.tracer = app, role, metrics, tracer

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        supplied = headers.get(b"x-request-id", b"").decode("ascii", errors="replace")
        request_id = supplied if supplied and len(supplied) <= 64 and all(
            c.isascii() and (c.isalnum() or c in "-_") for c in supplied
        ) else str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        method = scope["method"] if scope["method"] in METHODS else "OTHER"
        measured = scope["path"] not in EXCLUDED
        started, status, error_type = time.perf_counter(), 500, None
        if measured:
            self.metrics.inflight.labels(self.role).inc()

        async def wrapped_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [(k, v) for k, v in message.get("headers", [])
                                      if k.lower() != b"x-request-id"] + [
                                          (b"x-request-id", request_id.encode("ascii"))]
            await send(message)

        carrier = {k.decode("latin1"): v.decode("latin1") for k, v in scope.get("headers", [])}
        span_context = self.tracer.start_as_current_span(
            method, context=propagator.extract(carrier), kind=SpanKind.SERVER,
            attributes={"request_id": request_id, "http.request.method": method},
            record_exception=False, set_status_on_exception=False) if measured else nullcontext(None)
        with span_context as span:
            try:
                await self.app(scope, receive, wrapped_send)
            except BaseException as exc:
                error_type = type(exc).__name__
                raise
            finally:
                elapsed = time.perf_counter() - started
                route = getattr(scope.get("route"), "path", "__unmatched__")
                if span:
                    span.update_name(f"{method} {route}")
                    span.set_attribute("http.route", route)
                    span.set_attribute("http.response.status_code", status)
                    if status >= 500 or error_type:
                        span.set_status(Status(StatusCode.ERROR))
                if measured:
                    labels = (self.role, method, route, f"{status // 100}xx")
                    self.metrics.requests.labels(*labels).inc()
                    self.metrics.duration.labels(*labels).observe(elapsed)
                    self.metrics.inflight.labels(self.role).dec()
                if scope["path"] != "/metrics":
                    logger.info(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": self.role, "request_id": request_id, "method": method,
                        "path": route, "status": status, "duration_ms": round(elapsed * 1000, 3),
                        "exception_type": error_type,
                        "trace_id": f"{span.get_span_context().trace_id:032x}" if span else None,
                        "span_id": f"{span.get_span_context().span_id:016x}" if span else None}))
