"""
Unit tests for session management.

Tests the ManagedSession class and SessionManager functionality including
session creation, lifecycle management, timeout handling, and cleanup.
"""

import asyncio
import time
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from microsandbox_wrapper.session_manager import ManagedSession, SessionManager
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus, SessionInfo
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import (
    SandboxCreationError, CodeExecutionError, CommandExecutionError
)


class TestManagedSession:
    """Test ManagedSession class functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            session_timeout=300,  # 5 minutes
            cleanup_interval=60,  # 1 minute
            max_concurrent_sessions=5,
            default_execution_timeout=120
        )
    
    @pytest.fixture
    def managed_session(self, config):
        """Create a managed session instance."""
        return ManagedSession(
            session_id="test-session-123",
            template="python",
            flavor=SandboxFlavor.MEDIUM,
            config=config
        )
    
    def test_managed_session_creation(self, managed_session):
        """Test basic managed session creation."""
        assert managed_session.session_id == "test-session-123"
        assert managed_session.template == "python"
        assert managed_session.flavor == SandboxFlavor.MEDIUM
        assert managed_session.status == SessionStatus.CREATED
        assert isinstance(managed_session.created_at, float)
        assert isinstance(managed_session.last_accessed, float)
    
    def test_managed_session_template_normalization(self, config):
        """Test template name normalization."""
        session = ManagedSession(
            session_id="test",
            template="Python",  # Capital P
            flavor=SandboxFlavor.SMALL,
            config=config
        )
        assert session.template == "python"
    
    def test_get_info(self, managed_session):
        """Test getting session information."""
        info = managed_session.get_info()
        
        assert isinstance(info, SessionInfo)
        assert info.session_id == "test-session-123"
        assert info.template == "python"
        assert info.flavor == SandboxFlavor.MEDIUM
        assert info.status == SessionStatus.CREATED
        assert isinstance(info.created_at, float)
        assert isinstance(info.last_accessed, float)
    
    def test_is_expired_not_expired(self, managed_session):
        """Test session expiration check for non-expired session."""
        # New session should not be expired
        assert not managed_session.is_expired(timeout_seconds=300)
    
    def test_is_expired_time_based(self, managed_session):
        """Test session expiration based on time."""
        # Mock old last accessed time
        managed_session.last_accessed = time.time() - 400  # 400 seconds ago
        
        # Should be expired with 300 second timeout
        assert managed_session.is_expired(timeout_seconds=300)
        
        # Should not be expired with 500 second timeout
        assert not managed_session.is_expired(timeout_seconds=500)
    
    def test_is_expired_stopped_session(self, managed_session):
        """Test that stopped sessions are always considered expired."""
        managed_session.status = SessionStatus.STOPPED
        
        # Should be expired regardless of timeout
        assert managed_session.is_expired(timeout_seconds=1000)
    
    @pytest.mark.asyncio
    async def test_ensure_started_creates_sandbox(self, managed_session):
        """Test that ensure_started creates and starts the sandbox."""
        with patch.object(managed_session, '_create_sandbox', new_callable=AsyncMock) as mock_create:
            await managed_session.ensure_started()
            
            mock_create.assert_called_once()
            assert managed_session.status == SessionStatus.READY
    
    @pytest.mark.asyncio
    async def test_ensure_started_idempotent(self, managed_session):
        """Test that ensure_started is idempotent."""
        # Set status to ready
        managed_session.status = SessionStatus.READY
        managed_session._sandbox = Mock()
        
        with patch.object(managed_session, '_create_sandbox', new_callable=AsyncMock) as mock_create:
            await managed_session.ensure_started()
            
            # Should not create sandbox again
            mock_create.assert_not_called()
            assert managed_session.status == SessionStatus.READY
    
    @pytest.mark.asyncio
    async def test_ensure_started_unsupported_template(self, config):
        """Test ensure_started with unsupported template."""
        session = ManagedSession(
            session_id="test",
            template="unsupported",
            flavor=SandboxFlavor.SMALL,
            config=config
        )
        
        with pytest.raises(SandboxCreationError) as exc_info:
            await session.ensure_started()
        
        assert "Unsupported template" in str(exc_info.value)
        assert session.status == SessionStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_execute_code_success(self, managed_session):
        """Test successful code execution."""
        # Mock sandbox
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_code.return_value = "Hello, World!"
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        result = await managed_session.execute_code("print('Hello, World!')")
        
        assert result == "Hello, World!"
        mock_sandbox.execute_code.assert_called_once_with("print('Hello, World!')", timeout=120)
    
    @pytest.mark.asyncio
    async def test_execute_code_with_timeout(self, managed_session):
        """Test code execution with custom timeout."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_code.return_value = "result"
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        result = await managed_session.execute_code("print('test')", timeout=60)
        
        assert result == "result"
        mock_sandbox.execute_code.assert_called_once_with("print('test')", timeout=60)
    
    @pytest.mark.asyncio
    async def test_execute_code_timeout_error(self, managed_session):
        """Test code execution timeout handling."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_code.side_effect = asyncio.TimeoutError()
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        with pytest.raises(CodeExecutionError) as exc_info:
            await managed_session.execute_code("print('test')")
        
        assert "timed out" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_execute_command_success(self, managed_session):
        """Test successful command execution."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_command.return_value = "file1.txt\nfile2.txt"
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        result = await managed_session.execute_command("ls")
        
        assert result == "file1.txt\nfile2.txt"
        mock_sandbox.execute_command.assert_called_once_with("ls", timeout=120)
    
    @pytest.mark.asyncio
    async def test_execute_command_with_timeout(self, managed_session):
        """Test command execution with custom timeout."""
        mock_sandbox = AsyncMock()
        mock_sandbox.execute_command.return_value = "output"
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        result = await managed_session.execute_command("ls -la", timeout=30)
        
        assert result == "output"
        mock_sandbox.execute_command.assert_called_once_with("ls -la", timeout=30)
    
    @pytest.mark.asyncio
    async def test_stop_session(self, managed_session):
        """Test stopping a session."""
        mock_sandbox = AsyncMock()
        managed_session._sandbox = mock_sandbox
        managed_session.status = SessionStatus.READY
        
        await managed_session.stop()
        
        mock_sandbox.cleanup.assert_called_once()
        assert managed_session.status == SessionStatus.STOPPED
    
    @pytest.mark.asyncio
    async def test_stop_session_idempotent(self, managed_session):
        """Test that stopping a session is idempotent."""
        managed_session.status = SessionStatus.STOPPED
        
        with patch.object(managed_session, '_sandbox', None):
            # Should not raise exception
            await managed_session.stop()
            
            assert managed_session.status == SessionStatus.STOPPED


