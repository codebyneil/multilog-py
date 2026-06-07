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

### Changed
- `BetterstackSink` now sends a Unix-millisecond `dt` event-time (the
  `timestamp_ms` value, passed through directly) so the real event time is
  preserved through batching and retries instead of falling back to
  Betterstack's ingestion time. A user-supplied `dt` is left untouched.
- `BetterstackSink` honors the HTTP `Retry-After` header (delta-seconds or
  HTTP-date) on retryable responses, falling back to jittered exponential
  backoff when the header is absent. Retry waits remain bounded by the shutdown
  deadline.

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
