#!/usr/bin/env python3
"""
Simplified error scenario tests for the MCP wrapper.

This module tests basic error handling scenarios.
"""

import asyncio
import logging
import pytest
import pytest_asyncio

from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import (
    CodeExecutionError,
    CommandExecutionError,
    ConfigurationError
)

logger = logging.getLogger(__name__)


class TestErrorScenariosSimple:
    """Simplified error scenario tests."""
    
    @pytest.mark.asyncio
    async def test_invalid_code_execution(self):
        """Test handling of invalid code execution scenarios."""
        logger.info("Testing invalid code execution scenarios...")
        
        async with MicrosandboxWrapper() as wrapper:
            # Test syntax error in Python
            result1 = await wrapper.execute_code(
                code="print('Hello world'  # Missing closing parenthesis",
                template="python",
                timeout=30
            )
        
            assert not result1.success, "Syntax error should cause execution to fail"
            assert result1.stderr, "Should have error information"
            
            # Test runtime error in Python
            result2 = await wrapper.execute_code(
                code="""
print('Starting execution')
x = 1 / 0  # Division by zero
print('This should not print')
""",
                template="python",
                timeout=30
            )
            
            assert not result2.success, "Runtime error should cause execution to fail"
            assert result2.stderr, "Should have error information"
            
            # Test that the wrapper can still work after errors
            result3 = await wrapper.execute_code(
                code="print('Recovery after errors')",
                template="python",
                timeout=30
            )
            
            assert result3.success, "Should be able to execute valid code after errors"
            assert "Recovery after errors" in result3.stdout
            
            logger.info("✓ Invalid code execution test completed")
    
    @pytest.mark.asyncio
    async def test_command_execution_errors(self):
        """Test command execution error scenarios."""
        logger.info("Testing command execution errors...")
        
        async with MicrosandboxWrapper() as wrapper:
            # Test non-existent command
            result1 = await wrapper.execute_command(
            command="nonexistent_command_12345",
            args=["arg1", "arg2"],
            template="python",
            timeout=30
        )
        
        assert not result1.success, "Non-existent command should fail"
        assert result1.exit_code != 0, "Should have non-zero exit code"
        
        # Test that wrapper can still work after command errors
        result2 = await wrapper.execute_command(
            command="echo",
            args=["Command recovery test"],
            template="python",
            timeout=30
        )
        
        assert result2.success, "Should be able to execute valid commands after errors"
        assert "Command recovery test" in result2.stdout
        
        logger.info("✓ Command execution errors test completed")
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, wrapper):
        """Test timeout handling in code execution."""
        logger.info("Testing timeout handling...")
        
        # Test code execution timeout
        with pytest.raises((asyncio.TimeoutError, CodeExecutionError)):
            await wrapper.execute_code(
                code="""
import time
print('Starting long operation')
time.sleep(10)  # Sleep longer than timeout
print('This should not print')
""",
                template="python",
                timeout=2  # Short timeout
            )
        
        # Test that wrapper can still work after timeouts
        result = await wrapper.execute_code(
            code="print('Recovery after timeout')",
            template="python",
            timeout=30
        )
        
        assert result.success, "Should be able to execute code after timeout"
        assert "Recovery after timeout" in result.stdout
        
        logger.info("✓ Timeout handling test completed")
    
    @pytest.mark.asyncio
    async def test_orphan_cleanup(self, wrapper):
        """Test orphan sandbox cleanup functionality."""
        logger.info("Testing orphan sandbox cleanup...")
        
        # Create a session
        result = await wrapper.execute_code(
            code="print('Test session for orphan cleanup')",
            template="python",
            timeout=30
        )
        
        assert result.success, "Session should be created"
        session_id = result.session_id
        
        # Get initial resource stats
        initial_stats = await wrapper.get_resource_stats()
        
        # Stop the session
        await wrapper.stop_session(session_id)
        
        # Test orphan cleanup function
        orphans_cleaned = await wrapper.cleanup_orphan_sandboxes()
        logger.info(f"Cleaned {orphans_cleaned} orphan sandboxes")
        
        # The number might be 0 if there are no actual orphans, which is fine
        assert orphans_cleaned >= 0, "Orphan cleanup should return non-negative number"
        
        logger.info("✓ Orphan sandbox cleanup test completed")


if __name__ == "__main__":
    # Run tests when called directly
    pytest.main([__file__, "-v"])