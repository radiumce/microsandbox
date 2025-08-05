#!/usr/bin/env python3
"""
Test for the auxiliary methods in MicrosandboxWrapper.

This test specifically verifies that all auxiliary methods required by task 11
are implemented and working correctly:
- get_sessions
- stop_session
- get_volume_mappings
- get_resource_stats
- cleanup_orphan_sandboxes
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the wrapper
sys.path.insert(0, str(Path(__file__).parent))

from microsandbox_wrapper import (
    MicrosandboxWrapper,
    SandboxFlavor,
    WrapperConfig,
    VolumeMapping
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_get_sessions():
    """Test the get_sessions auxiliary method."""
    logger.info("Testing get_sessions method...")
    
    try:
        async with MicrosandboxWrapper() as wrapper:
            # Test getting all sessions (should be empty initially)
            sessions = await wrapper.get_sessions()
            assert isinstance(sessions, list), "get_sessions should return a list"
            logger.info(f"✓ get_sessions() returned {len(sessions)} sessions")
            
            # Test getting specific session (non-existent)
            specific_sessions = await wrapper.get_sessions(session_id="non-existent")
            assert isinstance(specific_sessions, list), "get_sessions with session_id should return a list"
            assert len(specific_sessions) == 0, "Non-existent session should return empty list"
            logger.info("✓ get_sessions(session_id='non-existent') returned empty list")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ get_sessions test failed: {e}")
        return False


async def test_stop_session():
    """Test the stop_session auxiliary method."""
    logger.info("Testing stop_session method...")
    
    try:
        async with MicrosandboxWrapper() as wrapper:
            # Test stopping non-existent session
            result = await wrapper.stop_session("non-existent-session")
            assert isinstance(result, bool), "stop_session should return a boolean"
            assert result is False, "Stopping non-existent session should return False"
            logger.info("✓ stop_session('non-existent-session') returned False")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ stop_session test failed: {e}")
        return False


async def test_get_volume_mappings():
    """Test the get_volume_mappings auxiliary method."""
    logger.info("Testing get_volume_mappings method...")
    
    try:
        # Test with no volume mappings
        async with MicrosandboxWrapper() as wrapper:
            mappings = await wrapper.get_volume_mappings()
            assert isinstance(mappings, list), "get_volume_mappings should return a list"
            logger.info(f"✓ get_volume_mappings() returned {len(mappings)} mappings")
            
            # All items should be VolumeMapping objects
            for mapping in mappings:
                assert isinstance(mapping, VolumeMapping), "Each mapping should be a VolumeMapping object"
            
        # Test with configured volume mappings
        config = WrapperConfig(
            shared_volume_mappings=["/tmp:/sandbox/tmp", "/data:/sandbox/data"]
        )
        async with MicrosandboxWrapper(config=config) as wrapper:
            mappings = await wrapper.get_volume_mappings()
            assert len(mappings) == 2, "Should have 2 configured mappings"
            
            # Check first mapping
            assert mappings[0].host_path == "/tmp", "First mapping host path should be /tmp"
            assert mappings[0].container_path == "/sandbox/tmp", "First mapping container path should be /sandbox/tmp"
            
            # Check second mapping
            assert mappings[1].host_path == "/data", "Second mapping host path should be /data"
            assert mappings[1].container_path == "/sandbox/data", "Second mapping container path should be /sandbox/data"
            
            logger.info("✓ get_volume_mappings() correctly parsed configured mappings")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ get_volume_mappings test failed: {e}")
        return False


async def test_get_resource_stats():
    """Test the get_resource_stats auxiliary method."""
    logger.info("Testing get_resource_stats method...")
    
    try:
        async with MicrosandboxWrapper() as wrapper:
            stats = await wrapper.get_resource_stats()
            
            # Check that stats object has expected attributes
            assert hasattr(stats, 'active_sessions'), "ResourceStats should have active_sessions"
            assert hasattr(stats, 'max_sessions'), "ResourceStats should have max_sessions"
            assert hasattr(stats, 'sessions_by_flavor'), "ResourceStats should have sessions_by_flavor"
            assert hasattr(stats, 'total_memory_mb'), "ResourceStats should have total_memory_mb"
            assert hasattr(stats, 'total_cpus'), "ResourceStats should have total_cpus"
            assert hasattr(stats, 'uptime_seconds'), "ResourceStats should have uptime_seconds"
            
            # Check data types
            assert isinstance(stats.active_sessions, int), "active_sessions should be int"
            assert isinstance(stats.max_sessions, int), "max_sessions should be int"
            assert isinstance(stats.sessions_by_flavor, dict), "sessions_by_flavor should be dict"
            assert isinstance(stats.total_memory_mb, int), "total_memory_mb should be int"
            assert isinstance(stats.total_cpus, float), "total_cpus should be float"
            assert isinstance(stats.uptime_seconds, int), "uptime_seconds should be int"
            
            # Check initial values (no sessions)
            assert stats.active_sessions == 0, "Should have 0 active sessions initially"
            assert stats.total_memory_mb == 0, "Should have 0 memory usage initially"
            assert stats.total_cpus == 0.0, "Should have 0 CPU usage initially"
            assert stats.uptime_seconds >= 0, "Uptime should be non-negative"
            
            logger.info(f"✓ get_resource_stats() returned valid stats: {stats.active_sessions} sessions, {stats.total_memory_mb}MB, {stats.total_cpus} CPUs")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ get_resource_stats test failed: {e}")
        return False


async def test_cleanup_orphan_sandboxes():
    """Test the cleanup_orphan_sandboxes auxiliary method."""
    logger.info("Testing cleanup_orphan_sandboxes method...")
    
    try:
        async with MicrosandboxWrapper() as wrapper:
            # Test orphan cleanup (should return 0 since no orphans exist)
            cleaned_count = await wrapper.cleanup_orphan_sandboxes()
            assert isinstance(cleaned_count, int), "cleanup_orphan_sandboxes should return an int"
            assert cleaned_count >= 0, "Cleaned count should be non-negative"
            logger.info(f"✓ cleanup_orphan_sandboxes() cleaned {cleaned_count} orphan sandboxes")
            
        return True
        
    except Exception as e:
        logger.error(f"✗ cleanup_orphan_sandboxes test failed: {e}")
        return False


async def test_all_auxiliary_methods_exist():
    """Test that all required auxiliary methods exist and are callable."""
    logger.info("Testing that all auxiliary methods exist...")
    
    try:
        wrapper = MicrosandboxWrapper()
        
        # Check that all required methods exist
        required_methods = [
            'get_sessions',
            'stop_session', 
            'get_volume_mappings',
            'get_resource_stats',
            'cleanup_orphan_sandboxes'
        ]
        
        for method_name in required_methods:
            assert hasattr(wrapper, method_name), f"Wrapper should have {method_name} method"
            method = getattr(wrapper, method_name)
            assert callable(method), f"{method_name} should be callable"
            logger.info(f"✓ {method_name} method exists and is callable")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Method existence test failed: {e}")
        return False


async def main():
    """Run all auxiliary method tests."""
    logger.info("Starting auxiliary methods tests...")
    
    tests = [
        test_all_auxiliary_methods_exist,
        test_get_sessions,
        test_stop_session,
        test_get_volume_mappings,
        test_get_resource_stats,
        test_cleanup_orphan_sandboxes
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if await test():
                passed += 1
                logger.info(f"✓ {test.__name__} PASSED")
            else:
                failed += 1
                logger.error(f"✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            logger.error(f"✗ {test.__name__} FAILED with exception: {e}")
    
    logger.info(f"\nTest Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All auxiliary method tests passed!")
        return 0
    else:
        logger.error("❌ Some auxiliary method tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)