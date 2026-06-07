"""Tests for the synchronous Logger."""

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
        assert a.payloads[0]["level"] == LogLevel.INFO

    def test_payload_has_timestamp_message_level(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("hi", LogLevel.WARN)

        payload = sink.payloads[0]
        assert payload["message"] == "hi"
        assert payload["level"] == LogLevel.WARN
        assert isinstance(payload["timestamp_ms"], int)
        assert payload["timestamp_ms"] > 0

    def test_context_dict_merges_into_payload(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("hi", LogLevel.INFO, {"user_id": 42, "action": "login"})

        payload = sink.payloads[0]
        assert payload["user_id"] == 42
        assert payload["action"] == "login"

    def test_base_context_merges_into_every_payload(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], context={"service": "api", "env": "test"})

        logger.log("one", LogLevel.INFO)
        logger.log("two", LogLevel.WARN, {"env": "override"})

        assert sink.payloads[0]["service"] == "api"
        assert sink.payloads[0]["env"] == "test"
        assert sink.payloads[1]["service"] == "api"
        assert sink.payloads[1]["env"] == "override"

    def test_call_context_overrides_base_context(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], context={"region": "us-west"})

        logger.log("hi", LogLevel.INFO, {"region": "eu-central"})

        assert sink.payloads[0]["region"] == "eu-central"

    def test_standard_keys_cannot_be_overridden_by_context(self):
        """level/message/timestamp_ms are written last and win over user context."""
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        logger.log("real", LogLevel.ERROR, {"level": "hacked", "message": "spoof"})

        payload = sink.payloads[0]
        assert payload["level"] == LogLevel.ERROR
        assert payload["message"] == "real"

    def test_context_property_reflects_base_context(self):
        logger = Logger(sinks=[RecordingSink()], context={"a": 1})
        assert dict(logger.context) == {"a": 1}


class TestPerSinkThresholdFiltering:
    def test_min_level_drops_below_threshold(self):
        warn_up = RecordingSink(min_level=LogLevel.WARN)
        everything = RecordingSink()
        logger = Logger(sinks=[warn_up, everything])

        logger.log("info-msg", LogLevel.INFO)
        logger.log("err-msg", LogLevel.ERROR)

        assert [p["message"] for p in warn_up.payloads] == ["err-msg"]
        assert [p["message"] for p in everything.payloads] == ["info-msg", "err-msg"]

    def test_default_min_level_emits_everything(self):
        sink = RecordingSink()
        logger = Logger(sinks=[sink])

        for level in LogLevel:
            logger.log("x", level)

        assert len(sink.payloads) == len(list(LogLevel))

    def test_only_overrides_min_level(self):
        # only=[INFO, ERROR] is authoritative; min_level is ignored.
        sink = RecordingSink(min_level=LogLevel.FATAL, only={LogLevel.INFO, LogLevel.ERROR})
        logger = Logger(sinks=[sink])

        for level in LogLevel:
            logger.log(level.value, level)

        assert sorted(p["message"] for p in sink.payloads) == ["error", "info"]


class TestSinkMutation:
    def test_add_sink_routes_subsequent_logs(self):
        a = RecordingSink()
        logger = Logger(sinks=[a])
        logger.log("before", LogLevel.INFO)

        b = RecordingSink()
        logger.add_sink(b)
        logger.log("after", LogLevel.INFO)

        assert [p["message"] for p in a.payloads] == ["before", "after"]
        assert [p["message"] for p in b.payloads] == ["after"]

    def test_remove_sink_stops_routing_and_closes(self):
        a, b = RecordingSink(), RecordingSink()
        logger = Logger(sinks=[a, b])

        logger.remove_sink(a)
        logger.log("hi", LogLevel.INFO)

        assert len(a.payloads) == 0
        assert a.close_calls == 1
        assert len(b.payloads) == 1

    def test_remove_sink_without_close(self):
        a = RecordingSink()
        logger = Logger(sinks=[a])

        logger.remove_sink(a, close=False)

        assert a.close_calls == 0

    def test_set_sinks_replaces_and_closes_removed(self):
        old = RecordingSink()
        logger = Logger(sinks=[old])

        new = RecordingSink()
        logger.set_sinks([new])
        logger.log("hi", LogLevel.INFO)

        assert old.close_calls == 1
        assert len(old.payloads) == 0
        assert len(new.payloads) == 1

    def test_set_sinks_keep_removed_open(self):
        old = RecordingSink()
        logger = Logger(sinks=[old])

        logger.set_sinks([RecordingSink()], close_removed=False)

        assert old.close_calls == 0


class TestDispatchIsolation:
    def test_one_failing_sink_does_not_break_others(self, capsys):
        good = RecordingSink()
        bad = RaisingSink(RuntimeError("kaboom"))
        logger = Logger(sinks=[bad, good])

        logger.log("hi", LogLevel.INFO)

        assert len(good.payloads) == 1
        captured = capsys.readouterr()
        assert "RaisingSink failed to emit" in captured.err
        assert "kaboom" in captured.err
        assert "Traceback" in captured.err

    def test_log_never_raises_into_caller(self):
        logger = Logger(sinks=[RaisingSink(ValueError("nope"))])
        # Must not raise.
        logger.log("hi", LogLevel.INFO)


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
        assert "BadCloseSink failed to close" in captured.err
