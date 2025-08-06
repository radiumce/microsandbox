#!/usr/bin/env python3
"""
Simple test to verify MCP server can start up correctly.
"""

import asyncio
import logging
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from microsandbox_wrapper import MicrosandboxWrapper
from mcp_server.server import MCPServer
from mcp_server.main import MCPServerConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_mcp_server_startup():
    """Test that MCP server can start up and shut down cleanly."""
    logger.info("Testing MCP server startup...")
    
    try:
        # Configure MCP server
        config = MCPServerConfig(
            host="localhost",
            port=8002,  # Use different port for testing
            enable_cors=True
        )
        
        # Create wrapper instance
        wrapper = MicrosandboxWrapper()
        logger.info("Starting wrapper...")
        await wrapper.start()
        
        # Create MCP server
        server = MCPServer(
            wrapper=wrapper,
            host=config.host,
            port=config.port,
            enable_cors=config.enable_cors
        )
        
        logger.info("Starting MCP server...")
        # Start server in background
        server_task = asyncio.create_task(server.start())
        
        # Wait a bit for server to start
        await asyncio.sleep(2)
        
        logger.info("✓ MCP server started successfully")
        
        # Test basic HTTP request
        import aiohttp
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"http://{config.host}:{config.port}") as response:
                    if response.status == 200:
                        logger.info("✓ Server responds to HTTP requests")
                    else:
                        logger.warning(f"Server returned status {response.status}")
            except Exception as e:
                logger.error(f"Failed to connect to server: {e}")
        
        # Cleanup
        logger.info("Shutting down server...")
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        
        logger.info("✓ MCP server test completed successfully")
        
    except Exception as e:
        logger.error(f"✗ MCP server test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_mcp_server_startup())