# multilog-py

A multi-destination Python logging library with first-class support for Betterstack, designed for modern async applications.

## Features

- 🚀 **Async-first design** - Non-blocking logging with full async/await support
- 🎯 **Multiple destinations** - Log to Betterstack, console, files, or custom handlers
- 🔒 **Type-safe** - Full type hints with Pydantic validation
- 📊 **Structured logging** - Rich metadata support for all log entries
- 🌐 **HTTP request tracking** - Specialized endpoint invocation logging
- 💥 **Exception logging** - Full stacktrace capture and serialization
- ⚙️ **Flexible configuration** - Environment variables or programmatic setup
- 🎨 **Colored console output** - Easy-to-read terminal logging

## Installation

```bash
uv add multilog-py
```

Or with pip:

```bash
pip install multilog-py
```

## Quick Start

### Basic Logging

```python
import asyncio
from multilog import Logger, LogLevel

async def main():
    # Auto-detect from BETTERSTACK_TOKEN environment variable
    logger = Logger()

    await logger.log("User logged in", LogLevel.INFO, {"user_id": "123"})
    await logger.log("Query slow", LogLevel.WARN, {"duration_ms": 1500})
    await logger.close()

asyncio.run(main())
```

### Multiple Handlers

```python
from multilog import Logger, BetterstackHandler, ConsoleHandler

logger = Logger(handlers=[
    BetterstackHandler(
        token="your-betterstack-token",
        ingest_url="https://s1598061.eu-nbg-2.betterstackdata.com"
    ),
    ConsoleHandler(level=LogLevel.DEBUG)  # Also log to console
])
```

### Endpoint Logging

Track HTTP requests with full details:

```python
await logger.log_endpoint(
    endpoint_name="create_user",
    method="POST",
    path="/api/users",
    headers={"Content-Type": "application/json"},
    query_params={"source": "web"},
    body={"username": "john_doe", "email": "john@example.com"}
)
```

### Exception Logging

Capture exceptions with full stacktraces:

```python
try:
    risky_operation()
except Exception as exc:
    await logger.log_exception(
        "Payment processing failed",
        exc,
        context={"order_id": "12345"}
    )
```

## Configuration

### Environment Variables

Set these environment variables for automatic configuration:

- `BETTERSTACK_TOKEN` - Your Betterstack authentication token
- `BETTERSTACK_INGEST_URL` - Betterstack ingest URL (optional, has default)

### Programmatic Configuration

```python
from multilog import Config

# From environment
config = Config.from_env()
logger = config.create_logger()

# Explicit configuration
config = Config(
    betterstack_token="your-token",
    betterstack_ingest_url="https://...",
    default_context={"service": "api", "env": "production"}
)
logger = config.create_logger()
```

## Advanced Usage

### Default Context

Add context to all log entries:

```python
logger = Logger(
    handlers=[ConsoleHandler()],
    default_context={
        "service": "payment-api",
        "environment": "production",
        "version": "1.0.0"
    }
)

# All logs will include the default context
await logger.log("Processing payment", LogLevel.INFO, {"order_id": "123"})
```

### Context Manager

Automatic cleanup with async context manager:

```python
async with Logger() as logger:
    await logger.log("Task started", LogLevel.INFO)
    await logger.log("Task completed", LogLevel.INFO)
# Logger automatically closed
```

### Custom Handlers

Create custom log destinations by extending `BaseHandler`:

```python
from multilog.handlers import BaseHandler

class SlackHandler(BaseHandler):
    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url

    async def emit(self, payload: dict[str, Any]) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                self.webhook_url,
                json={"text": payload["message"]}
            )

logger = Logger(handlers=[SlackHandler("https://hooks.slack.com/...")])
```

## API Reference

### Logger

**`Logger(handlers=None, default_context=None)`**

Main logger class.

**Methods:**
- `log(message, level, content)` - Log a message with optional metadata
- `log_endpoint(endpoint_name, method, path, headers, ...)` - Log HTTP endpoint invocation
- `log_exception(message, exception, context)` - Log exception with stacktrace
- `close()` - Close all handlers

### LogLevel

Enum with values following OpenTelemetry specification:
- `TRACE` - Detailed trace information
- `DEBUG` - Debugging information
- `INFO` - Informational messages
- `WARN` - Warning conditions
- `ERROR` - Error conditions
- `FATAL` - Fatal/critical conditions

### Handlers

- **BetterstackHandler** - Send logs to Betterstack
- **ConsoleHandler** - Print logs to stdout/stderr with colors
- **FileHandler** - Write logs to file in JSONL format
- **BaseHandler** - Abstract base class for custom handlers

## Examples

See [example.py](example.py) for comprehensive usage examples.

Run the test suite:

```bash
uv run python test_logger.py
```

## Development

```bash
# Install dependencies (including dev tools)
uv sync --group dev

# Run tests
uv run python test_logger.py

# Run examples
uv run python example.py

# Linting and formatting
uv run ruff check src/
uv run ruff format src/

# Type checking
uv run ty check src/
```

### Development Tools

- **[Ruff](https://docs.astral.sh/ruff/)** - Fast Python linter and formatter
- **[ty](https://docs.astral.sh/ty/)** - Extremely fast Python type checker from Astral

## License

MIT
