"""
Unit tests for LRU eviction mechanism.

Tests the LRU (Least Recently Used) eviction functionality in the
microsandbox wrapper, including session ordering, eviction logic,
and protection of processing sessions.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus
from microsandbox_wrapper.resource_manager import ResourceManager
from microsandbox_wrapper.session_manager import SessionManager, ManagedSession
from microsandbox_wrapper.exceptions import ResourceLimitError


class TestLRUEviction:
    """Test LRU eviction functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration with low limits for testing."""
        return WrapperConfig(
            server_url="http://localhost:5555",
            max_concurrent_sessions=3,
            max_total_memory_mb=3072,  # 3GB
            enable_lru_eviction=True,
            session_timeout=300
        )
    
    @pytest.fixture
    def session_manager(self, config):
        """Create session manager for testing."""
        return SessionManager(config)
    
    @pytest.fixture
    def resource_manager(self, config, session_manager):
        """Create resource manager for testing."""
        return ResourceManager(config, session_manager)
    
    def test_managed_session_can_be_evicted(self, config):
        """Test ManagedSession.can_be_evicted() method."""
        session = ManagedSession("test-id", "python", SandboxFlavor.SMALL, config)
        
        # Test different statuses
        session.status = SessionStatus.READY
        assert session.can_be_evicted() is True
        
        session.status = SessionStatus.RUNNING
        assert session.can_be_evicted() is True
        
        session.status = SessionStatus.ERROR
        assert session.can_be_evicted() is True
        
        session.status = SessionStatus.STOPPED
        assert session.can_be_evicted() is True
        
        # These statuses should NOT be evictable
        session.status = SessionStatus.PROCESSING
        assert session.can_be_evicted() is False
        
        session.status = SessionStatus.CREATING
        assert session.can_be_evicted() is False
    
    def test_managed_session_touch(self, config):
        """Test ManagedSession.touch() method updates last_accessed."""
        session = ManagedSession("test-id", "python", SandboxFlavor.SMALL, config)
        original_time = session.last_accessed
        
        # Wait a bit to ensure different timestamp
        import time
        time.sleep(0.01)
        
        session.touch()
        assert session.last_accessed > original_time
    
    @pytest.mark.asyncio
    async def test_lru_eviction_basic(self, resource_manager, session_manager):
        """Test basic LRU eviction functionality."""
        # Mock session manager methods
        mock_sessions = []
        
        # Create mock sessions with different last_accessed times
        base_time = datetime.now()
        for i in range(3):
            session_info = MagicMock()
            session_info.session_id = f"session-{i}"
            session_info.last_accessed = base_time - timedelta(minutes=i)  # i=0 is most recent
            session_info.flavor = SandboxFlavor.SMALL
            session_info.status = SessionStatus.READY
            mock_sessions.append(session_info)
        
        # Create corresponding managed sessions
        managed_sessions = {}
        for i, session_info in enumerate(mock_sessions):
            managed_session = MagicMock()
            managed_session.can_be_evicted.return_value = True
            managed_sessions[session_info.session_id] = managed_session
        
        session_manager._sessions = managed_sessions
        session_manager.get_sessions = AsyncMock(return_value=mock_sessions)
        session_manager.stop_session = AsyncMock(return_value=True)
        
        # Test evicting 1 session
        evicted_count = await resource_manager._evict_lru_sessions(1, 0)
        
        assert evicted_count == 1
        # Should evict the oldest session (session-2, which has the oldest timestamp)
        session_manager.stop_session.assert_called_once_with("session-2")
    
    @pytest.mark.asyncio
    async def test_lru_eviction_memory_based(self, resource_manager, session_manager):
        """Test LRU eviction based on memory requirements."""
        # Mock sessions with different memory usage
        mock_sessions = []
        base_time = datetime.now()
        
        for i in range(3):
            session_info = MagicMock()
            session_info.session_id = f"session-{i}"
            session_info.last_accessed = base_time - timedelta(minutes=i)
            session_info.flavor = SandboxFlavor.SMALL  # 1GB each
            session_info.status = SessionStatus.READY
            mock_sessions.append(session_info)
        
        managed_sessions = {}
        for session_info in mock_sessions:
            managed_session = MagicMock()
            managed_session.can_be_evicted.return_value = True
            managed_sessions[session_info.session_id] = managed_session
        
        session_manager._sessions = managed_sessions
        session_manager.get_sessions = AsyncMock(return_value=mock_sessions)
        session_manager.stop_session = AsyncMock(return_value=True)
        
        # Test evicting to free 2GB of memory
        evicted_count = await resource_manager._evict_lru_sessions(0, 2048)
        
        assert evicted_count == 2
        # Should evict 2 oldest sessions to free enough memory
        assert session_manager.stop_session.call_count == 2
    
    @pytest.mark.asyncio
    async def test_lru_eviction_processing_protection(self, resource_manager, session_manager):
        """Test that processing sessions are protected from eviction."""
        mock_sessions = []
        base_time = datetime.now()
        
        # Create sessions where oldest is processing
        for i in range(3):
            session_info = MagicMock()
            session_info.session_id = f"session-{i}"
            session_info.last_accessed = base_time - timedelta(minutes=i)
            session_info.flavor = SandboxFlavor.SMALL
            session_info.status = SessionStatus.READY
            mock_sessions.append(session_info)
        
        managed_sessions = {}
        for i, session_info in enumerate(mock_sessions):
            managed_session = MagicMock()
            # Oldest session (session-2) is processing and cannot be evicted
            managed_session.can_be_evicted.return_value = (i != 2)
            managed_sessions[session_info.session_id] = managed_session
        
        session_manager._sessions = managed_sessions
        session_manager.get_sessions = AsyncMock(return_value=mock_sessions)
        session_manager.stop_session = AsyncMock(return_value=True)
        
        # Try to evict 1 session
        evicted_count = await resource_manager._evict_lru_sessions(1, 0)
        
        assert evicted_count == 1
        # Should evict session-1 (second oldest) since session-2 is protected
        session_manager.stop_session.assert_called_once_with("session-1")
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_with_eviction(self, resource_manager, session_manager):
        """Test resource limit checking with LRU eviction enabled."""
        # Mock get_resource_stats to return stats at limit
        mock_stats = MagicMock()
        mock_stats.active_sessions = 3  # At limit
        mock_stats.total_memory_mb = 3072  # At memory limit
        
        resource_manager.get_resource_stats = AsyncMock(return_value=mock_stats)
        resource_manager._evict_lru_sessions = AsyncMock(return_value=1)
        
        # Mock updated stats after eviction
        updated_stats = MagicMock()
        updated_stats.active_sessions = 2  # After eviction
        updated_stats.total_memory_mb = 2048  # After eviction
        
        resource_manager.get_resource_stats.side_effect = [mock_stats, updated_stats]
        
        # Test requesting a new small session
        result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
        
        assert result is True
        resource_manager._evict_lru_sessions.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_eviction_disabled(self, session_manager):
        """Test resource limit checking with LRU eviction disabled."""
        config = WrapperConfig(
            max_concurrent_sessions=2,
            enable_lru_eviction=False  # Disabled
        )
        resource_manager = ResourceManager(config, session_manager)
        
        # Mock stats showing we're at limit
        mock_stats = MagicMock()
        mock_stats.active_sessions = 2  # At limit
        mock_stats.total_memory_mb = 2048
        
        resource_manager.get_resource_stats = AsyncMock(return_value=mock_stats)
        
        # Should return False without attempting eviction
        result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_no_evictable_sessions(self, resource_manager, session_manager):
        """Test behavior when no sessions can be evicted."""
        # Mock stats at limit
        mock_stats = MagicMock()
        mock_stats.active_sessions = 3
        mock_stats.total_memory_mb = 3072
        
        resource_manager.get_resource_stats = AsyncMock(return_value=mock_stats)
        resource_manager._evict_lru_sessions = AsyncMock(return_value=0)  # No sessions evicted
        
        # Should return False when no sessions can be evicted
        result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_resource_request_with_eviction(self, resource_manager):
        """Test validate_resource_request with successful eviction."""
        resource_manager.check_resource_limits = AsyncMock(return_value=True)
        
        # Should not raise exception when eviction succeeds
        await resource_manager.validate_resource_request(SandboxFlavor.SMALL)
        
        resource_manager.check_resource_limits.assert_called_once_with(SandboxFlavor.SMALL)
    
    @pytest.mark.asyncio
    async def test_validate_resource_request_eviction_fails(self, resource_manager):
        """Test validate_resource_request when eviction fails."""
        resource_manager.check_resource_limits = AsyncMock(return_value=False)
        
        # Mock get_resource_stats for error details
        mock_stats = MagicMock()
        mock_stats.active_sessions = 3
        mock_stats.total_memory_mb = 3072
        
        resource_manager.get_resource_stats = AsyncMock(return_value=mock_stats)
        
        # Should raise ResourceLimitError when eviction fails
        with pytest.raises(ResourceLimitError):
            await resource_manager.validate_resource_request(SandboxFlavor.SMALL)


class TestLRUEvictionIntegration:
    """Integration tests for LRU eviction with real components."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return WrapperConfig(
            server_url="http://localhost:5555",
            max_concurrent_sessions=2,
            max_total_memory_mb=2048,  # 2GB
            enable_lru_eviction=True,
            session_timeout=300
        )
    
    @pytest.mark.asyncio
    async def test_session_touch_on_access(self, config):
        """Test that sessions are touched when accessed."""
        session = ManagedSession("test-id", "python", SandboxFlavor.SMALL, config)
        original_time = session.last_accessed
        
        # Simulate accessing the session
        import time
        time.sleep(0.01)
        session.touch()
        
        assert session.last_accessed > original_time
    
    def test_lru_ordering_logic(self):
        """Test LRU ordering logic with mock sessions."""
        base_time = datetime.now()
        
        # Create sessions with different access times
        sessions = []
        for i in range(3):
            session_info = MagicMock()
            session_info.session_id = f"session-{i}"
            session_info.last_accessed = base_time - timedelta(minutes=i)
            sessions.append(session_info)
        
        # Sort by LRU (oldest first)
        sessions.sort(key=lambda s: s.last_accessed)
        
        # session-2 should be first (oldest), session-0 should be last (newest)
        assert sessions[0].session_id == "session-2"
        assert sessions[-1].session_id == "session-0"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])