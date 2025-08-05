"""
Unit tests for the main wrapper interface.

Tests the MicrosandboxWrapper class including execute_code, execute_command,
error handling, session reuse, and timeout control.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import List

import pytest

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.wrapper import MicrosandboxWrapper
from microsandbox_wrapper.models import (
    SandboxFlavor, SessionStatus, SessionInfo, ExecutionResult, 
    CommandResult, ResourceStats, VolumeMapping
)
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError, ResourceLimitError, ConfigurationError
)


class TestMicrosandboxWrapperInitialization:
    """Test MicrosandboxWrapper initialization and configuration."""
    
    def test_wrapper_initialization_with_config(self):
        """Test wrapper initialization with provided config."""
        config = WrapperConfig(
            server_url="http://test-server:5555",
            api_key="test-key",
            max_concurrent_sessions=5
        )
        
        wrapper = MicrosandboxWrapper(config=config)
        
        assert wrapper._config == config
        assert not wrapper._started
        assert wrapper._session_manager is not None
        assert wrapper._resource_manager is not None
    
    def test_wrapper_initialization_with_overrides(self):
        """Test wrapper initialization with parameter overrides."""
        config = WrapperConfig(
            server_url="http://original-server:5555",
            api_key="original-key"
        )
        
        wrapper = MicrosandboxWrapper(
            server_url="http://override-server:5555",
            api_key="override-key",
            config=config
        )
        
        assert wrapper._config.server_url == "http://override-server:5555"
        assert wrapper._config.api_key == "override-key"
    
    @patch('microsandbox_wrapper.wrapper.WrapperConfig.from_env')
    def test_wrapper_initialization_from_env(self, mock_from_env):
        """Test wrapper initialization loading config from environment."""
        mock_config = WrapperConfig()
        mock_from_env.return_value = mock_config
        
        wrapper = MicrosandboxWrapper()
        
        assert wrapper._config == mock_config
        mock_from_env.assert_called_once()
    
    def test_wrapper_initialization_config_error(self):
        """Test wrapper initialization with configuration error."""
        with patch('microsandbox_wrapper.wrapper.WrapperConfig.from_env', 
                   side_effect=Exception("Config error")):
            with pytest.raises(ConfigurationError):
                MicrosandboxWrapper()


class TestMicrosandboxWrapperLifecycle:
    """Test wrapper startup and shutdown lifecycle."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a wrapper instance for testing."""
        config = WrapperConfig()
        return MicrosandboxWrapper(config=config)
    
    @pytest.mark.asyncio
    async def test_start_wrapper(self, wrapper):
        """Test starting the wrapper."""
        with patch.object(wrapper._session_manager, 'start') as mock_session_start:
            with patch.object(wrapper._resource_manager, 'start') as mock_resource_start:
                await wrapper.start()
                
                assert wrapper._started is True
                mock_session_start.assert_called_once()
                mock_resource_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_wrapper_already_started(self, wrapper):
        """Test starting wrapper when already started."""
        wrapper._started = True
        
        with patch.object(wrapper._session_manager, 'start') as mock_session_start:
            await wrapper.start()
            
            # Should not call start again
            mock_session_start.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_wrapper_error(self, wrapper):
        """Test wrapper startup error handling."""
        with patch.object(wrapper._session_manager, 'start', side_effect=Exception("Start error")):
            with patch.object(wrapper, '_cleanup_on_error') as mock_cleanup:
                with pytest.raises(MicrosandboxWrapperError):
                    await wrapper.start()
                
                mock_cleanup.assert_called_once()
                assert wrapper._started is False 
   
    @pytest.mark.asyncio
    async def test_stop_wrapper(self, wrapper):
        """Test stopping the wrapper."""
        wrapper._started = True
        
        with patch.object(wrapper, 'graceful_shutdown') as mock_shutdown:
            mock_shutdown.return_value = {'status': 'success'}
            
            await wrapper.stop()
            
            mock_shutdown.assert_called_once_with(30.0)
    
    @pytest.mark.asyncio
    async def test_stop_wrapper_not_started(self, wrapper):
        """Test stopping wrapper when not started."""
        with patch.object(wrapper, 'graceful_shutdown') as mock_shutdown:
            await wrapper.stop()
            
            # Should not call graceful_shutdown
            mock_shutdown.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, wrapper):
        """Test wrapper as async context manager."""
        with patch.object(wrapper, 'start') as mock_start:
            with patch.object(wrapper, 'stop') as mock_stop:
                async with wrapper:
                    pass
                
                mock_start.assert_called_once()
                mock_stop.assert_called_once()
    
    def test_is_started(self, wrapper):
        """Test checking if wrapper is started."""
        assert wrapper.is_started() is False
        
        wrapper._started = True
        assert wrapper.is_started() is True
    
    def test_get_config(self, wrapper):
        """Test getting wrapper configuration."""
        config = wrapper.get_config()
        assert config == wrapper._config
    
    def test_ensure_started_not_started(self, wrapper):
        """Test _ensure_started when wrapper is not started."""
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            wrapper._ensure_started()
        
        assert "not been started" in str(exc_info.value)
    
    def test_ensure_started_when_started(self, wrapper):
        """Test _ensure_started when wrapper is started."""
        wrapper._started = True
        
        # Should not raise an exception
        wrapper._ensure_started()


