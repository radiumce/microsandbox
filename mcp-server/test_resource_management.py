"""
Unit tests for resource management.

Tests the ResourceManager class including resource limit checking,
resource usage statistics, orphan sandbox detection, and background cleanup tasks.
"""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from typing import Dict, List

import pytest
import aiohttp

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.resource_manager import ResourceManager
from microsandbox_wrapper.models import (
    SandboxFlavor, SessionStatus, SessionInfo, ResourceStats
)
from microsandbox_wrapper.exceptions import ResourceLimitError


class TestResourceManager:
    """Test ResourceManager initialization and basic functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            max_concurrent_sessions=5,
            max_total_memory_mb=8192,
            orphan_cleanup_interval=300,
            server_url="http://test-server:5555",
            api_key="test-key"
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    def test_resource_manager_initialization(self, config, mock_session_manager):
        """Test ResourceManager initialization."""
        manager = ResourceManager(config, mock_session_manager)
        
        assert manager._config == config
        assert manager._session_manager == mock_session_manager
        assert manager._orphan_cleanup_task is None
        assert isinstance(manager._start_time, float)
        assert manager._last_cleanup_time is None
        assert manager._total_cleanup_cycles == 0
        assert manager._total_orphans_cleaned == 0
        assert manager._last_cleanup_duration == 0.0
        assert manager._cleanup_errors == 0
    
    @pytest.mark.asyncio
    async def test_start_and_stop_manager(self, resource_manager):
        """Test starting and stopping the resource manager."""
        # Start the manager
        await resource_manager.start()
        assert resource_manager._orphan_cleanup_task is not None
        assert not resource_manager._orphan_cleanup_task.done()
        
        # Stop the manager
        await resource_manager.stop()
        assert resource_manager._orphan_cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_start_already_running(self, resource_manager):
        """Test starting the manager when it's already running."""
        # Start the manager
        await resource_manager.start()
        first_task = resource_manager._orphan_cleanup_task
        
        # Try to start again
        await resource_manager.start()
        
        # Should be the same task
        assert resource_manager._orphan_cleanup_task == first_task
        
        # Clean up
        await resource_manager.stop()


