"""Tests for Logger.log_exception() payload shape."""

from conftest import RecordingSink

from multilog import Logger, LogLevel


def _emit_caught(message: str, raiser, context: dict | None = None) -> dict:
    """Helper: invoke `raiser()`, catch, log via a Logger with a RecordingSink."""
    sink = RecordingSink()
    logger = Logger(sinks=[sink])
    try:
        raiser()
    except Exception as exc:
        logger.log_exception(message, exc, context=context)
    return sink.payloads[0]


class TestPayloadShape:
    def test_level_is_error(self):
        payload = _emit_caught("oops", lambda: (_ for _ in ()).throw(ValueError("v")))
        assert payload["level"] == LogLevel.ERROR.value

    def test_message_passed_through(self):
        payload = _emit_caught("custom msg", lambda: (_ for _ in ()).throw(ValueError("v")))
        assert payload["message"] == "custom msg"

    def test_exception_type_recorded(self):
        payload = _emit_caught("x", lambda: (_ for _ in ()).throw(ValueError("v")))
        assert payload["exception_type"] == "ValueError"

    def test_exception_message_recorded(self):
        payload = _emit_caught("x", lambda: (_ for _ in ()).throw(ValueError("specific text")))
        assert payload["exception_message"] == "specific text"

    def test_event_type_marker(self):
        payload = _emit_caught("x", lambda: (_ for _ in ()).throw(ValueError("v")))
        assert payload["event_type"] == "exception"

    def test_traceback_is_list_of_strings(self):
        payload = _emit_caught("x", lambda: (_ for _ in ()).throw(ValueError("v")))
        assert isinstance(payload["traceback"], list)
        assert all(isinstance(line, str) for line in payload["traceback"])
        assert any("ValueError" in line for line in payload["traceback"])

    def test_context_merges_into_payload(self):
        payload = _emit_caught(
            "x",
            lambda: (_ for _ in ()).throw(ValueError("v")),
            context={"order_id": 99, "module": "billing"},
        )
        assert payload["order_id"] == 99
        assert payload["module"] == "billing"


class TestNoTraceback:
    def test_manually_constructed_exception_still_emits(self):
        """An Exception with no __traceback__ (never raised) should still produce a payload."""
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log_exception("synthetic", RuntimeError("never raised"))

        payload = sink.payloads[0]
        assert payload["exception_type"] == "RuntimeError"
        assert payload["exception_message"] == "never raised"
        assert isinstance(payload["traceback"], list)