class TestSessionManager:
    """Test SessionManager functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            session_timeout=300,  # 5 minutes
            cleanup_interval=60,  # 1 minute
            max_concurrent_sessions=5,
            default_execution_timeout=120
        )
    
    @pytest.fixture
    def session_manager(self, config):
        """Create a session manager instance."""
        return SessionManager(config)
    
    def test_session_manager_initialization(self, config):
        """Test SessionManager initialization."""
        manager = SessionManager(config)
        
        assert manager._config == config
        assert manager._sessions == {}
        assert manager._cleanup_task is None
        assert isinstance(manager._start_time, float)
    
    @pytest.mark.asyncio
    async def test_start_and_stop_manager(self, session_manager):
        """Test starting and stopping the session manager."""
        # Start the manager
        await session_manager.start()
        assert session_manager._cleanup_task is not None
        assert not session_manager._cleanup_task.done()
        
        # Stop the manager
        await session_manager.stop()
        assert session_manager._cleanup_task is None
        assert session_manager._sessions == {}
    
    @pytest.mark.asyncio
    async def test_get_or_create_session_new(self, session_manager):
        """Test creating a new session."""
        with patch.object(ManagedSession, '__init__', return_value=None) as mock_init:
            mock_session = MagicMock()
            mock_session.session_id = "test-session-id"
            
            with patch.object(ManagedSession, '__new__', return_value=mock_session):
                session = await session_manager.get_or_create_session(
                    session_id=None,
                    template="python",
                    flavor=SandboxFlavor.MEDIUM
                )
                
                assert session == mock_session
                assert len(session_manager._sessions) == 1
    
    @pytest.mark.asyncio
    async def test_get_or_create_session_existing_valid(self, session_manager):
        """Test getting an existing valid session."""
        # Create a mock session
        mock_session = MagicMock()
        mock_session.session_id = "existing-session"
        mock_session.is_expired.return_value = False
        mock_session.template = "python"
        mock_session.flavor = SandboxFlavor.MEDIUM
        
        # Add to sessions
        session_manager._sessions["existing-session"] = mock_session
        
        # Get the session
        session = await session_manager.get_or_create_session(
            session_id="existing-session",
            template="python",
            flavor=SandboxFlavor.MEDIUM
        )
        
        assert session == mock_session
        mock_session.is_expired.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_or_create_session_existing_expired(self, session_manager):
        """Test getting an existing expired session creates a new one."""
        # Create a mock expired session
        mock_old_session = MagicMock()
        mock_old_session.session_id = "expired-session"
        mock_old_session.is_expired.return_value = True
        mock_old_session.stop = AsyncMock()
        
        # Add to sessions
        session_manager._sessions["expired-session"] = mock_old_session
        
        with patch.object(ManagedSession, '__init__', return_value=None) as mock_init:
            mock_new_session = MagicMock()
            mock_new_session.session_id = "expired-session"
            
            with patch.object(ManagedSession, '__new__', return_value=mock_new_session):
                session = await session_manager.get_or_create_session(
                    session_id="expired-session",
                    template="python",
                    flavor=SandboxFlavor.MEDIUM
                )
                
                # Should stop old session and return new one
                mock_old_session.stop.assert_called_once()
                assert session == mock_new_session
    
    @pytest.mark.asyncio
    async def test_touch_session(self, session_manager):
        """Test touching a session to update last accessed time."""
        mock_session = MagicMock()
        session_manager._sessions["test-session"] = mock_session
        
        await session_manager.touch_session("test-session")
        
        # Should update last accessed time
        assert isinstance(mock_session.last_accessed, float)
    
    @pytest.mark.asyncio
    async def test_touch_session_nonexistent(self, session_manager):
        """Test touching a non-existent session."""
        # Should not raise exception
        await session_manager.touch_session("nonexistent")
    
    @pytest.mark.asyncio
    async def test_stop_session_existing(self, session_manager):
        """Test stopping an existing session."""
        mock_session = AsyncMock()
        mock_session.session_id = "test-session"
        session_manager._sessions["test-session"] = mock_session
        
        result = await session_manager.stop_session("test-session")
        
        assert result is True
        mock_session.stop.assert_called_once()
        assert "test-session" not in session_manager._sessions
    
    @pytest.mark.asyncio
    async def test_stop_session_nonexistent(self, session_manager):
        """Test stopping a non-existent session."""
        result = await session_manager.stop_session("nonexistent")
        
        assert result is False
    
    def test_get_sessions_all(self, session_manager):
        """Test getting all sessions."""
        # Create mock sessions
        mock_session1 = MagicMock()
        mock_session2 = MagicMock()
        mock_info1 = SessionInfo(
            session_id="s1", template="python", flavor=SandboxFlavor.SMALL,
            status=SessionStatus.READY, created_at=time.time(), last_accessed=time.time()
        )
        mock_info2 = SessionInfo(
            session_id="s2", template="node", flavor=SandboxFlavor.MEDIUM,
            status=SessionStatus.READY, created_at=time.time(), last_accessed=time.time()
        )
        mock_session1.get_info.return_value = mock_info1
        mock_session2.get_info.return_value = mock_info2
        
        session_manager._sessions = {"s1": mock_session1, "s2": mock_session2}
        
        sessions = session_manager.get_sessions()
        
        assert len(sessions) == 2
        assert mock_info1 in sessions
        assert mock_info2 in sessions
    
    def test_get_sessions_specific(self, session_manager):
        """Test getting specific sessions by ID."""
        mock_session = MagicMock()
        mock_info = SessionInfo(
            session_id="s1", template="python", flavor=SandboxFlavor.SMALL,
            status=SessionStatus.READY, created_at=time.time(), last_accessed=time.time()
        )
        mock_session.get_info.return_value = mock_info
        
        session_manager._sessions = {"s1": mock_session, "s2": MagicMock()}
        
        sessions = session_manager.get_sessions(session_ids=["s1"])
        
        assert len(sessions) == 1
        assert sessions[0] == mock_info
    
    def test_get_sessions_specific_nonexistent(self, session_manager):
        """Test getting specific sessions with non-existent IDs."""
        sessions = session_manager.get_sessions(session_ids=["nonexistent"])
        
        assert len(sessions) == 0
    
    def test_get_cleanup_stats(self, session_manager):
        """Test getting cleanup statistics."""
        stats = session_manager.get_cleanup_stats()
        
        assert isinstance(stats, dict)
        assert "total_sessions" in stats
        assert "cleanup_task_running" in stats
        assert "last_cleanup_time" in stats
        assert "sessions_cleaned_total" in stats
        assert "uptime_seconds" in stats
    
    @pytest.mark.asyncio
    async def test_force_cleanup(self, session_manager):
        """Test manually triggering cleanup."""
        with patch.object(session_manager, '_cleanup_expired_sessions', new_callable=AsyncMock) as mock_cleanup:
            mock_cleanup.return_value = 2
            
            cleaned_count = await session_manager.force_cleanup()
            
            assert cleaned_count == 2
            mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_session_by_id_existing(self, session_manager):
        """Test cleaning up a specific session by ID."""
        mock_session = AsyncMock()
        session_manager._sessions["test-session"] = mock_session
        
        result = await session_manager.cleanup_session_by_id("test-session")
        
        assert result is True
        mock_session.stop.assert_called_once()
        assert "test-session" not in session_manager._sessions
    
    @pytest.mark.asyncio
    async def test_cleanup_session_by_id_nonexistent(self, session_manager):
        """Test cleaning up a non-existent session by ID."""
        result = await session_manager.cleanup_session_by_id("nonexistent")
        
        assert result is False
    
    def test_is_cleanup_healthy_no_task(self, session_manager):
        """Test cleanup health check when no task is running."""
        session_manager._cleanup_task = None
        
        assert not session_manager.is_cleanup_healthy()
    
    def test_is_cleanup_healthy_running_task(self, session_manager):
        """Test cleanup health check with running task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancelled.return_value = False
        session_manager._cleanup_task = mock_task
        
        assert session_manager.is_cleanup_healthy()
    
    def test_is_cleanup_healthy_cancelled_task(self, session_manager):
        """Test cleanup health check with cancelled task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = True
        session_manager._cleanup_task = mock_task
        
        assert not session_manager.is_cleanup_healthy()
    
    def test_get_background_task_status(self, session_manager):
        """Test getting background task status."""
        status = session_manager.get_background_task_status()
        
        assert isinstance(status, dict)
        assert "cleanup_task_exists" in status
        assert "cleanup_task_running" in status
        assert "cleanup_task_cancelled" in status
        assert "cleanup_task_exception" in status


class TestSessionManagerConcurrency:
    """Test concurrent access and thread safety."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            session_timeout=300,
            cleanup_interval=60,
            max_concurrent_sessions=10,
            default_execution_timeout=120
        )
    
    @pytest.fixture
    def session_manager(self, config):
        """Create a session manager instance."""
        return SessionManager(config)
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self, session_manager):
        """Test concurrent session creation."""
        session_ids = [f"session-{i}" for i in range(5)]
        
        with patch.object(ManagedSession, '__init__', return_value=None):
            mock_sessions = []
            for i, session_id in enumerate(session_ids):
                mock_session = MagicMock()
                mock_session.session_id = session_id
                mock_sessions.append(mock_session)
            
            with patch.object(ManagedSession, '__new__', side_effect=mock_sessions):
                # Create sessions concurrently
                tasks = [
                    session_manager.get_or_create_session(
                        session_id=None,
                        template="python",
                        flavor=SandboxFlavor.SMALL
                    )
                    for _ in range(5)
                ]
                
                sessions = await asyncio.gather(*tasks)
                
                assert len(sessions) == 5
                assert len(session_manager._sessions) == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_session_access(self, session_manager):
        """Test concurrent access to the same session."""
        # Create a session first
        with patch.object(ManagedSession, '__init__', return_value=None):
            mock_session = MagicMock()
            mock_session.session_id = "shared-session"
            
            with patch.object(ManagedSession, '__new__', return_value=mock_session):
                session = await session_manager.get_or_create_session(
                    session_id="shared-session",
                    template="python",
                    flavor=SandboxFlavor.MEDIUM
                )
                
                # Access session concurrently
                async def access_session():
                    return await session_manager.get_or_create_session(
                        session_id="shared-session",
                        template="python",
                        flavor=SandboxFlavor.MEDIUM
                    )
                
                tasks = [access_session() for _ in range(10)]
                results = await asyncio.gather(*tasks)
                
                # All should return the same session
                for result in results:
                    assert result == session
                
                # Should still only have one session
                assert len(session_manager._sessions) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])