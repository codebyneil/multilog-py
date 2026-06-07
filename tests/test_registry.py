"""Tests for the logger registry: stable handles and in-place reconfiguration.

These encode the central guarantee of the redesign: a handle obtained from
``get_logger`` is process-stable, and ``configure`` reconfigures it in place —
so a handle captured *before* configuration still routes correctly afterward.
"""

import asyncio

from conftest import RecordingSink

import multilog
from multilog import (
    AsyncLogger,
    Logger,
    LogLevel,
    configure,
    get_async_logger,
    get_logger,
)


class TestStableHandles:
    def test_same_name_returns_same_object(self):
        assert get_logger("svc") is get_logger("svc")

    def test_different_names_are_distinct(self):
        assert get_logger("a") is not get_logger("b")

    def test_async_same_name_returns_same_object(self):
        assert get_async_logger("svc") is get_async_logger("svc")

    def test_default_name_is_app(self):
        assert get_logger() is get_logger("app")

    def test_module_default_logger_is_app_handle(self):
        assert multilog.logger is get_logger("app")

    def test_sync_and_async_share_state(self):
        sink = RecordingSink()
        configure(sinks=[sink], name="shared")

        sync = get_logger("shared")
        asyncron = get_async_logger("shared")
        assert sync._state is asyncron._state

        sync.log("from-sync", LogLevel.INFO)
        asyncio.run(asyncron.log("from-async", LogLevel.INFO))

        assert [p["message"] for p in sink.payloads] == ["from-sync", "from-async"]


class TestConfigureInPlace:
    def test_handle_captured_before_configure_routes_to_new_sink(self):
        """THE regression test for bug #1.

        A handle captured at import time, before configure() runs, must deliver
        to the sinks installed by a later configure() — because configure
        mutates the existing handle's state rather than replacing the object.
        """
        captured = get_logger("regression")  # captured BEFORE configure

        sink = RecordingSink()
        configure(sinks=[sink], name="regression")  # configured AFTER capture

        captured.log("did it route?", LogLevel.INFO, {"k": "v"})

        assert len(sink.payloads) == 1
        assert sink.payloads[0]["message"] == "did it route?"
        assert sink.payloads[0]["level"] == LogLevel.INFO
        assert sink.payloads[0]["k"] == "v"

    def test_configure_returns_the_stable_handle(self):
        returned = configure(sinks=[RecordingSink()], name="r")
        assert returned is get_logger("r")

    def test_configure_replaces_sinks_and_closes_removed(self):
        first = RecordingSink()
        configure(sinks=[first], name="r")

        second = RecordingSink()
        configure(sinks=[second], name="r")

        # The removed sink was closed; the new one is active.
        assert first.close_calls == 1
        get_logger("r").log("hi", LogLevel.INFO)
        assert len(first.payloads) == 0
        assert len(second.payloads) == 1

    def test_configure_context_replaces_not_merges(self):
        sink = RecordingSink()
        configure(sinks=[sink], context={"env": "prod", "region": "us"}, name="r")
        configure(context={"env": "staging"}, name="r")  # replaces entirely

        get_logger("r").log("hi", LogLevel.INFO)

        payload = sink.payloads[0]
        assert payload["env"] == "staging"
        assert "region" not in payload

    def test_configure_only_context_keeps_existing_sinks(self):
        sink = RecordingSink()
        configure(sinks=[sink], name="r")
        configure(context={"env": "prod"}, name="r")  # no sinks arg

        get_logger("r").log("hi", LogLevel.INFO)

        assert len(sink.payloads) == 1
        assert sink.payloads[0]["env"] == "prod"

    def test_configure_empty_sinks_removes_all(self):
        sink = RecordingSink()
        configure(sinks=[sink], name="r")
        configure(sinks=[], name="r")

        get_logger("r").log("hi", LogLevel.INFO)
        assert len(sink.payloads) == 0
        assert sink.close_calls == 1


class TestHandleTypes:
    def test_get_logger_returns_logger(self):
        assert isinstance(get_logger("r"), Logger)

    def test_get_async_logger_returns_async_logger(self):
        assert isinstance(get_async_logger("r"), AsyncLogger)
