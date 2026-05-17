"""Tests for Logger.log_endpoint() payload shape."""

from conftest import RecordingSink

from multilog import Logger, LogLevel


def _emit_one(**call_kwargs) -> dict:
    sink = RecordingSink()
    logger = Logger(sinks=[sink])
    logger.log_endpoint(**call_kwargs)
    return sink.payloads[0]


class TestPayloadShape:
    def test_level_is_info(self):
        payload = _emit_one(endpoint_name="x", method="GET", path="/y", headers={})
        assert payload["level"] == LogLevel.INFO.value

    def test_event_markers_present(self):
        payload = _emit_one(endpoint_name="login", method="POST", path="/auth/login", headers={})
        assert payload["event_source"] == "http_endpoint"
        assert payload["event_type"] == "endpoint_invocation"
        assert payload["endpoint_name"] == "login"

    def test_message_includes_endpoint_name(self):
        payload = _emit_one(endpoint_name="create_user", method="POST", path="/users", headers={})
        assert payload["message"] == "Endpoint Invoked: create_user"

    def test_request_subfields(self):
        payload = _emit_one(
            endpoint_name="x",
            method="POST",
            path="/users",
            headers={"Content-Type": "application/json"},
            query_params={"source": "web"},
            body={"username": "alice"},
        )
        req = payload["request"]
        assert req["method"] == "POST"
        assert req["path"] == "/users"
        assert req["query"] == {"source": "web"}
        assert req["headers"] == {"Content-Type": "application/json"}
        assert req["body"] == {"username": "alice"}

    def test_query_defaults_to_empty_dict(self):
        payload = _emit_one(endpoint_name="x", method="GET", path="/y", headers={})
        assert payload["request"]["query"] == {}

    def test_body_defaults_to_none(self):
        payload = _emit_one(endpoint_name="x", method="GET", path="/y", headers={})
        assert payload["request"]["body"] is None

    def test_context_kwarg_merges_into_top_level_payload(self):
        payload = _emit_one(
            endpoint_name="x",
            method="GET",
            path="/y",
            headers={},
            context={"trace_id": "abc-123", "user_id": 99},
        )
        assert payload["trace_id"] == "abc-123"
        assert payload["user_id"] == 99
