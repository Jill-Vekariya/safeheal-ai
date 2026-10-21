"""Basic OpenTelemetry spans with W3C propagation and a local JSON-log exporter."""
import json
import logging

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

propagator = TraceContextTextMapPropagator()


class JsonLogExporter(SpanExporter):
    def export(self, spans):
        for span in spans:
            logging.getLogger("safeheal.traces").info(json.dumps({
                "event": "span", "service": span.resource.attributes["service.name"],
                "trace_id": f"{span.context.trace_id:032x}", "span_id": f"{span.context.span_id:016x}",
                "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else None,
                "name": span.name, "kind": span.kind.name, "status": span.status.status_code.name,
                "start_time_unix_nano": span.start_time, "end_time_unix_nano": span.end_time,
                "duration_ms": (span.end_time - span.start_time) / 1e6,
                "attributes": dict(span.attributes)}))
        return SpanExportResult.SUCCESS


def make_tracer(role):
    provider = TracerProvider(resource=Resource.create({"service.name": role}))
    provider.add_span_processor(SimpleSpanProcessor(JsonLogExporter()))
    return provider, provider.get_tracer("safeheal.manual", "0.1.0")
