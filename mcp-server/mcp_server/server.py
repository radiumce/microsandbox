"""
MCP Server Core Implementation

This module contains the core server logic for handling MCP protocol messages
and integrating with the MicrosandboxWrapper.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import asyncio
import signal
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from microsandbox_wrapper.wrapper import MicrosandboxWrapper
from microsandbox_wrapper.models import SandboxFlavor
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError,
    ResourceLimitError,
    ConfigurationError,
    SandboxCreationError,
    CodeExecutionError,
    CommandExecutionError,
    SessionNotFoundError,
    ConnectionError as WrapperConnectionError
)

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """
    Definition of an MCP tool.
    
    Contains all metadata needed to describe a tool to MCP clients,
    including name, description, and input schema.
    """
    name: str
    description: str
    inputSchema: Dict[str, Any]


class Tool(ABC):
    """
    Abstract base class for MCP tools.
    
    Each tool represents a specific operation that can be performed
    through the MCP protocol, such as executing code or managing sessions.
    """
    
    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """
        Get the tool definition for MCP protocol.
        
        Returns:
            ToolDefinition: Tool metadata including schema
        """
        pass
    
    @abstractmethod
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.
        
        Args:
            wrapper: MicrosandboxWrapper instance to use
            params: Tool parameters from MCP request
            
        Returns:
            Dict[str, Any]: Tool execution result in MCP format
        """
        pass


class ExecuteCodeTool(Tool):
    """Tool for executing code in a sandbox."""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="execute_code",
            description="Execute code in a sandbox with automatic session management",
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Code to execute"
                    },
                    "template": {
                        "type": "string",
                        "description": "Sandbox template",
                        "enum": ["python", "node"],
                        "default": "python"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for session reuse"
                    },
                    "flavor": {
                        "type": "string",
                        "enum": ["small", "medium", "large"],
                        "default": "small",
                        "description": "Resource configuration for the sandbox"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional execution timeout in seconds",
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["code"]
            }
        )
    
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code and return MCP-formatted result."""
        try:
            # Extract parameters with defaults
            code = params["code"]
            template = params.get("template", "python")
            session_id = params.get("session_id")
            flavor_str = params.get("flavor", "small")
            timeout = params.get("timeout")
            
            # Convert flavor string to enum
            flavor = SandboxFlavor(flavor_str)
            
            # Execute code through wrapper
            result = await wrapper.execute_code(
                code=code,
                template=template,
                session_id=session_id,
                flavor=flavor,
                timeout=timeout
            )
            
            # Format result for MCP protocol
            # Combine stdout and stderr for complete output
            output_text = result.stdout
            if result.stderr:
                if output_text:
                    output_text += "\n" + result.stderr
                else:
                    output_text = result.stderr
            
            # For code execution, the tool always succeeds even if the code has errors
            # Syntax errors and runtime errors are captured in the output, not as tool failures
            return {
                "content": [{"type": "text", "text": output_text}],
                "isError": False,  # Tool execution succeeded, code errors are in output
                "session_id": result.session_id,
                "execution_time_ms": result.execution_time_ms,
                "session_created": result.session_created,
                "template": result.template,
                "code_success": result.success  # Indicate if the code itself succeeded
            }
            
        except Exception as e:
            logger.error(f"Code execution failed: {e}", exc_info=True)
            raise


class ExecuteCommandTool(Tool):
    """Tool for executing commands in a sandbox."""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="execute_command",
            description="Execute a command in a sandbox with automatic session management",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional command arguments"
                    },
                    "template": {
                        "type": "string",
                        "description": "Sandbox template",
                        "enum": ["python", "node"],
                        "default": "python"
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for session reuse"
                    },
                    "flavor": {
                        "type": "string",
                        "enum": ["small", "medium", "large"],
                        "default": "small",
                        "description": "Resource configuration for the sandbox"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Optional execution timeout in seconds",
                        "minimum": 1,
                        "maximum": 300
                    }
                },
                "required": ["command"]
            }
        )
    
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute command and return MCP-formatted result."""
        try:
            # Extract parameters with defaults
            command = params["command"]
            args = params.get("args")
            template = params.get("template", "python")
            session_id = params.get("session_id")
            flavor_str = params.get("flavor", "small")
            timeout = params.get("timeout")
            
            # Convert flavor string to enum
            flavor = SandboxFlavor(flavor_str)
            
            # Execute command through wrapper
            result = await wrapper.execute_command(
                command=command,
                args=args,
                template=template,
                session_id=session_id,
                flavor=flavor,
                timeout=timeout
            )
            
            # Format result for MCP protocol
            # Combine stdout and stderr for complete output
            output_text = result.stdout
            if result.stderr:
                if output_text:
                    output_text += "\n" + result.stderr
                else:
                    output_text = result.stderr
            
            return {
                "content": [{"type": "text", "text": output_text}],
                "isError": not result.success,
                "session_id": result.session_id,
                "execution_time_ms": result.execution_time_ms,
                "session_created": result.session_created,
                "command": result.command,
                "args": result.args,
                "exit_code": result.exit_code
            }
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}", exc_info=True)
            raise


