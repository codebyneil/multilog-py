"""Shared test fixtures and helpers for multilog-py tests."""

from typing import Any

import pytest

from multilog._registry import _reset_registry_for_testing
from multilog.sinks.base import BaseSink


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset the process-wide registry around every test.

    The registry is global, so without this fixture loggers and sinks
    configured in one test would leak into the next.
    """
    _reset_registry_for_testing()
    yield
    _reset_registry_for_testing()


class RecordingSink(BaseSink):
    """Sink that records every emitted payload in-memory for assertions."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.payloads: list[dict[str, Any]] = []
        self.close_calls: int = 0

    def _emit(self, payload: dict[str, Any]) -> None:
        self.payloads.append(payload)

    def close(self) -> None:
        self.close_calls += 1


class RaisingSink(BaseSink):
    """Sink that raises on every emit. Used to test dispatcher isolation."""

    def __init__(self, exc: Exception | None = None, **kwargs):
        super().__init__(**kwargs)
        self.exc = exc or RuntimeError("boom")

    def _emit(self, payload: dict[str, Any]) -> None:
        raise self.exc