class TestMicrosandboxWrapperCodeExecution:
    """Test code execution functionality."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a started wrapper instance for testing."""
        config = WrapperConfig()
        wrapper = MicrosandboxWrapper(config=config)
        wrapper._started = True
        return wrapper
    
    @pytest.mark.asyncio
    async def test_execute_code_success(self, wrapper):
        """Test successful code execution."""
        # Mock the resource manager
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        
        # Mock the session manager
        mock_session = AsyncMock()
        mock_session.session_id = "test-session-id"
        mock_session.execute_code.return_value = ExecutionResult(
            session_id="test-session-id",
            stdout="Hello, World!",
            stderr="",
            success=True,
            execution_time_ms=100,
            session_created=False,
            template="python"
        )
        
        wrapper._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)
        
        result = await wrapper.execute_code("print('Hello, World!')")
        
        assert isinstance(result, ExecutionResult)
        assert result.session_id == "test-session-id"
        assert result.stdout == "Hello, World!"
        assert result.success is True
        
        # Verify resource validation was called
        wrapper._resource_manager.validate_resource_request.assert_called_once_with(SandboxFlavor.SMALL)
        
        # Verify session creation was called
        wrapper._session_manager.get_or_create_session.assert_called_once_with(
            session_id=None,
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        # Verify code execution was called
        mock_session.execute_code.assert_called_once_with("print('Hello, World!')", None)
    
    @pytest.mark.asyncio
    async def test_execute_code_with_parameters(self, wrapper):
        """Test code execution with custom parameters."""
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.session_id = "custom-session-id"
        mock_session.execute_code.return_value = ExecutionResult(
            session_id="custom-session-id",
            stdout="output",
            stderr="",
            success=True,
            execution_time_ms=50,
            session_created=False,
            template="node"
        )
        
        wrapper._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)
        
        result = await wrapper.execute_code(
            code="console.log('test')",
            template="node",
            session_id="custom-session-id",
            flavor=SandboxFlavor.MEDIUM,
            timeout=60
        )
        
        assert result.session_id == "custom-session-id"
        assert result.template == "node"
        
        # Verify parameters were passed correctly
        wrapper._resource_manager.validate_resource_request.assert_called_once_with(SandboxFlavor.MEDIUM)
        wrapper._session_manager.get_or_create_session.assert_called_once_with(
            session_id="custom-session-id",
            template="node",
            flavor=SandboxFlavor.MEDIUM
        )
        mock_session.execute_code.assert_called_once_with("console.log('test')", 60)
    
    @pytest.mark.asyncio
    async def test_execute_code_resource_limit_error(self, wrapper):
        """Test code execution with resource limit error."""
        wrapper._resource_manager.validate_resource_request = AsyncMock(
            side_effect=ResourceLimitError("Resource limit exceeded", "memory", "4GB", "2GB")
        )
        
        with pytest.raises(ResourceLimitError):
            await wrapper.execute_code("print('test')")
    
    @pytest.mark.asyncio
    async def test_execute_code_not_started(self, wrapper):
        """Test code execution when wrapper is not started."""
        wrapper._started = False
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.execute_code("print('test')")
        
        assert "not been started" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_code_session_error(self, wrapper):
        """Test code execution with session error."""
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        wrapper._session_manager.get_or_create_session = AsyncMock(
            side_effect=Exception("Session creation failed")
        )
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.execute_code("print('test')")
        
        assert "Code execution failed" in str(exc_info.value)


