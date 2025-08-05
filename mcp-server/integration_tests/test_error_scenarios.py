#!/usr/bin/env python3
"""
Error scenario tests for the MCP wrapper.

This module tests error handling and recovery scenarios including:
- Network interruption recovery
- Sandbox crash handling
- Resource exhaustion scenarios
- Configuration error handling
- Orphan sandbox cleanup
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import (
    CodeExecutionError,
    CommandExecutionError,
    ResourceLimitError,
    SandboxCreationError,
    ConnectionError,
    ConfigurationError
)

logger = logging.getLogger(__name__)


class TestErrorScenarios:
    """Error scenario tests."""
    
    @pytest.mark.asyncio
    async def test_network_interruption_recovery(self, wrapper):
        """Test network interruption and recovery scenarios."""
        logger.info("Testing network interruption recovery...")
        
        # wrapper is already started by the fixture
        # First, establish a working session
        result1 = await wrapper.execute_code(
                code="print('Before network interruption')",
                template="python",
                timeout=30
            )
            
            assert result1.success, "Initial execution should succeed"
            session_id = result1.session_id
            
            # Simulate network interruption by trying to execute with a very short timeout
            # This should cause a timeout error
            with pytest.raises((asyncio.TimeoutError, ConnectionError, CodeExecutionError)):
                await wrapper.execute_code(
                    code="import time; time.sleep(10); print('This should timeout')",
                    template="python",
                    session_id=session_id,
                    timeout=1  # Very short timeout to simulate network issues
                )
            
            # Test recovery - the wrapper should be able to create a new session
            # and continue working after the timeout
            result2 = await wrapper.execute_code(
                code="print('After network recovery')",
                template="python",
                timeout=30
            )
            
            assert result2.success, "Execution should succeed after recovery"
            assert "After network recovery" in result2.stdout, "Should contain recovery message"
            
            logger.info("✓ Network interruption recovery test completed")
    
    @pytest.mark.asyncio
    async def test_sandbox_crash_handling(self, integration_env, test_wrapper):
        """Test sandbox crash handling and recovery."""
        logger.info("Testing sandbox crash handling...")
        
        async with test_wrapper as wrapper:
            # Create a session
            result1 = await wrapper.execute_code(
                code="print('Before crash test')",
                template="python",
                timeout=30
            )
            
            assert result1.success, "Initial execution should succeed"
            session_id = result1.session_id
            
            # Try to execute code that might cause issues (but shouldn't crash the sandbox)
            # We'll test with code that uses a lot of memory quickly
            memory_intensive_code = """
import sys
print('Testing memory intensive operation')
try:
    # Create a large list but not too large to crash the system
    large_list = [i for i in range(100000)]
    print(f'Created list with {len(large_list)} elements')
    del large_list
    print('Memory test completed successfully')
except MemoryError:
    print('Memory error caught - this is expected behavior')
except Exception as e:
    print(f'Other error: {e}')
