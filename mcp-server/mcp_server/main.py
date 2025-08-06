"""
MCP Server Entry Point and Configuration

This module provides the main entry point and configuration management
for the MCP server.
"""

import os
import sys
import signal
import asyncio
import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from microsandbox_wrapper import (
    MicrosandboxWrapper,
    setup_logging,
    get_logger,
    ConfigurationError
)


@dataclass
class MCPServerConfig:
    """Configuration class for MCP Server"""
    host: str = "localhost"
    port: int = 8000
    enable_cors: bool = False
    
    @classmethod
    def from_env(cls) -> 'MCPServerConfig':
        """Create configuration from environment variables"""
        try:
            port = int(os.getenv("MCP_SERVER_PORT", "8000"))
            if port < 1 or port > 65535:
                raise ValueError(f"Invalid port number: {port}")
        except ValueError as e:
            raise ConfigurationError(f"Invalid MCP_SERVER_PORT: {e}")
        
        return cls(
            host=os.getenv("MCP_SERVER_HOST", "localhost"),
            port=port,
            enable_cors=os.getenv("MCP_ENABLE_CORS", "false").lower() == "true"
        )
    
    def validate(self) -> None:
        """Validate configuration values"""
        if not self.host:
            raise ConfigurationError("Host cannot be empty")
        
        if not isinstance(self.port, int) or self.port < 1 or self.port > 65535:
            raise ConfigurationError(f"Invalid port: {self.port}")


class MCPServerApp:
    """Main MCP Server application with lifecycle management"""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.wrapper: Optional[MicrosandboxWrapper] = None
        self.server = None
        self.shutdown_event = asyncio.Event()
        self.logger = get_logger(__name__)
        
    async def start(self) -> None:
        """Start the MCP server with proper lifecycle management"""
        try:
            self.logger.info("Starting MCP Server...")
            self.logger.info(f"Configuration: host={self.config.host}, port={self.config.port}, cors={self.config.enable_cors}")
            
            # 1. Initialize and start wrapper first
            self.logger.info("Initializing MicrosandboxWrapper...")
            self.wrapper = MicrosandboxWrapper()
            await self.wrapper.start()
            self.logger.info("MicrosandboxWrapper started successfully")
            
            # 2. Initialize MCP server (will be implemented in task 3)
            # For now, we'll create a placeholder that shows the server would start
            self.logger.info("MCP Server would start here (to be implemented in task 3)")
            self.logger.info(f"Server would listen on {self.config.host}:{self.config.port}")
            
            # 3. Wait for shutdown signal
            self.logger.info("MCP Server startup complete, waiting for shutdown signal...")
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Failed to start MCP Server: {e}")
            await self.cleanup()
            raise
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the server"""
        self.logger.info("Initiating graceful shutdown...")
        
        try:
            # 1. Stop accepting new requests (will be implemented in task 3)
            self.logger.info("Stopping new request acceptance...")
            
            # 2. Wait for existing requests to complete (will be implemented in task 3)
            self.logger.info("Waiting for existing requests to complete...")
            
            # 3. Shutdown wrapper
            if self.wrapper:
                self.logger.info("Shutting down MicrosandboxWrapper...")
                await self.wrapper.stop()
                self.logger.info("MicrosandboxWrapper shutdown complete")
            
            # 4. Signal shutdown complete
            self.shutdown_event.set()
            self.logger.info("Graceful shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Emergency cleanup in case of startup failure"""
        self.logger.info("Performing emergency cleanup...")
        
        if self.wrapper:
            try:
                await self.wrapper.stop()
            except Exception as e:
                self.logger.error(f"Error during wrapper cleanup: {e}")


# Global app instance for signal handlers
_app_instance: Optional[MCPServerApp] = None


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals"""
    logger = get_logger(__name__)
    signal_name = signal.Signals(signum).name
    logger.info(f"Received {signal_name} signal, initiating shutdown...")
    
    if _app_instance:
        # Create a new event loop if we're not in one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Schedule shutdown
        asyncio.create_task(_app_instance.shutdown())


def setup_signal_handlers() -> None:
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # On Unix systems, also handle SIGHUP
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MCP Server for Microsandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  MCP_SERVER_HOST     Server host address (default: localhost)
  MCP_SERVER_PORT     Server port number (default: 8000)
  MCP_ENABLE_CORS     Enable CORS support (default: false)

Examples:
  python -m mcp_server.main
  MCP_SERVER_PORT=9000 python -m mcp_server.main
  MCP_SERVER_HOST=0.0.0.0 MCP_ENABLE_CORS=true python -m mcp_server.main
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        help="Server host address (overrides MCP_SERVER_HOST)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        help="Server port number (overrides MCP_SERVER_PORT)"
    )
    
    parser.add_argument(
        "--enable-cors",
        action="store_true",
        help="Enable CORS support (overrides MCP_ENABLE_CORS)"
    )
    
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    
    return parser.parse_args()


async def main() -> None:
    """Main entry point"""
    global _app_instance
    
    # Parse command line arguments
    args = parse_args()
    
    # Setup logging
    setup_logging(level=getattr(logging, args.log_level))
    logger = get_logger(__name__)
    
    try:
        # Load configuration from environment
        config = MCPServerConfig.from_env()
        
        # Override with command line arguments if provided
        if args.host:
            config.host = args.host
        if args.port:
            config.port = args.port
        if args.enable_cors:
            config.enable_cors = True
        
        # Validate configuration
        config.validate()
        
        # Create and start application
        _app_instance = MCPServerApp(config)
        setup_signal_handlers()
        
        await _app_instance.start()
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())