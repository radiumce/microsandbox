#!/usr/bin/env python3
"""
Basic usage examples for the MicrosandboxWrapper.

This script demonstrates the fundamental operations of the wrapper including:
- Code execution (Python and Node.js)
- Command execution
- Session management
- Basic error handling

Prerequisites:
- Microsandbox server running (use: ./start_msbserver_debug.sh)
- Environment variables configured (see ENVIRONMENT_CONFIG.md)
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the mcp-server directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor
from microsandbox_wrapper.exceptions import MicrosandboxWrapperError


async def basic_code_execution():
    """Demonstrate basic code execution functionality."""
    print("=== Basic Code Execution ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Execute simple Python code
        python_code = """
print("Hello from Python sandbox!")
import sys
print(f"Python version: {sys.version}")

# Simple calculation
result = 2 + 2
print(f"2 + 2 = {result}")
"""
        
        try:
            result = await wrapper.execute_code(
                code=python_code,
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            
            print(f"Session ID: {result.session_id}")
            print(f"Success: {result.success}")
            print(f"Execution time: {result.execution_time_ms}ms")
            print(f"Session created: {result.session_created}")
            print(f"Output:\n{result.stdout}")
            
            if result.stderr:
                print(f"Errors:\n{result.stderr}")
                
        except MicrosandboxWrapperError as e:
            print(f"Error executing Python code: {e}")


async def basic_command_execution():
    """Demonstrate basic command execution functionality."""
    print("\n=== Basic Command Execution ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Execute simple commands
        commands = [
            ("echo", ["Hello from command execution!"]),
            ("pwd", []),
            ("ls", ["-la"]),
            ("python3", ["--version"]),
        ]
        
        for command, args in commands:
            try:
                result = await wrapper.execute_command(
                    command=command,
                    args=args,
                    template="python",
                    flavor=SandboxFlavor.SMALL
                )
                
                print(f"\nCommand: {command} {' '.join(args)}")
                print(f"Session ID: {result.session_id}")
                print(f"Exit code: {result.exit_code}")
                print(f"Success: {result.success}")
                print(f"Execution time: {result.execution_time_ms}ms")
                print(f"Output: {result.stdout.strip()}")
                
                if result.stderr:
                    print(f"Errors: {result.stderr.strip()}")
                    
            except MicrosandboxWrapperError as e:
                print(f"Error executing command '{command}': {e}")


async def session_reuse_example():
    """Demonstrate session reuse functionality."""
    print("\n=== Session Reuse Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # First execution - creates a new session
        code1 = """
x = 42
print(f"Set x = {x}")
"""
        
        result1 = await wrapper.execute_code(
            code=code1,
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"First execution:")
        print(f"  Session ID: {result1.session_id}")
        print(f"  Session created: {result1.session_created}")
        print(f"  Output: {result1.stdout.strip()}")
        
        # Second execution - reuse the same session
        code2 = """
print(f"x from previous execution: {x}")
y = x * 2
print(f"y = x * 2 = {y}")
"""
        
        result2 = await wrapper.execute_code(
            code=code2,
            template="python",
            session_id=result1.session_id,  # Reuse the session
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"\nSecond execution (reusing session):")
        print(f"  Session ID: {result2.session_id}")
        print(f"  Session created: {result2.session_created}")
        print(f"  Output: {result2.stdout.strip()}")
        
        # Verify it's the same session
        assert result1.session_id == result2.session_id
        print(f"\n✓ Successfully reused session {result1.session_id}")


async def different_templates_example():
    """Demonstrate using different sandbox templates."""
    print("\n=== Different Templates Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Python template
        python_code = """
import json
data = {"language": "Python", "version": "3.x"}
print(json.dumps(data, indent=2))
"""
        
        python_result = await wrapper.execute_code(
            code=python_code,
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"Python execution:")
        print(f"  Session ID: {python_result.session_id}")
        print(f"  Template: {python_result.template}")
        print(f"  Output:\n{python_result.stdout}")
        
        # Node.js template
        node_code = """