class TestMicrosandboxWrapperCommandExecution:
    """Test command execution functionality."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a started wrapper instance for testing."""
        config = WrapperConfig()
        wrapper = MicrosandboxWrapper(config=config)
        wrapper._started = True
        return wrapper
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, wrapper):
        """Test successful command execution."""
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.session_id = "test-session-id"
        mock_session.execute_command.return_value = CommandResult(
            session_id="test-session-id",
            stdout="command output",
            stderr="",
            exit_code=0,
            success=True,
            execution_time_ms=75,
            session_created=False,
            command="ls",
            args=["-la"]
        )
        
        wrapper._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)
        
        # Mock the logging to avoid the 'args' conflict
        with patch('microsandbox_wrapper.wrapper.log_session_event'):
            result = await wrapper.execute_command("ls", ["-la"])
        
        assert isinstance(result, CommandResult)
        assert result.session_id == "test-session-id"
        assert result.stdout == "command output"
        assert result.exit_code == 0
        assert result.success is True
        assert result.command == "ls"
        assert result.args == ["-la"]
        
        # Verify session creation was called
        wrapper._session_manager.get_or_create_session.assert_called_once_with(
            session_id=None,
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        # Verify command execution was called
        mock_session.execute_command.assert_called_once_with("ls", ["-la"], None)
    
    @pytest.mark.asyncio
    async def test_execute_command_with_parameters(self, wrapper):
        """Test command execution with custom parameters."""
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        
        mock_session = AsyncMock()
        mock_session.session_id = "custom-session-id"
        mock_session.execute_command.return_value = CommandResult(
            session_id="custom-session-id",
            stdout="output",
            stderr="",
            exit_code=0,
            success=True,
            execution_time_ms=25,
            session_created=False,
            command="echo",
            args=["test"]
        )
        
        wrapper._session_manager.get_or_create_session = AsyncMock(return_value=mock_session)
        
        # Mock the logging to avoid the 'args' conflict
        with patch('microsandbox_wrapper.wrapper.log_session_event'):
            result = await wrapper.execute_command(
                command="echo",
                args=["test"],
                template="node",
                session_id="custom-session-id",
                flavor=SandboxFlavor.LARGE,
                timeout=30
            )
        
        assert result.session_id == "custom-session-id"
        
        # Verify parameters were passed correctly
        wrapper._resource_manager.validate_resource_request.assert_called_once_with(SandboxFlavor.LARGE)
        wrapper._session_manager.get_or_create_session.assert_called_once_with(
            session_id="custom-session-id",
            template="node",
            flavor=SandboxFlavor.LARGE
        )
        mock_session.execute_command.assert_called_once_with("echo", ["test"], 30)
    
    @pytest.mark.asyncio
    async def test_execute_command_not_started(self, wrapper):
        """Test command execution when wrapper is not started."""
        wrapper._started = False
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.execute_command("ls")
        
        assert "not been started" in str(exc_info.value)


class TestMicrosandboxWrapperSessionManagement:
    """Test session management functionality."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a started wrapper instance for testing."""
        config = WrapperConfig()
        wrapper = MicrosandboxWrapper(config=config)
        wrapper._started = True
        return wrapper
    
    @pytest.mark.asyncio
    async def test_get_sessions(self, wrapper):
        """Test getting session information."""
        mock_sessions = [
            SessionInfo(
                session_id="session1",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="session-1"
            )
        ]
        
        wrapper._session_manager.get_sessions = AsyncMock(return_value=mock_sessions)
        
        sessions = await wrapper.get_sessions()
        
        assert len(sessions) == 1
        assert sessions[0].session_id == "session1"
        wrapper._session_manager.get_sessions.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    async def test_get_sessions_specific(self, wrapper):
        """Test getting specific session information."""
        mock_sessions = [
            SessionInfo(
                session_id="specific-session",
                template="python",
                flavor=SandboxFlavor.MEDIUM,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.RUNNING,
                namespace="default",
                sandbox_name="session-specific"
            )
        ]
        
        wrapper._session_manager.get_sessions = AsyncMock(return_value=mock_sessions)
        
        sessions = await wrapper.get_sessions("specific-session")
        
        assert len(sessions) == 1
        assert sessions[0].session_id == "specific-session"
        wrapper._session_manager.get_sessions.assert_called_once_with("specific-session")
    
    @pytest.mark.asyncio
    async def test_stop_session(self, wrapper):
        """Test stopping a session."""
        wrapper._session_manager.stop_session = AsyncMock(return_value=True)
        
        result = await wrapper.stop_session("test-session")
        
        assert result is True
        wrapper._session_manager.stop_session.assert_called_once_with("test-session")
    
    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, wrapper):
        """Test stopping a non-existent session."""
        wrapper._session_manager.stop_session = AsyncMock(return_value=False)
        
        result = await wrapper.stop_session("nonexistent-session")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_sessions_not_started(self, wrapper):
        """Test getting sessions when wrapper is not started."""
        wrapper._started = False
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.get_sessions()
        
        assert "not been started" in str(exc_info.value)


