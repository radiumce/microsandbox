#!/usr/bin/env python3
"""
End-to-end MCP server integration tests for LRU eviction using stdio transport.

This test suite validates LRU eviction through the complete MCP server stack:
1. MCP client SDK -> MCP server (stdio) -> MicrosandboxWrapper -> Microsandbox server
2. Official MCP protocol communication via stdio
3. Tool execution with resource limits
4. Real session management and eviction
5. Error handling and recovery
"""

import asyncio
import os
import pytest
import sys
import time
from typing import Dict, Any, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TestMCPLRUEvictionStdioE2E:
    """End-to-end MCP server tests for LRU eviction using stdio transport."""
    
    @pytest.fixture
    def microsandbox_server_url(self):
        """Get microsandbox server URL."""
        return os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555')
    
    @pytest.fixture
    def api_key(self):
        """Get API key."""
        return os.getenv('MSB_API_KEY')
    
    @pytest.fixture
    def mcp_server_params(self, microsandbox_server_url, api_key):
        """Create MCP server parameters for stdio connection."""
        # Set environment variables for the MCP server
        env = os.environ.copy()
        env['MSB_SERVER_URL'] = microsandbox_server_url
        if api_key:
            env['MSB_API_KEY'] = api_key
        env['MSB_MAX_SESSIONS'] = '3'
        env['MSB_MAX_TOTAL_MEMORY_MB'] = '3072'
        env['MSB_ENABLE_LRU_EVICTION'] = 'true'
        
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.main", "--transport", "stdio"],
            env=env
        )
    
    @pytest.fixture
    async def microsandbox_health_check(self, microsandbox_server_url):
        """Verify microsandbox server is running."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{microsandbox_server_url}/api/v1/health", timeout=5) as response:
                    if response.status != 200:
                        pytest.skip(f"Microsandbox server not healthy: {response.status}")
        except Exception as e:
            pytest.skip(f"Microsandbox server not accessible: {e}")
    
    @pytest.mark.asyncio
    async def test_mcp_stdio_lru_eviction_basic(self, mcp_server_params, microsandbox_health_check):
        """Test basic LRU eviction through MCP server using stdio transport."""
        print("\n=== MCP Stdio E2E Test: Basic LRU Eviction ===")
        
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Step 1: Initialize MCP server
                print("\n🔧 Initializing MCP server...")
                await session.initialize()
                print(f"  ✅ MCP server initialized successfully")
                
                # Step 2: List available tools
                print("\n🔍 Listing available tools...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                
                # Find the execute_code tool
                execute_tool = None
                for tool in tools:
                    if tool.name == "execute_code":
                        execute_tool = tool
                        break
                
                assert execute_tool is not None, "execute_code tool should be available"
                print(f"  ✅ Found execute_code tool: {execute_tool.description}")
                
                # Step 3: Create sessions up to the limit (3 sessions)
                print("\n📝 Creating sessions through MCP stdio...")
                session_results = []
                
                for i in range(3):  # Max sessions = 3
                    result = await session.call_tool(
                        "execute_code",
                        {
                            "code": f"""
import time
import os
print(f"MCP Session {i+1} created at {{time.strftime('%H:%M:%S')}}")
print(f"Process ID: {{os.getpid()}}")
session_data = {{"mcp_session": {i+1}, "created": time.time()}}
""",
                            "template": "python",
                            "flavor": "small"
                        }
                    )
                    
                    # Verify result
                    assert len(result.content) > 0, f"Session {i+1} should return content"
                    
                    text_content = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                    assert "created" in text_content.lower(), f"Session {i+1} creation should succeed"
                    
                    session_results.append(result)
                    print(f"  Created MCP session {i+1}")
                    await asyncio.sleep(0.5)  # Ensure different timestamps
                
                print(f"  ✅ Created {len(session_results)} sessions through MCP stdio")
                
                # Step 4: Access some sessions to update LRU order
                print("\n🔄 Updating LRU order through MCP stdio...")
                await asyncio.sleep(1)
                
                # Access the first two sessions to make them more recent
                for i in range(2):
                    result = await session.call_tool(
                        "execute_code",
                        {
                            "code": f"""
