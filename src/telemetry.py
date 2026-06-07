"""OpenTelemetry SDK configuration and auto-instrumentation setup.

Initialise the TracerProvider once during ASGI lifespan startup.  When the
``OTEL_EXPORTER_OTLP_ENDPOINT`` environment variable is set the SDK exports
spans via OTLP/HTTP (compatible with Google Cloud Trace and any OpenTelemetry
Collector).  Without that variable it falls back to :class:`ConsoleSpanExporter`
for local development and debugging.

Usage (inside ``server_lifespan``)::

    from src.telemetry import setup_telemetry, instrument_asgi_app

    setup_telemetry()
    instrument_asgi_app(starlette_app)
"""

import json
import logging
from typing import Any, ClassVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from starlette.applications import Starlette

from src.config import OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_SERVICE_NAME

logger = logging.getLogger(__name__)

# Guard flag – prevents double-initialisation when the lifespan restarts in
# tests or during hot-reload scenarios.
_TELEMETRY_CONFIGURED: bool = False


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


class _TraceContextFilter(logging.Filter):
    """Inject the active OTel ``trace_id`` and ``span_id`` into every LogRecord.

    The filter reads the current span from the OTel context and attaches two
    new attributes to each record so downstream formatters can emit them.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = ""
            record.span_id = ""
        return True


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Includes ``trace_id`` / ``span_id`` (set by :class:`_TraceContextFilter`)
    and any additional fields passed via ``logger.info(..., extra={...})``.
    The output schema is compatible with Google Cloud Logging structured logs.
    """

    # Standard :class:`logging.LogRecord` attributes that must not appear in
    # the ``extra`` section of the emitted JSON object.
    _STD_ATTRS: ClassVar[frozenset[str]] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "span_id",
            "stack_info",
            "taskName",
            "thread",
            "threadName",
            "trace_id",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": self.formatTime(record),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "span_id": getattr(record, "span_id", ""),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in self._STD_ATTRS}
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _configure_logging() -> None:
    """Attach the trace context filter and JSON formatter to the root logger.

    If a :class:`~logging.StreamHandler` already exists on the root logger the
    filter and formatter are applied to it; otherwise a new handler is created.
    This prevents duplicate handlers when the function is called more than once.
    """
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.addFilter(_TraceContextFilter())
            handler.setFormatter(_JsonFormatter())
            return
    handler = logging.StreamHandler()
    handler.addFilter(_TraceContextFilter())
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_telemetry() -> None:
    """Initialise the OpenTelemetry TracerProvider and attach global instrumentors.

    This function is idempotent: subsequent calls are no-ops.  It must be
    invoked once during the ASGI lifespan startup **before** the HTTP client
    and Redis client are created so their spans are correctly captured.

    Exporter selection:

    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` set → :class:`OTLPSpanExporter` (HTTP)
      for Google Cloud Trace / any OTLP Collector.
    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` absent → :class:`ConsoleSpanExporter`
      for local development (spans printed to stdout).

    Global instrumentors activated:

    - :class:`~opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor` –
      traces every outbound HTTP request made via ``httpx.AsyncClient``.
    - :class:`~opentelemetry.instrumentation.redis.RedisInstrumentor` –
      traces every Redis command.

    Call :func:`instrument_asgi_app` separately to add ASGI-level spans.
    """
    global _TELEMETRY_CONFIGURED
    if _TELEMETRY_CONFIGURED:
        return

    resource = Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})

    exporter: ConsoleSpanExporter | OTLPSpanExporter
    if OTEL_EXPORTER_OTLP_ENDPOINT:
        exporter = OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)
    else:
        exporter = ConsoleSpanExporter()

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    RedisInstrumentor().instrument()
    _configure_logging()

    _TELEMETRY_CONFIGURED = True
    logger.info(
        "OpenTelemetry configured",
        extra={
            "exporter": "otlp" if OTEL_EXPORTER_OTLP_ENDPOINT else "console",
            "service_name": OTEL_SERVICE_NAME,
        },
    )


def instrument_asgi_app(app: Starlette) -> None:
    """Instrument a Starlette app with OpenTelemetry ASGI middleware.

    Wraps *app* with :class:`~opentelemetry.instrumentation.starlette.StarletteInstrumentor`
    so every incoming HTTP request generates a root span.  Must be called
    during lifespan startup, before the application handles its first request.

    Args:
        app: The :class:`~starlette.applications.Starlette` instance to
            instrument.  Typically the inner ``_starlette_app`` in
            ``src/server.py``, **not** the outer middleware-wrapped ``app``.
    """
    StarletteInstrumentor().instrument_app(app)
