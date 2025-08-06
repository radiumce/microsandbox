#!/usr/bin/env python3
"""
Simple test script for MCP server
"""

import asyncio
import json
import sys
import subprocess
from pathlib import Path

async def test_mcp_server_stdio():
    """Test MCP server using stdio transport."""
    
    print("Starting MCP server test...")
    
    # Start the MCP server process
    server_cmd = [
        sys.executable, "-m", "mcp_server.main_sdk", 
        "--transport", "stdio"
    ]
    
    try:
        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send initialization message
        init_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Sending initialize message...")
        process.stdin.write(json.dumps(init_message) + "\n")
        process.stdin.flush()
        
        # Give server time to start
        await asyncio.sleep(2)
        
        # Read any stderr output first
        import select
        if hasattr(select, 'select'):
            stderr_ready, _, _ = select.select([process.stderr], [], [], 0.1)
            while stderr_ready:
                stderr_line = process.stderr.readline().strip()
                if stderr_line:
                    print(f"[SERVER LOG] {stderr_line}")
                stderr_ready, _, _ = select.select([process.stderr], [], [], 0.1)
        
        # Read response with timeout
        if hasattr(select, 'select'):
            ready, _, _ = select.select([process.stdout], [], [], 5.0)
            if ready:
                response = process.stdout.readline().strip()
                if response:
                    print(f"Server response: {response}")
                    
                    # Try to parse response
                    try:
                        response_data = json.loads(response)
                        if 'result' in response_data:
                            print("✓ Server initialized successfully!")
                            
                            # Send initialized notification as per MCP protocol
                            initialized_notification = {
                                "jsonrpc": "2.0",
                                "method": "notifications/initialized"
                            }
                            
                            print("Sending initialized notification...")
                            process.stdin.write(json.dumps(initialized_notification) + "\n")
                            process.stdin.flush()
                            
                            # Give server time to process notification
                            await asyncio.sleep(0.5)
                            
                            # Send tools/list request
                            tools_message = {
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/list",
                                "params": {}
                            }
                            
                            print("Requesting tool list...")
                            process.stdin.write(json.dumps(tools_message) + "\n")
                            process.stdin.flush()
                            
                            # Read tools response
                            ready, _, _ = select.select([process.stdout], [], [], 5.0)
                            if ready:
                                tools_response = process.stdout.readline().strip()
                                if tools_response:
                                    print(f"Tools response: {tools_response}")
                                    tools_data = json.loads(tools_response)
                                    if 'result' in tools_data and 'tools' in tools_data['result']:
                                        tools = tools_data['result']['tools']
                                        print(f"✓ Found {len(tools)} tools:")
                                        for tool in tools:
                                            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                                    elif 'error' in tools_data:
                                        error = tools_data['error']
                                        print(f"✗ Tools list error: {error['code']} - {error['message']}")
                                        if error.get('data'):
                                            print(f"  Error details: {error['data']}")
                                        
                                        # Try alternate request format without params
                                        print("Trying alternate request format...")
                                        tools_message_alt = {
                                            "jsonrpc": "2.0",
                                            "id": 3,
                                            "method": "tools/list"
                                        }
                                        
                                        process.stdin.write(json.dumps(tools_message_alt) + "\n")
                                        process.stdin.flush()
                                        
                                        # Read alternate response
                                        ready, _, _ = select.select([process.stdout], [], [], 5.0)
                                        if ready:
                                            alt_response = process.stdout.readline().strip()
                                            if alt_response:
                                                print(f"Alternate response: {alt_response}")
                                                alt_data = json.loads(alt_response)
                                                if 'result' in alt_data:
                                                    tools = alt_data['result'].get('tools', [])
                                                    print(f"✓ Found {len(tools)} tools with alternate format:")
                                                    for tool in tools:
                                                        print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                        else:
                            print(f"Server error: {response_data.get('error', 'Unknown error')}")
                    except json.JSONDecodeError:
                        print(f"Invalid JSON response: {response}")
            else:
                print("✗ No response from server within timeout")
        else:
            # Fallback for systems without select
            response = process.stdout.readline().strip()
            print(f"Server response: {response}")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

if __name__ == "__main__":
    asyncio.run(test_mcp_server_stdio())
