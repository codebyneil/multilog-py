# multilog-py

A multi-destination Python logging library with structured logging, per-sink level filtering, and first-class Betterstack support.

## Features

- **Sync and async loggers** — `Logger` for synchronous code, `AsyncLogger` with `asyncio.to_thread()` for non-blocking I/O
- **Multiple sinks** — Console, file (JSONL), Betterstack, or build your own
- **Per-sink level filtering** — Each sink can accept a different set of log levels via `included_levels`
- **Per-sink default context** — Attach metadata (e.g. `{"env": "prod"}`) at the sink level; payload keys win on collision
- **Structured logging** — Every log entry carries a timestamp, level, message, and arbitrary context
- **HTTP request logging** — Dedicated `log_endpoint()` for capturing method, path, headers, query params, and body
- **Exception logging** — `log_exception()` captures type, message, and full traceback
- **Colored console output** — ANSI colors per level, human-readable timestamps, fixed-width columns
- **Level ranges** — `LogLevel` supports slice syntax (`LogLevel[LogLevel.INFO:]`) and severity comparisons

## Installation

```bash
uv add multilog-py
```

Or with pip:

```bash
pip install multilog-py
```

## Quick Start

### Synchronous

```python
from multilog import Logger, LogLevel

logger = Logger()  # Console sink by default; add Betterstack via env vars

logger.log("User logged in", LogLevel.INFO, {"user_id": "123"})
logger.log("Query slow", LogLevel.WARN, {"duration_ms": 1500})

logger.close()
```

### Asynchronous

```python
import asyncio
from multilog import AsyncLogger, LogLevel

async def main():
    async with AsyncLogger() as logger:
        await logger.log("Task started", LogLevel.INFO)
        await logger.log("Task completed", LogLevel.INFO)

asyncio.run(main())
```

## Sinks

### ConsoleSink

Prints formatted log lines to stdout (or stderr for warn/error/fatal). Output format:

```
2025-06-15 12:34:56.789  INFO   User logged in  {"user_id": "123"}
```

```python
from multilog import ConsoleSink, LogLevel

ConsoleSink()                                          # all levels, color on
ConsoleSink(use_color=False)                           # no ANSI codes
ConsoleSink(included_levels=[LogLevel.ERROR, LogLevel.FATAL])  # errors only
```

### BetterstackSink

Sends each log entry as an HTTP POST to Betterstack.

```python
from multilog import BetterstackSink

BetterstackSink(
    token="your-betterstack-token",
    ingest_url="https://s12345.eu-nbg-2.betterstackdata.com",
    timeout=10.0,  # optional, default 10s
)
```

### FileSink

Writes one JSON object per line to a file (JSONL format).

```python
from multilog import FileSink

FileSink("logs/app.jsonl")                # append by default
FileSink("logs/app.jsonl", append=False)  # overwrite on each run
```

### Custom Sinks

Subclass `BaseSink` and implement `_emit()`:

```python
from multilog import BaseSink

class SlackSink(BaseSink):
    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(**kwargs)
        self.webhook_url = webhook_url

    def _emit(self, payload: dict) -> None:
        httpx.post(self.webhook_url, json={"text": payload["message"]})
```

Every sink accepts these optional keyword arguments:

- `default_context` — dict merged into every payload (payload keys win on collision)
- `included_levels` — list of `LogLevel` values to accept (defaults to all)

## Composing Sinks

```python
from multilog import Logger, LogLevel, ConsoleSink, BetterstackSink, FileSink

logger = Logger(
    sinks=[
        ConsoleSink(included_levels=LogLevel[LogLevel.DEBUG:]),   # skip TRACE
        FileSink("logs/app.jsonl"),                                # everything
        BetterstackSink(
            token="...",
            ingest_url="https://...",
            included_levels=[LogLevel.ERROR, LogLevel.FATAL],     # errors only
        ),
    ],
    default_context={"service": "payment-api", "version": "1.0.0"},
)
```

## Endpoint and Exception Logging

```python
# HTTP request logging
logger.log_endpoint(
    endpoint_name="create_user",
    method="POST",
    path="/api/users",
    headers={"Content-Type": "application/json"},
    query_params={"source": "web"},
    body={"username": "john_doe"},
)

# Exception logging
try:
    risky_operation()
except Exception as exc:
    logger.log_exception("Payment failed", exc, context={"order_id": "12345"})
```

## LogLevel

Six levels ordered by severity, based on OpenTelemetry:

| Level   | Value     |
|---------|-----------|
| `TRACE` | `"trace"` |
| `DEBUG` | `"debug"` |
| `INFO`  | `"info"`  |
| `WARN`  | `"warn"`  |
| `ERROR` | `"error"` |
| `FATAL` | `"fatal"` |

Slice syntax returns inclusive ranges:

```python
LogLevel[LogLevel.INFO:]                # [INFO, WARN, ERROR, FATAL]
LogLevel[:LogLevel.INFO]                # [TRACE, DEBUG, INFO]
LogLevel[LogLevel.WARN:LogLevel.ERROR]  # [WARN, ERROR]
```

Severity comparisons work as expected:

```python
LogLevel.ERROR > LogLevel.INFO   # True
LogLevel.DEBUG <= LogLevel.WARN  # True
```

## Configuration

### Environment Variables

When no `sinks` are passed, the logger always creates a `ConsoleSink` and optionally adds a `BetterstackSink` if both env vars are set:

- `BETTERSTACK_TOKEN` — Betterstack authentication token
- `BETTERSTACK_INGEST_URL` — Betterstack ingest URL

Setting only one of the two raises `ConfigError`.

### Context Manager

Both logger classes support context managers for automatic cleanup:

```python
with Logger() as logger:
    logger.log("Hello", LogLevel.INFO)

async with AsyncLogger() as logger:
    await logger.log("Hello", LogLevel.INFO)
```

## Examples

See the [examples/](examples/) directory:

- [console_formatting.py](examples/console_formatting.py) — Console output at every log level
- [level_filtering.py](examples/level_filtering.py) — Per-sink level filtering
- [betterstack.py](examples/betterstack.py) — Sending logs to Betterstack
- [sync_and_async.py](examples/sync_and_async.py) — Sync and async logger usage
- [async_api.py](examples/async_api.py) — Async logging patterns

## Development

```bash
# Install dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run examples
uv run python examples/console_formatting.py

# Linting and formatting
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run ty check src/
```

## License

MIT
