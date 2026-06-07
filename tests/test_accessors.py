"""Coverage for accessors and state-mutation edge cases on both loggers."""

from conftest import RecordingSink

from multilog import AsyncLogger, Logger


class TestNameAndContext:
    def test_logger_name(self):
        assert Logger(name="svc").name == "svc"
        assert Logger().name == "app"

    def test_async_logger_name(self):
        assert AsyncLogger(name="svc").name == "svc"

    def test_async_logger_context_merges_base_and_bound(self):
        log = AsyncLogger(context={"a": 1}).bind(b=2)
        assert dict(log.context) == {"a": 1, "b": 2}


class TestAsyncMutationParity:
    def test_async_add_sink(self):
        a = RecordingSink()
        log = AsyncLogger(sinks=[a])
        b = RecordingSink()
        log.add_sink(b)
        assert b in log._state.sinks

    def test_async_set_sinks_closes_removed(self):
        old = RecordingSink()
        log = AsyncLogger(sinks=[old])
        log.set_sinks([RecordingSink()])
        assert old.close_calls == 1

    def test_async_remove_sink(self):
        a = RecordingSink()
        log = AsyncLogger(sinks=[a])
        log.remove_sink(a)
        assert a.close_calls == 1
        assert a not in log._state.sinks

    async def test_async_log_exception_with_context(self):
        sink = RecordingSink()
        log = AsyncLogger(sinks=[sink])
        await log.log_exception("boom", RuntimeError("x"), context={"order": 5})
        assert sink.payloads[0]["order"] == 5
        assert sink.payloads[0]["exception_type"] == "RuntimeError"

    async def test_async_bound_close_is_noop(self):
        sink = RecordingSink()
        root = AsyncLogger(sinks=[sink])
        await root.bind(x=1).close()
        assert sink.close_calls == 0


class TestStateMutationEdges:
    def test_remove_absent_sink_is_noop(self):
        present = RecordingSink()
        absent = RecordingSink()
        log = Logger(sinks=[present])

        log.remove_sink(absent)  # not in the logger

        assert absent.close_calls == 0
        assert present in log._state.sinks

    def test_set_sinks_does_not_close_retained_sink(self):
        keep = RecordingSink()
        drop = RecordingSink()
        log = Logger(sinks=[keep, drop])

        add = RecordingSink()
        log.set_sinks([keep, add])  # keep retained, drop removed

        assert keep.close_calls == 0  # retained -> not closed
        assert drop.close_calls == 1  # removed -> closed
        assert set(log._state.sinks) == {keep, add}

    def test_add_duplicate_sink_is_idempotent(self):
        a = RecordingSink()
        log = Logger(sinks=[a])

        log.add_sink(a)  # already present

        assert list(log._state.sinks).count(a) == 1


class TestFlushPropagation:
    def test_logger_flush_calls_flush_on_each_sink(self):
        a, b = RecordingSink(), RecordingSink()
        log = Logger(sinks=[a, b])

        log.flush()

        assert a.flush_calls == 1
        assert b.flush_calls == 1

    def test_bound_logger_flush_still_flushes_shared_sinks(self):
        sink = RecordingSink()
        log = Logger(sinks=[sink]).bind(x=1)

        log.flush()  # allowed on bound views (unlike close)

        assert sink.flush_calls == 1

    async def test_async_logger_flush_calls_flush_on_each_sink(self):
        a, b = RecordingSink(), RecordingSink()
        log = AsyncLogger(sinks=[a, b])

        await log.flush()

        assert a.flush_calls == 1
        assert b.flush_calls == 1

    def test_flush_isolates_a_failing_sink(self, capsys):
        class BadFlush(RecordingSink):
            def flush(self, timeout=None):
                raise RuntimeError("flush boom")

        good = RecordingSink()
        Logger(sinks=[BadFlush(), good]).flush()  # must not raise into the caller

        assert good.flush_calls == 1
        assert "failed to flush" in capsys.readouterr().err
