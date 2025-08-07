#!/usr/bin/env python3
"""
Test script using official MCP Python SDK client
"""

import asyncio
import sys
import subprocess
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server():
    """Test MCP server using official SDK client."""
    
    print("Starting MCP server test with official SDK client...")
    
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.main", "--transport", "stdio"],
        env={}
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("✓ Connected to MCP server")
                
                # Initialize the connection
                await session.initialize()
                print("✓ Server initialized successfully!")
                
                # List available tools
                print("\n=== Testing Tools ===")
                tools = await session.list_tools()
                print(f"✓ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")
                
                # Test execute_code tool
                if any(tool.name == "execute_code" for tool in tools.tools):
                    print("\n=== Testing execute_code tool ===")
                    try:
                        result = await session.call_tool(
                            "execute_code", 
                            {
                                "params": {
                                    "code": "print('Hello from microsandbox!')",
                                    "template": "python"
                                }
                            }
                        )
                        print("✓ execute_code tool call successful:")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(f"  Result: {content.text}")
                    except Exception as e:
                        print(f"✗ execute_code tool call failed: {e}")
                
                # Test get_sessions tool  
                if any(tool.name == "get_sessions" for tool in tools.tools):
                    print("\n=== Testing get_sessions tool ===")
                    try:
                        result = await session.call_tool("get_sessions", {"params": {}})
                        print("✓ get_sessions tool call successful:")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(f"  Result: {content.text}")
                    except Exception as e:
                        print(f"✗ get_sessions tool call failed: {e}")
                
                # Test get_volume_mappings tool
                if any(tool.name == "get_volume_mappings" for tool in tools.tools):
                    print("\n=== Testing get_volume_mappings tool ===")
                    try:
                        result = await session.call_tool("get_volume_mappings", {})
                        print("✓ get_volume_mappings tool call successful:")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                print(f"  Result: {content.text}")
                    except Exception as e:
                        print(f"✗ get_volume_mappings tool call failed: {e}")
                
                print("\n✓ All tests completed!")
                
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_server())
