"""Simple example demonstrating multilog-py usage."""

import asyncio
from multilog import AsyncLogger, LogLevel, ConsoleSink, BetterstackSink


async def example_basic_usage():
    """Basic logging example."""
    # Option 1: Auto-detect from environment (uses BETTERSTACK_TOKEN if set)
    logger = AsyncLogger()

    # Option 2: Explicit console sink for testing
    # logger = AsyncLogger(sinks=[ConsoleSink()])

    # Option 3: Multiple sinks (Betterstack + Console)
    # logger = AsyncLogger(sinks=[
    #     BetterstackSink(
    #         token="your-token",
    #         ingest_url="https://s1598061.eu-nbg-2.betterstackdata.com"
    #     ),
    #     ConsoleSink()
    # ])

    # Log messages with different levels
    await logger.log("Application started", LogLevel.INFO, {"version": "1.0.0"})
    await logger.log("Debug information", LogLevel.DEBUG, {"module": "auth"})
    await logger.log("Warning: high memory usage", LogLevel.WARNING, {"memory_mb": 1500})
    await logger.log("Error occurred", LogLevel.ERROR, {"error_code": "E500"})

    await logger.close()


async def example_endpoint_logging():
    """Example of logging HTTP endpoint invocations."""
    logger = AsyncLogger(sinks=[ConsoleSink()])

    # Log an API endpoint call with full request details
    await logger.log_endpoint(
        endpoint_name="user_login",
        method="POST",
        path="/api/auth/login",
        headers={"Content-Type": "application/json", "Authorization": "Bearer ***"},
        query_params={"redirect": "/dashboard"},
        body={"username": "user@example.com"},
        context={"ip_address": "192.168.1.100"},
    )

    await logger.close()


async def example_exception_logging():
    """Example of logging exceptions with full stacktraces."""
    logger = AsyncLogger(sinks=[ConsoleSink()])

    try:
        # Simulate an error
        data = {"users": []}
        user = data["users"][0]  # IndexError
    except Exception as exc:
        await logger.log_exception(
            "Failed to process user data",
            exc,
            context={"data_source": "database", "table": "users"},
        )

    await logger.close()


async def example_with_default_context():
    """Example using default context for all logs."""
    # Set context that will be included in ALL logs from this logger
    logger = AsyncLogger(
        sinks=[ConsoleSink()],
        default_context={
            "service": "payment-api",
            "environment": "production",
            "region": "us-west-2",
        },
    )

    await logger.log("Processing payment", LogLevel.INFO, {"order_id": "ORD-123"})
    await logger.log("Payment completed", LogLevel.INFO, {"amount": 99.99})

    await logger.close()


async def example_context_manager():
    """Example using async context manager (automatically closes)."""
    async with AsyncLogger(sinks=[ConsoleSink()]) as logger:
        await logger.log("Task started", LogLevel.INFO)
        await logger.log("Task completed", LogLevel.INFO)
    # Logger automatically closed here


async def main():
    """Run examples."""
    print("=" * 60)
    print("multilog-py Examples")
    print("=" * 60)

    print("\n1. Basic Usage:")
    await example_basic_usage()

    print("\n2. Endpoint Logging:")
    await example_endpoint_logging()

    print("\n3. Exception Logging:")
    await example_exception_logging()

    print("\n4. Default Context:")
    await example_with_default_context()

    print("\n5. Context Manager:")
    await example_context_manager()


if __name__ == "__main__":
    asyncio.run(main())
