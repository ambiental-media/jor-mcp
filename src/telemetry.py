"""OpenTelemetry SDK configuration and auto-instrumentation setup.

Initialise the TracerProvider once during ASGI lifespan startup.  Span export
is opt-in through ``OTEL_TRACES_EXPORTER`` (``otlp``, ``console`` or ``none``,
the default), so no deployment ships spans by accident: an unreachable OTLP
endpoint makes every batch export fail and fills the log with retry errors.
Spans are still created either way — that is where the ``trace_id`` on each log
record comes from.

This module also owns process-wide logging.  Every record leaves the process as
a single-line JSON object in the schema Cloud Logging expects — including
records emitted by libraries that install their own handlers.

Usage (inside ``server_lifespan``)::

    from src.telemetry import setup_telemetry, instrument_asgi_app

    setup_telemetry()
    instrument_asgi_app(starlette_app)
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar

import google.auth
import google.auth.exceptions
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.starlette import StarletteInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from starlette.applications import Starlette

from src.config import (
    CLOUD_RUN_SERVICE,
    GCP_PROJECT_ID,
    LOG_LEVEL,
    OTEL_EXPORTER_OTLP_ENDPOINT,
    OTEL_SERVICE_NAME,
    OTEL_TRACES_EXPORTER,
)

logger = logging.getLogger(__name__)

# Guard flag – prevents double-initialisation when the lifespan restarts in
# tests or during hot-reload scenarios.
_TELEMETRY_CONFIGURED: bool = False

# Third-party loggers whose handlers are removed so their records reach the
# single JSON handler configured by :func:`_configure_logging`.
_CAPTURED_LOGGERS: tuple[str, ...] = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastmcp",
    "mcp",
)

# Third-party loggers raised above INFO. httpx logs one line per outbound request
# containing the full URL, query string included — which is where API keys and
# tokens travel. WARNING keeps the failures without writing credentials to the log.
_LIBRARY_LOG_LEVELS: dict[str, int] = {
    "httpx": logging.WARNING,
}


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


class _TraceContextFilter(logging.Filter):
    """Inject the active OTel trace context into every LogRecord.

    The filter reads the current span from the OTel context and attaches
    ``trace_id``, ``span_id`` and ``trace_sampled`` to each record so
    downstream formatters can emit them.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
            record.trace_sampled = ctx.trace_flags.sampled
        else:
            record.trace_id = ""
            record.span_id = ""
            record.trace_sampled = False
        return True


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Includes ``trace_id`` / ``span_id`` (set by :class:`_TraceContextFilter`)
    and any additional fields passed via ``logger.info(..., extra={...})``.
    The output schema is compatible with Google Cloud Logging structured logs.

    Args:
        project_id: Google Cloud project owning the traces.  When empty the
            Cloud Logging correlation fields are omitted, since the ``trace``
            field is only valid as ``projects/<project-id>/traces/<trace-id>``.
    """

    def __init__(self, project_id: str = "") -> None:
        super().__init__()
        self._project_id = project_id

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
            "trace_sampled",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        trace_id = getattr(record, "trace_id", "")
        span_id = getattr(record, "span_id", "")

        # Tracebacks belong in `message`: Cloud Logging keeps the whole record as
        # one entry because the newlines are JSON-escaped, and Error Reporting only
        # groups a stack trace when it is part of the message.
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            message = f"{message}\n{self.formatStack(record.stack_info)}"

        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "severity": record.levelname,
            "logger": record.name,
            "message": message,
        }
        # The Cloud Logging fields already carry the trace and span; emitting the raw
        # pair alongside them would repeat the same ids three times per record.
        if trace_id and self._project_id:
            payload["logging.googleapis.com/trace"] = (
                f"projects/{self._project_id}/traces/{trace_id}"
            )
            payload["logging.googleapis.com/spanId"] = span_id
            payload["logging.googleapis.com/trace_sampled"] = getattr(
                record, "trace_sampled", False
            )
        elif trace_id:
            payload["trace_id"] = trace_id
            payload["span_id"] = span_id
        # The logger name locates routine records well enough; a file path is worth
        # its size only when something went wrong.
        if record.levelno >= logging.WARNING:
            payload["logging.googleapis.com/sourceLocation"] = {
                "file": record.pathname,
                "line": str(record.lineno),
                "function": record.funcName,
            }
        extra = {k: v for k, v in record.__dict__.items() if k not in self._STD_ATTRS}
        if extra:
            payload["extra"] = extra
        # `default=str` keeps a non-serialisable value in `extra` from raising inside
        # the handler, which would print a multi-line logging error to stderr.
        return json.dumps(payload, ensure_ascii=False, default=str)


def _resolve_gcp_project_id() -> str:
    """Return the Google Cloud project ID used in trace correlation fields.

    ``GCP_PROJECT_ID`` wins when set.  Cloud Run does not inject it, so there
    the project is read from the ambient credentials instead.  Returns an empty
    string anywhere else, and the Cloud Logging correlation fields are then
    omitted — a deployment outside Cloud Run must set ``GCP_PROJECT_ID``.
    """
    if GCP_PROJECT_ID:
        return GCP_PROJECT_ID
    # google.auth.default() probes the GCE metadata server as its last resort, and
    # where that server does not answer it retries for ~12s before giving up. Only
    # Cloud Run, where the reply is immediate, is allowed down that path.
    if not CLOUD_RUN_SERVICE:
        return ""
    try:
        _, project_id = google.auth.default()
    except google.auth.exceptions.DefaultCredentialsError:
        return ""
    return project_id or ""


def _configure_logging() -> None:
    """Route every log record through a single JSON handler on stdout.

    Replaces the root handlers with one :class:`~logging.StreamHandler` writing
    JSON to stdout, then strips the handlers of the libraries listed in
    :data:`_CAPTURED_LOGGERS` and re-enables their propagation.  Libraries in
    :data:`_LIBRARY_LOG_LEVELS` are raised to their configured level.  Calling
    this more than once is safe: handlers are replaced, never accumulated.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_TraceContextFilter())
    handler.setFormatter(_JsonFormatter(_resolve_gcp_project_id()))

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)

    # These libraries install their own handlers and set propagate=False, so their
    # records never reach the root handler: FastMCP writes through RichHandler
    # (which wraps long lines at the console width) and uvicorn writes plain text
    # with bare tracebacks. Cloud Logging ingests one entry per physical line, so
    # a single traceback lands as a dozen unrelated entries.
    for name in _CAPTURED_LOGGERS:
        lib_logger = logging.getLogger(name)
        for existing in lib_logger.handlers[:]:
            lib_logger.removeHandler(existing)
        lib_logger.propagate = True

    for name, level in _LIBRARY_LOG_LEVELS.items():
        logging.getLogger(name).setLevel(level)


