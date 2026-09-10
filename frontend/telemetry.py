import os
import sys
import logging
import json
from datetime import datetime
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource

class JsonFormatter(logging.Formatter):
    def __init__(self, service_name):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "message": record.getMessage(),
        }
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_record["trace_id"] = format(ctx.trace_id, '032x')
            log_record["span_id"] = format(ctx.span_id, '016x')
        else:
            log_record["trace_id"] = ""
            log_record["span_id"] = ""
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record)

def setup_logging(service_name):
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service_name))
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    
    # Configure werkzeug to use root logger handlers and log at INFO level
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.handlers = []

def setup_telemetry(app, service_name):
    setup_logging(service_name)
    
    resource = Resource.create(attributes={
        "service.name": service_name
    })
    
    provider = TracerProvider(resource=resource)
    
    # Detect if we are running in unit tests or pytest discovery
    is_testing = (
        app.config.get("TESTING")
        or os.environ.get("PYTEST_CURRENT_TEST") is not None
        or "pytest" in sys.modules
        or any("pytest" in arg for arg in sys.argv)
    )
    
    if is_testing:
        # No exporter in testing mode to avoid connection errors / noise in logs
        trace.set_tracer_provider(provider)
    else:
        # Default OTLP endpoint is http://otel-collector:4317
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
        
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        except Exception as e:
            logging.error(f"Failed to load OTLP gRPC exporter: {e}. Falling back to HTTP exporter.")
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            http_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_HTTP_ENDPOINT", "http://otel-collector:4318/v1/traces")
            exporter = OTLPSpanExporter(endpoint=http_endpoint)
            
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
    
    # Instrument Flask app
    from opentelemetry.instrumentation.flask import FlaskInstrumentor
    FlaskInstrumentor().instrument_app(app)
    
    # Instrument outgoing Requests calls
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    RequestsInstrumentor().instrument()
    
    # Setup metrics
    try:
        from prometheus_flask_exporter import PrometheusMetrics
        metrics = PrometheusMetrics(app, group_by='endpoint')
        metrics.info('app_info', 'Application info', version='1.0.0')
        logging.info("Prometheus metrics initialized on /metrics")
    except Exception as e:
        logging.error(f"Failed to initialize Prometheus metrics: {e}")
        
    logging.info(f"OpenTelemetry telemetry initialized for {service_name}")
