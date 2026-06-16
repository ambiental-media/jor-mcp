"""Tests for src/telemetry.py."""

import logging
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace

import src.telemetry as telemetry_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_telemetry_flag() -> Generator[None, None, None]:
    """Restore the _TELEMETRY_CONFIGURED flag after each test."""
    original = telemetry_mod._TELEMETRY_CONFIGURED
    yield
    telemetry_mod._TELEMETRY_CONFIGURED = original


# ---------------------------------------------------------------------------
# _TraceContextFilter
# ---------------------------------------------------------------------------


class TestTraceContextFilter:
    def test_injects_trace_and_span_ids_when_span_is_active(self) -> None:
        mock_span = MagicMock()
        ctx = MagicMock()
        ctx.is_valid = True
        ctx.trace_id = 0xABCDEF1234567890ABCDEF1234567890
        ctx.span_id = 0x1234567890ABCDEF
        mock_span.get_span_context.return_value = ctx

        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)

        with patch("src.telemetry.trace.get_current_span", return_value=mock_span):
            result = telemetry_mod._TraceContextFilter().filter(record)

        assert result is True
        assert getattr(record, "trace_id", "") != ""
        assert getattr(record, "span_id", "") != ""
        assert len(vars(record)["trace_id"]) == 32  # 128-bit hex
        assert len(vars(record)["span_id"]) == 16  # 64-bit hex

    def test_injects_empty_strings_when_no_active_span(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)

        with patch("src.telemetry.trace.get_current_span", return_value=trace.INVALID_SPAN):
            result = telemetry_mod._TraceContextFilter().filter(record)

        assert result is True
        assert getattr(record, "trace_id", None) == ""
        assert getattr(record, "span_id", None) == ""


# ---------------------------------------------------------------------------
# _JsonFormatter
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello world", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

        with patch("src.telemetry.GCP_PROJECT_ID", ""):
            output = telemetry_mod._JsonFormatter().format(record)
            parsed = json.loads(output)

        assert parsed["message"] == "hello world"
        assert parsed["severity"] == "INFO"
        assert parsed["logger"] == "mylogger"
        assert parsed["trace_id"] == "abc123"
        assert parsed["span_id"] == "def456"

    def test_gcp_trace_fields_are_present_when_project_is_configured(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello world", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

        with patch("src.telemetry.GCP_PROJECT_ID", "jor-prod"):
            output = telemetry_mod._JsonFormatter().format(record)
            parsed = json.loads(output)

        assert parsed["logging.googleapis.com/trace"] == "projects/jor-prod/traces/abc123"
        assert parsed["logging.googleapis.com/spanId"] == "def456"

    def test_gcp_trace_fields_are_not_present_without_project_id(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello world", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

        with patch("src.telemetry.GCP_PROJECT_ID", ""):
            output = telemetry_mod._JsonFormatter().format(record)
            parsed = json.loads(output)

        assert "logging.googleapis.com/trace" not in parsed
        assert "logging.googleapis.com/spanId" not in parsed

    def test_extra_fields_appear_under_extra_key(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.WARNING, "", 0, "w", (), None)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""
        record.__dict__["user_id"] = "u-42"

        output = telemetry_mod._JsonFormatter().format(record)
        parsed = json.loads(output)

        assert "extra" in parsed
        assert parsed["extra"]["user_id"] == "u-42"

    def test_exc_info_included_when_present(self) -> None:
        import json

        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord("mylogger", logging.ERROR, "", 0, "err", (), exc_info)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""

        output = telemetry_mod._JsonFormatter().format(record)
        parsed = json.loads(output)

        assert "exc_info" in parsed
        assert "ValueError" in parsed["exc_info"]


# ---------------------------------------------------------------------------
# setup_telemetry
# ---------------------------------------------------------------------------


class TestSetupTelemetry:
    def _patch_all(self, *, endpoint: str | None) -> tuple[object, ...]:
        return (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", endpoint),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.OTLPSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging"),
        )

    def test_uses_console_exporter_when_endpoint_absent(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", None),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.OTLPSpanExporter") as mock_otlp,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_console.assert_called_once()
        mock_otlp.assert_not_called()

    def test_uses_otlp_exporter_when_endpoint_present(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False
        endpoint = "http://otel-collector:4318"

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", endpoint),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.OTLPSpanExporter") as mock_otlp,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_otlp.assert_called_once_with(endpoint=endpoint)
        mock_console.assert_not_called()

    def test_is_idempotent_on_repeated_calls(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", None),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()
            telemetry_mod.setup_telemetry()  # second call – must be a no-op

        mock_console.assert_called_once()

    def test_instruments_httpx_and_redis(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        mock_httpx = MagicMock()
        mock_redis = MagicMock()

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", None),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor", return_value=mock_httpx),
            patch("src.telemetry.RedisInstrumentor", return_value=mock_redis),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_httpx.instrument.assert_called_once()
        mock_redis.instrument.assert_called_once()

    def test_sets_telemetry_configured_flag(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", None),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        assert telemetry_mod._TELEMETRY_CONFIGURED is True

    def test_calls_configure_logging(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", None),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry.RedisInstrumentor"),
            patch("src.telemetry._configure_logging") as mock_configure,
        ):
            telemetry_mod.setup_telemetry()

        mock_configure.assert_called_once()


# ---------------------------------------------------------------------------
# _configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    def test_adds_filter_and_formatter_to_existing_stream_handler(self) -> None:
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        handler = logging.StreamHandler()
        root.handlers = [handler]  # Isolate so _configure_logging finds only our handler
        try:
            root.setLevel(logging.WARNING)
            telemetry_mod._configure_logging()
            assert any(isinstance(f, telemetry_mod._TraceContextFilter) for f in handler.filters)
            assert isinstance(handler.formatter, telemetry_mod._JsonFormatter)
            assert root.level == logging.INFO
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)

    def test_creates_new_handler_when_root_has_no_stream_handler(self) -> None:
        root = logging.getLogger()
        original_handlers = root.handlers[:]
        original_level = root.level
        root.handlers = []
        try:
            telemetry_mod._configure_logging()
            assert len(root.handlers) == 1
            new_handler = root.handlers[0]
            assert isinstance(new_handler, logging.StreamHandler)
            assert any(
                isinstance(f, telemetry_mod._TraceContextFilter) for f in new_handler.filters
            )
            assert isinstance(new_handler.formatter, telemetry_mod._JsonFormatter)
            assert root.level == logging.INFO
        finally:
            root.handlers = original_handlers
            root.setLevel(original_level)


# ---------------------------------------------------------------------------
# instrument_asgi_app
# ---------------------------------------------------------------------------


class TestInstrumentAsgiApp:
    def test_calls_starlette_instrumentor_instrument_app(self) -> None:
        mock_instrumentor = MagicMock()
        mock_app = MagicMock()

        with patch("src.telemetry.StarletteInstrumentor", return_value=mock_instrumentor):
            telemetry_mod.instrument_asgi_app(mock_app)

        mock_instrumentor.instrument_app.assert_called_once_with(mock_app)
