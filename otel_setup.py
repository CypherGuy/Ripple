"""
Shared OpenTelemetry setup for all Ripple services.
Configures an OTLP exporter pointing at Dynatrace.
If DT_ENVIRONMENT or DT_OTEL_TOKEN are not set, falls back to a no-op tracer.
"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME


def setup_tracer(service_name: str) -> trace.Tracer:
    dt_env = os.environ.get("DT_ENVIRONMENT", "").strip()
    dt_token = os.environ.get("DT_OTEL_TOKEN", "").strip()

    resource = Resource.create({SERVICE_NAME: f"ripple-{service_name}"})

    if dt_env and dt_token:
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=f"https://{dt_env}/api/v2/otlp/v1/traces",
            headers={"Authorization": f"Api-Token {dt_token}"},
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    else:
        trace.set_tracer_provider(TracerProvider(resource=resource))

    return trace.get_tracer(f"ripple.{service_name}")
