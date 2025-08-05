#!/usr/bin/env python3
"""
Advanced usage examples for the MicrosandboxWrapper.

This script demonstrates advanced features including:
- Volume mapping and file operations
- Background task management
- Resource monitoring and limits
- Concurrent execution
- Configuration management
- Error recovery scenarios

Prerequisites:
- Microsandbox server running (use: ./start_msbserver_debug.sh)
- Environment variables configured (see ENVIRONMENT_CONFIG.md)
- Test data directory with shared volumes
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Add the mcp-server directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor, WrapperConfig
from microsandbox_wrapper.exceptions import MicrosandboxWrapperError, ResourceLimitError


async def volume_mapping_example():
    """Demonstrate volume mapping and file operations."""
    print("=== Volume Mapping Example ===")
    
    # Create temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = Path(temp_dir) / "input"
        output_dir = Path(temp_dir) / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create test input file
        test_file = input_dir / "test_data.txt"
        test_file.write_text("Hello from host filesystem!\nThis is test data.")
        
        # Configure wrapper with volume mappings
        config = WrapperConfig.from_env()
        config.shared_volume_mappings = [
            f"{input_dir}:/sandbox/input",
            f"{output_dir}:/sandbox/output"
        ]
        
        async with MicrosandboxWrapper(config=config) as wrapper:
            # Code that reads from input volume and writes to output volume
            file_processing_code = """
import os

# Read from input volume
input_file = '/sandbox/input/test_data.txt'
if os.path.exists(input_file):
    with open(input_file, 'r') as f:
        content = f.read()
    print(f"Read from input: {content}")
    
    # Process the content
    processed_content = content.upper() + "\\n\\nProcessed by sandbox!"
    
    # Write to output volume
    output_file = '/sandbox/output/processed_data.txt'
    with open(output_file, 'w') as f:
        f.write(processed_content)
    print(f"Wrote processed content to: {output_file}")
    
    # List files in both directories
    print("\\nInput directory contents:")
    for item in os.listdir('/sandbox/input'):
        print(f"  {item}")
    
    print("\\nOutput directory contents:")
    for item in os.listdir('/sandbox/output'):
        print(f"  {item}")
else:
    print(f"Input file not found: {input_file}")
"""
            
            result = await wrapper.execute_code(
                code=file_processing_code,
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            
            print(f"File processing result:")
            print(f"  Success: {result.success}")
            print(f"  Output:\n{result.stdout}")
            
            # Verify output file was created on host
            output_file = output_dir / "processed_data.txt"
            if output_file.exists():
                print(f"\n✓ Output file created on host:")
                print(f"  Content: {output_file.read_text()}")
            else:
                print(f"\n✗ Output file not found on host")


async def concurrent_execution_example():
    """Demonstrate concurrent execution capabilities."""
    print("\n=== Concurrent Execution Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Define multiple tasks to run concurrently
        tasks = []
        
        # Task 1: CPU-intensive calculation
        cpu_task_code = """
import time
start = time.time()
result = sum(i * i for i in range(100000))
end = time.time()
print(f"CPU task completed: result={result}, time={end-start:.3f}s")
"""
        
        # Task 2: I/O simulation
        io_task_code = """
import time
print("Starting I/O simulation...")
time.sleep(2)
print("I/O task completed")
"""
        
        # Task 3: Data processing
        data_task_code = """