class TestResourceLimitChecking:
    """Test resource limit checking functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            max_concurrent_sessions=3,
            max_total_memory_mb=4096,
            orphan_cleanup_interval=300
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_within_limits(self, resource_manager):
        """Test resource limit checking when within limits."""
        # Mock resource stats showing we're within limits
        mock_stats = ResourceStats(
            active_sessions=2,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.SMALL: 2},
            total_memory_mb=2048,
            total_cpus=2.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
            result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_session_limit_exceeded(self, resource_manager):
        """Test resource limit checking when session limit is exceeded."""
        # Mock resource stats showing session limit reached
        mock_stats = ResourceStats(
            active_sessions=3,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.SMALL: 3},
            total_memory_mb=3072,
            total_cpus=3.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
            result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_memory_limit_exceeded(self, resource_manager):
        """Test resource limit checking when memory limit would be exceeded."""
        # Mock resource stats showing memory limit would be exceeded
        mock_stats = ResourceStats(
            active_sessions=2,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.LARGE: 2},
            total_memory_mb=3072,  # 2 * 1536MB (assuming large = 1536MB)
            total_cpus=4.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
            # Requesting LARGE flavor (4096MB) would exceed 4096MB limit
            result = await resource_manager.check_resource_limits(SandboxFlavor.LARGE)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_no_memory_limit(self, resource_manager):
        """Test resource limit checking when no memory limit is configured."""
        # Remove memory limit from config
        resource_manager._config.max_total_memory_mb = None
        
        mock_stats = ResourceStats(
            active_sessions=2,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.LARGE: 2},
            total_memory_mb=8192,  # High memory usage
            total_cpus=4.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
            result = await resource_manager.check_resource_limits(SandboxFlavor.LARGE)
            assert result is True  # Should pass since no memory limit
    
    @pytest.mark.asyncio
    async def test_check_resource_limits_error_handling(self, resource_manager):
        """Test resource limit checking error handling."""
        # Mock get_resource_stats to raise an exception
        with patch.object(resource_manager, 'get_resource_stats', side_effect=Exception("Test error")):
            result = await resource_manager.check_resource_limits(SandboxFlavor.SMALL)
            assert result is False  # Should be conservative and deny request
    
    @pytest.mark.asyncio
    async def test_validate_resource_request_success(self, resource_manager):
        """Test successful resource request validation."""
        with patch.object(resource_manager, 'check_resource_limits', return_value=True):
            # Should not raise an exception
            await resource_manager.validate_resource_request(SandboxFlavor.MEDIUM)
    
    @pytest.mark.asyncio
    async def test_validate_resource_request_session_limit_error(self, resource_manager):
        """Test resource request validation with session limit error."""
        mock_stats = ResourceStats(
            active_sessions=3,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.SMALL: 3},
            total_memory_mb=3072,
            total_cpus=3.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'check_resource_limits', return_value=False):
            with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
                with pytest.raises(ResourceLimitError) as exc_info:
                    await resource_manager.validate_resource_request(SandboxFlavor.SMALL)
                
                assert "sessions" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_validate_resource_request_memory_limit_error(self, resource_manager):
        """Test resource request validation with memory limit error."""
        mock_stats = ResourceStats(
            active_sessions=2,
            max_sessions=3,
            sessions_by_flavor={SandboxFlavor.LARGE: 2},
            total_memory_mb=3072,
            total_cpus=4.0,
            uptime_seconds=100
        )
        
        with patch.object(resource_manager, 'check_resource_limits', return_value=False):
            with patch.object(resource_manager, 'get_resource_stats', return_value=mock_stats):
                with pytest.raises(ResourceLimitError) as exc_info:
                    await resource_manager.validate_resource_request(SandboxFlavor.LARGE)
                
                assert "memory" in str(exc_info.value).lower()


class TestResourceStats:
    """Test resource statistics functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            max_concurrent_sessions=5,
            max_total_memory_mb=8192
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_get_resource_stats_with_active_sessions(self, resource_manager):
        """Test getting resource stats with active sessions."""
        # Mock session data
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
            ),
            SessionInfo(
                session_id="session2",
                template="python",
                flavor=SandboxFlavor.MEDIUM,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.RUNNING,
                namespace="default",
                sandbox_name="session-2"
            ),
            SessionInfo(
                session_id="session3",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.STOPPED,  # This should not be counted
                namespace="default",
                sandbox_name="session-3"
            )
        ]
        
        resource_manager._session_manager.get_sessions.return_value = mock_sessions
        
        stats = await resource_manager.get_resource_stats()
        
        assert stats.active_sessions == 2  # Only non-stopped sessions
        assert stats.max_sessions == 5
        assert stats.sessions_by_flavor[SandboxFlavor.SMALL] == 1
        assert stats.sessions_by_flavor[SandboxFlavor.MEDIUM] == 1
        assert stats.total_memory_mb == SandboxFlavor.SMALL.get_memory_mb() + SandboxFlavor.MEDIUM.get_memory_mb()
        assert stats.total_cpus == SandboxFlavor.SMALL.get_cpus() + SandboxFlavor.MEDIUM.get_cpus()
        assert stats.uptime_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_get_resource_stats_no_sessions(self, resource_manager):
        """Test getting resource stats with no active sessions."""
        resource_manager._session_manager.get_sessions.return_value = []
        
        stats = await resource_manager.get_resource_stats()
        
        assert stats.active_sessions == 0
        assert stats.max_sessions == 5
        assert stats.sessions_by_flavor == {}
        assert stats.total_memory_mb == 0
        assert stats.total_cpus == 0.0
        assert stats.uptime_seconds >= 0
    
    @pytest.mark.asyncio
    async def test_get_resource_stats_error_handling(self, resource_manager):
        """Test resource stats error handling."""
        resource_manager._session_manager.get_sessions.side_effect = Exception("Test error")
        
        stats = await resource_manager.get_resource_stats()
        
        # Should return empty stats on error
        assert stats.active_sessions == 0
        assert stats.max_sessions == 5
        assert stats.sessions_by_flavor == {}
        assert stats.total_memory_mb == 0
        assert stats.total_cpus == 0.0
        assert stats.uptime_seconds >= 0