# ---------------------------------------------------------------------------
# Tracing helpers
# ---------------------------------------------------------------------------


def _build_span_exporter() -> SpanExporter | None:
    """Return the span exporter named by ``OTEL_TRACES_EXPORTER``.

    ``none`` — the default — returns ``None`` so the provider runs without a
    span processor, which is the right state wherever no collector is
    reachable.  ``console`` prints one span per line; the SDK default of
    ``indent=4`` would spread a single span over dozens of log entries.
    """
    if OTEL_TRACES_EXPORTER == "none":
        return None
    if OTEL_TRACES_EXPORTER == "console":
        return ConsoleSpanExporter(formatter=_single_line_span)
    return OTLPSpanExporter(endpoint=OTEL_EXPORTER_OTLP_ENDPOINT)


def _single_line_span(span: ReadableSpan) -> str:
    return f"{span.to_json(indent=None)}\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_telemetry() -> None:
    """Initialise the OpenTelemetry TracerProvider and attach global instrumentors.

    This function is idempotent: subsequent calls are no-ops.  It must be
    invoked once during the ASGI lifespan startup **before** the HTTP client
    is created so its spans are correctly captured.

    Exporter selection is delegated to :func:`_build_span_exporter`.

    Global instrumentors activated:

    - :class:`~opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor` –
      traces every outbound HTTP request made via ``httpx.AsyncClient``.

    Call :func:`instrument_asgi_app` separately to add ASGI-level spans.
    """
    global _TELEMETRY_CONFIGURED
    if _TELEMETRY_CONFIGURED:
        return

    resource = Resource.create({SERVICE_NAME: OTEL_SERVICE_NAME})

    provider = TracerProvider(resource=resource)
    exporter = _build_span_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    HTTPXClientInstrumentor().instrument()
    _configure_logging()

    _TELEMETRY_CONFIGURED = True
    logger.info(
        "OpenTelemetry configured",
        extra={
            "exporter": OTEL_TRACES_EXPORTER,
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
