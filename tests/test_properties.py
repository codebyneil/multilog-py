"""Property-based tests (hypothesis) for merging, filtering, and robustness."""

import json

from conftest import RecordingSink
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from multilog import FileSink, Logger, LogLevel

# Autouse registry-reset fixture is function-scoped; these tests use standalone
# loggers and don't depend on it re-running per example.
_SUPPRESS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)

_STD_KEYS = {"level", "message", "timestamp_ms"}

json_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text()
)
json_values = st.recursive(
    json_scalars,
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=12,
)
json_dicts = st.dictionaries(st.text(min_size=1, max_size=8), json_values, max_size=6)


class TestContextMerging:
    @given(
        base=json_dicts,
        call=json_dicts,
        level=st.sampled_from(list(LogLevel)),
        message=st.text(),
    )
    @_SUPPRESS
    def test_precedence_and_unshadowable_standard_keys(self, base, call, level, message):
        sink = RecordingSink()
        logger = Logger(sinks=[sink], context=base)

        logger.log(message, level, call)

        p = sink.payloads[0]
        # Standard keys always reflect the actual call, never user context.
        assert p["level"] == level
        assert p["message"] == message
        assert isinstance(p["timestamp_ms"], int)
        # Call context wins over base for non-standard keys.
        for k, v in call.items():
            if k not in _STD_KEYS:
                assert p[k] == v
        # Base keys survive when not overridden by the call.
        for k, v in base.items():
            if k not in _STD_KEYS and k not in call:
                assert p[k] == v


class TestLevelFiltering:
    @given(threshold=st.sampled_from(list(LogLevel)), level=st.sampled_from(list(LogLevel)))
    @_SUPPRESS
    def test_min_level_threshold_matches_severity_order(self, threshold, level):
        sink = RecordingSink(min_level=threshold)
        Logger(sinks=[sink]).log("x", level)
        received = len(sink.payloads) == 1
        assert received == (level >= threshold)

    @given(
        allow=st.sets(st.sampled_from(list(LogLevel)), min_size=1),
        level=st.sampled_from(list(LogLevel)),
    )
    @_SUPPRESS
    def test_only_allow_set(self, allow, level):
        sink = RecordingSink(only=allow)
        Logger(sinks=[sink]).log("x", level)
        assert (len(sink.payloads) == 1) == (level in allow)


class TestSerialization:
    @given(payload=json_dicts)
    @_SUPPRESS
    def test_filesink_roundtrips_json_payloads(self, tmp_path, payload):
        path = tmp_path / "rt.jsonl"
        sink = FileSink(path, append=False)
        sink.emit(payload)
        sink.close()

        line = path.read_text(encoding="utf-8").strip()
        assert json.loads(line) == payload


class TestNeverRaises:
    # Keys and values that JSON cannot represent natively, to stress the
    # never-raise-into-caller invariant (dispatch must isolate any failure).
    weird_keys = st.one_of(
        st.text(max_size=6), st.integers(), st.tuples(st.integers(), st.integers())
    )
    weird_values = (
        json_scalars | st.binary() | st.sets(st.integers(), max_size=3) | st.builds(object)
    )
    weird_dicts = st.dictionaries(weird_keys, weird_values, max_size=5)

    @given(context=weird_dicts)
    @_SUPPRESS
    def test_log_never_raises_for_arbitrary_context(self, tmp_path, context):
        sink = FileSink(tmp_path / "w.jsonl", append=False)
        logger = Logger(sinks=[sink])

        # Even when a payload can't be serialized, the caller must never see it.
        logger.log("msg", LogLevel.INFO, context)

        logger.close()
