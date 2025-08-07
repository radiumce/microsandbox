"""
MCP Server Entry Point using Official SDK

This module provides the main entry point using the official MCP Python SDK.
"""

import argparse
import asyncio
import atexit
import logging
import os
import signal
import sys

from microsandbox_wrapper import setup_logging, get_logger, ConfigurationError
from mcp_server.server import create_server_app, shutdown_wrapper


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MCP Server for Microsandbox (using official SDK)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport Options:
  stdio         Standard I/O transport (default)
  streamable-http   HTTP streaming transport
  sse           Server-Sent Events transport

Environment Variables:
  MCP_SERVER_HOST     Server host address for HTTP transports (default: localhost)
  MCP_SERVER_PORT     Server port number for HTTP transports (default: 8775)
  MCP_ENABLE_CORS     Enable CORS support for HTTP transports (default: false)

Examples:
  python -m mcp_server.main
  python -m mcp_server.main --transport streamable-http --port 9000
  python -m mcp_server.main --transport sse --host 0.0.0.0 --enable-cors
        """,
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )

    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Server host address for HTTP transports (overrides MCP_SERVER_HOST)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port number for HTTP transports (overrides MCP_SERVER_PORT)",
    )

    parser.add_argument(
        "--enable-cors",
        action="store_true",
        help="Enable CORS support for HTTP transports (overrides MCP_ENABLE_CORS)",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    return parser.parse_args()


def get_server_config(args: argparse.Namespace) -> dict:
    """Get server configuration from args and environment."""
    config = {}

    if args.transport in ["streamable-http", "sse"]:
        # HTTP-based transports need host and port
        config["host"] = args.host or os.getenv("MCP_SERVER_HOST", "localhost")
        config["port"] = args.port or int(os.getenv("MCP_SERVER_PORT", "8775"))

        if args.enable_cors or os.getenv("MCP_ENABLE_CORS", "false").lower() == "true":
            config["cors"] = True

    return config


def setup_cleanup_handlers():
    """Setup cleanup handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        """Signal handler for graceful shutdown."""
        print(f"Received signal {signum}, shutting down...", file=sys.stderr)
        # For now, rely on the MCP SDK's own cleanup mechanisms
        # The global wrapper will be cleaned up when the process exits
        sys.exit(0)
    
    # Register signal handlers only - let process exit handle cleanup
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()

    # Setup logging - for stdio transport, ensure we don't interfere with stdout
    # The logging is already configured to use stderr in the wrapper setup
    setup_logging(level=args.log_level)
    logger = get_logger(__name__)
    
    # Setup cleanup handlers for graceful shutdown
    setup_cleanup_handlers()

    try:
        # Only log startup for non-stdio transports to avoid interfering with MCP protocol
        if args.transport != "stdio":
            logger.info(f"Starting MCP Server with transport: {args.transport}")

        # Get server configuration
        config = get_server_config(args)

        # Create the server app
        server_app = create_server_app()

        # Run with the specified transport
        if args.transport == "stdio":
            # Don't log anything for stdio to avoid interfering with MCP protocol
            server_app.run(transport="stdio")
        elif args.transport == "streamable-http":
            # For HTTP transports, always use custom uvicorn approach to have full control
            logger.info(f"Using Streamable HTTP transport on {config['host']}:{config['port']}")
            run_http_server(server_app, config)
        elif args.transport == "sse":
            # For SSE transport, always use custom uvicorn approach to have full control
            logger.info(f"Using SSE transport on {config['host']}:{config['port']}")
            run_sse_server(server_app, config)

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def run_http_server(server_app, config):
    """Run HTTP server with custom configuration using Starlette + uvicorn."""
    import contextlib
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.middleware.cors import CORSMiddleware
    
    # Create a combined lifespan manager for the MCP server
    @contextlib.asynccontextmanager
    async def app_lifespan(app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(server_app.session_manager.run())
            yield
    
    # Create Starlette app and mount the MCP server
    app = Starlette(
        routes=[
            Mount("/", server_app.streamable_http_app()),
        ],
        lifespan=app_lifespan,
    )
    
    # Add CORS middleware if enabled
    if config.get("cors", False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=config["host"],
        port=config["port"],
        log_level="info"
    )


def run_sse_server(server_app, config):
    """Run SSE server with custom configuration using Starlette + uvicorn."""
    import contextlib
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount
    from starlette.middleware.cors import CORSMiddleware
    
    # Create a combined lifespan manager for the MCP server
    @contextlib.asynccontextmanager
    async def app_lifespan(app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(server_app.session_manager.run())
            yield
    
    # Create Starlette app and mount the MCP server
    app = Starlette(
        routes=[
            Mount("/", server_app.sse_app()),
        ],
        lifespan=app_lifespan,
    )
    
    # Add CORS middleware if enabled
    if config.get("cors", False):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=config["host"],
        port=config["port"],
        log_level="info"
    )


if __name__ == "__main__":
    main()
