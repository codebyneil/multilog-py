"""Tests for _default_sinks() environment variable configuration."""

import pytest

from multilog._core import _default_sinks
from multilog.exceptions import ConfigError
from multilog.sinks.base import BaseSink
from multilog.sinks.betterstack import BetterstackSink


class TestDefaultSinks:
    def test_no_env_vars_returns_console_only(self, monkeypatch):
        monkeypatch.delenv("BETTERSTACK_TOKEN", raising=False)
        monkeypatch.delenv("BETTERSTACK_INGEST_URL", raising=False)

        sinks = _default_sinks()

        assert len(sinks) == 1
        assert isinstance(sinks[0], BaseSink)

    def test_both_env_vars_returns_console_and_betterstack(self, monkeypatch):
        monkeypatch.setenv("BETTERSTACK_TOKEN", "test-token")
        monkeypatch.setenv("BETTERSTACK_INGEST_URL", "https://in.logs.betterstack.com")

        sinks = _default_sinks()

        assert len(sinks) == 2
        assert isinstance(sinks[0], BaseSink)
        assert isinstance(sinks[1], BetterstackSink)
        assert sinks[1].token == "test-token"
        assert sinks[1].ingest_url == "https://in.logs.betterstack.com"

    def test_only_token_raises_config_error(self, monkeypatch):
        monkeypatch.setenv("BETTERSTACK_TOKEN", "test-token")
        monkeypatch.delenv("BETTERSTACK_INGEST_URL", raising=False)

        with pytest.raises(ConfigError, match="BETTERSTACK_INGEST_URL"):
            _default_sinks()

    def test_only_url_raises_config_error(self, monkeypatch):
        monkeypatch.delenv("BETTERSTACK_TOKEN", raising=False)
        monkeypatch.setenv("BETTERSTACK_INGEST_URL", "https://in.logs.betterstack.com")

        with pytest.raises(ConfigError, match="BETTERSTACK_TOKEN"):
            _default_sinks()
