"""Tests for src/telemetry.py."""

import logging
from collections.abc import Generator
from io import StringIO
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
        assert getattr(record, "trace_sampled", None) is False

    def test_injects_sampling_decision_from_active_span(self) -> None:
        mock_span = MagicMock()
        ctx = MagicMock()
        ctx.is_valid = True
        ctx.trace_id = 0xABCDEF1234567890ABCDEF1234567890
        ctx.span_id = 0x1234567890ABCDEF
        ctx.trace_flags.sampled = True
        mock_span.get_span_context.return_value = ctx

        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)

        with patch("src.telemetry.trace.get_current_span", return_value=mock_span):
            telemetry_mod._TraceContextFilter().filter(record)

        assert vars(record)["trace_sampled"] is True


# ---------------------------------------------------------------------------
# _JsonFormatter
# ---------------------------------------------------------------------------


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello world", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

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

        output = telemetry_mod._JsonFormatter("jor-prod").format(record)
        parsed = json.loads(output)

        assert parsed["logging.googleapis.com/trace"] == "projects/jor-prod/traces/abc123"
        assert parsed["logging.googleapis.com/spanId"] == "def456"

    def test_gcp_trace_fields_are_not_present_without_project_id(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello world", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

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

    def test_traceback_is_appended_to_message_as_a_single_line(self) -> None:
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

        assert "\n" not in output  # one physical line -> one Cloud Logging entry
        assert parsed["message"].startswith("err\n")
        assert "ValueError: boom" in parsed["message"]
        assert "Traceback (most recent call last)" in parsed["message"]

    def test_stack_info_is_appended_to_message(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.WARNING, "", 0, "where am i", (), None)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""
        record.stack_info = 'Stack (most recent call last):\n  File "x.py", line 1'

        output = telemetry_mod._JsonFormatter().format(record)
        parsed = json.loads(output)

        assert "\n" not in output
        assert parsed["message"].startswith("where am i\n")
        assert "Stack (most recent call last)" in parsed["message"]

    def test_time_is_rfc3339(self) -> None:
        import json
        from datetime import datetime

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello", (), None)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""

        parsed = json.loads(telemetry_mod._JsonFormatter().format(record))

        parsed_time = datetime.fromisoformat(parsed["time"])
        assert parsed_time.tzinfo is not None
        assert parsed_time.timestamp() == pytest.approx(record.created)

    def test_source_location_is_reported_from_warning_up(self) -> None:
        import json

        record = logging.LogRecord(
            "mylogger", logging.WARNING, "/app/src/tools.py", 42, "hello", (), None, func="search"
        )
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""

        parsed = json.loads(telemetry_mod._JsonFormatter().format(record))

        assert parsed["logging.googleapis.com/sourceLocation"] == {
            "file": "/app/src/tools.py",
            "line": "42",
            "function": "search",
        }

    def test_source_location_is_omitted_below_warning(self) -> None:
        import json

        record = logging.LogRecord(
            "mylogger", logging.INFO, "/app/src/tools.py", 42, "hello", (), None, func="search"
        )
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""

        parsed = json.loads(telemetry_mod._JsonFormatter().format(record))

        assert "logging.googleapis.com/sourceLocation" not in parsed

    def test_raw_trace_ids_are_dropped_when_cloud_fields_are_emitted(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"

        parsed = json.loads(telemetry_mod._JsonFormatter("jor-prod").format(record))

        assert "trace_id" not in parsed
        assert "span_id" not in parsed
        assert parsed["logging.googleapis.com/trace"] == "projects/jor-prod/traces/abc123"

    def test_trace_ids_are_omitted_entirely_without_an_active_span(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello", (), None)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""

        parsed = json.loads(telemetry_mod._JsonFormatter("jor-prod").format(record))

        assert "trace_id" not in parsed
        assert "span_id" not in parsed

    def test_trace_sampled_is_reported_with_project_id(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello", (), None)
        record.__dict__["trace_id"] = "abc123"
        record.__dict__["span_id"] = "def456"
        record.__dict__["trace_sampled"] = True

        parsed = json.loads(telemetry_mod._JsonFormatter("jor-prod").format(record))

        assert parsed["logging.googleapis.com/trace_sampled"] is True

    def test_non_serialisable_extra_does_not_raise(self) -> None:
        import json

        record = logging.LogRecord("mylogger", logging.INFO, "", 0, "hello", (), None)
        record.__dict__["trace_id"] = ""
        record.__dict__["span_id"] = ""
        record.__dict__["client"] = object()

        parsed = json.loads(telemetry_mod._JsonFormatter().format(record))

        assert "object object at" in parsed["extra"]["client"]


# ---------------------------------------------------------------------------
# setup_telemetry
# ---------------------------------------------------------------------------


class TestSetupTelemetry:
    def test_uses_console_exporter_when_selected(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "console"),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.OTLPSpanExporter") as mock_otlp,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_console.assert_called_once_with(formatter=telemetry_mod._single_line_span)
        mock_otlp.assert_not_called()

    def test_uses_otlp_exporter_when_selected(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False
        endpoint = "http://otel-collector:4318"

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "otlp"),
            patch("src.telemetry.OTEL_EXPORTER_OTLP_ENDPOINT", endpoint),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.OTLPSpanExporter") as mock_otlp,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_otlp.assert_called_once_with(endpoint=endpoint)
        mock_console.assert_not_called()

    def test_registers_no_span_processor_when_exporter_is_none(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False
        mock_provider = MagicMock()

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "none"),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.OTLPSpanExporter") as mock_otlp,
            patch("src.telemetry.BatchSpanProcessor") as mock_processor,
            patch("src.telemetry.TracerProvider", return_value=mock_provider),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_console.assert_not_called()
        mock_otlp.assert_not_called()
        mock_processor.assert_not_called()
        mock_provider.add_span_processor.assert_not_called()

    def test_is_idempotent_on_repeated_calls(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "console"),
            patch("src.telemetry.ConsoleSpanExporter") as mock_console,
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()
            telemetry_mod.setup_telemetry()  # second call – must be a no-op

        mock_console.assert_called_once()

    def test_instruments_httpx(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        mock_httpx = MagicMock()

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "console"),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor", return_value=mock_httpx),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        mock_httpx.instrument.assert_called_once()

    def test_sets_telemetry_configured_flag(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "console"),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging"),
        ):
            telemetry_mod.setup_telemetry()

        assert telemetry_mod._TELEMETRY_CONFIGURED is True

    def test_calls_configure_logging(self) -> None:
        telemetry_mod._TELEMETRY_CONFIGURED = False

        with (
            patch("src.telemetry.OTEL_TRACES_EXPORTER", "console"),
            patch("src.telemetry.ConsoleSpanExporter"),
            patch("src.telemetry.BatchSpanProcessor"),
            patch("src.telemetry.TracerProvider"),
            patch("src.telemetry.trace.set_tracer_provider"),
            patch("src.telemetry.HTTPXClientInstrumentor"),
            patch("src.telemetry._configure_logging") as mock_configure,
        ):
            telemetry_mod.setup_telemetry()

        mock_configure.assert_called_once()


# ---------------------------------------------------------------------------
# _configure_logging
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_logging() -> Generator[None, None, None]:
    """Snapshot the loggers _configure_logging mutates and restore them afterwards."""
    root = logging.getLogger()
    root_handlers = root.handlers[:]
    root_level = root.level
    captured = {
        name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate)
        for name in telemetry_mod._CAPTURED_LOGGERS
    }
    levels = {name: logging.getLogger(name).level for name in telemetry_mod._LIBRARY_LOG_LEVELS}
    try:
        yield
    finally:
        root.handlers = root_handlers
        root.setLevel(root_level)
        for name, (handlers, propagate) in captured.items():
            lib_logger = logging.getLogger(name)
            lib_logger.handlers = handlers
            lib_logger.propagate = propagate
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)


class TestSingleLineSpan:
    def test_serialises_a_span_onto_one_line(self) -> None:
        span = MagicMock()
        span.to_json.return_value = '{"name": "GET /mcp"}'

        output = telemetry_mod._single_line_span(span)

        assert output == '{"name": "GET /mcp"}\n'
        span.to_json.assert_called_once_with(indent=None)


class TestResolveGcpProjectId:
    def test_prefers_the_configured_environment_variable(self) -> None:
        with (
            patch("src.telemetry.GCP_PROJECT_ID", "from-env"),
            patch("src.telemetry.google.auth.default") as mock_default,
        ):
            assert telemetry_mod._resolve_gcp_project_id() == "from-env"

        mock_default.assert_not_called()

    def test_falls_back_to_the_ambient_credentials_on_cloud_run(self) -> None:
        with (
            patch("src.telemetry.GCP_PROJECT_ID", ""),
            patch("src.telemetry.CLOUD_RUN_SERVICE", "jor-mcp-server"),
            patch("src.telemetry.google.auth.default", return_value=(MagicMock(), "from-adc")),
        ):
            assert telemetry_mod._resolve_gcp_project_id() == "from-adc"

    def test_skips_the_metadata_lookup_outside_cloud_run(self) -> None:
        with (
            patch("src.telemetry.GCP_PROJECT_ID", ""),
            patch("src.telemetry.CLOUD_RUN_SERVICE", ""),
            patch("src.telemetry.google.auth.default") as mock_default,
        ):
            assert telemetry_mod._resolve_gcp_project_id() == ""

        mock_default.assert_not_called()

    def test_returns_empty_string_without_credentials(self) -> None:
        from google.auth.exceptions import DefaultCredentialsError

        with (
            patch("src.telemetry.GCP_PROJECT_ID", ""),
            patch("src.telemetry.CLOUD_RUN_SERVICE", "jor-mcp-server"),
            patch("src.telemetry.google.auth.default", side_effect=DefaultCredentialsError),
        ):
            assert telemetry_mod._resolve_gcp_project_id() == ""

    def test_returns_empty_string_when_credentials_carry_no_project(self) -> None:
        with (
            patch("src.telemetry.GCP_PROJECT_ID", ""),
            patch("src.telemetry.CLOUD_RUN_SERVICE", "jor-mcp-server"),
            patch("src.telemetry.google.auth.default", return_value=(MagicMock(), None)),
        ):
            assert telemetry_mod._resolve_gcp_project_id() == ""


@pytest.mark.usefixtures("restore_logging")
class TestConfigureLogging:
    @pytest.fixture(autouse=True)
    def _stub_project_id(self) -> Generator[None, None, None]:
        """Keep _configure_logging from reaching out for real credentials."""
        with patch("src.telemetry._resolve_gcp_project_id", return_value=""):
            yield

    def test_installs_a_single_json_handler_on_stdout(self) -> None:
        import sys

        root = logging.getLogger()
        root.handlers = [logging.StreamHandler(), logging.StreamHandler()]

        telemetry_mod._configure_logging()

        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.stream is sys.stdout
        assert any(isinstance(f, telemetry_mod._TraceContextFilter) for f in handler.filters)
        assert isinstance(handler.formatter, telemetry_mod._JsonFormatter)

    def test_applies_configured_log_level(self) -> None:
        root = logging.getLogger()
        root.setLevel(logging.WARNING)

        with patch("src.telemetry.LOG_LEVEL", "DEBUG"):
            telemetry_mod._configure_logging()

        assert root.level == logging.DEBUG

    def test_repeated_calls_do_not_accumulate_handlers(self) -> None:
        root = logging.getLogger()

        telemetry_mod._configure_logging()
        telemetry_mod._configure_logging()

        assert len(root.handlers) == 1

    def test_third_party_loggers_are_routed_to_the_root_handler(self) -> None:
        for name in telemetry_mod._CAPTURED_LOGGERS:
            lib_logger = logging.getLogger(name)
            lib_logger.handlers = [logging.StreamHandler()]
            lib_logger.propagate = False

        telemetry_mod._configure_logging()

        for name in telemetry_mod._CAPTURED_LOGGERS:
            lib_logger = logging.getLogger(name)
            assert lib_logger.handlers == []
            assert lib_logger.propagate is True

    def test_noisy_libraries_are_raised_above_info(self) -> None:
        for name in telemetry_mod._LIBRARY_LOG_LEVELS:
            logging.getLogger(name).setLevel(logging.NOTSET)

        telemetry_mod._configure_logging()

        for name, level in telemetry_mod._LIBRARY_LOG_LEVELS.items():
            assert logging.getLogger(name).level == level

    def test_third_party_traceback_becomes_one_json_line(self) -> None:
        import json

        telemetry_mod._configure_logging()
        handler = logging.getLogger().handlers[0]
        stream = StringIO()
        handler.stream = stream  # type: ignore[attr-defined]

        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("uvicorn.error").exception("Application shutdown failed")

        written = stream.getvalue()
        assert written.count("\n") == 1
        parsed = json.loads(written)
        assert parsed["logger"] == "uvicorn.error"
        assert parsed["severity"] == "ERROR"
        assert "ValueError: boom" in parsed["message"]


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
