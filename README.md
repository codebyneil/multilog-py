# multilog-py

A multi-destination Python logging library with **stable, reconfigurable logger handles**, structured logging, threshold-based level filtering, and a robust, batching Betterstack sink.

## Why stable handles

multilog owns logger identity and lifecycle the way stdlib `logging.getLogger`, loguru, and structlog do. You get a named handle once and keep it forever; you configure its sinks separately, whenever you like:

```python
# anywhere — even at module import, before anything is configured:
from multilog import get_logger, LogLevel
log = get_logger()                 # the process-stable handle for "app"

# once, at startup (a different file, imported later):
from multilog import configure, ConsoleSink, BetterstackSink
configure(sinks=[ConsoleSink(), BetterstackSink(token="...", ingest_url="...")])

log.log("ready", LogLevel.INFO)    # routes to the sinks configured above
```

`get_logger(name)` returns the **same object** for the life of the process, and `configure(...)` mutates that object **in place** — it never swaps it out. So a handle captured at import time keeps working after configuration runs later.

### The bug this prevents

A common home-grown pattern captures a logger at import and *replaces* the logger object on init:

```python
# DON'T do this — the classic stale-handle bug
# logging_setup.py
_logger = Logger()                       # unconfigured
def init():
    global _logger
    _logger = Logger(sinks=[...])         # replaces the object

# other_module.py
from logging_setup import _logger         # captured BEFORE init() runs
_logger.log(...)                          # forever points at the OLD, unconfigured logger
```

Modules that imported `_logger` before `init()` keep the old reference, and their logs silently never reach the configured sinks. multilog makes this impossible: there is one stable handle per name and `configure()` reconfigures it in place.

```python
# DO this instead
from multilog import get_logger, configure
log = get_logger("app")                   # stable; safe to capture at import
# ...later...
configure(sinks=[...])                     # the captured `log` now uses these sinks
```

## Installation

```bash
uv add multilog        # or: pip install multilog
```

## Quick start

### Synchronous

```python
from multilog import get_logger, configure, ConsoleSink, LogLevel

configure(sinks=[ConsoleSink()])
log = get_logger()

log.log("User logged in", LogLevel.INFO, {"user_id": "123"})
log.log("Query slow", LogLevel.WARN, {"duration_ms": 1500})
```

### Asynchronous

The async logger shares state with the sync one of the same name, so a single `configure()` sets up both:

```python
import asyncio
from multilog import get_async_logger, configure, ConsoleSink, LogLevel

configure(sinks=[ConsoleSink()])

async def main():
    log = get_async_logger()
    await log.log("Task started", LogLevel.INFO)
    await log.log("Task completed", LogLevel.INFO)

asyncio.run(main())
```

### The default handle

For quick use, a ready-made handle for `"app"` is exported:

```python
from multilog import logger, LogLevel
logger.log("hello", LogLevel.INFO)
```

### Named loggers

Applications should use `"app"` (the default). Libraries should use their own name so an app can configure them independently:

```python
log = get_logger("my_library")     # configure(name="my_library", sinks=[...])
```

## Context binding

`bind()` returns a lightweight view that adds context to every entry. It shares the parent's sinks (and picks up later `configure()` changes), so it's perfect for per-request or per-component tagging:

```python
log = get_logger()
request_log = log.bind(request_id="abc123", user_id=42)
request_log.log("handling request", LogLevel.INFO)
# -> every entry carries request_id and user_id

# precedence (later wins): configure(context=...)  <  bind(...)  <  per-call context
```

Bound views are ephemeral and do not own lifecycle: calling `close()` on one is a no-op (it would be wrong to close sinks shared with everyone else).

## Levels

Six levels ordered by severity (OpenTelemetry-based):

| Level   | Value     |
|---------|-----------|
| `TRACE` | `"trace"` |
| `DEBUG` | `"debug"` |
| `INFO`  | `"info"`  |
| `WARN`  | `"warn"`  |
| `ERROR` | `"error"` |
| `FATAL` | `"fatal"` |

