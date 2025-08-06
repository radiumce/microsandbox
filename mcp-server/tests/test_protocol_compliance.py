"""
Unit tests for JSON-RPC 2.0 and MCP protocol compliance.

Tests that the server correctly implements JSON-RPC 2.0 specification
and MCP protocol message structures and error responses.
"""

import json
import pytest
from typing import Dict, Any

from mcp_server.server import (
    RequestHandler,
    ErrorHandler,
    ToolRegistry,
    ExecuteCodeTool,
    ExecuteCommandTool,
    GetSessionsTool,
    StopSessionTool,
    GetVolumePathTool
)
from unittest.mock import AsyncMock


class TestJSONRPC20Compliance:
    """Test JSON-RPC 2.0 protocol compliance."""
    
    @pytest.fixture
    def request_handler(self):
        """Create RequestHandler instance."""
        mock_wrapper = AsyncMock()
        tool_registry = ToolRegistry()
        error_handler = ErrorHandler()
        return RequestHandler(mock_wrapper, tool_registry, error_handler)
    
    def test_jsonrpc_version_required(self, request_handler):
        """Test that jsonrpc version field is required."""
        invalid_request = {
            "method": "tools/list",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert result is not None
        
        content = json.loads(result.body.decode())
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "jsonrpc version" in content["error"]["message"]
    
    def test_jsonrpc_version_must_be_2_0(self, request_handler):
        """Test that jsonrpc version must be exactly '2.0'."""
        invalid_versions = ["1.0", "2.1", "3.0", 2.0, None]
        
        for version in invalid_versions:
            invalid_request = {
                "jsonrpc": version,
                "method": "tools/list",
                "id": "test-id"
            }
            
            result = request_handler._validate_jsonrpc_request(invalid_request)
            assert result is not None, f"Failed for version: {version}"
            
            content = json.loads(result.body.decode())
            assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
            assert "must be '2.0'" in content["error"]["message"]
    
    def test_method_field_required(self, request_handler):
        """Test that method field is required."""
        invalid_request = {
            "jsonrpc": "2.0",
            "id": "test-id"
        }
        
        result = request_handler._validate_jsonrpc_request(invalid_request)
        assert result is not None
        
        content = json.loads(result.body.decode())
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Missing required 'method' field" in content["error"]["message"]
    
    def test_method_must_be_string(self, request_handler):
        """Test that method field must be a string."""
        invalid_methods = [123, None, [], {}]
        
        for method in invalid_methods:
            invalid_request = {
                "jsonrpc": "2.0",
                "method": method,
                "id": "test-id"
            }
            
            result = request_handler._validate_jsonrpc_request(invalid_request)
            assert result is not None, f"Failed for method: {method}"
            
            content = json.loads(result.body.decode())
            assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
            assert "Method must be a string" in content["error"]["message"]
    
    def test_params_must_be_object_or_array(self, request_handler):
        """Test that params field must be object or array if present."""
        invalid_params = ["string", 123, None, True]
        
        for params in invalid_params:
            invalid_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": params,
                "id": "test-id"
            }
            
            result = request_handler._validate_jsonrpc_request(invalid_request)
            assert result is not None, f"Failed for params: {params}"
            
            content = json.loads(result.body.decode())
            assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
            assert "Params must be an object or array" in content["error"]["message"]
    
    def test_valid_jsonrpc_request_formats(self, request_handler):
        """Test various valid JSON-RPC request formats."""
        valid_requests = [
            # Basic request with id
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "test-id"
            },
            # Request with object params
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "execute_code", "arguments": {"code": "print('test')"}},
                "id": "test-id"
            },
            # Request with array params (though not used in MCP)
            {
                "jsonrpc": "2.0",
                "method": "some/method",
                "params": ["arg1", "arg2"],
                "id": "test-id"
            },
            # Request without params
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": "test-id"
            },
            # Request with numeric id
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 123
            },
            # Request with null id
            {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": None
            }
        ]
        
        for request in valid_requests:
            result = request_handler._validate_jsonrpc_request(request)
            assert result is None, f"Valid request failed validation: {request}"
    
    @pytest.mark.asyncio
    async def test_response_format_compliance(self, request_handler):
        """Test that responses follow JSON-RPC 2.0 format."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_list(request_body)
        content = json.loads(response.body.decode())
        
        # Check required fields
        assert "jsonrpc" in content
        assert content["jsonrpc"] == "2.0"
        assert "id" in content
        assert content["id"] == "test-id"
        
        # Should have either result or error, not both
        assert ("result" in content) != ("error" in content)
        
        # This should be a successful response
        assert "result" in content
        assert "error" not in content
    
    def test_error_response_format_compliance(self, request_handler):
        """Test that error responses follow JSON-RPC 2.0 format."""
        error_handler = ErrorHandler()
        error = ValueError("Test error")
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        # Check required fields
        assert "jsonrpc" in content
        assert content["jsonrpc"] == "2.0"
        assert "id" in content
        assert content["id"] == "test-id"
        assert "error" in content
        assert "result" not in content
        
        # Check error object structure
        error_obj = content["error"]
        assert "code" in error_obj
        assert "message" in error_obj
        assert isinstance(error_obj["code"], int)
        assert isinstance(error_obj["message"], str)
    
    def test_standard_error_codes(self):
        """Test that standard JSON-RPC error codes are used."""
        # Test that our error codes match JSON-RPC 2.0 specification
        assert ErrorHandler.PARSE_ERROR == -32700
        assert ErrorHandler.INVALID_REQUEST == -32600
        assert ErrorHandler.METHOD_NOT_FOUND == -32601
        assert ErrorHandler.INVALID_PARAMS == -32602
        assert ErrorHandler.INTERNAL_ERROR == -32603
    
    def test_http_status_code_compliance(self, request_handler):
        """Test that HTTP status codes follow JSON-RPC over HTTP guidelines."""
        error_handler = ErrorHandler()
        
        # JSON-RPC errors should use HTTP 200
        error = ValueError("Test error")
        response = error_handler.handle_exception(error, "test-id")
        assert response.status_code == 200
        
        # Parse errors should also use HTTP 200
        parse_error_response = error_handler.create_parse_error()
        assert parse_error_response.status_code == 200


class TestMCPProtocolCompliance:
    """Test MCP protocol message structure compliance."""
    
    @pytest.fixture
    def tool_registry(self):
        """Create ToolRegistry instance."""
        return ToolRegistry()
    
    @pytest.fixture
    def request_handler(self):
        """Create RequestHandler instance."""
        mock_wrapper = AsyncMock()
        tool_registry = ToolRegistry()
        error_handler = ErrorHandler()
        return RequestHandler(mock_wrapper, tool_registry, error_handler)
    
    @pytest.mark.asyncio
    async def test_tools_list_response_structure(self, request_handler):
        """Test that tools/list response follows MCP structure."""
        request_body = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_list(request_body)
        content = json.loads(response.body.decode())
        
        # Check MCP-specific structure
        assert "result" in content
        result = content["result"]
        assert "tools" in result
        assert isinstance(result["tools"], list)
        
        # Check each tool has required MCP fields
        for tool in result["tools"]:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            assert isinstance(tool["inputSchema"], dict)
    
    @pytest.mark.asyncio
    async def test_tools_call_request_structure(self, request_handler):
        """Test that tools/call request validation follows MCP structure."""
        # Valid MCP tools/call request
        valid_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "execute_code",
                "arguments": {
                    "code": "print('Hello, World!')"
                }
            },
            "id": "test-id"
        }
        
        # Should pass validation
        validation_result = request_handler._validate_jsonrpc_request(valid_request)
        assert validation_result is None
        
        # Test missing name parameter
        invalid_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "arguments": {"code": "print('test')"}
            },
            "id": "test-id"
        }
        
        response = await request_handler._handle_tools_call(invalid_request)
        content = json.loads(response.body.decode())
        
        assert "error" in content
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Missing required parameter: name" in content["error"]["message"]
    
    def test_tool_definition_schema_compliance(self, tool_registry):
        """Test that tool definitions follow MCP schema requirements."""
        tools = tool_registry.list_tools()
        
        for tool_def in tools:
            # Check required fields
            assert hasattr(tool_def, 'name')
            assert hasattr(tool_def, 'description')
            assert hasattr(tool_def, 'inputSchema')
            
            # Check field types
            assert isinstance(tool_def.name, str)
            assert isinstance(tool_def.description, str)
            assert isinstance(tool_def.inputSchema, dict)
            
            # Check schema structure
            schema = tool_def.inputSchema
            assert "type" in schema
            assert schema["type"] == "object"
            assert "properties" in schema
            assert isinstance(schema["properties"], dict)
            
            # Check that required fields are listed
            if "required" in schema:
                assert isinstance(schema["required"], list)
                for required_field in schema["required"]:
                    assert required_field in schema["properties"]
    
    def test_execute_code_tool_schema(self, tool_registry):
        """Test execute_code tool schema compliance."""
        tool = tool_registry.get_tool("execute_code")
        assert tool is not None
        
        definition = tool.get_definition()
        schema = definition.inputSchema
        
        # Check required fields
        assert "code" in schema["required"]
        assert "code" in schema["properties"]
        
        # Check optional fields have proper defaults
        properties = schema["properties"]
        assert "template" in properties
        assert properties["template"].get("default") == "python"
        assert "flavor" in properties
        assert properties["flavor"].get("default") == "small"
        
        # Check enum constraints
        assert "enum" in properties["template"]
        assert "python" in properties["template"]["enum"]
        assert "node" in properties["template"]["enum"]
        
        assert "enum" in properties["flavor"]
        assert "small" in properties["flavor"]["enum"]
        assert "medium" in properties["flavor"]["enum"]
        assert "large" in properties["flavor"]["enum"]
    
    def test_execute_command_tool_schema(self, tool_registry):
        """Test execute_command tool schema compliance."""
        tool = tool_registry.get_tool("execute_command")
        assert tool is not None
        
        definition = tool.get_definition()
        schema = definition.inputSchema
        
        # Check required fields
        assert "command" in schema["required"]
        assert "command" in schema["properties"]
        
        # Check array field for args
        properties = schema["properties"]
        assert "args" in properties
        assert properties["args"]["type"] == "array"
        assert properties["args"]["items"]["type"] == "string"
    
    def test_get_sessions_tool_schema(self, tool_registry):
        """Test get_sessions tool schema compliance."""
        tool = tool_registry.get_tool("get_sessions")
        assert tool is not None
        
        definition = tool.get_definition()
        schema = definition.inputSchema
        
        # Should have no required fields
        assert schema["required"] == []
        
        # Optional session_id parameter
        properties = schema["properties"]
        assert "session_id" in properties
        assert properties["session_id"]["type"] == "string"
    
    def test_stop_session_tool_schema(self, tool_registry):
        """Test stop_session tool schema compliance."""
        tool = tool_registry.get_tool("stop_session")
        assert tool is not None
        
        definition = tool.get_definition()
        schema = definition.inputSchema
        
        # Should require session_id
        assert "session_id" in schema["required"]
        assert "session_id" in schema["properties"]
        assert schema["properties"]["session_id"]["type"] == "string"
    
    def test_get_volume_path_tool_schema(self, tool_registry):
        """Test get_volume_path tool schema compliance."""
        tool = tool_registry.get_tool("get_volume_path")
        assert tool is not None
        
        definition = tool.get_definition()
        schema = definition.inputSchema
        
        # Should have no required fields
        assert schema["required"] == []


class TestParameterValidation:
    """Test parameter validation compliance."""
    
    @pytest.fixture
    def request_handler(self):
        """Create RequestHandler instance."""
        mock_wrapper = AsyncMock()
        tool_registry = ToolRegistry()
        error_handler = ErrorHandler()
        return RequestHandler(mock_wrapper, tool_registry, error_handler)
    
    def test_required_parameter_validation(self, request_handler):
        """Test validation of required parameters."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        
        # Missing required parameter
        args = {}
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Missing required parameter: code" in content["error"]["message"]
    
    def test_type_validation(self, request_handler):
        """Test parameter type validation."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        
        # Wrong type for code parameter
        args = {"code": 123}  # Should be string
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert "Parameter 'code' must be a string" in content["error"]["message"]
    
    def test_enum_validation(self, request_handler):
        """Test enum parameter validation."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        
        # Invalid enum value
        args = {
            "code": "print('test')",
            "template": "invalid_template"
        }
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert "must be one of:" in content["error"]["message"]
    
    def test_range_validation(self, request_handler):
        """Test numeric range validation."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        
        # Value above maximum
        args = {
            "code": "print('test')",
            "timeout": 500  # Above maximum of 300
        }
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert "must be <= 300" in content["error"]["message"]
        
        # Value below minimum
        args = {
            "code": "print('test')",
            "timeout": 0  # Below minimum of 1
        }
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert "must be >= 1" in content["error"]["message"]
    
    def test_array_type_validation(self, request_handler):
        """Test array parameter validation."""
        tool = request_handler.tool_registry.get_tool("execute_command")
        
        # Wrong type for args parameter
        args = {
            "command": "ls",
            "args": "not_an_array"  # Should be array
        }
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is not None
        content = json.loads(result.body.decode())
        assert "Parameter 'args' must be an array" in content["error"]["message"]
    
    def test_valid_parameters_pass_validation(self, request_handler):
        """Test that valid parameters pass validation."""
        tool = request_handler.tool_registry.get_tool("execute_code")
        
        # Valid parameters
        args = {
            "code": "print('Hello, World!')",
            "template": "python",
            "flavor": "small",
            "timeout": 60
        }
        result = request_handler._validate_tool_arguments(tool, args, "test-id")
        
        assert result is None  # No validation error


class TestErrorResponseCompliance:
    """Test error response compliance with MCP and JSON-RPC standards."""
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    def test_error_response_includes_recovery_suggestions(self, error_handler):
        """Test that MCP error responses include recovery suggestions."""
        from microsandbox_wrapper.exceptions import ResourceLimitError
        
        error = ResourceLimitError(
            "Session limit exceeded",
            resource_type="sessions",
            current_usage=10,
            limit=10
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        # Should have additional error data
        assert "data" in content["error"]
        error_data = content["error"]["data"]
        
        # Should include recovery suggestions
        assert "recovery_suggestions" in error_data
        assert isinstance(error_data["recovery_suggestions"], list)
        assert len(error_data["recovery_suggestions"]) > 0
    
    def test_error_response_includes_context(self, error_handler):
        """Test that error responses include relevant context."""
        from microsandbox_wrapper.exceptions import CodeExecutionError
        
        error = CodeExecutionError(
            "Syntax error",
            error_type="compilation",
            session_id="test-session",
            code_snippet="print("
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        error_data = content["error"]["data"]
        assert "context" in error_data
        assert "session_id" in str(error_data["context"])
        assert "compilation" in str(error_data["context"])
    
    def test_error_categorization(self, error_handler):
        """Test that errors are properly categorized."""
        from microsandbox_wrapper.exceptions import (
            ResourceLimitError,
            ConfigurationError,
            ConnectionError as WrapperConnectionError
        )
        
        test_cases = [
            (ResourceLimitError("test", resource_type="memory"), "resource"),
            (ConfigurationError("test"), "configuration"),
            (WrapperConnectionError("test", server_url="http://test"), "network")
        ]
        
        for error, expected_category in test_cases:
            response = error_handler.handle_exception(error, "test-id")
            content = json.loads(response.body.decode())
            
            error_data = content["error"]["data"]
            assert error_data["category"] == expected_category