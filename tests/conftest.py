"""Shared test fixtures and helpers for multilog-py tests."""

from typing import Any

from multilog.sinks.base import BaseSink


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
