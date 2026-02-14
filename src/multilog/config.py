"""Configuration management for multilog-py."""

import os
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from multilog.levels import LogLevel

if TYPE_CHECKING:
    from multilog.logger import Logger


class Config(BaseModel):
    """Configuration for multilog-py."""

    betterstack_token: str | None = None
    betterstack_ingest_url: str | None = None
    log_level: LogLevel = LogLevel.DEBUG
    default_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Config:
        """
        Create configuration from environment variables.

        Environment variables:
            BETTERSTACK_TOKEN: Authentication token
            BETTERSTACK_INGEST_URL: Ingest URL

        Returns:
            Config instance populated from environment variables
        """
        return cls(
            betterstack_token=os.getenv("BETTERSTACK_TOKEN"),
            betterstack_ingest_url=os.getenv("BETTERSTACK_INGEST_URL"),
        )

    def create_logger(self) -> Logger:
        """
        Create a Logger instance from this config.

        Returns:
            Configured Logger instance
        """
        from multilog.logger import Logger
        from multilog.sinks.betterstack import BetterstackSink
        from multilog.sinks.console import ConsoleSink

        sinks = []

        # Always include console sink
        sinks.append(ConsoleSink())

        # Add Betterstack if both token and ingest URL are configured
        if self.betterstack_token and self.betterstack_ingest_url:
            sinks.append(BetterstackSink.from_config(self))

        return Logger(sinks=sinks, default_context=self.default_context)
