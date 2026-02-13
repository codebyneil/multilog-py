"""Test script for multilog-py library."""

import asyncio
from multilog_py import Logger, LogLevel, ConsoleHandler


async def test_basic_logging():
    """Test basic logging functionality."""
    print("=" * 60)
    print("Testing basic logging with ConsoleHandler")
    print("=" * 60)

    # Create logger with console handler (no Betterstack needed for testing)
    logger = Logger(handlers=[ConsoleHandler()])

    # Test different log levels
    await logger.log("This is a debug message", LogLevel.DEBUG, {"user_id": "123"})
    await logger.log("User logged in successfully", LogLevel.INFO, {"user_id": "456", "ip": "192.168.1.1"})
    await logger.log("Database query took longer than expected", LogLevel.WARN, {"duration_ms": 1500})
    await logger.log("Payment processing failed", LogLevel.ERROR, {"error": "timeout", "order_id": "ORD-789"})

    await logger.close()


async def test_endpoint_logging():
    """Test endpoint invocation logging."""
    print("\n" + "=" * 60)
    print("Testing endpoint invocation logging")
    print("=" * 60)

    logger = Logger(handlers=[ConsoleHandler()])

    # Simulate logging an HTTP endpoint
    await logger.log_endpoint(
        endpoint_name="create_user",
        method="POST",
        path="/api/users",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        query_params={"source": "web"},
        body={"username": "john_doe", "email": "john@example.com"},
        context={"request_id": "req-12345"},
    )

    await logger.close()


async def test_exception_logging():
    """Test exception logging."""
    print("\n" + "=" * 60)
    print("Testing exception logging")
    print("=" * 60)

    logger = Logger(handlers=[ConsoleHandler()])

    # Simulate an exception
    try:
        # This will raise a ValueError
        result = 10 / 0
    except Exception as exc:
        await logger.log_exception(
            "Division by zero error occurred",
            exc,
            context={"operation": "calculate_total", "user_id": "999"},
        )

    await logger.close()


async def test_context_manager():
    """Test using logger as async context manager."""
    print("\n" + "=" * 60)
    print("Testing logger as async context manager")
    print("=" * 60)

    async with Logger(handlers=[ConsoleHandler()]) as logger:
        await logger.log("Message from context manager", LogLevel.INFO)
        await logger.log("Another message", LogLevel.DEBUG, {"test": True})

    print("Logger automatically closed!")


async def test_default_context():
    """Test logger with default context."""
    print("\n" + "=" * 60)
    print("Testing logger with default context")
    print("=" * 60)

    # Create logger with default context that will be added to all logs
    logger = Logger(
        handlers=[ConsoleHandler()],
        default_context={"service": "api", "environment": "production", "version": "1.0.0"},
    )

    await logger.log("Service started", LogLevel.INFO)
    await logger.log("Processing request", LogLevel.DEBUG, {"request_id": "abc123"})

    await logger.close()


async def main():
    """Run all tests."""
    await test_basic_logging()
    await test_endpoint_logging()
    await test_exception_logging()
    await test_context_manager()
    await test_default_context()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
