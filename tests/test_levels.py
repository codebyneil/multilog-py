"""Tests for LogLevel enum: slice syntax, comparison operators, and serialization."""

import json

import pytest

from multilog.levels import LogLevel

ALL_LEVELS = [
    LogLevel.TRACE,
    LogLevel.DEBUG,
    LogLevel.INFO,
    LogLevel.WARNING,
    LogLevel.ERROR,
    LogLevel.CRITICAL,
]


# --- Slice syntax: member endpoints ---


class TestSliceWithMembers:
    def test_middle_range(self):
        assert LogLevel[LogLevel.INFO : LogLevel.CRITICAL] == [
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_full_range(self):
        assert LogLevel[LogLevel.TRACE : LogLevel.CRITICAL] == ALL_LEVELS

    def test_single_element(self):
        assert LogLevel[LogLevel.WARNING : LogLevel.WARNING] == [LogLevel.WARNING]

    def test_first_two(self):
        assert LogLevel[LogLevel.TRACE : LogLevel.DEBUG] == [
            LogLevel.TRACE,
            LogLevel.DEBUG,
        ]

    def test_last_two(self):
        assert LogLevel[LogLevel.ERROR : LogLevel.CRITICAL] == [
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_adjacent_pair(self):
        assert LogLevel[LogLevel.DEBUG : LogLevel.INFO] == [
            LogLevel.DEBUG,
            LogLevel.INFO,
        ]


# --- Slice syntax: value strings ---


class TestSliceWithValueStrings:
    def test_lowercase_values(self):
        assert LogLevel["info":"critical"] == [
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_trace_to_warning(self):
        assert LogLevel["trace":"warning"] == [
            LogLevel.TRACE,
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
        ]


# --- Slice syntax: name strings ---


class TestSliceWithNameStrings:
    def test_uppercase_names(self):
        assert LogLevel["INFO":"CRITICAL"] == [
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_debug_to_error(self):
        assert LogLevel["DEBUG":"ERROR"] == [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
        ]


# --- Slice syntax: open-ended ranges ---


class TestOpenEndedSlices:
    def test_open_start(self):
        assert LogLevel[: LogLevel.INFO] == [
            LogLevel.TRACE,
            LogLevel.DEBUG,
            LogLevel.INFO,
        ]

    def test_open_end(self):
        assert LogLevel[LogLevel.WARNING :] == [
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_fully_open(self):
        assert LogLevel[:] == ALL_LEVELS

    def test_open_start_string(self):
        assert LogLevel[:"warning"] == [
            LogLevel.TRACE,
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
        ]

    def test_open_end_string(self):
        assert LogLevel["error":] == [
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]


# --- Slice syntax: edge cases ---


class TestSliceEdgeCases:
    def test_reversed_range_returns_empty(self):
        assert LogLevel[LogLevel.CRITICAL : LogLevel.TRACE] == []

    def test_reversed_adjacent_returns_empty(self):
        assert LogLevel[LogLevel.INFO : LogLevel.DEBUG] == []

    def test_invalid_start_raises(self):
        with pytest.raises((ValueError, KeyError)):
            LogLevel["bogus" : LogLevel.CRITICAL]

    def test_invalid_stop_raises(self):
        with pytest.raises((ValueError, KeyError)):
            LogLevel[LogLevel.TRACE : "bogus"]

    def test_each_single_level_slice(self):
        for level in ALL_LEVELS:
            assert LogLevel[level:level] == [level]


# --- Name access (standard enum behavior) ---


class TestNameAccess:
    def test_access_by_name(self):
        assert LogLevel["INFO"] is LogLevel.INFO

    def test_access_all_by_name(self):
        for level in ALL_LEVELS:
            assert LogLevel[level.name] is level

    def test_invalid_name_raises(self):
        with pytest.raises(KeyError):
            LogLevel["NOPE"]


# --- Value construction ---


class TestValueConstruction:
    def test_construct_from_value(self):
        assert LogLevel("info") is LogLevel.INFO

    def test_all_values(self):
        for level in ALL_LEVELS:
            assert LogLevel(level.value) is level

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            LogLevel("nope")


# --- Comparison operators ---


class TestComparisons:
    def test_ge_higher(self):
        assert LogLevel.CRITICAL >= LogLevel.TRACE

    def test_ge_equal(self):
        assert LogLevel.INFO >= LogLevel.INFO

    def test_ge_lower_is_false(self):
        assert not (LogLevel.DEBUG >= LogLevel.ERROR)

    def test_gt_higher(self):
        assert LogLevel.ERROR > LogLevel.WARNING

    def test_gt_equal_is_false(self):
        assert not (LogLevel.INFO > LogLevel.INFO)

    def test_gt_lower_is_false(self):
        assert not (LogLevel.TRACE > LogLevel.DEBUG)

    def test_le_lower(self):
        assert LogLevel.TRACE <= LogLevel.CRITICAL

    def test_le_equal(self):
        assert LogLevel.WARNING <= LogLevel.WARNING

    def test_le_higher_is_false(self):
        assert not (LogLevel.CRITICAL <= LogLevel.ERROR)

    def test_lt_lower(self):
        assert LogLevel.DEBUG < LogLevel.INFO

    def test_lt_equal_is_false(self):
        assert not (LogLevel.WARNING < LogLevel.WARNING)

    def test_lt_higher_is_false(self):
        assert not (LogLevel.ERROR < LogLevel.DEBUG)

    def test_not_implemented_for_other_types(self):
        assert LogLevel.INFO.__ge__(42) is NotImplemented
        assert LogLevel.INFO.__gt__("info") is NotImplemented
        assert LogLevel.INFO.__le__(3.14) is NotImplemented
        assert LogLevel.INFO.__lt__(None) is NotImplemented


class TestComparisonOrdering:
    """Verify the full severity ordering is correct."""

    def test_strict_ascending_order(self):
        for i in range(len(ALL_LEVELS) - 1):
            lower = ALL_LEVELS[i]
            higher = ALL_LEVELS[i + 1]
            assert lower < higher, f"{lower} should be < {higher}"
            assert higher > lower, f"{higher} should be > {lower}"

    def test_all_pairs(self):
        for i, a in enumerate(ALL_LEVELS):
            for j, b in enumerate(ALL_LEVELS):
                if i < j:
                    assert a < b
                    assert a <= b
                    assert b > a
                    assert b >= a
                elif i == j:
                    assert a <= b
                    assert a >= b
                    assert not (a < b)
                    assert not (a > b)
                else:
                    assert a > b
                    assert a >= b
                    assert b < a
                    assert b <= a


# --- Equality and identity ---


class TestEquality:
    def test_same_member_is_equal(self):
        assert LogLevel.INFO == LogLevel.INFO

    def test_same_member_is_identical(self):
        assert LogLevel.INFO is LogLevel.INFO

    def test_different_members_not_equal(self):
        assert LogLevel.INFO != LogLevel.DEBUG

    def test_equal_to_string_value(self):
        # StrEnum members compare equal to their string value
        assert LogLevel.INFO == "info"

    def test_hashable(self):
        s = {LogLevel.INFO, LogLevel.DEBUG, LogLevel.INFO}
        assert len(s) == 2


# --- JSON serialization ---


class TestSerialization:
    def test_json_dumps(self):
        assert json.dumps({"level": LogLevel.INFO}) == '{"level": "info"}'

    def test_json_all_levels(self):
        data = json.dumps(list(ALL_LEVELS))
        assert data == '["trace", "debug", "info", "warning", "error", "critical"]'

    def test_json_roundtrip(self):
        original = LogLevel.WARNING
        serialized = json.dumps({"level": original})
        deserialized = json.loads(serialized)
        assert LogLevel(deserialized["level"]) is original


# --- Backward-compatible aliases ---


class TestAliases:
    def test_warn_is_warning(self):
        assert LogLevel.WARN is LogLevel.WARNING

    def test_fatal_is_critical(self):
        assert LogLevel.FATAL is LogLevel.CRITICAL

    def test_warn_value_resolves(self):
        assert LogLevel("warn") is LogLevel.WARNING

    def test_fatal_value_resolves(self):
        assert LogLevel("fatal") is LogLevel.CRITICAL

    def test_warn_name_access(self):
        assert LogLevel["WARN"] is LogLevel.WARNING

    def test_fatal_name_access(self):
        assert LogLevel["FATAL"] is LogLevel.CRITICAL

    def test_aliases_not_in_iteration(self):
        members = list(LogLevel)
        assert len(members) == 6
        assert LogLevel.WARNING in members
        assert LogLevel.CRITICAL in members

    def test_legacy_slice_with_warn(self):
        assert LogLevel["trace":"warn"] == [
            LogLevel.TRACE,
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
        ]

    def test_legacy_slice_with_fatal(self):
        assert LogLevel["info":"fatal"] == [
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

    def test_legacy_json_roundtrip(self):
        # Old logs serialized as "warn" can still be deserialized
        assert LogLevel("warn") is LogLevel.WARNING
        assert LogLevel("fatal") is LogLevel.CRITICAL