const data = {language: "Node.js", version: process.version};
console.log(JSON.stringify(data, null, 2));
"""
        
        node_result = await wrapper.execute_code(
            code=node_code,
            template="node",
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"Node.js execution:")
        print(f"  Session ID: {node_result.session_id}")
        print(f"  Template: {node_result.template}")
        print(f"  Output:\n{node_result.stdout}")


async def error_handling_example():
    """Demonstrate error handling."""
    print("\n=== Error Handling Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Syntax error example
        print("1. Syntax error example:")
        try:
            await wrapper.execute_code(
                code="print('Hello world'",  # Missing closing parenthesis
                template="python"
            )
        except MicrosandboxWrapperError as e:
            print(f"   Caught expected error: {e}")
        
        # Runtime error example
        print("\n2. Runtime error example:")
        try:
            result = await wrapper.execute_code(
                code="x = 1 / 0",  # Division by zero
                template="python"
            )
            print(f"   Success: {result.success}")
            print(f"   Stderr: {result.stderr}")
        except MicrosandboxWrapperError as e:
            print(f"   Caught error: {e}")
        
        # Command not found example
        print("\n3. Command not found example:")
        try:
            result = await wrapper.execute_command(
                command="nonexistent_command",
                template="python"
            )
            print(f"   Exit code: {result.exit_code}")
            print(f"   Success: {result.success}")
            print(f"   Stderr: {result.stderr}")
        except MicrosandboxWrapperError as e:
            print(f"   Caught error: {e}")


async def session_management_example():
    """Demonstrate session management operations."""
    print("\n=== Session Management Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Create a few sessions
        sessions = []
        for i in range(3):
            result = await wrapper.execute_code(
                code=f"session_number = {i + 1}\nprint(f'This is session {{session_number}}')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            sessions.append(result.session_id)
            print(f"Created session {i + 1}: {result.session_id}")
        
        # List all sessions
        print("\nActive sessions:")
        session_infos = await wrapper.get_sessions()
        for info in session_infos:
            print(f"  {info.session_id}: {info.template} ({info.flavor.value}) - {info.status.value}")
        
        # Stop a specific session
        if sessions:
            session_to_stop = sessions[0]
            print(f"\nStopping session: {session_to_stop}")
            stopped = await wrapper.stop_session(session_to_stop)
            print(f"Session stopped: {stopped}")
            
            # List sessions again
            print("\nActive sessions after stopping one:")
            session_infos = await wrapper.get_sessions()
            for info in session_infos:
                print(f"  {info.session_id}: {info.template} ({info.flavor.value}) - {info.status.value}")


async def resource_monitoring_example():
    """Demonstrate resource monitoring."""
    print("\n=== Resource Monitoring Example ===")
    
    async with MicrosandboxWrapper() as wrapper:
        # Get initial resource stats
        stats = await wrapper.get_resource_stats()
        print(f"Initial resource stats:")
        print(f"  Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        print(f"  Total memory: {stats.total_memory_mb} MB")
        print(f"  Total CPUs: {stats.total_cpus}")
        print(f"  Sessions by flavor: {stats.sessions_by_flavor}")
        
        # Create some sessions with different flavors
        print("\nCreating sessions with different flavors...")
        
        # Small session
        await wrapper.execute_code(
            code="print('Small session')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        # Medium session
        await wrapper.execute_code(
            code="print('Medium session')",
            template="python",
            flavor=SandboxFlavor.MEDIUM
        )
        
        # Get updated stats
        stats = await wrapper.get_resource_stats()
        print(f"\nUpdated resource stats:")
        print(f"  Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        print(f"  Total memory: {stats.total_memory_mb} MB")
        print(f"  Total CPUs: {stats.total_cpus}")
        print(f"  Sessions by flavor: {stats.sessions_by_flavor}")
        
        # Get volume mappings
        volume_mappings = await wrapper.get_volume_mappings()
        print(f"\nConfigured volume mappings:")
        for mapping in volume_mappings:
            print(f"  {mapping.host_path} -> {mapping.container_path}")


async def main():
    """Run all examples."""
    print("MicrosandboxWrapper Basic Usage Examples")
    print("=" * 50)
    
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
        basic_code_execution,
        basic_command_execution,
        session_reuse_example,
        different_templates_example,
        error_handling_example,
        session_management_example,
        resource_monitoring_example,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}")
        
        # Small delay between examples
        await asyncio.sleep(1)
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())