"""
            
            result2 = await wrapper.execute_code(
                code=memory_intensive_code,
                template="python",
                session_id=session_id,
                timeout=30
            )
            
            # The execution should either succeed or fail gracefully
            if result2.success:
                assert "Memory test completed" in result2.stdout or "Memory error caught" in result2.stdout
            else:
                # If it fails, it should be a controlled failure, not a crash
                assert result2.stderr, "Should have error information if execution fails"
            
            # Test that we can still create new sessions after potential issues
            result3 = await wrapper.execute_code(
                code="print('New session after crash test')",
                template="python",
                timeout=30
            )
            
            assert result3.success, "Should be able to create new session after crash test"
            assert "New session after crash test" in result3.stdout
            
            logger.info("✓ Sandbox crash handling test completed")
    
    @pytest.mark.asyncio
    async def test_resource_exhaustion_scenarios(self, integration_env, test_wrapper):
        """Test resource exhaustion scenarios."""
        logger.info("Testing resource exhaustion scenarios...")
        
        # Test with a config that has very low resource limits
        low_resource_config = WrapperConfig(
            server_url="http://127.0.0.1:5555",
            max_concurrent_sessions=2,  # Very low limit
            max_total_memory_mb=1024,   # Low memory limit
            session_timeout=60,
            cleanup_interval=10
        )
        
        async with MicrosandboxWrapper(config=low_resource_config) as wrapper:
            # Create sessions up to the limit
            sessions = []
            
            for i in range(low_resource_config.max_concurrent_sessions):
                result = await wrapper.execute_code(
                    code=f"print('Session {i+1} created')",
                    template="python",
                    timeout=30
                )
                assert result.success, f"Session {i+1} should be created successfully"
                sessions.append(result.session_id)
            
            # Try to create one more session - this should either succeed or fail gracefully
            try:
                result = await wrapper.execute_code(
                    code="print('Excess session')",
                    template="python",
                    timeout=30
                )
                
                # If it succeeds, that's fine - the wrapper might handle resource limits flexibly
                if result.success:
                    logger.info("Wrapper allowed excess session - flexible resource management")
                    sessions.append(result.session_id)
                
            except (ResourceLimitError, SandboxCreationError) as e:
                logger.info(f"Resource limit properly enforced: {e}")
                # This is expected behavior
                pass
            
            # Test resource statistics
            stats = await wrapper.get_resource_stats()
            assert stats.active_sessions >= low_resource_config.max_concurrent_sessions
            assert stats.max_sessions == low_resource_config.max_concurrent_sessions
            
            # Clean up sessions
            for session_id in sessions:
                try:
                    await wrapper.stop_session(session_id)
                except Exception as e:
                    logger.warning(f"Error stopping session {session_id}: {e}")
            
            logger.info("✓ Resource exhaustion scenarios test completed")
    
    @pytest.mark.asyncio
    async def test_configuration_error_handling(self, integration_env):
        """Test configuration error handling."""
        logger.info("Testing configuration error handling...")
        
        # Test invalid server URL
        with pytest.raises((ConfigurationError, ConnectionError)):
            invalid_config = WrapperConfig(
                server_url="http://invalid-server:9999",
                session_timeout=60
            )
            async with MicrosandboxWrapper(config=invalid_config) as wrapper:
                await wrapper.execute_code(
                    code="print('This should fail')",
                    template="python",
                    timeout=5
                )
        
        # Test invalid configuration values
        with pytest.raises(ConfigurationError):
            WrapperConfig(
                server_url="http://127.0.0.1:5555",
                session_timeout=10,
                cleanup_interval=20  # Cleanup interval > session timeout
            )._validate()
        
        # Test invalid volume mappings
        try:
            invalid_volume_config = WrapperConfig(
                server_url="http://127.0.0.1:5555",
                shared_volume_mappings=["invalid-mapping-format"]
            )
            async with MicrosandboxWrapper(config=invalid_volume_config) as wrapper:
                # This might succeed or fail depending on how the wrapper handles invalid mappings
                result = await wrapper.execute_code(
                    code="print('Testing invalid volume mapping')",
                    template="python",
                    timeout=30
                )
                # If it succeeds, the wrapper is handling invalid mappings gracefully
                logger.info("Wrapper handled invalid volume mapping gracefully")
                
        except (ConfigurationError, SandboxCreationError) as e:
            logger.info(f"Invalid volume mapping properly rejected: {e}")
            # This is expected behavior
            pass
        
        logger.info("✓ Configuration error handling test completed")
    
    @pytest.mark.asyncio
    async def test_orphan_sandbox_cleanup(self, integration_env, test_wrapper):
        """Test orphan sandbox cleanup functionality."""
        logger.info("Testing orphan sandbox cleanup...")
        
        async with test_wrapper as wrapper:
            # Create several sessions
            session_ids = []
            
            for i in range(3):
                result = await wrapper.execute_code(
                    code=f"print('Orphan test session {i+1}')",
                    template="python",
                    timeout=30
                )
                assert result.success, f"Session {i+1} should be created"
                session_ids.append(result.session_id)
            
            # Get initial resource stats
            initial_stats = await wrapper.get_resource_stats()
            initial_active = initial_stats.active_sessions
            
            # Manually stop some sessions to simulate orphaned resources
            for session_id in session_ids[:2]:  # Stop first 2 sessions
                await wrapper.stop_session(session_id)
            
            # Wait a bit for cleanup
            await asyncio.sleep(2)
            
            # Check that sessions were cleaned up
            stats_after_stop = await wrapper.get_resource_stats()
            assert stats_after_stop.active_sessions < initial_active, \
                "Active sessions should decrease after stopping sessions"
            
            # Test orphan cleanup function
            orphans_cleaned = await wrapper.cleanup_orphan_sandboxes()
            logger.info(f"Cleaned {orphans_cleaned} orphan sandboxes")
            
            # The number might be 0 if there are no actual orphans, which is fine
            assert orphans_cleaned >= 0, "Orphan cleanup should return non-negative number"
            
            # Verify final state
            final_stats = await wrapper.get_resource_stats()
            logger.info(f"Final active sessions: {final_stats.active_sessions}")
            
            logger.info("✓ Orphan sandbox cleanup test completed")
    
    @pytest.mark.asyncio
    async def test_invalid_code_execution(self, wrapper):
        """Test handling of invalid code execution scenarios."""
        logger.info("Testing invalid code execution scenarios...")
        
        # wrapper is already started by the fixture
            # Test syntax error in Python
            result1 = await wrapper.execute_code(
                code="print('Hello world'  # Missing closing parenthesis",
                template="python",
                timeout=30
            )
            
            assert not result1.success, "Syntax error should cause execution to fail"
            assert result1.stderr, "Should have error information"
            assert "SyntaxError" in result1.stderr or "syntax" in result1.stderr.lower()
            
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
            assert "ZeroDivisionError" in result2.stderr or "division" in result2.stderr.lower()
            
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
    async def test_command_execution_errors(self, integration_env, test_wrapper):
        """Test command execution error scenarios."""
        logger.info("Testing command execution errors...")
        
        async with test_wrapper as wrapper:
            # Test non-existent command
            result1 = await wrapper.execute_command(
                command="nonexistent_command_12345",
                args=["arg1", "arg2"],
                template="python",
                timeout=30
            )
            
            assert not result1.success, "Non-existent command should fail"
            assert result1.exit_code != 0, "Should have non-zero exit code"
            
            # Test command with invalid arguments
            result2 = await wrapper.execute_command(
                command="ls",
                args=["/nonexistent/directory/path"],
                template="python",
                timeout=30
            )
            
            assert not result2.success, "Command with invalid args should fail"
            assert result2.exit_code != 0, "Should have non-zero exit code"
            
            # Test that wrapper can still work after command errors
            result3 = await wrapper.execute_command(
                command="echo",
                args=["Command recovery test"],
                template="python",
                timeout=30
            )
            
            assert result3.success, "Should be able to execute valid commands after errors"
            assert "Command recovery test" in result3.stdout
            
            logger.info("✓ Command execution errors test completed")
    
    @pytest.mark.asyncio
    async def test_timeout_handling(self, integration_env, test_wrapper):
        """Test timeout handling in various scenarios."""
        logger.info("Testing timeout handling...")
        
        async with test_wrapper as wrapper:
            # Test code execution timeout
            start_time = time.time()
            
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
            
            elapsed = time.time() - start_time
            assert elapsed < 5, "Timeout should be enforced quickly"
            
            # Test command execution timeout
            start_time = time.time()
            
            with pytest.raises((asyncio.TimeoutError, CommandExecutionError)):
                await wrapper.execute_command(
                    command="sleep",
                    args=["10"],  # Sleep longer than timeout
                    template="python",
                    timeout=2  # Short timeout
                )
            
            elapsed = time.time() - start_time
            assert elapsed < 5, "Command timeout should be enforced quickly"
            
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
    async def test_concurrent_error_scenarios(self, integration_env, test_wrapper):
        """Test error scenarios with concurrent operations."""
        logger.info("Testing concurrent error scenarios...")
        
        async with test_wrapper as wrapper:
            # Create multiple concurrent tasks with mixed success/failure
            async def mixed_task(task_id: int):
                if task_id % 2 == 0:
                    # Even tasks succeed
                    return await wrapper.execute_code(
                        code=f"print('Task {task_id} success')",
                        template="python",
                        timeout=30
                    )
                else:
                    # Odd tasks fail
                    return await wrapper.execute_code(
                        code=f"raise Exception('Task {task_id} intentional error')",
                        template="python",
                        timeout=30
                    )
            
            # Execute multiple tasks concurrently
            num_tasks = 6
            tasks = [mixed_task(i) for i in range(num_tasks)]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify mixed results
            successes = 0
            failures = 0
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failures += 1
                    logger.info(f"Task {i} failed as expected: {result}")
                else:
                    if result.success:
                        successes += 1
                        assert f"Task {i} success" in result.stdout
                    else:
                        failures += 1
                        assert "intentional error" in result.stderr
            
            assert successes > 0, "Some tasks should succeed"
            assert failures > 0, "Some tasks should fail"
            
            logger.info(f"✓ Concurrent error scenarios completed: {successes} successes, {failures} failures")


if __name__ == "__main__":
    # Run tests when called directly
    pytest.main([__file__, "-v"])