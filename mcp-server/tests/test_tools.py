"""
Unit tests for MCP Server tools.

Tests the tool classes with mocked wrapper to verify tool functionality,
parameter validation, and result formatting.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from mcp_server.server import (
    ExecuteCodeTool,
    ExecuteCommandTool,
    GetSessionsTool,
    StopSessionTool,
    GetVolumePathTool,
    ToolRegistry
)
from microsandbox_wrapper.models import (
    ExecutionResult,
    CommandResult,
    SessionInfo,
    SessionStatus,
    SandboxFlavor,
    VolumeMapping
)
from microsandbox_wrapper.exceptions import (
    CodeExecutionError,
    CommandExecutionError,
    SessionNotFoundError
)
from datetime import datetime


class TestExecuteCodeTool:
    """Test ExecuteCodeTool functionality."""
    
    @pytest.fixture
    def tool(self):
        """Create ExecuteCodeTool instance."""
        return ExecuteCodeTool()
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    def test_get_definition(self, tool):
        """Test tool definition is correct."""
        definition = tool.get_definition()
        
        assert definition.name == "execute_code"
        assert "Execute code in a sandbox" in definition.description
        assert definition.inputSchema["type"] == "object"
        assert "code" in definition.inputSchema["required"]
        assert "code" in definition.inputSchema["properties"]
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_wrapper):
        """Test successful code execution."""
        # Setup mock result
        mock_result = ExecutionResult(
            session_id="test-session",
            stdout="Hello, World!",
            stderr="",
            success=True,
            execution_time_ms=100,
            session_created=True,
            template="python"
        )
        mock_wrapper.execute_code.return_value = mock_result
        
        # Execute tool
        params = {"code": "print('Hello, World!')"}
        result = await tool.execute(mock_wrapper, params)
        
        # Verify wrapper was called correctly
        mock_wrapper.execute_code.assert_called_once_with(
            code="print('Hello, World!')",
            template="python",
            session_id=None,
            flavor=SandboxFlavor.SMALL,
            timeout=None
        )
        
        # Verify result format
        assert result["content"][0]["text"] == "Hello, World!"
        assert result["isError"] is False
        assert result["session_id"] == "test-session"
        assert result["execution_time_ms"] == 100
        assert result["session_created"] is True
        assert result["template"] == "python"
    
    @pytest.mark.asyncio
    async def test_execute_with_all_params(self, tool, mock_wrapper):
        """Test code execution with all parameters."""
        mock_result = ExecutionResult(
            session_id="existing-session",
            stdout="Result",
            stderr="",
            success=True,
            execution_time_ms=200,
            session_created=False,
            template="node"
        )
        mock_wrapper.execute_code.return_value = mock_result
        
        params = {
            "code": "console.log('test')",
            "template": "node",
            "session_id": "existing-session",
            "flavor": "medium",
            "timeout": 60
        }
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.execute_code.assert_called_once_with(
            code="console.log('test')",
            template="node",
            session_id="existing-session",
            flavor=SandboxFlavor.MEDIUM,
            timeout=60
        )
        
        assert result["session_created"] is False
    
    @pytest.mark.asyncio
    async def test_execute_failure(self, tool, mock_wrapper):
        """Test code execution failure."""
        mock_result = ExecutionResult(
            session_id="test-session",
            stdout="",
            stderr="SyntaxError: invalid syntax",
            success=False,
            execution_time_ms=50,
            session_created=True,
            template="python"
        )
        mock_wrapper.execute_code.return_value = mock_result
        
        params = {"code": "print("}
        result = await tool.execute(mock_wrapper, params)
        
        assert result["isError"] is True
        assert result["success"] is False
    
    @pytest.mark.asyncio
    async def test_execute_exception(self, tool, mock_wrapper):
        """Test tool execution with wrapper exception."""
        mock_wrapper.execute_code.side_effect = CodeExecutionError(
            "Execution failed",
            error_type="runtime",
            session_id="test-session"
        )
        
        params = {"code": "raise Exception('test')"}
        
        with pytest.raises(CodeExecutionError):
            await tool.execute(mock_wrapper, params)


class TestExecuteCommandTool:
    """Test ExecuteCommandTool functionality."""
    
    @pytest.fixture
    def tool(self):
        """Create ExecuteCommandTool instance."""
        return ExecuteCommandTool()
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    def test_get_definition(self, tool):
        """Test tool definition is correct."""
        definition = tool.get_definition()
        
        assert definition.name == "execute_command"
        assert "Execute a command in a sandbox" in definition.description
        assert "command" in definition.inputSchema["required"]
        assert "command" in definition.inputSchema["properties"]
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_wrapper):
        """Test successful command execution."""
        mock_result = CommandResult(
            session_id="test-session",
            stdout="file1.txt\nfile2.txt",
            stderr="",
            exit_code=0,
            success=True,
            execution_time_ms=150,
            session_created=True,
            command="ls",
            args=[]
        )
        mock_wrapper.execute_command.return_value = mock_result
        
        params = {"command": "ls"}
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.execute_command.assert_called_once_with(
            command="ls",
            args=None,
            template="python",
            session_id=None,
            flavor=SandboxFlavor.SMALL,
            timeout=None
        )
        
        assert result["content"][0]["text"] == "file1.txt\nfile2.txt"
        assert result["isError"] is False
        assert result["exit_code"] == 0
        assert result["command"] == "ls"
    
    @pytest.mark.asyncio
    async def test_execute_with_args(self, tool, mock_wrapper):
        """Test command execution with arguments."""
        mock_result = CommandResult(
            session_id="test-session",
            stdout="total 0",
            stderr="",
            exit_code=0,
            success=True,
            execution_time_ms=100,
            session_created=False,
            command="ls",
            args=["-la"]
        )
        mock_wrapper.execute_command.return_value = mock_result
        
        params = {
            "command": "ls",
            "args": ["-la"],
            "session_id": "existing-session"
        }
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.execute_command.assert_called_once_with(
            command="ls",
            args=["-la"],
            template="python",
            session_id="existing-session",
            flavor=SandboxFlavor.SMALL,
            timeout=None
        )
        
        assert result["args"] == ["-la"]
    
    @pytest.mark.asyncio
    async def test_execute_command_failure(self, tool, mock_wrapper):
        """Test command execution failure."""
        mock_result = CommandResult(
            session_id="test-session",
            stdout="",
            stderr="command not found",
            exit_code=127,
            success=False,
            execution_time_ms=25,
            session_created=True,
            command="nonexistent",
            args=[]
        )
        mock_wrapper.execute_command.return_value = mock_result
        
        params = {"command": "nonexistent"}
        result = await tool.execute(mock_wrapper, params)
        
        assert result["isError"] is True
        assert result["exit_code"] == 127


class TestGetSessionsTool:
    """Test GetSessionsTool functionality."""
    
    @pytest.fixture
    def tool(self):
        """Create GetSessionsTool instance."""
        return GetSessionsTool()
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    def test_get_definition(self, tool):
        """Test tool definition is correct."""
        definition = tool.get_definition()
        
        assert definition.name == "get_sessions"
        assert "Get information about active sandbox sessions" in definition.description
        assert definition.inputSchema["required"] == []
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_wrapper):
        """Test successful session retrieval."""
        mock_sessions = [
            SessionInfo(
                session_id="session-1",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                last_accessed=datetime(2024, 1, 1, 12, 5, 0),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="sandbox-1"
            ),
            SessionInfo(
                session_id="session-2",
                template="node",
                flavor=SandboxFlavor.MEDIUM,
                created_at=datetime(2024, 1, 1, 12, 1, 0),
                last_accessed=datetime(2024, 1, 1, 12, 6, 0),
                status=SessionStatus.RUNNING,
                namespace="default",
                sandbox_name="sandbox-2"
            )
        ]
        mock_wrapper.get_sessions.return_value = mock_sessions
        
        params = {}
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.get_sessions.assert_called_once_with(None)
        
        # Verify result structure
        assert "sessions" in result
        assert len(result["sessions"]) == 2
        
        session_1 = result["sessions"][0]
        assert session_1["session_id"] == "session-1"
        assert session_1["template"] == "python"
        assert session_1["flavor"] == "small"
        assert session_1["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_execute_with_session_id(self, tool, mock_wrapper):
        """Test session retrieval with specific session ID."""
        mock_sessions = [
            SessionInfo(
                session_id="specific-session",
                template="python",
                flavor=SandboxFlavor.LARGE,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
                last_accessed=datetime(2024, 1, 1, 12, 5, 0),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="sandbox-specific"
            )
        ]
        mock_wrapper.get_sessions.return_value = mock_sessions
        
        params = {"session_id": "specific-session"}
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.get_sessions.assert_called_once_with("specific-session")
        assert len(result["sessions"]) == 1
        assert result["sessions"][0]["session_id"] == "specific-session"


class TestStopSessionTool:
    """Test StopSessionTool functionality."""
    
    @pytest.fixture
    def tool(self):
        """Create StopSessionTool instance."""
        return StopSessionTool()
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    def test_get_definition(self, tool):
        """Test tool definition is correct."""
        definition = tool.get_definition()
        
        assert definition.name == "stop_session"
        assert "Stop a specific sandbox session" in definition.description
        assert "session_id" in definition.inputSchema["required"]
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_wrapper):
        """Test successful session stop."""
        mock_wrapper.stop_session.return_value = True
        
        params = {"session_id": "test-session"}
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.stop_session.assert_called_once_with("test-session")
        
        assert result["success"] is True
        assert result["session_id"] == "test-session"
        assert "stopped successfully" in result["content"][0]["text"]
    
    @pytest.mark.asyncio
    async def test_execute_session_not_found(self, tool, mock_wrapper):
        """Test session stop when session not found."""
        mock_wrapper.stop_session.return_value = False
        
        params = {"session_id": "nonexistent-session"}
        result = await tool.execute(mock_wrapper, params)
        
        assert result["success"] is False
        assert "not found" in result["content"][0]["text"]


class TestGetVolumePathTool:
    """Test GetVolumePathTool functionality."""
    
    @pytest.fixture
    def tool(self):
        """Create GetVolumePathTool instance."""
        return GetVolumePathTool()
    
    @pytest.fixture
    def mock_wrapper(self):
        """Create mock wrapper."""
        return AsyncMock()
    
    def test_get_definition(self, tool):
        """Test tool definition is correct."""
        definition = tool.get_definition()
        
        assert definition.name == "get_volume_path"
        assert "Get configured volume mappings" in definition.description
        assert definition.inputSchema["required"] == []
    
    @pytest.mark.asyncio
    async def test_execute_success(self, tool, mock_wrapper):
        """Test successful volume mapping retrieval."""
        mock_mappings = [
            VolumeMapping(host_path="/host/data", container_path="/data"),
            VolumeMapping(host_path="/host/logs", container_path="/logs")
        ]
        mock_wrapper.get_volume_mappings.return_value = mock_mappings
        
        params = {}
        result = await tool.execute(mock_wrapper, params)
        
        mock_wrapper.get_volume_mappings.assert_called_once()
        
        assert "volume_mappings" in result
        assert len(result["volume_mappings"]) == 2
        
        mapping_1 = result["volume_mappings"][0]
        assert mapping_1["host_path"] == "/host/data"
        assert mapping_1["container_path"] == "/data"
    
    @pytest.mark.asyncio
    async def test_execute_empty_mappings(self, tool, mock_wrapper):
        """Test volume mapping retrieval with no mappings."""
        mock_wrapper.get_volume_mappings.return_value = []
        
        params = {}
        result = await tool.execute(mock_wrapper, params)
        
        assert result["volume_mappings"] == []


class TestToolRegistry:
    """Test ToolRegistry functionality."""
    
    @pytest.fixture
    def registry(self):
        """Create ToolRegistry instance."""
        return ToolRegistry()
    
    def test_default_tools_registered(self, registry):
        """Test that default tools are registered."""
        tools = registry.list_tools()
        tool_names = [tool.name for tool in tools]
        
        expected_tools = [
            "execute_code",
            "execute_command", 
            "get_sessions",
            "stop_session",
            "get_volume_path"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names
    
    def test_get_tool_exists(self, registry):
        """Test getting an existing tool."""
        tool = registry.get_tool("execute_code")
        assert tool is not None
        assert isinstance(tool, ExecuteCodeTool)
    
    def test_get_tool_not_exists(self, registry):
        """Test getting a non-existent tool."""
        tool = registry.get_tool("nonexistent_tool")
        assert tool is None
    
    def test_list_tools_format(self, registry):
        """Test that list_tools returns correct format."""
        tools = registry.list_tools()
        
        assert len(tools) > 0
        for tool in tools:
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'inputSchema')
            assert isinstance(tool.inputSchema, dict)