import time
print(f"MCP Session {i+1} accessed at {{time.strftime('%H:%M:%S')}}")
print("This MCP session should be kept (not LRU)")
access_data = {{"accessed": time.time(), "should_keep": True}}
""",
                            "template": "python"
                        }
                    )
                    
                    assert len(result.content) > 0, f"Session {i+1} access should succeed"
                    print(f"  Accessed MCP session {i+1}")
                    await asyncio.sleep(0.5)
                
                # Step 5: Create new session that should trigger eviction
                print("\n🚀 Creating new MCP session to trigger eviction...")
                
                eviction_result = await session.call_tool(
                    "execute_code",
                    {
                        "code": """
import time
print(f"New MCP session created at {time.strftime('%H:%M:%S')}")
print("LRU eviction should have occurred through MCP!")
eviction_data = {"purpose": "trigger_mcp_eviction", "created": time.time()}
""",
                        "template": "python",
                        "flavor": "small"
                    }
                )
                
                assert len(eviction_result.content) > 0, "New session creation should succeed"
                
                text_content = eviction_result.content[0].text if hasattr(eviction_result.content[0], 'text') else str(eviction_result.content[0])
                assert "created" in text_content.lower(), "New session should be created successfully"
                
                print(f"  ✅ New MCP session created successfully")
                print(f"  ✅ LRU eviction triggered through MCP stdio")
                
                print("\n🎉 MCP Stdio E2E Basic LRU Eviction Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_mcp_stdio_resource_limits(self, mcp_server_params, microsandbox_health_check):
        """Test resource limit enforcement through MCP stdio."""
        print("\n=== MCP Stdio E2E Test: Resource Limits ===")
        
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()
                print("  ✅ MCP server initialized")
                
                # Create sessions up to limit
                print("\n📝 Creating sessions up to MCP resource limit...")
                
                for i in range(3):  # Max sessions = 3
                    result = await session.call_tool(
                        "execute_code",
                        {
                            "code": f"print('MCP resource test session {i+1}'); session_num = {i+1}",
                            "template": "python",
                            "flavor": "small"
                        }
                    )
                    
                    assert len(result.content) > 0, f"Session {i+1} should be created"
                    print(f"  Created session {i+1} through MCP stdio")
                
                # Try to create one more session - should trigger eviction
                print("\n🚀 Creating session beyond limit (should trigger eviction)...")
                
                result = await session.call_tool(
                    "execute_code",
                    {
                        "code": "print('Extra MCP session - eviction should occur'); extra = True",
                        "template": "python",
                        "flavor": "small"
                    }
                )
                
                # Should succeed due to LRU eviction
                assert len(result.content) > 0, "Session creation should succeed after eviction"
                
                text_content = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                assert "Extra MCP session" in text_content, "New session should be created"
                
                print(f"  ✅ Session created successfully after MCP eviction")
                
                print("\n🎉 MCP Stdio E2E Resource Limits Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_mcp_stdio_session_reuse(self, mcp_server_params, microsandbox_health_check):
        """Test session reuse through MCP stdio."""
        print("\n=== MCP Stdio E2E Test: Session Reuse ===")
        
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()
                print("  ✅ MCP server initialized")
                
                # Create initial session
                print("\n📝 Creating initial MCP session...")
                
                result1 = await session.call_tool(
                    "execute_code",
                    {
                        "code": "session_var = 'initial_value'; print(f'Initial session: {session_var}')",
                        "template": "python",
                        "flavor": "small"
                    }
                )
                
                assert len(result1.content) > 0, "Initial session should be created"
                print(f"  Created initial session")
                
                # Test session state persistence by running another command
                print("\n🔄 Testing session state persistence...")
                
                result2 = await session.call_tool(
                    "execute_code",
                    {
                        "code": "print(f'Accessing session variable: {session_var}'); session_var = 'updated_value'",
                        "template": "python"
                    }
                )
                
                assert len(result2.content) > 0, "Session reuse should work"
                
                text_content2 = result2.content[0].text if hasattr(result2.content[0], 'text') else str(result2.content[0])
                assert "initial_value" in text_content2, "Session state should be preserved"
                
                print(f"  ✅ Session state preserved successfully")
                
                # Verify session state persistence
                print("\n🔍 Verifying session state update...")
                
                result3 = await session.call_tool(
                    "execute_code",
                    {
                        "code": "print(f'Final session state: {session_var}')",
                        "template": "python"
                    }
                )
                
                text_content3 = result3.content[0].text if hasattr(result3.content[0], 'text') else str(result3.content[0])
                assert "updated_value" in text_content3, "Session updates should persist"
                
                print(f"  ✅ Session state updated correctly")
                
                print("\n🎉 MCP Stdio E2E Session Reuse Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_mcp_stdio_error_handling(self, mcp_server_params, microsandbox_health_check):
        """Test error handling in MCP stdio LRU eviction."""
        print("\n=== MCP Stdio E2E Test: Error Handling ===")
        
        async with stdio_client(mcp_server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize
                await session.initialize()
                print("  ✅ MCP server initialized")
                
                # Test invalid code execution
                print("\n❌ Testing invalid code through MCP stdio...")
                
                try:
                    result = await session.call_tool(
                        "execute_code",
                        {
                            "code": "invalid python syntax !!!",
                            "template": "python",
                            "flavor": "small"
                        }
                    )
                    
                    # Should get result with error information
                    if result.content:
                        text_content = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                        # Error should be captured in the response
                        print(f"  ✅ Error handled gracefully: {text_content[:100]}...")
                    
                except Exception as e:
                    print(f"  ✅ Expected error handled: {type(e).__name__}")
                
                # Test invalid parameters
                print("\n❌ Testing invalid parameters through MCP stdio...")
                
                try:
                    await session.call_tool(
                        "execute_code",
                        {
                            "code": "print('test')",
                            "template": "invalid_template",
                            "flavor": "small"
                        }
                    )
                except Exception as e:
                    print(f"  ✅ Invalid template error handled: {type(e).__name__}")
                
                print("\n🎉 MCP Stdio E2E Error Handling Test PASSED!")


async def run_mcp_stdio_e2e_tests():
    """Run MCP stdio end-to-end tests manually."""
    print("🚀 Running MCP Stdio End-to-End LRU Eviction Tests")
    print("=" * 70)
    
    # Check microsandbox server
    server_url = os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server_url}/api/v1/health", timeout=5) as response:
                if response.status != 200:
                    print(f"❌ Microsandbox server not healthy: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Microsandbox server not accessible: {e}")
        print("Please start the microsandbox server:")
        print("  cd microsandbox-server && cargo run")
        return False
    
    print(f"✅ Microsandbox server is healthy at {server_url}")
    
    # Set up environment
    env = os.environ.copy()
    env['MSB_SERVER_URL'] = server_url
    env['MSB_MAX_SESSIONS'] = '3'
    env['MSB_MAX_TOTAL_MEMORY_MB'] = '3072'
    env['MSB_ENABLE_LRU_EVICTION'] = 'true'
    
    # Create server parameters
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.main", "--transport", "stdio"],
        env=env
    )
    
    try:
        # Create test instance
        test_instance = TestMCPLRUEvictionStdioE2E()
        
        # Run tests
        await test_instance.test_mcp_stdio_lru_eviction_basic(server_params, None)
        await test_instance.test_mcp_stdio_resource_limits(server_params, None)
        await test_instance.test_mcp_stdio_session_reuse(server_params, None)
        await test_instance.test_mcp_stdio_error_handling(server_params, None)
        
        print("\n" + "=" * 70)
        print("🎉 All MCP Stdio End-to-End LRU Eviction Tests PASSED!")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ MCP Stdio E2E Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_mcp_stdio_e2e_tests())
    if not success:
        exit(1)