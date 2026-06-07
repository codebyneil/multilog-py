"""Tests for context binding via Logger.bind()."""

from conftest import RecordingSink

from multilog import Logger, LogLevel, configure, get_logger


class TestBoundView:
    def test_bind_adds_context_to_every_entry(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink]).bind(component="auth", request_id="r1")

        logger.log("hi", LogLevel.INFO)

        payload = sink.payloads[0]
        assert payload["component"] == "auth"
        assert payload["request_id"] == "r1"

    def test_bind_shares_state_with_parent(self):
        sink = RecordingSink()
        parent = Logger(sinks=[sink])
        child = parent.bind(x=1)

        assert child._state is parent._state

    def test_call_context_overrides_bound_context(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink]).bind(env="prod")

        logger.log("hi", LogLevel.INFO, {"env": "override"})

        assert sink.payloads[0]["env"] == "override"

    def test_bound_context_overrides_base_context(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], context={"env": "base"}).bind(env="bound")

        logger.log("hi", LogLevel.INFO)

        assert sink.payloads[0]["env"] == "bound"

    def test_bind_of_bind_merges(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink]).bind(a=1).bind(b=2)

        logger.log("hi", LogLevel.INFO)

        payload = sink.payloads[0]
        assert payload["a"] == 1
        assert payload["b"] == 2

    def test_parent_unaffected_by_child_context(self):
        sink = RecordingSink()
        parent = Logger(sinks=[sink])
        child = parent.bind(only_on="child")

        parent.log("parent-msg", LogLevel.INFO)
        child.log("child-msg", LogLevel.INFO)

        assert "only_on" not in sink.payloads[0]
        assert sink.payloads[1]["only_on"] == "child"

    def test_context_property_includes_bound(self):
        logger = Logger(sinks=[RecordingSink()], context={"a": 1}).bind(b=2)
        assert dict(logger.context) == {"a": 1, "b": 2}


class TestBoundPicksUpReconfiguration:
    def test_bound_view_sees_sinks_added_after_binding(self):
        """A bound view captured early still routes to sinks added later via configure."""
        bound = get_logger("svc").bind(component="worker")

        sink = RecordingSink()
        configure(sinks=[sink], name="svc")

        bound.log("after configure", LogLevel.INFO)

        assert len(sink.payloads) == 1
        assert sink.payloads[0]["component"] == "worker"


class TestBoundLifecycle:
    def test_close_on_bound_view_is_noop(self):
        sink = RecordingSink()
        root = Logger(sinks=[sink])
        bound = root.bind(x=1)

        bound.close()

        # Shared sink must NOT be closed by closing a bound view.
        assert sink.close_calls == 0
        # Root still works.
        root.log("still-alive", LogLevel.INFO)
        assert len(sink.payloads) == 1

    def test_context_manager_on_bound_view_does_not_close_shared_sinks(self):
        sink = RecordingSink()
        root = Logger(sinks=[sink])

        with root.bind(x=1) as bound:
            bound.log("inside", LogLevel.INFO)

        assert sink.close_calls == 0
        assert sink.payloads[0]["x"] == 1
