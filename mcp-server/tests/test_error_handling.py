"""
Unit tests for error handling and exception conversion.

Tests the error handling system, exception mapping to JSON-RPC errors,
and error response formatting.
"""

import json
import pytest
from unittest.mock import MagicMock

from mcp_server.server import ErrorHandler
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError,
    ResourceLimitError,
    ConfigurationError,
    SandboxCreationError,
    CodeExecutionError,
    CommandExecutionError,
    SessionNotFoundError,
    ConnectionError as WrapperConnectionError,
    ErrorSeverity,
    ErrorCategory
)


class TestErrorHandlerExceptionMapping:
    """Test ErrorHandler exception mapping functionality."""
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    def test_resource_limit_error_mapping(self, error_handler):
        """Test ResourceLimitError mapping to JSON-RPC error."""
        error = ResourceLimitError(
            message="Maximum sessions exceeded",
            resource_type="sessions",
            current_usage=10,
            limit=10
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["jsonrpc"] == "2.0"
        assert content["id"] == "test-id"
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Resource limit exceeded" in content["error"]["message"]
        
        # Check error data
        error_data = content["error"]["data"]
        assert error_data["category"] == "resource"
        assert error_data["severity"] == "high"
        assert "recovery_suggestions" in error_data
        assert len(error_data["recovery_suggestions"]) > 0
    
    def test_configuration_error_mapping(self, error_handler):
        """Test ConfigurationError mapping to JSON-RPC error."""
        error = ConfigurationError(
            message="Invalid server URL configuration",
            config_key="MICROSANDBOX_SERVER_URL",
            config_value="invalid-url"
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Configuration error" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "configuration"
        assert "MICROSANDBOX_SERVER_URL" in str(error_data["context"])
    
    def test_sandbox_creation_error_mapping(self, error_handler):
        """Test SandboxCreationError mapping to JSON-RPC error."""
        error = SandboxCreationError(
            message="Failed to create Python sandbox",
            template="python",
            flavor="small"
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Sandbox creation failed" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "resource"
        assert "python" in str(error_data["context"])
        assert "small" in str(error_data["context"])
    
    def test_code_execution_error_mapping(self, error_handler):
        """Test CodeExecutionError mapping to JSON-RPC error."""
        error = CodeExecutionError(
            message="Syntax error in Python code",
            error_type="compilation",
            session_id="test-session",
            code_snippet="print("
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Code execution failed" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "execution"
        assert "test-session" in str(error_data["context"])
        assert "compilation" in str(error_data["context"])
    
    def test_command_execution_error_mapping(self, error_handler):
        """Test CommandExecutionError mapping to JSON-RPC error."""
        error = CommandExecutionError(
            message="Command not found",
            command="nonexistent-command",
            exit_code=127,
            session_id="test-session"
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Command execution failed" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "execution"
        assert "nonexistent-command" in str(error_data["context"])
        assert "127" in str(error_data["context"])
    
    def test_session_not_found_error_mapping(self, error_handler):
        """Test SessionNotFoundError mapping to JSON-RPC error."""
        error = SessionNotFoundError(
            message="Session not found",
            session_id="missing-session"
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Session not found" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "session"
        assert "missing-session" in str(error_data["context"])
    
    def test_connection_error_mapping(self, error_handler):
        """Test ConnectionError mapping to JSON-RPC error."""
        error = WrapperConnectionError(
            message="Failed to connect to microsandbox server",
            server_url="http://localhost:5555",
            retry_count=3
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Connection error" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "network"
        assert "localhost:5555" in str(error_data["context"])
    
    def test_generic_wrapper_error_mapping(self, error_handler):
        """Test generic MicrosandboxWrapperError mapping."""
        error = MicrosandboxWrapperError(
            message="Generic wrapper error",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM
        )
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert "Wrapper error" in content["error"]["message"]
        
        error_data = content["error"]["data"]
        assert error_data["category"] == "system"
        assert error_data["severity"] == "medium"
    
    def test_value_error_mapping(self, error_handler):
        """Test ValueError mapping to JSON-RPC error."""
        error = ValueError("Invalid parameter format")
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS
        assert "Invalid parameters" in content["error"]["message"]
        assert "data" not in content["error"]  # No additional data for ValueError
    
    def test_json_decode_error_mapping(self, error_handler):
        """Test JSONDecodeError mapping to JSON-RPC error."""
        error = json.JSONDecodeError("Invalid JSON", "", 0)
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.PARSE_ERROR
        assert "Invalid JSON format" in content["error"]["message"]
    
    def test_generic_exception_mapping(self, error_handler):
        """Test generic Exception mapping to JSON-RPC error."""
        error = RuntimeError("Unexpected runtime error")
        
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INTERNAL_ERROR
        assert content["error"]["message"] == "Internal server error"
        assert "data" not in content["error"]
    
    def test_error_without_request_id(self, error_handler):
        """Test error handling without request ID."""
        error = ValueError("Test error")
        
        response = error_handler.handle_exception(error, None)
        content = json.loads(response.body.decode())
        
        assert content["id"] is None
        assert content["error"]["code"] == ErrorHandler.INVALID_PARAMS


class TestErrorHandlerUtilityMethods:
    """Test ErrorHandler utility methods."""
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    def test_extract_error_data_with_wrapper_error(self, error_handler):
        """Test extracting error data from wrapper error."""
        error = ResourceLimitError(
            message="Test error",
            resource_type="memory",
            current_usage=1024,
            limit=512
        )
        
        data = error_handler._extract_error_data(error)
        
        assert data is not None
        assert data["category"] == "resource"
        assert data["severity"] == "high"
        assert len(data["recovery_suggestions"]) > 0
        assert "memory" in str(data["context"])
    
    def test_extract_error_data_without_to_dict(self, error_handler):
        """Test extracting error data from error without to_dict method."""
        error = MagicMock()
        del error.to_dict  # Remove to_dict method
        
        data = error_handler._extract_error_data(error)
        
        assert data is None
    
    def test_extract_error_data_with_exception(self, error_handler):
        """Test extracting error data when to_dict raises exception."""
        error = MagicMock()
        error.to_dict.side_effect = Exception("to_dict failed")
        
        data = error_handler._extract_error_data(error)
        
        assert data is None
    
    def test_create_error_response_with_data(self, error_handler):
        """Test creating error response with additional data."""
        data = {
            "error_code": "TEST_ERROR",
            "category": "test",
            "context": {"key": "value"}
        }
        
        response = error_handler._create_error_response(
            "test-id", ErrorHandler.INTERNAL_ERROR, "Test message", data
        )
        content = json.loads(response.body.decode())
        
        assert content["error"]["data"] == data
        assert response.status_code == 200  # JSON-RPC uses HTTP 200
    
    def test_create_error_response_without_data(self, error_handler):
        """Test creating error response without additional data."""
        response = error_handler._create_error_response(
            "test-id", ErrorHandler.INTERNAL_ERROR, "Test message"
        )
        content = json.loads(response.body.decode())
        
        assert "data" not in content["error"]
    
    def test_create_method_not_found_error(self, error_handler):
        """Test creating method not found error."""
        response = error_handler.create_method_not_found_error(
            "test-id", "unknown/method"
        )
        content = json.loads(response.body.decode())
        
        assert content["jsonrpc"] == "2.0"
        assert content["id"] == "test-id"
        assert content["error"]["code"] == ErrorHandler.METHOD_NOT_FOUND
        assert "unknown/method" in content["error"]["message"]
    
    def test_create_invalid_request_error(self, error_handler):
        """Test creating invalid request error."""
        response = error_handler.create_invalid_request_error(
            "test-id", "Missing required field"
        )
        content = json.loads(response.body.decode())
        
        assert content["error"]["code"] == ErrorHandler.INVALID_REQUEST
        assert "Missing required field" in content["error"]["message"]
    
    def test_create_parse_error(self, error_handler):
        """Test creating parse error."""
        response = error_handler.create_parse_error()
        content = json.loads(response.body.decode())
        
        assert content["jsonrpc"] == "2.0"
        assert content["id"] is None
        assert content["error"]["code"] == ErrorHandler.PARSE_ERROR
        assert "Parse error" in content["error"]["message"]


class TestErrorHandlerConstants:
    """Test ErrorHandler constants and error codes."""
    
    def test_error_code_constants(self):
        """Test that error code constants are correct."""
        assert ErrorHandler.PARSE_ERROR == -32700
        assert ErrorHandler.INVALID_REQUEST == -32600
        assert ErrorHandler.METHOD_NOT_FOUND == -32601
        assert ErrorHandler.INVALID_PARAMS == -32602
        assert ErrorHandler.INTERNAL_ERROR == -32603
    
    def test_error_codes_are_json_rpc_compliant(self):
        """Test that error codes follow JSON-RPC 2.0 specification."""
        # JSON-RPC 2.0 reserved error codes
        reserved_codes = {
            -32700: "Parse error",
            -32600: "Invalid Request", 
            -32601: "Method not found",
            -32602: "Invalid params",
            -32603: "Internal error"
        }
        
        assert ErrorHandler.PARSE_ERROR in reserved_codes
        assert ErrorHandler.INVALID_REQUEST in reserved_codes
        assert ErrorHandler.METHOD_NOT_FOUND in reserved_codes
        assert ErrorHandler.INVALID_PARAMS in reserved_codes
        assert ErrorHandler.INTERNAL_ERROR in reserved_codes


class TestErrorResponseFormat:
    """Test error response format compliance."""
    
    @pytest.fixture
    def error_handler(self):
        """Create ErrorHandler instance."""
        return ErrorHandler()
    
    def test_error_response_structure(self, error_handler):
        """Test that error responses have correct JSON-RPC structure."""
        error = ValueError("Test error")
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        # Required JSON-RPC 2.0 fields
        assert "jsonrpc" in content
        assert content["jsonrpc"] == "2.0"
        assert "id" in content
        assert "error" in content
        
        # Error object structure
        error_obj = content["error"]
        assert "code" in error_obj
        assert "message" in error_obj
        assert isinstance(error_obj["code"], int)
        assert isinstance(error_obj["message"], str)
    
    def test_error_response_with_data_structure(self, error_handler):
        """Test error response structure with additional data."""
        error = ResourceLimitError(
            "Test error",
            resource_type="sessions",
            current_usage=5,
            limit=5
        )
        response = error_handler.handle_exception(error, "test-id")
        content = json.loads(response.body.decode())
        
        error_obj = content["error"]
        assert "data" in error_obj
        assert isinstance(error_obj["data"], dict)
        
        # Check data structure
        data = error_obj["data"]
        assert "error_code" in data
        assert "category" in data
        assert "severity" in data
        assert "recovery_suggestions" in data
        assert "context" in data
    
    def test_http_status_code(self, error_handler):
        """Test that error responses use HTTP 200 (JSON-RPC requirement)."""
        error = ValueError("Test error")
        response = error_handler.handle_exception(error, "test-id")
        
        # JSON-RPC errors should use HTTP 200
        assert response.status_code == 200
    
    def test_content_type(self, error_handler):
        """Test that error responses have correct content type."""
        error = ValueError("Test error")
        response = error_handler.handle_exception(error, "test-id")
        
        # Should be JSON response
        assert response.media_type == "application/json"