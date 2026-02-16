"""Test script for multilog-py synchronous and asynchronous usage."""

import asyncio

from multilog import AsyncLogger, ConsoleSink, Logger, LogLevel


def test_sync_basic():
    """Test synchronous basic logging."""
    print("=" * 60)
    print("Testing SYNC basic logging")
    print("=" * 60)

    logger = Logger(sinks=[ConsoleSink()])

    # Test different log levels (no await!)
    logger.log("SYNC: Debug message", LogLevel.DEBUG, {"user_id": "123"})
    logger.log("SYNC: User logged in", LogLevel.INFO, {"user_id": "456"})
    logger.log("SYNC: Query slow", LogLevel.WARNING, {"duration_ms": 1500})
    logger.log("SYNC: Payment failed", LogLevel.ERROR, {"error": "timeout"})

    logger.close()


def test_sync_endpoint():
    """Test synchronous endpoint logging."""
    print("\n" + "=" * 60)
    print("Testing SYNC endpoint logging")
    print("=" * 60)

    logger = Logger(sinks=[ConsoleSink()])

    logger.log_endpoint(
        endpoint_name="create_user",
        method="POST",
        path="/api/users",
        headers={"Content-Type": "application/json"},
        query_params={"source": "web"},
        body={"username": "john_doe"},
    )

    logger.close()


def test_sync_exception():
    """Test synchronous exception logging."""
    print("\n" + "=" * 60)
    print("Testing SYNC exception logging")
    print("=" * 60)

    logger = Logger(sinks=[ConsoleSink()])

    try:
        _ = 10 / 0
    except Exception as exc:
        logger.log_exception("SYNC: Division error", exc, context={"operation": "calc"})

    logger.close()


def test_sync_context_manager():
    """Test sync context manager."""
    print("\n" + "=" * 60)
    print("Testing SYNC context manager")
    print("=" * 60)

    with Logger(sinks=[ConsoleSink()]) as logger:
        logger.log("SYNC: From context manager", LogLevel.INFO)

    print("✅ Logger automatically closed!")


async def test_async_basic():
    """Test asynchronous basic logging."""
    print("\n" + "=" * 60)
    print("Testing ASYNC basic logging")
    print("=" * 60)

    logger = AsyncLogger(sinks=[ConsoleSink()])

    # Test different log levels (with await!)
    await logger.log("ASYNC: Debug message", LogLevel.DEBUG, {"user_id": "789"})
    await logger.log("ASYNC: User logged in", LogLevel.INFO, {"user_id": "012"})
    await logger.log("ASYNC: Query slow", LogLevel.WARNING, {"duration_ms": 2000})
    await logger.log("ASYNC: Payment failed", LogLevel.ERROR, {"error": "network"})

    await logger.close()


async def test_async_endpoint():
    """Test asynchronous endpoint logging."""
    print("\n" + "=" * 60)
    print("Testing ASYNC endpoint logging")
    print("=" * 60)

    logger = AsyncLogger(sinks=[ConsoleSink()])

    await logger.log_endpoint(
        endpoint_name="update_user",
        method="PATCH",
        path="/api/users/123",
        headers={"Content-Type": "application/json"},
        query_params={"source": "api"},
        body={"email": "new@example.com"},
    )

    await logger.close()


async def test_async_exception():
    """Test asynchronous exception logging."""
    print("\n" + "=" * 60)
    print("Testing ASYNC exception logging")
    print("=" * 60)

    logger = AsyncLogger(sinks=[ConsoleSink()])

    try:
        raise ValueError("Async test error")
    except Exception as exc:
        await logger.log_exception(
            "ASYNC: Test error", exc, context={"request_id": "xyz"}
        )

    await logger.close()


async def test_async_context_manager():
    """Test async context manager."""
    print("\n" + "=" * 60)
    print("Testing ASYNC context manager")
    print("=" * 60)

    async with AsyncLogger(sinks=[ConsoleSink()]) as logger:
        await logger.log("ASYNC: From context manager", LogLevel.INFO)

    print("✅ AsyncLogger automatically closed!")


def test_default_context():
    """Test logger with default context."""
    print("\n" + "=" * 60)
    print("Testing default context (sync)")
    print("=" * 60)

    logger = Logger(
        sinks=[ConsoleSink()],
        default_context={"service": "api", "env": "prod", "version": "1.0.0"},
    )

    logger.log("Service started", LogLevel.INFO)
    logger.log("Processing request", LogLevel.DEBUG, {"request_id": "abc"})

    logger.close()


def main():
    """Run all tests."""
    print("\n" + "🚀" * 30)
    print("MULTILOG-PY TEST SUITE")
    print("🚀" * 30 + "\n")

    # SYNC tests (no asyncio needed!)
    test_sync_basic()
    test_sync_endpoint()
    test_sync_exception()
    test_sync_context_manager()
    test_default_context()

    # ASYNC tests (runs in executor via asyncio.to_thread)
    asyncio.run(test_async_basic())
    asyncio.run(test_async_endpoint())
    asyncio.run(test_async_exception())
    asyncio.run(test_async_context_manager())

    print("\n" + "✨" * 30)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("✨" * 30 + "\n")


if __name__ == "__main__":
    main()