import json
data = [{"id": i, "value": i * 2} for i in range(1000)]
processed = [item for item in data if item["value"] % 10 == 0]
print(f"Data task completed: processed {len(processed)} items")
"""
        
        # Create concurrent tasks
        print("Starting concurrent executions...")
        start_time = time.time()
        
        tasks.append(wrapper.execute_code(cpu_task_code, template="python", flavor=SandboxFlavor.SMALL))
        tasks.append(wrapper.execute_code(io_task_code, template="python", flavor=SandboxFlavor.SMALL))
        tasks.append(wrapper.execute_code(data_task_code, template="python", flavor=SandboxFlavor.SMALL))
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        print(f"\nAll tasks completed in {total_time:.3f}s")
        
        # Display results
        for i, result in enumerate(results, 1):
            if isinstance(result, Exception):
                print(f"Task {i} failed: {result}")
            else:
                print(f"Task {i} (Session: {result.session_id}):")
                print(f"  Time: {result.execution_time_ms}ms")
                print(f"  Output: {result.stdout.strip()}")


async def background_task_management_example():
    """Demonstrate background task management."""
    print("\n=== Background Task Management Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Get initial background task status
        print("Initial background task status:")
        status = await wrapper.get_background_task_status()
        print(f"  Overall status: {status['overall_status']}")
        for component, info in status['components'].items():
            print(f"  {component}: {info['status']}")
        
        # Pause background tasks
        print("\nPausing background tasks...")
        pause_result = await wrapper.pause_background_tasks()
        print(f"  Pause status: {pause_result['status']}")
        print(f"  Tasks paused: {pause_result['tasks_paused']}")
        
        # Check status while paused
        print("\nStatus while paused:")
        status = await wrapper.get_background_task_status()
        print(f"  Overall status: {status['overall_status']}")
        
        # Create some sessions while paused
        print("\nCreating sessions while background tasks are paused...")
        await wrapper.execute_code("print('Session created while paused')", template="python")
        
        # Resume background tasks
        print("\nResuming background tasks...")
        resume_result = await wrapper.resume_background_tasks()
        print(f"  Resume status: {resume_result['status']}")
        print(f"  Tasks resumed: {resume_result['tasks_resumed']}")
        
        # Final status check
        print("\nFinal status:")
        status = await wrapper.get_background_task_status()
        print(f"  Overall status: {status['overall_status']}")


async def resource_limit_example():
    """Demonstrate resource limit handling."""
    print("\n=== Resource Limit Example ===")
    
    # Configure wrapper with low limits for demonstration
    config = WrapperConfig.from_env()
    config.max_concurrent_sessions = 2  # Very low limit for demo
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        print(f"Configured max sessions: {config.max_concurrent_sessions}")
        
        # Create sessions up to the limit
        sessions = []
        for i in range(config.max_concurrent_sessions):
            result = await wrapper.execute_code(
                code=f"import time; session_id = {i + 1}; print(f'Session {{session_id}} created')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            sessions.append(result.session_id)
            print(f"Created session {i + 1}: {result.session_id}")
        
        # Check resource stats
        stats = await wrapper.get_resource_stats()
        print(f"\nResource stats at limit:")
        print(f"  Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        
        # Try to create one more session (should hit limit)
        print(f"\nTrying to create session beyond limit...")
        try:
            await wrapper.execute_code(
                code="print('This should fail due to resource limits')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            print("  ✗ Unexpected success - limit not enforced")
        except ResourceLimitError as e:
            print(f"  ✓ Expected resource limit error: {e}")
        except Exception as e:
            print(f"  ? Unexpected error type: {e}")
        
        # Clean up one session and try again
        if sessions:
            print(f"\nStopping one session: {sessions[0]}")
            await wrapper.stop_session(sessions[0])
            
            # Now try creating a new session
            print("Trying to create session after cleanup...")
            result = await wrapper.execute_code(
                code="print('Session created after cleanup')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            print(f"  ✓ Successfully created session: {result.session_id}")


async def configuration_management_example():
    """Demonstrate configuration management."""
    print("\n=== Configuration Management Example ===")
    
    # Create custom configuration
    custom_config = WrapperConfig(
        server_url="http://127.0.0.1:5555",
        session_timeout=3600,  # 1 hour
        max_concurrent_sessions=5,
        default_flavor=SandboxFlavor.MEDIUM,
        default_execution_timeout=120,  # 2 minutes
        shared_volume_mappings=[],
        cleanup_interval=30,  # 30 seconds
        orphan_cleanup_interval=300  # 5 minutes
    )
    
    print("Custom configuration:")
    print(f"  Server URL: {custom_config.server_url}")
    print(f"  Session timeout: {custom_config.session_timeout}s")
    print(f"  Max sessions: {custom_config.max_concurrent_sessions}")
    print(f"  Default flavor: {custom_config.default_flavor.value}")
    print(f"  Default timeout: {custom_config.default_execution_timeout}s")
    print(f"  Cleanup interval: {custom_config.cleanup_interval}s")
    
    async with MicrosandboxWrapper(config=custom_config) as wrapper:
        # Test with custom configuration
        result = await wrapper.execute_code(
            code="import os; print(f'Running with custom config')",
            template="python"
            # Note: flavor not specified, should use default (MEDIUM)
        )
        
        print(f"\nExecution with custom config:")
        print(f"  Session ID: {result.session_id}")
        print(f"  Output: {result.stdout.strip()}")
        
        # Get and display current config
        current_config = wrapper.get_config()
        print(f"\nCurrent wrapper configuration:")
        print(f"  Default flavor: {current_config.default_flavor.value}")
        print(f"  Max sessions: {current_config.max_concurrent_sessions}")


async def error_recovery_example():
    """Demonstrate error recovery scenarios."""
    print("\n=== Error Recovery Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Scenario 1: Timeout handling
        print("1. Testing timeout handling:")
        try:
            result = await wrapper.execute_code(
                code="import time; time.sleep(10)",  # Long-running code
                template="python",
                timeout=2  # Short timeout
            )
            print(f"   Unexpected success: {result.success}")
        except MicrosandboxWrapperError as e:
            print(f"   ✓ Caught expected timeout error: {e}")
        
        # Scenario 2: Invalid template
        print("\n2. Testing invalid template handling:")
        try:
            await wrapper.execute_code(
                code="print('Hello')",
                template="invalid_template"
            )
        except MicrosandboxWrapperError as e:
            print(f"   ✓ Caught expected template error: {e}")
        
        # Scenario 3: Session recovery after error
        print("\n3. Testing session recovery after error:")
        
        # Create a session
        result1 = await wrapper.execute_code(
            code="x = 42; print(f'Initial value: {x}')",
            template="python"
        )
        session_id = result1.session_id
        print(f"   Created session: {session_id}")
        
        # Cause an error in the session
        try:
            await wrapper.execute_code(
                code="raise ValueError('Intentional error')",
                template="python",
                session_id=session_id
            )
        except MicrosandboxWrapperError:
            print(f"   ✓ Intentional error occurred")
        
        # Try to use the session again
        try:
            result2 = await wrapper.execute_code(
                code="print(f'Session recovered, x = {x}')",
                template="python",
                session_id=session_id
            )
            print(f"   ✓ Session recovered: {result2.stdout.strip()}")
        except MicrosandboxWrapperError as e:
            print(f"   Session recovery failed: {e}")


async def orphan_cleanup_example():
    """Demonstrate orphan sandbox cleanup."""
    print("\n=== Orphan Cleanup Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Create some sessions
        print("Creating sessions for orphan cleanup test...")
        sessions = []
        for i in range(3):
            result = await wrapper.execute_code(
                code=f"print('Session {i + 1} for orphan test')",
                template="python"
            )
            sessions.append(result.session_id)
            print(f"  Created session: {result.session_id}")
        
        # Get initial resource stats
        stats = await wrapper.get_resource_stats()
        print(f"\nActive sessions before cleanup: {stats.active_sessions}")
        
        # Manually trigger orphan cleanup
        print("\nTriggering manual orphan cleanup...")
        cleaned_count = await wrapper.cleanup_orphan_sandboxes()
        print(f"Cleaned {cleaned_count} orphan sandboxes")
        
        # Check stats after cleanup
        stats = await wrapper.get_resource_stats()
        print(f"Active sessions after cleanup: {stats.active_sessions}")
        
        # List remaining sessions
        session_infos = await wrapper.get_sessions()
        print(f"\nRemaining sessions:")
        for info in session_infos:
            print(f"  {info.session_id}: {info.status.value}")


async def performance_monitoring_example():
    """Demonstrate performance monitoring."""
    print("\n=== Performance Monitoring Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Execute various operations and monitor performance
        operations = [
            ("Quick calculation", "result = sum(range(1000)); print(f'Result: {result}')"),
            ("String processing", "text = 'hello world ' * 1000; print(f'Length: {len(text)}')"),
            ("List comprehension", "data = [x**2 for x in range(1000)]; print(f'Items: {len(data)}')"),
            ("JSON processing", "import json; data = {'items': list(range(100))}; json_str = json.dumps(data); print(f'JSON length: {len(json_str)}')"),
        ]
        
        print("Performance monitoring for different operations:")
        
        for name, code in operations:
            start_time = time.time()
            result = await wrapper.execute_code(
                code=code,
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            total_time = time.time() - start_time
            
            print(f"\n{name}:")
            print(f"  Total time: {total_time * 1000:.1f}ms")
            print(f"  Execution time: {result.execution_time_ms}ms")
            print(f"  Overhead: {(total_time * 1000) - result.execution_time_ms:.1f}ms")
            print(f"  Success: {result.success}")
            print(f"  Output: {result.stdout.strip()}")
        
        # Get final resource statistics
        print(f"\nFinal resource statistics:")
        stats = await wrapper.get_resource_stats()
        print(f"  Active sessions: {stats.active_sessions}")
        print(f"  Total memory: {stats.total_memory_mb} MB")
        print(f"  Total CPUs: {stats.total_cpus}")
        print(f"  Uptime: {stats.uptime_seconds}s")


async def main():
    """Run all advanced examples."""
    print("MicrosandboxWrapper Advanced Usage Examples")
    print("=" * 60)
    
    # Check if server is running
    wrapper_test = MicrosandboxWrapper()
    try:
        await wrapper_test.start()
        await wrapper_test.stop()
        print("✓ Microsandbox server is accessible")
    except Exception as e:
        print(f"✗ Cannot connect to microsandbox server: {e}")
        print("Please ensure the server is running with: ./start_msbserver_debug.sh")
        return
    
    # Run examples
    examples = [
        volume_mapping_example,
        concurrent_execution_example,
        background_task_management_example,
        resource_limit_example,
        configuration_management_example,
        error_recovery_example,
        orphan_cleanup_example,
        performance_monitoring_example,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay between examples
        await asyncio.sleep(2)
    
    print("\n" + "=" * 60)
    print("All advanced examples completed!")


if __name__ == "__main__":
    asyncio.run(main())