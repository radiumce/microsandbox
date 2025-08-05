#!/usr/bin/env python3
"""
Integration test for RPC API calls in orphan cleanup.

This test verifies that the ResourceManager correctly formats
and makes JSON-RPC calls to the microsandbox server.
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

# Add the microsandbox_wrapper to the path
sys.path.insert(0, 'microsandbox_wrapper')

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.resource_manager import ResourceManager


class MockSessionManager:
    """Mock session manager for testing"""
    
    async def get_sessions(self):
        return []


@pytest.mark.asyncio
async def test_rpc_call_format():
    """Test that RPC calls are formatted correctly"""
    print("Testing RPC call formatting...")
    
    config = WrapperConfig(
        server_url="http://localhost:5555",
        api_key="test-api-key"
    )
    
    session_manager = MockSessionManager()
    resource_manager = ResourceManager(config, session_manager)
    
    # Track the actual RPC calls made
    captured_calls = []
    
    # Mock aiohttp.ClientSession
    class MockResponse:
        def __init__(self, status=200, json_data=None):
            self.status = status
            self._json_data = json_data or {"jsonrpc": "2.0", "result": {"sandboxes": []}, "id": 1}
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def json(self):
            return self._json_data
        
        async def text(self):
            return json.dumps(self._json_data)
    
    class MockSession:
        def __init__(self, timeout=None):
            self.timeout = timeout
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        def post(self, url, json=None, headers=None):
            # Capture the call details
            captured_calls.append({
                'url': url,
                'json': json,
                'headers': headers
            })
            
            # Return appropriate mock response
            if json and json.get('method') == 'sandbox.metrics.get':
                return MockResponse(200, {
                    "jsonrpc": "2.0",
                    "result": {
                        "sandboxes": [
                            {
                                "namespace": "default",
                                "name": "orphan-test",
                                "running": True,
                                "cpu_usage": 10.0,
                                "memory_usage": 256,
                                "disk_usage": 512000
                            }
                        ]
                    },
                    "id": 1
                })
            elif json and json.get('method') == 'sandbox.stop':
                return MockResponse(200, {
                    "jsonrpc": "2.0",
                    "result": "Sandbox stopped successfully",
                    "id": 1
                })
            
            return MockResponse()
    
    # Patch aiohttp.ClientSession
    with patch('microsandbox_wrapper.resource_manager.aiohttp.ClientSession', MockSession):
        # Test getting running sandboxes
        running_sandboxes = await resource_manager._get_running_sandboxes()
        
        # Verify the call was made correctly
        assert len(captured_calls) == 1
        call = captured_calls[0]
        
        # Check URL
        assert call['url'] == "http://localhost:5555/api/v1/rpc"
        
        # Check headers
        assert call['headers']['Content-Type'] == 'application/json'
        assert call['headers']['Authorization'] == 'Bearer test-api-key'
        
        # Check JSON-RPC request format
        rpc_request = call['json']
        assert rpc_request['jsonrpc'] == '2.0'
        assert rpc_request['method'] == 'sandbox.metrics.get'
        assert rpc_request['params']['namespace'] == '*'
        assert rpc_request['params']['sandbox'] is None
        assert 'id' in rpc_request
        
        # Check response parsing
        assert len(running_sandboxes) == 1
        assert running_sandboxes[0]['namespace'] == 'default'
        assert running_sandboxes[0]['name'] == 'orphan-test'
        assert running_sandboxes[0]['running'] is True
        
        print("✓ RPC call formatting test passed!")
        
        # Test orphan cleanup (which will make stop calls)
        captured_calls.clear()
        cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
        
        # Should have made 1 get call + 1 stop call
        assert len(captured_calls) == 2
        assert cleaned_count == 1
        
        # Check the stop call
        stop_call = captured_calls[1]
        assert stop_call['json']['method'] == 'sandbox.stop'
        assert stop_call['json']['params']['sandbox'] == 'orphan-test'
        assert stop_call['json']['params']['namespace'] == 'default'
        
        print("✓ Orphan cleanup RPC calls test passed!")


@pytest.mark.asyncio
async def test_rpc_error_handling():
    """Test RPC error handling"""
    print("\nTesting RPC error handling...")
    
    config = WrapperConfig(server_url="http://localhost:5555")
    session_manager = MockSessionManager()
    resource_manager = ResourceManager(config, session_manager)
    
    # Mock session that returns RPC errors
    class MockErrorSession:
        def __init__(self, timeout=None):
            self.timeout = timeout
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        def post(self, url, json=None, headers=None):
            if json and json.get('method') == 'sandbox.metrics.get':
                # Return RPC error
                return MockResponse(200, {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32602,
                        "message": "Invalid params"
                    },
                    "id": 1
                })
            return MockResponse()
    
    class MockResponse:
        def __init__(self, status=200, json_data=None):
            self.status = status
            self._json_data = json_data
        
        async def json(self):
            return self._json_data
        
        async def text(self):
            return json.dumps(self._json_data)
    
    with patch('microsandbox_wrapper.resource_manager.aiohttp.ClientSession', MockErrorSession):
        # Test that RPC errors are handled gracefully
        running_sandboxes = await resource_manager._get_running_sandboxes()
        
        # Should return empty list on error
        assert running_sandboxes == []
        
        print("✓ RPC error handling test passed!")


@pytest.mark.asyncio
async def test_http_error_handling():
    """Test HTTP error handling"""
    print("\nTesting HTTP error handling...")
    
    config = WrapperConfig(server_url="http://localhost:5555")
    session_manager = MockSessionManager()
    resource_manager = ResourceManager(config, session_manager)
    
    # Mock session that returns HTTP errors
    class MockHttpErrorSession:
        def __init__(self, timeout=None):
            self.timeout = timeout
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        def post(self, url, json=None, headers=None):
            return MockResponse(500, {"error": "Internal server error"})
    
    class MockResponse:
        def __init__(self, status=200, json_data=None):
            self.status = status
            self._json_data = json_data
        
        async def json(self):
            return self._json_data
        
        async def text(self):
            return "Internal server error"
    
    with patch('microsandbox_wrapper.resource_manager.aiohttp.ClientSession', MockHttpErrorSession):
        # Test that HTTP errors are handled gracefully
        running_sandboxes = await resource_manager._get_running_sandboxes()
        
        # Should return empty list on error
        assert running_sandboxes == []
        
        print("✓ HTTP error handling test passed!")


async def main():
    """Run all tests"""
    print("Starting RPC integration tests...\n")
    
    try:
        await test_rpc_call_format()
        await test_rpc_error_handling()
        await test_http_error_handling()
        
        print("\n🎉 All RPC integration tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())