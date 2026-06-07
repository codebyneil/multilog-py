"""Tests for log_exception() payload shape and the level parameter."""

from conftest import RecordingSink

from multilog import Logger, LogLevel


def _emit_caught(
    message: str, raiser, *, level=LogLevel.ERROR, context: dict | None = None
) -> dict:
    """Helper: invoke `raiser()`, catch, log via a Logger with a RecordingSink."""
    sink = RecordingSink()
    logger = Logger(sinks=[sink])
    try:
        raiser()
    except Exception as exc:
        logger.log_exception(message, exc, level=level, context=context)
    return sink.payloads[0]


def _raise(exc: Exception):
    def _r():
        raise exc

    return _r


class TestPayloadShape:
    def test_default_level_is_error(self):
        payload = _emit_caught("oops", _raise(ValueError("v")))
        assert payload["level"] == LogLevel.ERROR

    def test_message_passed_through(self):
        payload = _emit_caught("custom msg", _raise(ValueError("v")))
        assert payload["message"] == "custom msg"

    def test_exception_type_recorded(self):
        payload = _emit_caught("x", _raise(ValueError("v")))
        assert payload["exception_type"] == "ValueError"

    def test_exception_message_recorded(self):
        payload = _emit_caught("x", _raise(ValueError("specific text")))
        assert payload["exception_message"] == "specific text"

    def test_event_type_marker(self):
        payload = _emit_caught("x", _raise(ValueError("v")))
        assert payload["event_type"] == "exception"

    def test_traceback_is_list_of_strings(self):
        payload = _emit_caught("x", _raise(ValueError("v")))
        assert isinstance(payload["traceback"], list)
        assert all(isinstance(line, str) for line in payload["traceback"])
        assert any("ValueError" in line for line in payload["traceback"])

    def test_context_merges_into_payload(self):
        payload = _emit_caught(
            "x",
            _raise(ValueError("v")),
            context={"order_id": 99, "module": "billing"},
        )
        assert payload["order_id"] == 99
        assert payload["module"] == "billing"


class TestLevelParameter:
    def test_level_can_be_overridden_to_fatal(self):
        payload = _emit_caught("crash", _raise(RuntimeError("x")), level=LogLevel.FATAL)
        assert payload["level"] == LogLevel.FATAL

    def test_level_can_be_warn_for_caught_recoverable(self):
        payload = _emit_caught("recovered", _raise(RuntimeError("x")), level=LogLevel.WARN)
        assert payload["level"] == LogLevel.WARN

    def test_level_filtering_applies_to_exception_logs(self):
        sink = RecordingSink(min_level=LogLevel.ERROR)
        logger = Logger(sinks=[sink])

        logger.log_exception("below threshold", RuntimeError("x"), level=LogLevel.WARN)
        logger.log_exception("at threshold", RuntimeError("y"), level=LogLevel.ERROR)

        assert [p["message"] for p in sink.payloads] == ["at threshold"]


class TestNoTraceback:
    def test_manually_constructed_exception_still_emits(self):
        """An exception with no __traceback__ (never raised) should still produce a payload."""
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log_exception("synthetic", RuntimeError("never raised"))

        payload = sink.payloads[0]
        assert payload["exception_type"] == "RuntimeError"
        assert payload["exception_message"] == "never raised"
        assert isinstance(payload["traceback"], list)

    def test_base_exception_accepted(self):
        """log_exception accepts BaseException, not just Exception."""
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log_exception("interrupted", KeyboardInterrupt(), level=LogLevel.WARN)

        assert sink.payloads[0]["exception_type"] == "KeyboardInterrupt"
