"""Configuration management for multilog-py."""

import os
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from multilog_py.levels import LogLevel

if TYPE_CHECKING:
    from multilog_py.logger import Logger


class Config(BaseModel):
    """Configuration for multilog-py."""

    betterstack_token: str | None = None
    betterstack_ingest_url: str = "https://s1598061.eu-nbg-2.betterstackdata.com"
    log_level: LogLevel = LogLevel.DEBUG
    default_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Config:
        """
        Create configuration from environment variables.

        Environment variables:
            BETTERSTACK_TOKEN: Authentication token
            BETTERSTACK_INGEST_URL: Ingest URL (optional, has default)

        Returns:
            Config instance populated from environment variables
        """
        return cls(
            betterstack_token=os.getenv("BETTERSTACK_TOKEN"),
            betterstack_ingest_url=os.getenv(
                "BETTERSTACK_INGEST_URL",
                "https://s1598061.eu-nbg-2.betterstackdata.com",
            ),
        )

    def create_logger(self) -> Logger:
        """
        Create a Logger instance from this config.

        Returns:
            Configured Logger instance
        """
        from multilog_py.handlers.betterstack import BetterstackHandler
        from multilog_py.logger import Logger

        handlers = []

        if self.betterstack_token:
            handlers.append(BetterstackHandler.from_config(self))

        return Logger(handlers=handlers, default_context=self.default_context)