class TestOrphanCleanup:
    """Test orphan sandbox cleanup functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            max_concurrent_sessions=5,
            orphan_cleanup_interval=60,
            server_url="http://test-server:5555",
            api_key="test-key"
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_cleanup_orphan_sandboxes_no_orphans(self, resource_manager):
        """Test orphan cleanup when no orphans exist."""
        # Mock running sandboxes that all have corresponding sessions
        running_sandboxes = [
            {'namespace': 'default', 'name': 'session-12345678'},
            {'namespace': 'default', 'name': 'session-87654321'}
        ]
        
        active_sessions = [
            SessionInfo(
                session_id="session1",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="session-12345678"
            ),
            SessionInfo(
                session_id="session2",
                template="python",
                flavor=SandboxFlavor.MEDIUM,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.RUNNING,
                namespace="default",
                sandbox_name="session-87654321"
            )
        ]
        
        with patch.object(resource_manager, '_get_running_sandboxes', return_value=running_sandboxes):
            resource_manager._session_manager.get_sessions.return_value = active_sessions
            
            cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
            
            assert cleaned_count == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_orphan_sandboxes_with_orphans(self, resource_manager):
        """Test orphan cleanup when orphans exist."""
        # Mock running sandboxes with some orphans
        running_sandboxes = [
            {'namespace': 'default', 'name': 'session-12345678'},  # Has session
            {'namespace': 'default', 'name': 'session-87654321'},  # Orphan
            {'namespace': 'default', 'name': 'session-11111111'}   # Orphan
        ]
        
        active_sessions = [
            SessionInfo(
                session_id="session1",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="session-12345678"
            )
        ]
        
        with patch.object(resource_manager, '_get_running_sandboxes', return_value=running_sandboxes):
            with patch.object(resource_manager, '_stop_orphan_sandbox', return_value=None) as mock_stop:
                resource_manager._session_manager.get_sessions.return_value = active_sessions
                
                cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
                
                assert cleaned_count == 2
                assert mock_stop.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_orphan_sandboxes_with_failures(self, resource_manager):
        """Test orphan cleanup when some cleanups fail."""
        running_sandboxes = [
            {'namespace': 'default', 'name': 'session-orphan1'},
            {'namespace': 'default', 'name': 'session-orphan2'}
        ]
        
        active_sessions = []  # No active sessions, so both are orphans
        
        async def mock_stop_orphan(sandbox_info):
            if sandbox_info['name'] == 'session-orphan1':
                return None  # Success
            else:
                raise Exception("Failed to stop sandbox")  # Failure
        
        with patch.object(resource_manager, '_get_running_sandboxes', return_value=running_sandboxes):
            with patch.object(resource_manager, '_stop_orphan_sandbox', side_effect=mock_stop_orphan):
                resource_manager._session_manager.get_sessions.return_value = active_sessions
                
                cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
                
                assert cleaned_count == 1  # Only one successful cleanup
    
    @pytest.mark.asyncio
    async def test_cleanup_orphan_sandboxes_error_handling(self, resource_manager):
        """Test orphan cleanup error handling."""
        with patch.object(resource_manager, '_get_running_sandboxes', side_effect=Exception("Test error")):
            cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
            assert cleaned_count == 0
    
    @pytest.mark.asyncio
    async def test_force_orphan_cleanup(self, resource_manager):
        """Test manual orphan cleanup trigger."""
        with patch.object(resource_manager, 'cleanup_orphan_sandboxes', return_value=3) as mock_cleanup:
            result = await resource_manager.force_orphan_cleanup()
            
            assert result == 3
            mock_cleanup.assert_called_once()
            assert resource_manager._total_cleanup_cycles == 1
            assert resource_manager._total_orphans_cleaned == 3
            assert resource_manager._last_cleanup_time is not None
    
    @pytest.mark.asyncio
    async def test_force_orphan_cleanup_with_error(self, resource_manager):
        """Test manual orphan cleanup with error."""
        with patch.object(resource_manager, 'cleanup_orphan_sandboxes', side_effect=Exception("Test error")):
            with pytest.raises(Exception):
                await resource_manager.force_orphan_cleanup()
            
            assert resource_manager._cleanup_errors == 1


class TestHealthAndStatus:
    """Test health monitoring and status reporting."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            max_concurrent_sessions=5,
            max_total_memory_mb=8192,
            orphan_cleanup_interval=300
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    def test_get_resource_health_status(self, resource_manager):
        """Test getting resource health status."""
        status = resource_manager.get_resource_health_status()
        
        assert 'orphan_cleanup_task_running' in status
        assert 'orphan_cleanup_task_healthy' in status
        assert 'orphan_cleanup_interval' in status
        assert 'max_concurrent_sessions' in status
        assert 'max_total_memory_mb' in status
        assert 'manager_uptime_seconds' in status
        assert 'last_cleanup_time' in status
        assert 'total_cleanup_cycles' in status
        assert 'total_orphans_cleaned' in status
        assert 'last_cleanup_duration_seconds' in status
        assert 'cleanup_errors' in status
        
        assert status['orphan_cleanup_task_running'] is False
        assert status['orphan_cleanup_task_healthy'] is False
        assert status['orphan_cleanup_interval'] == 300
        assert status['max_concurrent_sessions'] == 5
        assert status['max_total_memory_mb'] == 8192
        assert status['manager_uptime_seconds'] >= 0
    
    def test_is_orphan_cleanup_healthy_no_task(self, resource_manager):
        """Test orphan cleanup health check when no task exists."""
        assert not resource_manager.is_orphan_cleanup_healthy()
    
    def test_is_orphan_cleanup_healthy_running_task(self, resource_manager):
        """Test orphan cleanup health check with running task."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        resource_manager._orphan_cleanup_task = mock_task
        
        assert resource_manager.is_orphan_cleanup_healthy()
    
    def test_is_orphan_cleanup_healthy_cancelled_task(self, resource_manager):
        """Test orphan cleanup health check with cancelled task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = True
        resource_manager._orphan_cleanup_task = mock_task
        
        assert not resource_manager.is_orphan_cleanup_healthy()
    
    def test_is_orphan_cleanup_healthy_failed_task(self, resource_manager):
        """Test orphan cleanup health check with failed task."""
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.cancelled.return_value = False
        mock_task.result.side_effect = Exception("Task failed")
        resource_manager._orphan_cleanup_task = mock_task
        
        assert not resource_manager.is_orphan_cleanup_healthy()
    
    def test_get_background_task_status(self, resource_manager):
        """Test getting background task status."""
        status = resource_manager.get_background_task_status()
        
        assert 'orphan_cleanup_task_exists' in status
        assert 'orphan_cleanup_task_healthy' in status
        assert 'orphan_cleanup_interval_seconds' in status
        assert 'manager_uptime_seconds' in status
        assert 'total_cleanup_cycles' in status
        assert 'total_orphans_cleaned' in status
        assert 'cleanup_errors' in status
        assert 'last_cleanup_time' in status
        assert 'last_cleanup_duration_seconds' in status
        
        assert status['orphan_cleanup_task_exists'] is False
        assert status['orphan_cleanup_task_healthy'] is False
        assert status['orphan_cleanup_interval_seconds'] == 300
        assert status['manager_uptime_seconds'] >= 0
    
    def test_get_orphan_cleanup_stats(self, resource_manager):
        """Test getting orphan cleanup statistics."""
        # Set some test data
        resource_manager._total_cleanup_cycles = 10
        resource_manager._total_orphans_cleaned = 5
        resource_manager._cleanup_errors = 1
        resource_manager._last_cleanup_time = time.time()
        resource_manager._last_cleanup_duration = 2.5
        
        stats = resource_manager.get_orphan_cleanup_stats()
        
        assert stats['total_cleanup_cycles'] == 10
        assert stats['total_orphans_cleaned'] == 5
        assert stats['cleanup_errors'] == 1
        assert stats['last_cleanup_time'] is not None
        assert stats['last_cleanup_duration_seconds'] == 2.5
        assert stats['cleanup_interval_seconds'] == 300
        assert stats['average_orphans_per_cycle'] == 0.5
        assert stats['cleanup_success_rate'] == 0.9  # 9/10 successful
    
    @pytest.mark.asyncio
    async def test_restart_orphan_cleanup_if_needed_healthy(self, resource_manager):
        """Test restarting orphan cleanup when it's already healthy."""
        with patch.object(resource_manager, 'is_orphan_cleanup_healthy', return_value=True):
            result = await resource_manager.restart_orphan_cleanup_if_needed()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_restart_orphan_cleanup_if_needed_unhealthy(self, resource_manager):
        """Test restarting orphan cleanup when it's unhealthy."""
        # Create a mock task that can be awaited
        async def mock_task_coroutine():
            pass
        
        mock_task = asyncio.create_task(mock_task_coroutine())
        mock_task.cancel()  # Cancel it so it's done
        
        # Wait for it to be cancelled
        try:
            await mock_task
        except asyncio.CancelledError:
            pass
        
        resource_manager._orphan_cleanup_task = mock_task
        
        with patch.object(resource_manager, 'is_orphan_cleanup_healthy', return_value=False):
            with patch('asyncio.create_task') as mock_create_task:
                new_task = MagicMock()
                mock_create_task.return_value = new_task
                
                result = await resource_manager.restart_orphan_cleanup_if_needed()
                
                assert result is True
                mock_create_task.assert_called_once()
                assert resource_manager._orphan_cleanup_task == new_task


