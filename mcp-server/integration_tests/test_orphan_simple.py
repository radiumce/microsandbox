#!/usr/bin/env python3
"""
Simple test for orphan sandbox detection logic.

This test focuses on the core logic without complex HTTP mocking.
"""

import asyncio
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

# Add the microsandbox_wrapper to the path
sys.path.insert(0, 'microsandbox_wrapper')

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.resource_manager import ResourceManager
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus, SessionInfo


class MockSessionManager:
    """Mock session manager for testing"""
    
    def __init__(self, sessions=None):
        self.sessions = sessions or []
    
    async def get_sessions(self):
        return self.sessions


async def test_orphan_identification():
    """Test the core orphan identification logic"""
    print("Testing orphan identification logic...")
    
    # Create test configuration
    config = WrapperConfig(server_url="http://localhost:5555")
    
    # Create mock sessions (active sandboxes managed by session manager)
    mock_sessions = [
        SessionInfo(
            session_id="session-1",
            template="python",
            flavor=SandboxFlavor.SMALL,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            status=SessionStatus.READY,
            namespace="default",
            sandbox_name="session-12345678"
        ),
        SessionInfo(
            session_id="session-2",
            template="node",
            flavor=SandboxFlavor.MEDIUM,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            status=SessionStatus.RUNNING,
            namespace="default",
            sandbox_name="session-87654321"
        )
    ]
    
    # Create mock session manager
    session_manager = MockSessionManager(mock_sessions)
    
    # Create resource manager
    resource_manager = ResourceManager(config, session_manager)
    
    # Mock running sandboxes from server (including orphans)
    mock_running_sandboxes = [
        {
            "namespace": "default",
            "name": "session-12345678",  # Managed by session-1
            "running": True,
            "cpu_usage": 15.5,
            "memory_usage": 512,
            "disk_usage": 1024000
        },
        {
            "namespace": "default", 
            "name": "session-87654321",  # Managed by session-2
            "running": True,
            "cpu_usage": 25.0,
            "memory_usage": 1024,
            "disk_usage": 2048000
        },
        {
            "namespace": "default",
            "name": "orphan-sandbox-1",  # ORPHAN - not managed
            "running": True,
            "cpu_usage": 5.0,
            "memory_usage": 256,
            "disk_usage": 512000
        },
        {
            "namespace": "test",
            "name": "orphan-sandbox-2",  # ORPHAN - not managed
            "running": True,
            "cpu_usage": 10.0,
            "memory_usage": 512,
            "disk_usage": 1024000
        }
    ]
    
    # Mock the _get_running_sandboxes method directly
    with patch.object(resource_manager, '_get_running_sandboxes', return_value=mock_running_sandboxes):
        # Test the cleanup_orphan_sandboxes method (but mock the actual stopping)
        with patch.object(resource_manager, '_stop_orphan_sandbox', new_callable=AsyncMock) as mock_stop:
            cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
            
            print(f"Identified and would clean {cleaned_count} orphan sandboxes")
            
            # Verify results
            assert cleaned_count == 2, f"Expected 2 orphans, got {cleaned_count}"
            
            # Verify the correct orphans were identified for cleanup
            assert mock_stop.call_count == 2
            
            # Get the sandbox info that was passed to _stop_orphan_sandbox
            stopped_sandboxes = []
            for call in mock_stop.call_args_list:
                sandbox_info = call[0][0]  # First argument
                stopped_sandboxes.append(f"{sandbox_info['namespace']}/{sandbox_info['name']}")
            
            expected_orphans = {"default/orphan-sandbox-1", "test/orphan-sandbox-2"}
            actual_orphans = set(stopped_sandboxes)
            
            assert actual_orphans == expected_orphans, f"Expected {expected_orphans}, got {actual_orphans}"
            
            print("✓ Orphan identification test passed!")


