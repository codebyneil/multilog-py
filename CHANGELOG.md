# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - Unreleased

### Added
- `Logger.flush()` / `await AsyncLogger.flush()` and `BaseSink.flush()` to force
  buffered sinks (e.g. a batching `BetterstackSink`) to deliver at a checkpoint
  without closing them. `FileSink.flush()` flushes the OS handle; the base
  default is a no-op for synchronous sinks.
- `BetterstackSink(retry_after_max=60.0)` caps how long a `Retry-After` header
  may delay a retry, so a misbehaving server cannot stall the worker.
- Sinks accept levels as strings: `min_level="warn"` (or `"WARN"`) and
  `only={"info", "error"}` are normalized to `LogLevel` members; an unknown
  level raises `ValueError` at construction.
- `ConsoleSink.flush()` flushes stdout and stderr, and every line is written
  with `flush=True`, so output is not held in Python's block buffer when
  stdout is a pipe.

### Changed
- `BetterstackSink` now sends a Unix-millisecond `dt` event-time (the
  `timestamp_ms` value, passed through directly) so the real event time is
  preserved through batching and retries instead of falling back to
  Betterstack's ingestion time. A user-supplied `dt` is left untouched.
- `BetterstackSink` honors the HTTP `Retry-After` header (delta-seconds or
  HTTP-date) on retryable responses, capped at `retry_after_max`, falling back
  to jittered exponential backoff when the header is absent. Retry waits remain
  bounded by the shutdown deadline.
- `BetterstackSink` validates its numeric options up front and raises
  `ValueError` for out-of-range values. `batch_size < 1` now raises instead of
  being silently clamped to 1.
- The distribution is now named `multilog-py` — `multilog` on PyPI is an
  unrelated project. The import name is unchanged: `import multilog`.
- `Logger.close()` / `AsyncLogger.close()` detach the sinks they close. A
  closed registry handle routes nowhere, instead of writing
  `FileSink(...) is closed` tracebacks to stderr on every later call, until
  `configure()` installs new sinks.
- `LogLevel` comparison operators accept a level value string on either side
  and compare by severity (`LogLevel.WARN >= "error"` is `False`).
- Packaging: the license is declared as an SPDX expression with
  `license-files`, so wheels and sdists now include `LICENSE`; Python 3.14 is
  added to the classifiers and the CI matrix, and CI installs from the
  lockfile (`uv sync --locked`).

### Fixed
- `BetterstackSink.close()` no longer drops events silently. Once the drain
  deadline passes, the worker stops consuming the queue so every still-queued
  event is reported via `on_error`, and a batch the worker already holds is
  reported as a `TimeoutError` instead of being skipped without a callback.
  Previously, with the destination down, most of the queue could vanish at
  shutdown with no `on_error` call.
- `BetterstackSink.flush(timeout=...)` and `close(flush_timeout=...)` honor
  their timeouts when the queue is full; they used to block on the queue for
  as long as the worker was stuck.
- `BetterstackSink.close()` wakes a retry backoff that is already in progress,
  so shutdown drains immediately instead of giving up on queued events while
  the worker sleeps. The worker thread now always exits after `close()`; it
  could previously keep polling forever after a timed-out close.
- A non-httpx exception during delivery (for example httpx's `RuntimeError`
  for a closed client) is reported via `on_error` and no longer kills the
  worker thread or loses the in-flight batch.
- `BetterstackSink` options that previously broke delivery silently are now
  rejected: `flush_interval <= 0` (busy-spin or dead worker), `queue_size < 1`
  (an unbounded queue, so the overflow policy never applied), and
  `max_retries < 0` (every event dropped without any callback).
- A plain string passed as `min_level` filtered alphabetically instead of by
  severity (`min_level="error"` emitted `trace`, `info` and `warn` too),
  because mixed-type comparisons fell back to `str` ordering.
- `LogLevel[...]` slice syntax now type-checks: `__getitem__` is overloaded to
  return `list[LogLevel]` for slices.
- README: the Betterstack `dt` field is documented as Unix milliseconds (it
  was still described as ISO 8601), and `Retry-After` is documented for every
  retryable status, not just 429/503.

## [1.0.0] - 2026-06-06

Clean-break redesign. Backward compatibility was an explicit non-goal — the API
is rebuilt around process-stable logger handles.

### Added
- Process-stable logger registry: `get_logger` / `get_async_logger` return a
  singleton per name, and `configure(...)` reconfigures it in place (never
  replacing the object), so a handle captured at import time stays valid. A
  ready-to-use default `logger` handle is exported.
- `Logger.bind(**context)` / `AsyncLogger.bind(**context)` lightweight
  shared-state views for per-request/component context.
- Robust `BetterstackSink`: background batching worker (queue + flush interval),
  synchronous unbuffered mode (`batch=False`), `overflow_policy`
  (`OverflowPolicy.DROP`/`BUFFER`/`BLOCK`), an `on_error` hook, and an `atexit`
  flush. Logging never raises into the caller.
- `log_exception(message, exception, *, level=LogLevel.ERROR, context=None)` with
  a selectable level.

### Changed
- Sinks filter by threshold (`min_level`) plus an optional explicit `only` set.
- Standard payload keys (`level`, `message`, `timestamp_ms`) are written last and
  can no longer be shadowed by user context.

### Removed
- Implicit environment-driven default sinks (`BETTERSTACK_*`), `log_endpoint`,
  `ConfigError`, sink-level `default_context`, the list-based `included_levels`,
  and the `AsyncLogger(executor=...)` parameter.