`LogLevel` is a `StrEnum`, so it serializes straight to its string value, supports severity comparisons, and offers slice syntax for ranges:

```python
LogLevel.ERROR > LogLevel.INFO          # True
LogLevel[LogLevel.INFO:]                # [INFO, WARN, ERROR, FATAL]
LogLevel[:LogLevel.INFO]                # [TRACE, DEBUG, INFO]
```

## Level filtering (threshold-based)

Every sink takes a `min_level` threshold (default `TRACE` — emit everything). No expanding ranges into lists:

```python
ConsoleSink(min_level=LogLevel.WARN)     # WARN and above
```

For the rare case where you want an explicit allow-set instead of a threshold, pass `only` — it is authoritative and ignores `min_level`:

```python
ConsoleSink(only={LogLevel.INFO, LogLevel.ERROR})   # exactly these two
```

## Sinks

### ConsoleSink

Prints formatted lines to stdout (or stderr for warn/error/fatal):

```
2026-06-07 02:00:39.466  INFO   User logged in  {"user_id": "123"}
```

```python
ConsoleSink()                            # color on
ConsoleSink(use_color=False)             # no ANSI codes
ConsoleSink(min_level=LogLevel.ERROR)    # errors and fatals only
```

### FileSink

Writes one JSON object per line (JSONL), with a lock so concurrent threads never interleave:

```python
FileSink("logs/app.jsonl")               # append (default)
FileSink("logs/app.jsonl", append=False) # overwrite on each run
```

### BetterstackSink

Robust by default. `batch=True` (the default) hands each event to a background worker that POSTs events in batches, so your calling thread is never blocked on network I/O, and delivery failures are surfaced through an `on_error` callback instead of vanishing.

```python
from multilog import BetterstackSink, OverflowPolicy

BetterstackSink(
    token="your-source-token",
    ingest_url="https://sNNNN.region.betterstackdata.com",
    # batching (defaults shown)
    batch=True,
    batch_size=100,
    flush_interval=1.0,
    queue_size=10_000,
    overflow_policy=OverflowPolicy.DROP,   # DROP | BUFFER | BLOCK (string ok: "drop")
    on_error=lambda exc, payloads: ...,    # observe failures; must not raise
    register_atexit=True,                  # flush on interpreter shutdown
    # delivery (defaults shown)
    timeout=10.0,
    max_retries=3,
    backoff_base=0.5,
    backoff_max=8.0,
    flush_timeout=5.0,                     # max drain time on close()
)
```

**Overflow policy** — what happens when the queue fills because the destination can't keep up:

| Policy   | Behavior | Use when |
|----------|----------|----------|
| `DROP` (default) | Drop the new event, report it via `on_error(QueueFull, …)` | Long-running services — losing a log beats stalling a request |
| `BUFFER` | Move overflow to an unbounded in-memory buffer | Batch jobs — keep everything, accept memory risk if the sink stays down |
| `BLOCK`  | Block the caller until there's room | You'd rather stall than lose a log (can hang the caller — use with care) |

**Synchronous mode for CLIs.** A background worker never gets to flush in a short-lived process, so use `batch=False` there — it POSTs one event per call:

```python
BetterstackSink(token="...", ingest_url="...", batch=False)
```

**Never raises.** A broken or blocked Betterstack sink can never crash or (except under `BLOCK`) hang your app. Failed deliveries go to `on_error` if provided, otherwise to stderr.

**`on_error`** is called as `on_error(exception, payloads)` where `payloads` is a tuple of the affected log dicts. It runs on the worker thread (or the calling thread for an overflow drop), so keep it fast and make sure it doesn't raise.

### Custom sinks

Subclass `BaseSink` and implement `_emit()`:

```python
import httpx
from multilog import BaseSink

class SlackSink(BaseSink):
    def __init__(self, webhook_url: str, **kwargs):
        super().__init__(**kwargs)            # min_level / only
        self.webhook_url = webhook_url

    def _emit(self, payload: dict) -> None:
        httpx.post(self.webhook_url, json={"text": payload["message"]})
```

Treat `payload` as read-only in `_emit` — it is shared across all of a logger's sinks for a single call.

## Composing and reconfiguring

```python
from multilog import configure, get_logger, LogLevel, ConsoleSink, FileSink, BetterstackSink

configure(
    sinks=[
        ConsoleSink(min_level=LogLevel.DEBUG),                 # skip TRACE on console
        FileSink("logs/app.jsonl"),                            # everything
        BetterstackSink(token="...", ingest_url="https://...",
                        min_level=LogLevel.ERROR),             # errors to Betterstack
    ],
    context={"service": "payment-api", "version": "1.0.0"},    # base context for every entry
)
```

`configure(context=...)` **replaces** the base context (it does not merge). To extend it, read the current context — exposed as a read-only mapping — and build on it:

```python
configure(context={**get_logger().context, "request_id": rid})
```

You can also mutate sinks on a handle directly: `add_sink()`, `remove_sink()`, and `set_sinks()`. Removing or replacing a sink **closes** the removed sink by default (so file handles and Betterstack workers don't leak); pass `close_removed=False` / `close=False` to keep it open.

## Exception logging

`log_exception()` records the type, message, and full traceback, and lets you choose the severity (defaults to `ERROR`):

```python
try:
    risky_operation()
except Exception as exc:
    logger.log_exception("Payment failed", exc, context={"order_id": "12345"})

# pick a level for caught-but-recoverable vs fatal cases:
logger.log_exception("retry scheduled", exc, level=LogLevel.WARN)
logger.log_exception("unrecoverable", exc, level=LogLevel.FATAL)
```

Guidance: **FATAL** for crashes, **ERROR** for an operation that can't continue, **WARN** for an exception you caught and recovered from.

## Lifecycle

```python
log = get_logger()
configure(sinks=[FileSink("logs/app.jsonl")])
# ...
log.close()                  # flushes/closes every sink

# context managers close on exit:
with get_logger("job") as log:
    log.log("started", LogLevel.INFO)

async with get_async_logger("job") as log:
    await log.log("started", LogLevel.INFO)
```

## Notes

- **No implicit environment coupling.** multilog does not read `BETTERSTACK_*` (or any) env vars to build sinks — you pass sinks explicitly to `configure()`. Read your own env if you want: `BetterstackSink(token=os.environ["BETTERSTACK_TOKEN"], ...)`.
- **multiprocessing / fork.** A batching `BetterstackSink`'s worker thread does not survive `fork()`. In a forked child, call `configure(...)` again to install fresh sinks.
- **Migrating from `log_endpoint`** (removed in 1.0): write the structured event directly.
  ```python
  logger.log(f"Endpoint Invoked: {name}", LogLevel.INFO, {
      "event_source": "http_endpoint",
      "event_type": "endpoint_invocation",
      "endpoint_name": name,
      "request": {"method": method, "path": path, "headers": headers, "body": body},
  })
  ```

## Examples

See the [examples/](examples/) directory:

- [quickstart.py](examples/quickstart.py) — `get_logger`/`configure`, the stable-handle guarantee
- [stable_handle.py](examples/stable_handle.py) — capturing a handle before `configure()` (the bug-#1 fix)
- [binding.py](examples/binding.py) — per-request/component context with `bind()`
- [level_filtering.py](examples/level_filtering.py) — per-sink `min_level` / `only`
- [betterstack.py](examples/betterstack.py) — batching sink, `on_error`, sync mode
- [async_api.py](examples/async_api.py) — async logging patterns

## Development

```bash
uv sync --group dev
uv run pytest                 # tests + coverage
uv run ruff check src/        # lint
uv run ruff format src/       # format
uv run ty check src/          # type check
```

## License

MIT
