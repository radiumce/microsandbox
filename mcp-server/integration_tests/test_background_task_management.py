#!/usr/bin/env python3
"""
Test script for background task management functionality.

This script tests the enhanced background task management features
implemented in task 14, including task status queries, restart
functionality, and graceful shutdown.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the microsandbox_wrapper to the path
sys.path.insert(0, str(Path(__file__).parent))

from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_background_task_status():
    """Test background task status reporting."""
    logger.info("=== Testing Background Task Status ===")
    
    # Create wrapper with test configuration
    config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        cleanup_interval=5,  # Short interval for testing
        orphan_cleanup_interval=10,  # Short interval for testing
        session_timeout=30
    )
    
    wrapper = MicrosandboxWrapper(config=config)
    
    try:
        # Start wrapper
        await wrapper.start()
        logger.info("Wrapper started successfully")
        
        # Wait a moment for tasks to initialize
        await asyncio.sleep(1)
        
        # Get background task status
        task_status = await wrapper.get_background_task_status()
        logger.info(f"Background task status: {task_status}")
        
        # Verify expected fields are present
        assert 'overall_status' in task_status
        assert 'components' in task_status
        assert 'session_manager' in task_status['components']
        assert 'resource_manager' in task_status['components']
        
        # Check session manager task status
        session_status = task_status['components']['session_manager']
        assert 'cleanup_task_healthy' in session_status
        assert 'cleanup_task_exists' in session_status
        
        # Check resource manager task status
        resource_status = task_status['components']['resource_manager']
        assert 'orphan_cleanup_task_healthy' in resource_status
        assert 'orphan_cleanup_task_exists' in resource_status
        
        logger.info("✓ Background task status reporting works correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"Background task status test failed: {e}", exc_info=True)
        return False
    finally:
        try:
            await wrapper.stop()
        except Exception as e:
            logger.error(f"Error stopping wrapper: {e}")


async def test_task_restart_functionality():
    """Test background task restart functionality."""
    logger.info("=== Testing Task Restart Functionality ===")
    
    config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        cleanup_interval=5,
        orphan_cleanup_interval=10,
        session_timeout=30
    )
    
    wrapper = MicrosandboxWrapper(config=config)
    
    try:
        # Start wrapper
        await wrapper.start()
        logger.info("Wrapper started successfully")
        
        # Wait for tasks to initialize
        await asyncio.sleep(1)
        
        # Get initial status
        initial_status = await wrapper.get_background_task_status()
        logger.info(f"Initial status: healthy={initial_status['overall_status']}")
        
        # Test restart when tasks are already healthy (should be no-op)
        restart_result = await wrapper.restart_background_tasks()
        logger.info(f"Restart result (healthy tasks): {restart_result}")
        
        assert restart_result['status'] == 'no_action_needed'
        assert len(restart_result['actions_taken']) == 0
        
        # Pause tasks to simulate unhealthy state
        pause_result = await wrapper.pause_background_tasks()
        logger.info(f"Pause result: {pause_result}")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Check status after pause
        paused_status = await wrapper.get_background_task_status()
        logger.info(f"Status after pause: {paused_status['overall_status']}")
        
        # Restart tasks (should restart the paused tasks)
        restart_result = await wrapper.restart_background_tasks()
        logger.info(f"Restart result (after pause): {restart_result}")
        
        assert restart_result['status'] in ['success', 'partial_success']
        assert len(restart_result['actions_taken']) > 0
        
        # Wait for tasks to stabilize
        await asyncio.sleep(2)
        
        # Check final status
        final_status = await wrapper.get_background_task_status()
        logger.info(f"Final status: {final_status['overall_status']}")
        
        logger.info("✓ Task restart functionality works correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"Task restart test failed: {e}", exc_info=True)
        return False
    finally:
        try:
            await wrapper.stop()
        except Exception as e:
            logger.error(f"Error stopping wrapper: {e}")


async def test_pause_resume_functionality():
    """Test pause and resume functionality."""
    logger.info("=== Testing Pause/Resume Functionality ===")
    
    config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        cleanup_interval=5,
        orphan_cleanup_interval=10,
        session_timeout=30
    )
    
    wrapper = MicrosandboxWrapper(config=config)
    
    try:
        # Start wrapper
        await wrapper.start()
        logger.info("Wrapper started successfully")
        
        # Wait for tasks to initialize
        await asyncio.sleep(1)
        
        # Get initial status
        initial_status = await wrapper.get_background_task_status()
        logger.info(f"Initial status: {initial_status['overall_status']}")
        
        # Pause background tasks
        pause_result = await wrapper.pause_background_tasks()
        logger.info(f"Pause result: {pause_result}")
        
        assert pause_result['status'] in ['success', 'partial_success', 'no_tasks_to_pause']
        
        # Check status after pause
        paused_status = await wrapper.get_background_task_status()
        logger.info(f"Status after pause: {paused_status['overall_status']}")
        
        # Resume background tasks
        resume_result = await wrapper.resume_background_tasks()
        logger.info(f"Resume result: {resume_result}")
        
        assert resume_result['status'] in ['success', 'partial_success', 'no_tasks_to_resume']
        
        # Wait for tasks to stabilize
        await asyncio.sleep(2)
        
        # Check final status
        final_status = await wrapper.get_background_task_status()
        logger.info(f"Final status: {final_status['overall_status']}")
        
        logger.info("✓ Pause/resume functionality works correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"Pause/resume test failed: {e}", exc_info=True)
        return False
    finally:
        try:
            await wrapper.stop()
        except Exception as e:
            logger.error(f"Error stopping wrapper: {e}")


async def test_graceful_shutdown():
    """Test graceful shutdown functionality."""
    logger.info("=== Testing Graceful Shutdown ===")
    
    config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        cleanup_interval=5,
        orphan_cleanup_interval=10,
        session_timeout=30
    )
    
    wrapper = MicrosandboxWrapper(config=config)
    
    try:
        # Start wrapper
        await wrapper.start()
        logger.info("Wrapper started successfully")
        
        # Wait for tasks to initialize
        await asyncio.sleep(1)
        
        # Test graceful shutdown with timeout
        shutdown_start = time.time()
        shutdown_result = await wrapper.graceful_shutdown(timeout_seconds=10.0)
        shutdown_duration = time.time() - shutdown_start
        
        logger.info(f"Graceful shutdown result: {shutdown_result}")
        logger.info(f"Shutdown took {shutdown_duration:.2f} seconds")
        
        assert 'status' in shutdown_result
        assert shutdown_result['status'] in ['success', 'partial_success', 'failed']
        assert 'duration_seconds' in shutdown_result
        assert shutdown_result['duration_seconds'] <= 10.0  # Should not exceed timeout
        
        # Verify wrapper is marked as stopped
        assert not wrapper.is_started()
        
        logger.info("✓ Graceful shutdown works correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"Graceful shutdown test failed: {e}", exc_info=True)
        return False


async def test_health_check_integration():
    """Test health check integration with background tasks."""
    logger.info("=== Testing Health Check Integration ===")
    
    config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        cleanup_interval=5,
        orphan_cleanup_interval=10,
        session_timeout=30
    )
    
    wrapper = MicrosandboxWrapper(config=config)
    
    try:
        # Start wrapper
        await wrapper.start()
        logger.info("Wrapper started successfully")
        
        # Wait for tasks to initialize
        await asyncio.sleep(1)
        
        # Get health check
        health_status = await wrapper.health_check()
        logger.info(f"Health check result: {health_status}")
        
        # Verify expected fields
        assert 'status' in health_status
        assert 'components' in health_status
        assert 'session_manager' in health_status['components']
        assert 'resource_manager' in health_status['components']
        
        # Check that background task health is included
        session_comp = health_status['components']['session_manager']
        resource_comp = health_status['components']['resource_manager']
        
        assert 'background_task_healthy' in session_comp
        assert 'background_task_healthy' in resource_comp
        
        logger.info("✓ Health check integration works correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"Health check integration test failed: {e}", exc_info=True)
        return False
    finally:
        try:
            await wrapper.stop()
        except Exception as e:
            logger.error(f"Error stopping wrapper: {e}")


async def main():
    """Run all background task management tests."""
    logger.info("Starting background task management tests")
    
    tests = [
        ("Background Task Status", test_background_task_status),
        ("Task Restart Functionality", test_task_restart_functionality),
        ("Pause/Resume Functionality", test_pause_resume_functionality),
        ("Graceful Shutdown", test_graceful_shutdown),
        ("Health Check Integration", test_health_check_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running test: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            result = await test_func()
            if result:
                logger.info(f"✓ {test_name} PASSED")
                passed += 1
            else:
                logger.error(f"✗ {test_name} FAILED")
                failed += 1
        except Exception as e:
            logger.error(f"✗ {test_name} FAILED with exception: {e}", exc_info=True)
            failed += 1
        
        # Wait between tests
        await asyncio.sleep(1)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info(f"{'='*60}")
    
    if failed == 0:
        logger.info("🎉 All background task management tests passed!")
        return 0
    else:
        logger.error(f"❌ {failed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)