class GetSessionsTool(Tool):
    """Tool for getting information about active sessions."""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_sessions",
            description="Get information about active sandbox sessions",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional specific session ID to query"
                    }
                },
                "required": []
            }
        )
    
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get sessions and return MCP-formatted result."""
        try:
            session_id = params.get("session_id")
            
            # Get sessions through wrapper
            sessions = await wrapper.get_sessions(session_id)
            
            # Format sessions for MCP protocol
            session_data = []
            for session in sessions:
                session_data.append({
                    "session_id": session.session_id,
                    "template": session.template,
                    "flavor": session.flavor.value,
                    "created_at": session.created_at.isoformat(),
                    "last_accessed": session.last_accessed.isoformat(),
                    "status": session.status.value,
                    "namespace": session.namespace,
                    "sandbox_name": session.sandbox_name
                })
            
            return {
                "content": [{"type": "text", "text": json.dumps(session_data, indent=2)}],
                "isError": False,
                "sessions": session_data
            }
            
        except Exception as e:
            logger.error(f"Get sessions failed: {e}", exc_info=True)
            raise


class StopSessionTool(Tool):
    """Tool for stopping a specific session."""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="stop_session",
            description="Stop a specific sandbox session and clean up its resources",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "ID of the session to stop"
                    }
                },
                "required": ["session_id"]
            }
        )
    
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """Stop session and return MCP-formatted result."""
        try:
            session_id = params["session_id"]
            
            # Stop session through wrapper
            success = await wrapper.stop_session(session_id)
            
            # Format result for MCP protocol
            message = f"Session {session_id} {'stopped successfully' if success else 'not found'}"
            
            return {
                "content": [{"type": "text", "text": message}],
                "isError": False,
                "success": success,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Stop session failed: {e}", exc_info=True)
            raise


class GetVolumePathTool(Tool):
    """Tool for getting configured volume mappings."""
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_volume_path",
            description="Get configured volume mappings between host and container paths",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    
    async def execute(self, wrapper: MicrosandboxWrapper, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get volume mappings and return MCP-formatted result."""
        try:
            # Get volume mappings through wrapper
            mappings = await wrapper.get_volume_mappings()
            
            # Format mappings for MCP protocol
            mapping_data = []
            for mapping in mappings:
                mapping_data.append({
                    "host_path": mapping.host_path,
                    "container_path": mapping.container_path
                })
            
            return {
                "content": [{"type": "text", "text": json.dumps(mapping_data, indent=2)}],
                "isError": False,
                "volume_mappings": mapping_data
            }
            
        except Exception as e:
            logger.error(f"Get volume mappings failed: {e}", exc_info=True)
            raise