class TestRunningSandboxes:
    """Test running sandbox information and management."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            server_url="http://test-server:5555",
            api_key="test-key"
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_get_running_sandboxes_info(self, resource_manager):
        """Test getting detailed running sandbox information."""
        running_sandboxes = [
            {
                'namespace': 'default',
                'name': 'session-12345678',
                'cpu_usage': 25.5,
                'memory_usage': 512,
                'disk_usage': 1024
            },
            {
                'namespace': 'default',
                'name': 'session-orphan1',
                'cpu_usage': 10.0,
                'memory_usage': 256,
                'disk_usage': 512
            }
        ]
        
        active_sessions = [
            SessionInfo(
                session_id="session1",
                template="python",
                flavor=SandboxFlavor.SMALL,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                status=SessionStatus.READY,
                namespace="default",
                sandbox_name="session-12345678"
            )
        ]
        
        with patch.object(resource_manager, '_get_running_sandboxes', return_value=running_sandboxes):
            resource_manager._session_manager.get_sessions.return_value = active_sessions
            
            info = await resource_manager.get_running_sandboxes_info()
            
            assert info['total_running_sandboxes'] == 2
            assert info['managed_sandboxes_count'] == 1
            assert info['orphan_sandboxes_count'] == 1
            assert info['active_sessions_count'] == 1
            assert info['resource_usage']['total_memory_mb'] == 768
            assert info['resource_usage']['total_cpu_percent'] == 35.5
            assert info['resource_usage']['total_disk_bytes'] == 1536
            assert len(info['managed_sandboxes']) == 1
            assert len(info['orphan_sandboxes']) == 1
            assert 'query_timestamp' in info
    
    @pytest.mark.asyncio
    async def test_get_running_sandboxes_info_error(self, resource_manager):
        """Test getting running sandbox information with error."""
        with patch.object(resource_manager, '_get_running_sandboxes', side_effect=Exception("Test error")):
            info = await resource_manager.get_running_sandboxes_info()
            
            assert 'error' in info
            assert info['total_running_sandboxes'] == 0
            assert info['managed_sandboxes_count'] == 0
            assert info['orphan_sandboxes_count'] == 0
            assert info['active_sessions_count'] == 0


class TestOrphanSandboxStopping:
    """Test orphan sandbox stopping functionality."""
    
    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return WrapperConfig(
            server_url="http://test-server:5555",
            api_key="test-key"
        )
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        return AsyncMock()
    
    @pytest.fixture
    def resource_manager(self, config, mock_session_manager):
        """Create a resource manager instance."""
        return ResourceManager(config, mock_session_manager)
    
    @pytest.mark.asyncio
    async def test_stop_orphan_sandbox_error_handling(self, resource_manager):
        """Test that stopping orphan sandbox handles errors properly."""
        sandbox_info = {
            'namespace': 'default',
            'name': 'session-orphan1'
        }
        
        # The method should handle any exception and re-raise it
        with pytest.raises(Exception):
            await resource_manager._stop_orphan_sandbox(sandbox_info)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])