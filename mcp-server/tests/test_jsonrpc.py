"""
Unit tests for JSON-RPC message parsing and response building.

Tests the JSON-RPC 2.0 protocol implementation, message validation,
and response formatting.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from fastapi.responses import JSONResponse

from mcp_server.server import RequestHandler, ErrorHandler, ToolRegistry
from microsandbox_wrapper.exceptions import (
    ResourceLimitError,
    ConfigurationError,
    CodeExecutionError
)


class TestErrorHandler:
    """Test ErrorHandler functionality."""
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    def test_handle_resource_limit_error(self, error_handler):
        """Test handling ResourceLimitError."""
        error = ResourceLimitError(
            "Session limit exceeded",
            resource_type="sessions",
            current_usage=5,
            limit=5
        )
        
        response = error_handler.handle_exception(error, "test-request-id")
        
        assert isinstance(response, JSONResponse)
        content = json.loads(response.body.decode())
        
        assert content["jsonrpc"] == "2.0"
        assert content["id"] == "test-request-id"
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Resource limit exceeded" in content["error"]["message"]
        assert "error_code" in content["error"]["data"]
    
    def test_handle_configuration_error(self, error_handler):
        """Test handling ConfigurationError."""
        error = ConfigurationError(
            "Invalid server URL",
            config_key="SERVER_URL"
        )
        
        response = error_handler.handle_exception(error, "test-request-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Configuration error" in content["error"]["message"]
    
    def test_handle_code_execution_error(self, error_handler):
        """Test handling CodeExecutionError."""
        error = CodeExecutionError(
            "Syntax error in code",
            error_type="compilation",
            session_id="test-session"
        )
        
        response = error_handler.handle_exception(error, "test-request-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Code execution failed" in content["error"]["message"]
    
    def test_handle_value_error(self, error_handler):
        """Test handling ValueError."""
        error = ValueError("Invalid parameter value")
        
        response = error_handler.handle_exception(error, "test-request-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Invalid parameters" in content["error"]["message"]
    
    def test_handle_generic_exception(self, error_handler):
        """Test handling generic exception."""
        error = Exception("Something went wrong")
        
        response = error_handler.handle_exception(error, "test-request-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert content["error"]["message"] == "Internal server error"
    
    def test_create_method_not_found_error(self, error_handler):
        """Test creating method not found error."""
        response = error_handler.create_method_not_found_error(
            "test-request-id", "unknown/method"
        )
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.METHOD_NOT_FOUND
        assert "unknown/method" in content["error"]["message"]
    
    def test_create_invalid_request_error(self, error_handler):
        """Test creating invalid request error."""
        response = error_handler.create_invalid_request_error(
            "test-request-id", "Missing required field"
        )
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Missing required field" in content["error"]["message"]
    
    def test_create_parse_error(self, error_handler):
        """Test creating parse error."""
        response = error_handler.create_parse_error()
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.PARSE_ERROR
        assert content["id"] is None


class TestRequestHandler:
    """Test RequestHandler functionality."""
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    @pytest.fixture
    def tool_registry(self):
        """Create ToolRegistry instance."""
        return ToolRegistry()
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    @pytest.fixture
    def request_handler(self, mock_wrapper, tool_registry, error_handler):
        """Create RequestHandler instance."""
        return RequestHandler(mock_wrapper, tool_registry, error_handler)
    
    def test_validate_jsonrpc_request_valid(self, request_handler):
        """Test validation of valid JSON-RPC request."""
        valid_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(valid_request)
        assert result is None
    
    def test_validate_jsonrpc_request_missing_version(self, request_handler):
        """Test validation with missing jsonrpc version."""
        invalid_request = {
            "method": "tools/list",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "jsonrpc version" in content["error"]["message"]
    
    def test_validate_jsonrpc_request_wrong_version(self, request_handler):
        """Test validation with wrong jsonrpc version."""
        invalid_request = {
            "jsonrpc": "1.0",
            "method": "tools/list",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "must be '2.0'" in content["error"]["message"]
    
    def test_validate_jsonrpc_request_missing_method(self, request_handler):
        """Test validation with missing method."""
        invalid_request = {
            "jsonrpc": "2.0",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "Missing required 'method' field" in content["error"]["message"]
    
    def test_validate_jsonrpc_request_invalid_method_type(self, request_handler):
        """Test validation with invalid method type."""
        invalid_request = {
            "jsonrpc": "2.0",
            "method": 123,
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "Method must be a string" in content["error"]["message"]
    
    def test_validate_jsonrpc_request_invalid_params_type(self, request_handler):
        """Test validation with invalid params type."""
        invalid_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": "invalid",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "Params must be an object or array" in content["error"]["message"]
    
    def test_validate_jsonrpc_request_not_dict(self, request_handler):
        """Test validation with non-dict request."""
        invalid_request = "not a dict"
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "Request must be a JSON object" in content["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_tools_list(self, request_handler):
        """Test handling tools/list request."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_list(request_body)
        content = json.loads(response.body.decode())
        
        assert content["jsonrpc"] == "2.0"
        assert content["id"] == "test-id"
        assert "result" in content
        assert "tools" in content["result"]
        assert len(content["result"]["tools"]) > 0
        
        # Check tool structure
        tool = content["result"]["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_missing_name(self, request_handler):
        """Test handling tools/call request with missing tool name."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"arguments": {}},
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_call(request_body)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Missing required parameter: name" in content["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_invalid_tool(self, request_handler):
        """Test handling tools/call request with invalid tool name."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            },
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_call(request_body)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.METHOD_NOT_FOUND
        assert "tool:nonexistent_tool" in content["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_invalid_params_type(self, request_handler):
        """Test handling tools/call request with invalid params type."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": "invalid",
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_call(request_body)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Params must be an object" in content["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_tools_call_invalid_arguments_type(self, request_handler):
        """Test handling tools/call request with invalid arguments type."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": "invalid"
            },
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_call(request_body)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Tool arguments must be an object" in content["error"]["message"]
    
    def test_validate_tool_arguments_missing_required(self, request_handler):
        """Test tool argument validation with missing required field."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        args = {}  # Missing required 'code' field
        
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Missing required parameter: code" in content["error"]["message"]
    
    def test_validate_tool_arguments_invalid_type(self, request_handler):
        """Test tool argument validation with invalid type."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        args = {"code": 123}  # Should be string
        
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "Parameter 'code' must be a string" in content["error"]["message"]
    
    def test_validate_tool_arguments_invalid_enum(self, request_handler):
        """Test tool argument validation with invalid enum value."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        args = {
            "code": "print('test')",
            "template": "invalid_template"
        }
        
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "must be one of:" in content["error"]["message"]
    
    def test_validate_tool_arguments_invalid_range(self, request_handler):
        """Test tool argument validation with value out of range."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        args = {
            "code": "print('test')",
            "timeout": 500  # Above maximum of 300
        }
        
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        assert isinstance(result, JSONResponse)
        
        content = json.loads(result.body.decode())
        assert "must be <= 300" in content["error"]["message"]
    
    def test_validate_tool_arguments_valid(self, request_handler):
        """Test tool argument validation with valid arguments."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        args = {
            "code": "print('test')",
            "template": "python",
            "flavor": "small",
            "timeout": 60
        }
        
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        assert result is None
    
    def test_add_cors_headers(self, request_handler):
        """Test adding CORS headers to response."""
        response = JSONResponse(content={"test": "data"})
        
        cors_response = request_handler._add_cors_headers(response)
        
        assert cors_response.headers["Access-Control-Allow-Origin"] == "*"
        assert "GET, POST, OPTIONS" in cors_response.headers["Access-Control-Allow-Methods"]
        assert "Content-Type" in cors_response.headers["Access-Control-Allow-Headers"]
        assert cors_response.headers["Access-Control-Max-Age"] == "86400"


class MockRequest:
    """Mock FastAPI Request for testing."""
    
    def __init__(self, method: str, headers: dict = None, json_data: dict = None):
        self.method = method
        self.headers = headers or {}
        self._json_data = json_data or {}
    
    async def json(self):
        if self._json_data is None:
            raise json.JSONDecodeError("Invalid JSON", "", 0)
        return self._json_data


class TestRequestHandlerIntegration:
    """Integration tests for RequestHandler with mock requests."""
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    @pytest.fixture
    def request_handler(self, mock_wrapper):
        """Create RequestHandler instance."""
        tool_registry = ToolRegistry()
        error_handler = ErrorHandler()
        return RequestHandler(mock_wrapper, tool_registry, error_handler)
    
    @pytest.mark.asyncio
    async def test_handle_post_request_valid(self, request_handler):
        """Test handling valid POST request."""
        request = MockRequest(
            method="POST",
            headers={"content-type": "application/json"},
            json_data={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "test-id"
            }
        )
        
        response = await request_handler.handle_request(request)
        assert isinstance(response, JSONResponse)
        
        content = json.loads(response.body.decode())
        assert content["jsonrpc"] == "2.0"
        assert "result" in content
    
    @pytest.mark.asyncio
    async def test_handle_post_request_invalid_content_type(self, request_handler):
        """Test handling POST request with invalid content type."""
        request = MockRequest(
            method="POST",
            headers={"content-type": "text/plain"},
            json_data={"test": "data"}
        )
        
        response = await request_handler.handle_request(request)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Content-Type must be application/json" in content["error"]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_post_request_invalid_json(self, request_handler):
        """Test handling POST request with invalid JSON."""
        request = MockRequest(
            method="POST",
            headers={"content-type": "application/json"},
            json_data=None  # Will trigger JSONDecodeError
        )
        
        response = await request_handler.handle_request(request)
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.PARSE_ERROR
    
    @pytest.mark.asyncio
    async def test_handle_get_request(self, request_handler, mock_wrapper):
        """Test handling GET request for status."""
        mock_wrapper.is_started.return_value = True
        
        request = MockRequest(method="GET")
        
        response = await request_handler.handle_request(request)
        content = json.loads(response.body.decode())
        
        assert content["status"] == "healthy"
        assert content["wrapper_started"] is True
        assert "available_tools" in content
    
    @pytest.mark.asyncio
    async def test_handle_options_request(self, request_handler):
        """Test handling OPTIONS request for CORS."""
        request = MockRequest(method="OPTIONS")
        
        response = await request_handler.handle_request(request)
        
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "*"
    
    @pytest.mark.asyncio
    async def test_handle_unsupported_method(self, request_handler):
        """Test handling unsupported HTTP method."""
        request = MockRequest(method="PUT")
        
        response = await request_handler.handle_request(request)
        
        assert response.status_code == 405
    
    @pytest.mark.asyncio
    async def test_handle_request_with_cors(self, request_handler):
        """Test handling request with CORS enabled."""
        request = MockRequest(method="GET")
        
        response = await request_handler.handle_request(request, enable_cors=True)
        
        assert response.headers["Access-Control-Allow-Origin"] == "*"