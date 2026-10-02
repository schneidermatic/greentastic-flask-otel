"""OpenTelemetry: traces, metrics and logs of the shop, sent via OTLP to the EDOT collector.

Nothing happens unless OTEL_EXPORTER_OTLP_ENDPOINT is set (see docker-compose.yml) - tests and local runs
work without a collector. The exporters read the standard OTEL_* environment variables themselves.

What you get:
  * traces  - one server span per HTTP request (Flask) with a child span for every SQL statement (psycopg),
              Redis command and Elasticsearch request, plus a few own spans (cache lookup, checkout)
  * metrics - the shop's business numbers below, plus the HTTP metrics of the Flask instrumentation
  * logs    - every Python log record, correlated with the trace it was written in
"""
import logging
import os
import socket

from opentelemetry import metrics, trace

# --- Own instruments. They can be used anywhere; until setup() runs they do nothing. -----------------
tracer = trace.get_tracer("greentastic")
meter = metrics.get_meter("greentastic")

orders_placed = meter.create_counter("greentastic.orders.placed", unit="1", description="Orders placed at checkout")
order_value = meter.create_histogram("greentastic.orders.value", unit="EUR", description="Value of placed orders")
cart_additions = meter.create_counter("greentastic.cart.additions", unit="1", description="Products added to a cart")
cache_lookups = meter.create_counter("greentastic.cache.lookups", unit="1", description="Product list lookups (hit/miss/error)")
searches = meter.create_counter("greentastic.searches", unit="1", description="Search requests (kind, outcome)")
logins = meter.create_counter("greentastic.logins", unit="1", description="Login attempts (outcome)")
simulated_errors = meter.create_counter("greentastic.simulated_errors", unit="1", description="Calls of /api/simulate/* (kind)")


def setup(app):
    """Configure the OpenTelemetry SDK and instrument Flask, psycopg, Redis and Elasticsearch."""
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.elasticsearch import ElasticsearchInstrumentor
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.resource.detector.containerid import ContainerResourceDetector
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Who is sending? service.name comes from OTEL_SERVICE_NAME. Every gunicorn worker is its own instance;
    # container.id and host.name link the service to its container in Kibana.
    resource = Resource.create({
        "service.version": "0.1.0",
        "service.instance.id": f"{socket.gethostname()}-{os.getpid()}",
        "host.name": socket.gethostname(),
    }).merge(ContainerResourceDetector().detect())

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(), export_interval_millis=10000)],
    ))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)  # it logs every request at INFO level

    # Automatic instrumentation: these create the spans for HTTP requests and for every call to a service.
    FlaskInstrumentor().instrument_app(app)
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    ElasticsearchInstrumentor().instrument()