class ToolRegistry:
    """
    Registry for managing MCP tools.
    
    Provides centralized tool registration, lookup, and listing functionality.
    """
    
    def __init__(self):
        """Initialize the tool registry with default tools."""
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register all default tools."""
        default_tools = [
            ExecuteCodeTool(),
            ExecuteCommandTool(),
            GetSessionsTool(),
            StopSessionTool(),
            GetVolumePathTool()
        ]
        
        for tool in default_tools:
            definition = tool.get_definition()
            self.tools[definition.name] = tool
            logger.debug(f"Registered tool: {definition.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Optional[Tool]: Tool instance or None if not found
        """
        return self.tools.get(name)
    
    def list_tools(self) -> List[ToolDefinition]:
        """
        Get list of all registered tool definitions.
        
        Returns:
            List[ToolDefinition]: List of tool definitions
        """
        return [tool.get_definition() for tool in self.tools.values()]


class ErrorHandler:
    """
    Unified error handling for MCP server.
    
    Converts wrapper exceptions to appropriate MCP error responses
    following JSON-RPC 2.0 error format.
    """
    
    # JSON-RPC 2.0 standard error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    def handle_exception(self, exc: Exception, request_id: Optional[str]) -> JSONResponse:
        """
        Convert exception to MCP error response.
        
        Args:
            exc: Exception to handle
            request_id: JSON-RPC request ID
            
        Returns:
            JSONResponse: JSON-RPC error response
        """
        logger.error(f"Handling exception: {exc}", exc_info=True)
        
        # Map wrapper exceptions to JSON-RPC error codes with detailed context
        if isinstance(exc, ResourceLimitError):
            return self._create_error_response(
                request_id, 
                self.INVALID_REQUEST, 
                f"Resource limit exceeded: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, ConfigurationError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Configuration error: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, SandboxCreationError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Sandbox creation failed: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, CodeExecutionError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Code execution failed: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, CommandExecutionError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Command execution failed: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, SessionNotFoundError):
            return self._create_error_response(
                request_id, 
                self.INVALID_PARAMS, 
                f"Session not found: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, WrapperConnectionError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Connection error: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, MicrosandboxWrapperError):
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                f"Wrapper error: {str(exc)}",
                self._extract_error_data(exc)
            )
        elif isinstance(exc, ValueError):
            return self._create_error_response(
                request_id, 
                self.INVALID_PARAMS, 
                f"Invalid parameters: {str(exc)}"
            )
        elif isinstance(exc, json.JSONDecodeError):
            return self._create_error_response(
                request_id, 
                self.PARSE_ERROR, 
                "Invalid JSON format"
            )
        else:
            return self._create_error_response(
                request_id, 
                self.INTERNAL_ERROR, 
                "Internal server error"
            )
    
    def _extract_error_data(self, exc: MicrosandboxWrapperError) -> Optional[Dict[str, Any]]:
        """
        Extract additional error data from wrapper exceptions.
        
        Args:
            exc: Wrapper exception
            
        Returns:
            Optional[Dict[str, Any]]: Error data or None
        """
        try:
            if hasattr(exc, 'to_dict'):
                error_dict = exc.to_dict()
                # Return relevant fields for MCP clients
                return {
                    "error_code": error_dict.get("error_code"),
                    "category": error_dict.get("category"),
                    "severity": error_dict.get("severity"),
                    "recovery_suggestions": error_dict.get("recovery_suggestions", []),
                    "context": error_dict.get("context", {})
                }
        except Exception as e:
            logger.warning(f"Failed to extract error data: {e}")
        
        return None
    
    def _create_error_response(
        self, 
        request_id: Optional[str], 
        code: int, 
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Create a JSON-RPC error response.
        
        Args:
            request_id: JSON-RPC request ID
            code: Error code
            message: Error message
            data: Optional additional error data
            
        Returns:
            JSONResponse: JSON-RPC error response
        """
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
        
        # Add additional error data if available
        if data:
            error_response["error"]["data"] = data
        
        return JSONResponse(
            content=error_response,
            status_code=200  # JSON-RPC errors use HTTP 200
        )
    
    def create_method_not_found_error(self, request_id: Optional[str], method: str) -> JSONResponse:
        """
        Create a method not found error response.
        
        Args:
            request_id: JSON-RPC request ID
            method: Method name that was not found
            
        Returns:
            JSONResponse: Method not found error response
        """
        return self._create_error_response(
            request_id,
            self.METHOD_NOT_FOUND,
            f"Method not found: {method}"
        )
    
    def create_invalid_request_error(self, request_id: Optional[str], reason: str) -> JSONResponse:
        """
        Create an invalid request error response.
        
        Args:
            request_id: JSON-RPC request ID
            reason: Reason for invalid request
            
        Returns:
            JSONResponse: Invalid request error response
        """
        return self._create_error_response(
            request_id,
            self.INVALID_REQUEST,
            f"Invalid request: {reason}"
        )
    
    def create_parse_error(self) -> JSONResponse:
        """
        Create a parse error response.
        
        Returns:
            JSONResponse: Parse error response
        """
        return self._create_error_response(
            None,
            self.PARSE_ERROR,
            "Parse error: Invalid JSON"
        )


class RequestHandler:
    """
    Handles HTTP requests and JSON-RPC message processing.
    
    Coordinates between HTTP layer, JSON-RPC protocol, and tool execution.
    """
    
    def __init__(
        self,
        wrapper: MicrosandboxWrapper,
        tool_registry: ToolRegistry,
        error_handler: ErrorHandler
    ):
        """
        Initialize request handler.
        
        Args:
            wrapper: MicrosandboxWrapper instance
            tool_registry: Tool registry for tool lookup
            error_handler: Error handler for exception conversion
        """
        self.wrapper = wrapper
        self.tool_registry = tool_registry
        self.error_handler = error_handler
    
    async def handle_request(self, request: Request, enable_cors: bool = False) -> Response:
        """
        Handle HTTP request and route to appropriate handler.
        
        Args:
            request: FastAPI request object
            enable_cors: Whether to add CORS headers
            
        Returns:
            Response: HTTP response
        """
        try:
            # Route to appropriate handler based on method
            if request.method == "POST":
                response = await self._handle_jsonrpc_request(request)
            elif request.method == "GET":
                response = await self._handle_status_request(request)
            elif request.method == "OPTIONS":
                response = await self._handle_options_request(request)
            else:
                response = Response(status_code=405, content="Method Not Allowed")
            
            # Add CORS headers if enabled
            if enable_cors:
                response = self._add_cors_headers(response)
            
            return response
                
        except Exception as e:
            logger.error(f"Request handling failed: {e}", exc_info=True)
            error_response = self.error_handler.handle_exception(e, None)
            
            # Add CORS headers to error responses too
            if enable_cors:
                error_response = self._add_cors_headers(error_response)
            
            return error_response
    
    async def _handle_jsonrpc_request(self, request: Request) -> Response:
        """
        Handle JSON-RPC request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Response: JSON-RPC response
        """
        try:
            # Validate content type
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                return self.error_handler.create_invalid_request_error(
                    None, "Content-Type must be application/json"
                )
            
            # Parse JSON body
            body = await request.json()
            
            # Validate JSON-RPC format
            validation_error = self._validate_jsonrpc_request(body)
            if validation_error:
                return validation_error
            
            request_id = body.get("id")
            method = body["method"]
            
            # Route to appropriate method handler
            if method == "tools/list":
                return await self._handle_tools_list(body)
            elif method == "tools/call":
                return await self._handle_tools_call(body)
            else:
                return self.error_handler.create_method_not_found_error(request_id, method)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self.error_handler.create_parse_error()
        except Exception as e:
            logger.error(f"JSON-RPC request handling failed: {e}", exc_info=True)
            return self.error_handler.handle_exception(e, None)
    
    async def _handle_tools_list(self, body: Dict[str, Any]) -> JSONResponse:
        """
        Handle tools/list request.
        
        Args:
            body: JSON-RPC request body
            
        Returns:
            JSONResponse: Tools list response
        """
        try:
            request_id = body.get("id")
            
            # Get all tool definitions
            tools = self.tool_registry.list_tools()
            
            # Format tools for MCP protocol
            tools_data = []
            for tool in tools:
                tools_data.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                })
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": tools_data
                }
            }
            
            return JSONResponse(content=response)
            
        except Exception as e:
            return self.error_handler.handle_exception(e, body.get("id"))
    
    async def _handle_tools_call(self, body: Dict[str, Any]) -> JSONResponse:
        """
        Handle tools/call request.
        
        Args:
            body: JSON-RPC request body
            
        Returns:
            JSONResponse: Tool execution response
        """
        try:
            request_id = body.get("id")
            params = body.get("params", {})
            
            # Validate params structure
            if not isinstance(params, dict):
                return self.error_handler._create_error_response(
                    request_id, self.error_handler.INVALID_PARAMS, 
                    "Params must be an object"
                )
            
            # Extract tool name and arguments
            tool_name = params.get("name")
            if not tool_name:
                return self.error_handler._create_error_response(
                    request_id, self.error_handler.INVALID_PARAMS, 
                    "Missing required parameter: name"
                )
            
            if not isinstance(tool_name, str):
                return self.error_handler._create_error_response(
                    request_id, self.error_handler.INVALID_PARAMS, 
                    "Tool name must be a string"
                )
            
            tool_args = params.get("arguments", {})
            if not isinstance(tool_args, dict):
                return self.error_handler._create_error_response(
                    request_id, self.error_handler.INVALID_PARAMS, 
                    "Tool arguments must be an object"
                )
            
            # Get tool from registry
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                return self.error_handler.create_method_not_found_error(
                    request_id, f"tool:{tool_name}"
                )
            
            # Validate tool arguments against schema
            validation_error = self._validate_tool_arguments(tool, tool_args, request_id)
            if validation_error:
                return validation_error
            
            # Execute tool
            result = await tool.execute(self.wrapper, tool_args)
            
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
            return JSONResponse(content=response)
            
        except Exception as e:
            return self.error_handler.handle_exception(e, body.get("id"))
    
    def _validate_tool_arguments(
        self, 
        tool: Tool, 
        args: Dict[str, Any], 
        request_id: Optional[str]
    ) -> Optional[JSONResponse]:
        """
        Validate tool arguments against the tool's input schema.
        
        Args:
            tool: Tool instance
            args: Tool arguments to validate
            request_id: JSON-RPC request ID
            
        Returns:
            Optional[JSONResponse]: Error response if validation fails, None if valid
        """
        try:
            definition = tool.get_definition()
            schema = definition.inputSchema
            
            # Check required fields
            required_fields = schema.get("required", [])
            for field in required_fields:
                if field not in args:
                    return self.error_handler._create_error_response(
                        request_id, 
                        self.error_handler.INVALID_PARAMS,
                        f"Missing required parameter: {field}"
                    )
            
            # Basic type validation for known fields
            properties = schema.get("properties", {})
            for field_name, field_value in args.items():
                if field_name in properties:
                    field_schema = properties[field_name]
                    field_type = field_schema.get("type")
                    
                    # Validate basic types
                    if field_type == "string" and not isinstance(field_value, str):
                        return self.error_handler._create_error_response(
                            request_id,
                            self.error_handler.INVALID_PARAMS,
                            f"Parameter '{field_name}' must be a string"
                        )
                    elif field_type == "integer" and not isinstance(field_value, int):
                        return self.error_handler._create_error_response(
                            request_id,
                            self.error_handler.INVALID_PARAMS,
                            f"Parameter '{field_name}' must be an integer"
                        )
                    elif field_type == "array" and not isinstance(field_value, list):
                        return self.error_handler._create_error_response(
                            request_id,
                            self.error_handler.INVALID_PARAMS,
                            f"Parameter '{field_name}' must be an array"
                        )
                    
                    # Validate enum values
                    enum_values = field_schema.get("enum")
                    if enum_values and field_value not in enum_values:
                        return self.error_handler._create_error_response(
                            request_id,
                            self.error_handler.INVALID_PARAMS,
                            f"Parameter '{field_name}' must be one of: {enum_values}"
                        )
                    
                    # Validate numeric ranges
                    if field_type == "integer":
                        minimum = field_schema.get("minimum")
                        maximum = field_schema.get("maximum")
                        if minimum is not None and field_value < minimum:
                            return self.error_handler._create_error_response(
                                request_id,
                                self.error_handler.INVALID_PARAMS,
                                f"Parameter '{field_name}' must be >= {minimum}"
                            )
                        if maximum is not None and field_value > maximum:
                            return self.error_handler._create_error_response(
                                request_id,
                                self.error_handler.INVALID_PARAMS,
                                f"Parameter '{field_name}' must be <= {maximum}"
                            )
            
            return None
            
        except Exception as e:
            logger.error(f"Tool argument validation failed: {e}", exc_info=True)
            return self.error_handler._create_error_response(
                request_id,
                self.error_handler.INTERNAL_ERROR,
                "Failed to validate tool arguments"
            )
    
    def _validate_jsonrpc_request(self, body: Dict[str, Any]) -> Optional[JSONResponse]:
        """
        Validate JSON-RPC 2.0 message format.
        
        Args:
            body: Parsed JSON body
            
        Returns:
            Optional[JSONResponse]: Error response if invalid, None if valid
        """
        if not isinstance(body, dict):
            return self.error_handler.create_invalid_request_error(
                None, "Request must be a JSON object"
            )
        
        if body.get("jsonrpc") != "2.0":
            return self.error_handler.create_invalid_request_error(
                body.get("id"), "Missing or invalid jsonrpc version (must be '2.0')"
            )
        
        if "method" not in body:
            return self.error_handler.create_invalid_request_error(
                body.get("id"), "Missing required 'method' field"
            )
        
        if not isinstance(body["method"], str):
            return self.error_handler.create_invalid_request_error(
                body.get("id"), "Method must be a string"
            )
        
        # Validate params if present
        if "params" in body and not isinstance(body["params"], (dict, list)):
            return self.error_handler.create_invalid_request_error(
                body.get("id"), "Params must be an object or array"
            )
        
        return None
    
    def _add_cors_headers(self, response: Response) -> Response:
        """
        Add CORS headers to response.
        
        Args:
            response: Response to add headers to
            
        Returns:
            Response: Response with CORS headers
        """
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours
        return response
    
    async def _handle_status_request(self, request: Request) -> JSONResponse:
        """
        Handle GET request for server status.
        
        Args:
            request: FastAPI request object
            
        Returns:
            JSONResponse: Server status response
        """
        try:
            status = {
                "status": "healthy",
                "version": "1.0.0",
                "wrapper_started": self.wrapper.is_started(),
                "tools_count": len(self.tool_registry.list_tools()),
                "available_tools": [tool.name for tool in self.tool_registry.list_tools()]
            }
            
            return JSONResponse(content=status)
            
        except Exception as e:
            logger.error(f"Status request failed: {e}", exc_info=True)
            return JSONResponse(
                content={"status": "error", "error": str(e)},
                status_code=500
            )
    
    async def _handle_options_request(self, request: Request) -> Response:
        """
        Handle OPTIONS request for CORS preflight.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Response: CORS preflight response
        """
        response = Response(status_code=200)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response


class MCPServer:
    """
    Main MCP Server class that coordinates all components.
    
    Manages the HTTP server lifecycle, wrapper integration, and
    provides unified configuration and startup/shutdown handling.
    """
    
    def __init__(
        self,
        wrapper: MicrosandboxWrapper,
        host: str = "localhost",
        port: int = 8000,
        enable_cors: bool = False
    ):
        """
        Initialize MCP Server.
        
        Args:
            wrapper: MicrosandboxWrapper instance
            host: Host to bind to
            port: Port to listen on
            enable_cors: Whether to enable CORS support
        """
        self.wrapper = wrapper
        self.host = host
        self.port = port
        self.enable_cors = enable_cors
        
        # Initialize components
        self.tool_registry = ToolRegistry()
        self.error_handler = ErrorHandler()
        self.request_handler = RequestHandler(
            wrapper=self.wrapper,
            tool_registry=self.tool_registry,
            error_handler=self.error_handler
        )
        
        # Server state
        self._server = None
        self._shutdown_event = asyncio.Event()
        self._started = False
        
        logger.info(
            f"Initialized MCPServer: host={host}, port={port}, cors={enable_cors}"
        )
    
    async def start(self) -> None:
        """
        Start the MCP server.
        
        This method starts the wrapper first, then initializes and starts
        the HTTP server. It ensures proper startup order and error handling.
        
        Raises:
            MicrosandboxWrapperError: If startup fails
        """
        if self._started:
            logger.warning("MCP Server is already started")
            return
        
        try:
            logger.info("Starting MCP Server")
            
            # Step 1: Start the wrapper first
            logger.info("Starting MicrosandboxWrapper")
            await self.wrapper.start()
            logger.info("MicrosandboxWrapper started successfully")
            
            # Step 2: Create FastAPI app with lifecycle management
            app = self._create_fastapi_app()
            
            # Step 3: Configure and start HTTP server
            config = uvicorn.Config(
                app=app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            
            self._server = uvicorn.Server(config)
            
            # Step 4: Start server in background task
            server_task = asyncio.create_task(self._server.serve())
            
            # Wait a moment to ensure server starts properly
            await asyncio.sleep(0.1)
            
            self._started = True
            logger.info(f"MCP Server started successfully on {self.host}:{self.port}")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
            # Cancel server task
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            
        except Exception as e:
            logger.error(f"Failed to start MCP Server: {e}", exc_info=True)
            # Cleanup on error
            await self._cleanup_on_error()
            raise MicrosandboxWrapperError(f"Failed to start MCP Server: {str(e)}")
    
    async def stop(self, timeout_seconds: float = 30.0) -> None:
        """
        Stop the MCP server gracefully.
        
        This method stops accepting new requests, waits for existing requests
        to complete, then shuts down the wrapper and HTTP server.
        
        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown
        """
        if not self._started:
            logger.warning("MCP Server is not started")
            return
        
        try:
            logger.info("Stopping MCP Server")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Step 1: Stop HTTP server
            if self._server:
                logger.info("Stopping HTTP server")
                self._server.should_exit = True
                
                # Wait for server to stop with timeout
                try:
                    await asyncio.wait_for(
                        self._wait_for_server_shutdown(),
                        timeout=timeout_seconds / 2
                    )
                    logger.info("HTTP server stopped successfully")
                except asyncio.TimeoutError:
                    logger.warning("HTTP server shutdown timed out")
            
            # Step 2: Stop wrapper
            logger.info("Stopping MicrosandboxWrapper")
            await self.wrapper.stop(timeout_seconds / 2)
            logger.info("MicrosandboxWrapper stopped successfully")
            
            self._started = False
            logger.info("MCP Server stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during MCP Server shutdown: {e}", exc_info=True)
            self._started = False
            raise MicrosandboxWrapperError(f"Error during shutdown: {str(e)}")
    
    def _create_fastapi_app(self) -> FastAPI:
        """
        Create and configure FastAPI application.
        
        Returns:
            FastAPI: Configured FastAPI app
        """
        # Create lifespan context manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info("FastAPI app starting up")
            yield
            # Shutdown
            logger.info("FastAPI app shutting down")
        
        # Create FastAPI app
        app = FastAPI(
            title="MCP Server",
            description="HTTP streamable transport MCP server for microsandbox",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # Add CORS middleware if enabled
        if self.enable_cors:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
            )
            logger.info("CORS middleware enabled")
        
        # Add main route handler
        @app.api_route("/", methods=["GET", "POST", "OPTIONS"])
        @app.api_route("/mcp", methods=["GET", "POST", "OPTIONS"])
        async def handle_mcp_request(request: Request) -> Response:
            """Handle MCP requests."""
            return await self.request_handler.handle_request(request, self.enable_cors)
        
        # Add health check endpoint
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "wrapper_started": self.wrapper.is_started(),
                "server_started": self._started
            }
        
        return app
    
    async def _wait_for_server_shutdown(self) -> None:
        """Wait for HTTP server to shut down completely."""
        while self._server and not self._server.should_exit:
            await asyncio.sleep(0.1)
    
    async def _cleanup_on_error(self) -> None:
        """
        Clean up resources when an error occurs during startup.
        
        This method attempts to stop any partially started services
        to prevent resource leaks.
        """
        try:
            if self._server:
                self._server.should_exit = True
        except Exception as e:
            logger.error(f"Error stopping server during cleanup: {e}")
        
        try:
            if self.wrapper.is_started():
                await self.wrapper.stop()
        except Exception as e:
            logger.error(f"Error stopping wrapper during cleanup: {e}")
        
        self._started = False
    
    def is_started(self) -> bool:
        """
        Check if the server is started and ready.
        
        Returns:
            bool: True if server is started and ready for requests
        """
        return self._started and self.wrapper.is_started()
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get server information and status.
        
        Returns:
            Dict[str, Any]: Server information
        """
        return {
            "host": self.host,
            "port": self.port,
            "cors_enabled": self.enable_cors,
            "server_started": self._started,
            "wrapper_started": self.wrapper.is_started(),
            "available_tools": [tool.name for tool in self.tool_registry.list_tools()]
        }
    
    async def graceful_shutdown(self, timeout_seconds: float = 30.0) -> Dict[str, Any]:
        """
        Perform graceful shutdown with detailed status reporting.
        
        Args:
            timeout_seconds: Maximum time to wait for shutdown
            
        Returns:
            Dict[str, Any]: Shutdown status information
        """
        shutdown_info = {
            "timestamp": asyncio.get_event_loop().time(),
            "timeout_seconds": timeout_seconds,
            "steps_completed": [],
            "errors": []
        }
        
        try:
            # Step 1: Signal shutdown
            self._shutdown_event.set()
            shutdown_info["steps_completed"].append("shutdown_signaled")
            
            # Step 2: Stop accepting new requests
            if self._server:
                self._server.should_exit = True
                shutdown_info["steps_completed"].append("server_stop_signaled")
            
            # Step 3: Wait for existing requests to complete
            try:
                await asyncio.wait_for(
                    self._wait_for_server_shutdown(),
                    timeout=timeout_seconds * 0.6
                )
                shutdown_info["steps_completed"].append("server_stopped")
            except asyncio.TimeoutError:
                error_msg = "HTTP server shutdown timed out"
                shutdown_info["errors"].append(error_msg)
                logger.warning(error_msg)
            
            # Step 4: Stop wrapper
            try:
                await self.wrapper.stop(timeout_seconds * 0.4)
                shutdown_info["steps_completed"].append("wrapper_stopped")
            except Exception as e:
                error_msg = f"Wrapper shutdown failed: {str(e)}"
                shutdown_info["errors"].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Determine final status
            if shutdown_info["errors"]:
                shutdown_info["status"] = "partial_success" if shutdown_info["steps_completed"] else "failed"
            else:
                shutdown_info["status"] = "success"
            
            self._started = False
            
        except Exception as e:
            error_msg = f"Graceful shutdown failed: {str(e)}"
            shutdown_info["errors"].append(error_msg)
            shutdown_info["status"] = "failed"
            logger.error(error_msg, exc_info=True)
            self._started = False
        
        return shutdown_info
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


def setup_signal_handlers(server: MCPServer) -> None:
    """
    Set up signal handlers for graceful shutdown.
    
    Args:
        server: MCPServer instance to shutdown on signal
    """
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        asyncio.create_task(server.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Signal handlers registered for graceful shutdown")