class TestMicrosandboxWrapperResourceManagement:
    """Test resource management functionality."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a started wrapper instance for testing."""
        config = WrapperConfig()
        wrapper = MicrosandboxWrapper(config=config)
        wrapper._started = True
        return wrapper
    
    @pytest.mark.asyncio
    async def test_get_resource_stats(self, wrapper):
        """Test getting resource statistics."""
        mock_stats = ResourceStats(
            active_sessions=3,
            max_sessions=10,
            sessions_by_flavor={SandboxFlavor.SMALL: 2, SandboxFlavor.MEDIUM: 1},
            total_memory_mb=3072,
            total_cpus=3.0,
            uptime_seconds=1800
        )
        
        wrapper._resource_manager.get_resource_stats = AsyncMock(return_value=mock_stats)
        
        stats = await wrapper.get_resource_stats()
        
        assert stats.active_sessions == 3
        assert stats.max_sessions == 10
        assert stats.total_memory_mb == 3072
        wrapper._resource_manager.get_resource_stats.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_orphan_sandboxes(self, wrapper):
        """Test cleaning up orphan sandboxes."""
        wrapper._resource_manager.force_orphan_cleanup = AsyncMock(return_value=2)
        
        result = await wrapper.cleanup_orphan_sandboxes()
        
        assert result == 2
        wrapper._resource_manager.force_orphan_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_volume_mappings(self, wrapper):
        """Test getting volume mappings."""
        mock_mappings = [
            VolumeMapping(host_path="/host/data", container_path="/app/data"),
            VolumeMapping(host_path="/host/logs", container_path="/app/logs")
        ]
        
        wrapper._config.get_parsed_volume_mappings = Mock(return_value=mock_mappings)
        
        mappings = await wrapper.get_volume_mappings()
        
        assert len(mappings) == 2
        assert mappings[0].host_path == "/host/data"
        assert mappings[1].container_path == "/app/logs"
    
    @pytest.mark.asyncio
    async def test_get_resource_stats_not_started(self, wrapper):
        """Test getting resource stats when wrapper is not started."""
        wrapper._started = False
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.get_resource_stats()
        
        assert "not been started" in str(exc_info.value)


class TestMicrosandboxWrapperErrorHandling:
    """Test error handling and exception propagation."""
    
    @pytest.fixture
    def wrapper(self):
        """Create a started wrapper instance for testing."""
        config = WrapperConfig()
        wrapper = MicrosandboxWrapper(config=config)
        wrapper._started = True
        return wrapper
    
    @pytest.mark.asyncio
    async def test_execute_code_wrapper_error_propagation(self, wrapper):
        """Test that MicrosandboxWrapperError exceptions are propagated."""
        wrapper._resource_manager.validate_resource_request = AsyncMock(
            side_effect=ResourceLimitError("Limit exceeded", "memory", "4GB", "2GB")
        )
        
        with pytest.raises(ResourceLimitError):
            await wrapper.execute_code("print('test')")
    
    @pytest.mark.asyncio
    async def test_execute_code_generic_error_wrapping(self, wrapper):
        """Test that generic exceptions are wrapped in MicrosandboxWrapperError."""
        wrapper._resource_manager.validate_resource_request = AsyncMock()
        wrapper._session_manager.get_or_create_session = AsyncMock(
            side_effect=Exception("Generic error")
        )
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.execute_code("print('test')")
        
        assert "Code execution failed" in str(exc_info.value)
        assert "Generic error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_sessions_error_handling(self, wrapper):
        """Test error handling in get_sessions."""
        wrapper._session_manager.get_sessions = AsyncMock(
            side_effect=Exception("Session manager error")
        )
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.get_sessions()
        
        assert "Failed to get session info" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_resource_stats_error_handling(self, wrapper):
        """Test error handling in get_resource_stats."""
        wrapper._resource_manager.get_resource_stats = AsyncMock(
            side_effect=Exception("Resource manager error")
        )
        
        with pytest.raises(MicrosandboxWrapperError) as exc_info:
            await wrapper.get_resource_stats()
        
        assert "Failed to get resource stats" in str(exc_info.value)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])