async def test_no_orphans():
    """Test case where there are no orphan sandboxes"""
    print("\nTesting no orphans scenario...")
    
    config = WrapperConfig(server_url="http://localhost:5555")
    
    # Create mock session with matching sandbox
    mock_sessions = [
        SessionInfo(
            session_id="session-1",
            template="python",
            flavor=SandboxFlavor.SMALL,
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            status=SessionStatus.READY,
            namespace="default",
            sandbox_name="session-12345678"
        )
    ]
    
    session_manager = MockSessionManager(mock_sessions)
    resource_manager = ResourceManager(config, session_manager)
    
    # Mock running sandboxes - all are managed
    mock_running_sandboxes = [
        {
            "namespace": "default",
            "name": "session-12345678",  # Managed by session-1
            "running": True,
            "cpu_usage": 15.5,
            "memory_usage": 512,
            "disk_usage": 1024000
        }
    ]
    
    with patch.object(resource_manager, '_get_running_sandboxes', return_value=mock_running_sandboxes):
        with patch.object(resource_manager, '_stop_orphan_sandbox', new_callable=AsyncMock) as mock_stop:
            cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
            
            print(f"Found {cleaned_count} orphan sandboxes (expected 0)")
            
            assert cleaned_count == 0
            assert mock_stop.call_count == 0
            
            print("✓ No orphans test passed!")


async def test_all_orphans():
    """Test case where all running sandboxes are orphans"""
    print("\nTesting all orphans scenario...")
    
    config = WrapperConfig(server_url="http://localhost:5555")
    
    # Empty session manager (no active sessions)
    session_manager = MockSessionManager([])
    resource_manager = ResourceManager(config, session_manager)
    
    # Mock running sandboxes - all are orphans
    mock_running_sandboxes = [
        {
            "namespace": "default",
            "name": "orphan-1",
            "running": True,
            "cpu_usage": 15.5,
            "memory_usage": 512,
            "disk_usage": 1024000
        },
        {
            "namespace": "default",
            "name": "orphan-2",
            "running": True,
            "cpu_usage": 25.0,
            "memory_usage": 1024,
            "disk_usage": 2048000
        }
    ]
    
    with patch.object(resource_manager, '_get_running_sandboxes', return_value=mock_running_sandboxes):
        with patch.object(resource_manager, '_stop_orphan_sandbox', new_callable=AsyncMock) as mock_stop:
            cleaned_count = await resource_manager.cleanup_orphan_sandboxes()
            
            print(f"Found {cleaned_count} orphan sandboxes (expected 2)")
            
            assert cleaned_count == 2
            assert mock_stop.call_count == 2
            
            print("✓ All orphans test passed!")


async def test_statistics_tracking():
    """Test that statistics are properly tracked"""
    print("\nTesting statistics tracking...")
    
    config = WrapperConfig(server_url="http://localhost:5555")
    session_manager = MockSessionManager([])
    resource_manager = ResourceManager(config, session_manager)
    
    # Check initial statistics
    initial_stats = resource_manager.get_orphan_cleanup_stats()
    assert initial_stats['total_cleanup_cycles'] == 0
    assert initial_stats['total_orphans_cleaned'] == 0
    assert initial_stats['cleanup_errors'] == 0
    
    # Mock a successful cleanup
    with patch.object(resource_manager, 'cleanup_orphan_sandboxes', return_value=3):
        cleaned = await resource_manager.force_orphan_cleanup()
        assert cleaned == 3
    
    # Check updated statistics
    stats = resource_manager.get_orphan_cleanup_stats()
    assert stats['total_cleanup_cycles'] == 1
    assert stats['total_orphans_cleaned'] == 3
    assert stats['cleanup_errors'] == 0
    assert stats['average_orphans_per_cycle'] == 3.0
    assert stats['cleanup_success_rate'] == 1.0
    
    print("✓ Statistics tracking test passed!")


async def main():
    """Run all tests"""
    print("Starting orphan cleanup logic tests...\n")
    
    try:
        await test_orphan_identification()
        await test_no_orphans()
        await test_all_orphans()
        await test_statistics_tracking()
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())