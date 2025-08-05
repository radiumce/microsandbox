"""
Unit tests for session management - focused on pure unit testing.

This file contains only tests that can be run without external dependencies
like real sandbox servers or network connections.
"""

import time
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from microsandbox_wrapper.session_manager import ManagedSession, SessionManager
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus, SessionInfo
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import SandboxCreationError


class TestManagedSessionUnit:
    """Unit tests for ManagedSession class - no external dependencies."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            session_timeout=300,
            cleanup_interval=60,
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
        assert managed_session.status == SessionStatus.CREATING
        assert isinstance(managed_session.created_at, datetime)
        assert isinstance(managed_session.last_accessed, datetime)
    
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
        assert info.status == SessionStatus.CREATING
        assert isinstance(info.created_at, datetime)
        assert isinstance(info.last_accessed, datetime)
    
    def test_is_expired_not_expired(self, managed_session):
        """Test session expiration check for non-expired session."""
        # New session should not be expired
        assert not managed_session.is_expired(timeout_seconds=300)
    
    def test_is_expired_time_based(self, managed_session):
        """Test session expiration based on time."""
        # Mock old last accessed time using timedelta
        from datetime import timedelta
        old_time = datetime.now() - timedelta(seconds=400)  # 400 seconds ago
        managed_session.last_accessed = old_time
        
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


class TestSessionManagerUnit:
    """Unit tests for SessionManager class - no external dependencies."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            session_timeout=300,
            cleanup_interval=60,
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
    async def test_touch_session_nonexistent(self, session_manager):
        """Test touching a non-existent session."""
        # Should not raise exception
        await session_manager.touch_session("nonexistent")
    
    @pytest.mark.asyncio
    async def test_stop_session_nonexistent(self, session_manager):
        """Test stopping a non-existent session."""
        result = await session_manager.stop_session("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_sessions_empty(self, session_manager):
        """Test getting sessions when none exist."""
        sessions = await session_manager.get_sessions()
        
        assert len(sessions) == 0
        assert sessions == []
    
    def test_get_cleanup_stats(self, session_manager):
        """Test getting cleanup statistics."""
        stats = session_manager.get_cleanup_stats()
        
        assert isinstance(stats, dict)
        assert "total_sessions" in stats
        assert "active_sessions" in stats
        assert "expired_sessions" in stats
        assert "cleanup_task_running" in stats
        assert "session_timeout" in stats
        assert "cleanup_interval" in stats
        assert "manager_uptime_seconds" in stats
        
        # Check initial values
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["expired_sessions"] == 0
        assert stats["cleanup_task_running"] is False
    
    @pytest.mark.asyncio
    async def test_force_cleanup_empty(self, session_manager):
        """Test manually triggering cleanup when no sessions exist."""
        cleaned_count = await session_manager.force_cleanup()
        
        assert cleaned_count == 0
    
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
        assert "cleanup_task_healthy" in status
        assert "cleanup_interval_seconds" in status
        assert "session_timeout_seconds" in status
        assert "manager_uptime_seconds" in status
        
        # Check initial values
        assert status["cleanup_task_exists"] is False
        assert status["cleanup_task_healthy"] is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])