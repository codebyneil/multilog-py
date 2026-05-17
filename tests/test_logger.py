"""Tests for the synchronous Logger wrapper."""

from conftest import RaisingSink, RecordingSink

from multilog import Logger, LogLevel


class TestLogDispatch:
    def test_log_emits_to_all_sinks(self):
        a, b = RecordingSink(), RecordingSink()
        logger = Logger(sinks=[a, b])

        logger.log("hello", LogLevel.INFO)

        assert len(a.payloads) == 1
        assert len(b.payloads) == 1
        assert a.payloads[0]["message"] == "hello"
        assert a.payloads[0]["level"] == "info"

    def test_payload_has_timestamp_message_level(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("hi", LogLevel.WARN)

        payload = sink.payloads[0]
        assert payload["message"] == "hi"
        assert payload["level"] == "warn"
        assert isinstance(payload["timestamp_ms"], int)
        assert payload["timestamp_ms"] > 0

    def test_context_dict_merges_into_payload(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("hi", LogLevel.INFO, {"user_id": 42, "action": "login"})

        payload = sink.payloads[0]
        assert payload["user_id"] == 42
        assert payload["action"] == "login"

    def test_logger_default_context_merges_into_every_payload(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], default_context={"service": "api", "env": "test"})

        logger.log("one", LogLevel.INFO)
        logger.log("two", LogLevel.WARN, {"env": "override"})

        assert sink.payloads[0]["service"] == "api"
        assert sink.payloads[0]["env"] == "test"
        assert sink.payloads[1]["service"] == "api"
        assert sink.payloads[1]["env"] == "override"

    def test_context_can_override_default_context(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], default_context={"region": "us-west"})

        logger.log("hi", LogLevel.INFO, {"region": "eu-central"})

        assert sink.payloads[0]["region"] == "eu-central"


class TestPerSinkLevelFiltering:
    def test_sink_below_filter_does_not_receive(self):
        only_errors = RecordingSink(included_levels=[LogLevel.ERROR, LogLevel.FATAL])
        everything = RecordingSink()
        logger = Logger(sinks=[only_errors, everything])

        logger.log("info-msg", LogLevel.INFO)
        logger.log("err-msg", LogLevel.ERROR)

        assert [p["message"] for p in only_errors.payloads] == ["err-msg"]
        assert [p["message"] for p in everything.payloads] == ["info-msg", "err-msg"]


class TestLoggerLevelGate:
    def test_logger_gate_blocks_before_dispatch(self):
        sink = RecordingSink()
        logger = Logger(
            sinks=[sink],
            included_levels=LogLevel[LogLevel.WARN :],  # WARN, ERROR, FATAL
        )

        logger.log("info-dropped", LogLevel.INFO)
        logger.log("warn-kept", LogLevel.WARN)
        logger.log("fatal-kept", LogLevel.FATAL)

        assert [p["message"] for p in sink.payloads] == ["warn-kept", "fatal-kept"]

    def test_logger_gate_short_circuits_no_payload_built(self):
        """When the gate rejects, _emit is never reached even if the sink would accept it."""

        class BoomOnEmit(RecordingSink):
            def _emit(self, payload):
                raise RuntimeError("must not be called")

        sink = BoomOnEmit()
        logger = Logger(
            sinks=[sink],
            included_levels=[LogLevel.ERROR],
        )

        # Should not raise — the gate drops the entry before _emit.
        logger.log("dropped", LogLevel.INFO)
        logger.log("dropped", LogLevel.DEBUG)

    def test_logger_gate_none_means_all_levels(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], included_levels=None)

        for level in LogLevel:
            logger.log("x", level)

        assert len(sink.payloads) == len(list(LogLevel))

    def test_logger_gate_stacks_with_sink_gate(self):
        # Logger admits >= WARN; sink admits only ERROR. Intersection is {ERROR}.
        sink = RecordingSink(included_levels=[LogLevel.ERROR])
        logger = Logger(sinks=[sink], included_levels=LogLevel[LogLevel.WARN :])

        for level in LogLevel:
            logger.log(level.value, level)

        assert [p["message"] for p in sink.payloads] == ["error"]


class TestDispatchIsolation:
    def test_one_failing_sink_does_not_break_others(self, capsys):
        good = RecordingSink()
        bad = RaisingSink(RuntimeError("kaboom"))
        logger = Logger(sinks=[bad, good])

        logger.log("hi", LogLevel.INFO)

        assert len(good.payloads) == 1
        captured = capsys.readouterr()
        assert "RaisingSink failed" in captured.err
        assert "kaboom" in captured.err
        # Traceback included for debugging.
        assert "Traceback" in captured.err


class TestCloseAndContextManager:
    def test_close_calls_close_on_each_sink(self):
        a, b = RecordingSink(), RecordingSink()
        logger = Logger(sinks=[a, b])

        logger.close()

        assert a.close_calls == 1
        assert b.close_calls == 1

    def test_context_manager_closes_on_exit(self):
        sink = RecordingSink()

        with Logger(sinks=[sink]) as logger:
            logger.log("inside", LogLevel.INFO)

        assert sink.close_calls == 1
        assert sink.payloads[0]["message"] == "inside"

    def test_context_manager_closes_on_exception(self):
        sink = RecordingSink()

        try:
            with Logger(sinks=[sink]) as logger:
                logger.log("before-raise", LogLevel.INFO)
                raise ValueError("propagate me")
        except ValueError:
            pass

        assert sink.close_calls == 1

    def test_sink_close_failure_does_not_stop_other_closes(self, capsys):
        good = RecordingSink()

        class BadCloseSink(RecordingSink):
            def close(self):
                raise RuntimeError("close-fail")

        bad = BadCloseSink()
        logger = Logger(sinks=[bad, good])

        logger.close()

        assert good.close_calls == 1
        captured = capsys.readouterr()
        assert "BadCloseSink close failed" in captured.err
