#!/usr/bin/env python3
"""
Basic test for the MicrosandboxWrapper implementation.

This test verifies that the wrapper can be instantiated and basic
functionality works as expected.
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
    ConfigurationError
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_wrapper_initialization():
    """Test that the wrapper can be initialized with default configuration."""
    logger.info("Testing wrapper initialization...")
    
    try:
        # Test with default configuration from environment
        wrapper = MicrosandboxWrapper()
        logger.info(f"✓ Wrapper initialized with config: {wrapper.get_config()}")
        
        # Test with explicit configuration
        config = WrapperConfig(
            server_url="http://localhost:5555",
            session_timeout=1800,
            max_concurrent_sessions=5
        )
        wrapper2 = MicrosandboxWrapper(config=config)
        logger.info(f"✓ Wrapper initialized with explicit config: {wrapper2.get_config()}")
        
        # Test with parameter overrides
        wrapper3 = MicrosandboxWrapper(
            server_url="http://example.com:5555",
            api_key="test-key"
        )
        logger.info(f"✓ Wrapper initialized with parameter overrides")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Wrapper initialization failed: {e}")
        return False


async def test_wrapper_lifecycle():
    """Test wrapper start/stop lifecycle."""
    logger.info("Testing wrapper lifecycle...")
    
    try:
        wrapper = MicrosandboxWrapper()
        
        # Test initial state
        assert not wrapper.is_started(), "Wrapper should not be started initially"
        logger.info("✓ Initial state correct")
        
        # Test start
        await wrapper.start()
        assert wrapper.is_started(), "Wrapper should be started after start()"
        logger.info("✓ Wrapper started successfully")
        
        # Test health check
        health = await wrapper.health_check()
        logger.info(f"✓ Health check: {health['status']}")
        
        # Test stop
        await wrapper.stop()
        assert not wrapper.is_started(), "Wrapper should not be started after stop()"
        logger.info("✓ Wrapper stopped successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Wrapper lifecycle test failed: {e}")
        return False


async def test_context_manager():
    """Test wrapper as async context manager."""
    logger.info("Testing wrapper as context manager...")
    
    try:
        async with MicrosandboxWrapper() as wrapper:
            assert wrapper.is_started(), "Wrapper should be started in context"
            logger.info("✓ Context manager entry works")
            
            # Test basic operations
            sessions = await wrapper.get_sessions()
            logger.info(f"✓ Got sessions: {len(sessions)} active")
            
            stats = await wrapper.get_resource_stats()
            logger.info(f"✓ Got resource stats: {stats.active_sessions} active sessions")
            
            volume_mappings = await wrapper.get_volume_mappings()
            logger.info(f"✓ Got volume mappings: {len(volume_mappings)} mappings")
        
        # Wrapper should be stopped after context exit
        logger.info("✓ Context manager exit works")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Context manager test failed: {e}")
        return False


async def test_configuration_validation():
    """Test configuration validation."""
    logger.info("Testing configuration validation...")
    
    try:
        # Test invalid server URL
        try:
            config = WrapperConfig(server_url="invalid-url")
            config._validate()
            logger.error("✗ Should have failed with invalid server URL")
            return False
        except ConfigurationError:
            logger.info("✓ Invalid server URL correctly rejected")
        
        # Test invalid cleanup interval
        try:
            config = WrapperConfig(
                session_timeout=60,
                cleanup_interval=120  # Greater than session timeout
            )
            config._validate()
            logger.error("✗ Should have failed with invalid cleanup interval")
            return False
        except ConfigurationError:
            logger.info("✓ Invalid cleanup interval correctly rejected")
        
        # Test valid configuration
        config = WrapperConfig(
            server_url="http://localhost:5555",
            session_timeout=1800,
            cleanup_interval=60,
            max_concurrent_sessions=10
        )
        config._validate()
        logger.info("✓ Valid configuration accepted")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Configuration validation test failed: {e}")
        return False


async def main():
    """Run all basic tests."""
    logger.info("Starting basic wrapper tests...")
    
    tests = [
        test_wrapper_initialization,
        test_wrapper_lifecycle,
        test_context_manager,
        test_configuration_validation
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
        logger.info("🎉 All basic tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)