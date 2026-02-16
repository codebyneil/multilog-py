"""Test all OpenTelemetry log levels."""

import asyncio
from multilog import AsyncLogger, LogLevel, ConsoleSink


async def main():
    """Test all log levels."""
    print("=" * 60)
    print("Testing all OpenTelemetry log levels")
    print("=" * 60)

    logger = AsyncLogger(sinks=[ConsoleSink()])

    # Test all log levels
    await logger.log("Trace message - very detailed", LogLevel.TRACE, {"trace_id": "abc123"})
    await logger.log("Debug message - debugging info", LogLevel.DEBUG, {"debug_var": "value"})
    await logger.log("Info message - general information", LogLevel.INFO, {"user_id": "123"})
    await logger.log("Warning - something to watch", LogLevel.WARNING, {"memory_usage": "high"})
    await logger.log("Error message - something went wrong", LogLevel.ERROR, {"error_code": "E500"})
    await logger.log("Critical failure", LogLevel.CRITICAL, {"system": "database", "status": "crashed"})

    await logger.close()

    print("\n" + "=" * 60)
    print("Testing log level filtering (INFO and above)")
    print("=" * 60)

    # Test filtering - only INFO and above
    logger = AsyncLogger(sinks=[ConsoleSink(included_levels=LogLevel[LogLevel.INFO:])])

    await logger.log("This TRACE won't show", LogLevel.TRACE)
    await logger.log("This DEBUG won't show", LogLevel.DEBUG)
    await logger.log("This INFO will show", LogLevel.INFO)
    await logger.log("This WARNING will show", LogLevel.WARNING)
    await logger.log("This ERROR will show", LogLevel.ERROR)
    await logger.log("This CRITICAL will show", LogLevel.CRITICAL)

    await logger.close()


if __name__ == "__main__":
    asyncio.run(main())
