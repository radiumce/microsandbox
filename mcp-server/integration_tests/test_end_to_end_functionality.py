#!/usr/bin/env python3
"""
End-to-end functionality tests for the MCP wrapper.

This module tests the complete functionality of the MCP wrapper including:
- Code execution (Python and Node templates)
- Command execution
- Session lifecycle management
- Volume mapping functionality
- Resource cleanup verification
"""

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List

import pytest

from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import (
    CodeExecutionError,
    CommandExecutionError,
    ResourceLimitError
)

logger = logging.getLogger(__name__)


class TestEndToEndFunctionality:
    """End-to-end functionality tests."""
    
    @pytest.mark.asyncio
    async def test_python_code_execution_complete_flow(self, integration_env, test_wrapper):
        """Test complete Python code execution flow."""
        logger.info("Testing complete Python code execution flow...")
        
        async with test_wrapper as wrapper:
            # Test basic Python code execution
            python_code = """
import sys
import os
import json
import time

print("=== Python Execution Test ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Process ID: {os.getpid()}")

# Test computation
result = sum(range(100))
print(f"Sum of 0-99: {result}")

# Test file operations with shared volume
try:
    # Read from input directory
    if os.path.exists('/shared/input'):
        print("\\nShared input directory contents:")
        for item in sorted(os.listdir('/shared/input')):
            print(f"  {item}")
        
        # Read test file
        test_file = '/shared/input/test_file.txt'
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                content = f.read().strip()
                print(f"Test file content: {content}")
        
        # Read JSON data
        json_file = '/shared/input/data.json'
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                data = json.load(f)
                print(f"JSON data: {data}")
        
        # Write to output directory
        output_file = '/shared/output/python_test_output.txt'
        with open(output_file, 'w') as f:
            f.write(f"Python test completed at {time.time()}\\n")
            f.write(f"Computation result: {result}\\n")
            f.write("Test successful!")
        print(f"Wrote output to: {output_file}")
        
        # Create JSON output
        json_output = '/shared/output/python_results.json'
        with open(json_output, 'w') as f:
            json.dump({
                "test": "python_execution",
                "result": result,
                "timestamp": time.time(),
                "success": True
            }, f, indent=2)
        print(f"Wrote JSON output to: {json_output}")
        
    else:
        print("No shared volume available")
        
except Exception as e:
    print(f"File operation error: {e}")
    
print("=== Test Complete ===")
"""
            
            # Execute the code
            result = await wrapper.execute_code(
                code=python_code,
                template="python",
                flavor=SandboxFlavor.SMALL,
                timeout=60
            )
            
            # Verify execution results
            assert result.success, f"Python code execution should succeed: {result.stderr}"
            assert result.session_id, "Should have a session ID"
            assert result.template == "python", "Template should be python"
            assert "Python Execution Test" in result.stdout, "Should contain test header"
            assert "Sum of 0-99: 4950" in result.stdout, "Should contain correct computation result"
            assert "Test Complete" in result.stdout, "Should contain completion message"
            
            # Check if output files were created
            output_file = integration_env.output_dir / "python_test_output.txt"
            json_output = integration_env.output_dir / "python_results.json"
            
            # Wait a bit for file operations to complete
            await asyncio.sleep(1)
            
            assert output_file.exists(), "Output file should be created"
            assert json_output.exists(), "JSON output file should be created"
            
            # Verify output file content
            output_content = output_file.read_text()
            assert "Python test completed" in output_content, "Output file should contain completion message"
            assert "Computation result: 4950" in output_content, "Output file should contain result"
            
            # Verify JSON output
            json_data = json.loads(json_output.read_text())
            assert json_data["test"] == "python_execution", "JSON should contain test type"
            assert json_data["result"] == 4950, "JSON should contain correct result"
            assert json_data["success"] is True, "JSON should indicate success"
            
            logger.info("✓ Python code execution flow completed successfully")
    
    @pytest.mark.asyncio
    async def test_node_code_execution_complete_flow(self, integration_env, test_wrapper):
        """Test complete Node.js code execution flow."""
        logger.info("Testing complete Node.js code execution flow...")
        
        async with test_wrapper as wrapper:
            # Test Node.js code execution
            node_code = """
const fs = require('fs');
const path = require('path');

console.log('=== Node.js Execution Test ===');
console.log('Node.js version:', process.version);
console.log('Current directory:', process.cwd());
console.log('Process ID:', process.pid);

// Test computation
const result = Array.from({length: 100}, (_, i) => i).reduce((a, b) => a + b, 0);
console.log(`Sum of 0-99: ${result}`);

// Test file operations with shared volume
try {
    const sharedInputDir = '/shared/input';
    if (fs.existsSync(sharedInputDir)) {
        console.log('\\nShared input directory contents:');
        fs.readdirSync(sharedInputDir).sort().forEach(item => {
            console.log(`  ${item}`);
        });
        
        // Read test file
        const testFile = path.join(sharedInputDir, 'test_file.txt');
        if (fs.existsSync(testFile)) {
            const content = fs.readFileSync(testFile, 'utf8').trim();
            console.log(`Test file content: ${content}`);
        }
        
        // Read JSON data
        const jsonFile = path.join(sharedInputDir, 'data.json');
        if (fs.existsSync(jsonFile)) {
            const data = JSON.parse(fs.readFileSync(jsonFile, 'utf8'));
            console.log(`JSON data: ${JSON.stringify(data)}`);
        }
        
        // Write to output directory
        const outputFile = '/shared/output/node_test_output.txt';
        fs.writeFileSync(outputFile, 
            `Node.js test completed at ${Date.now()}\\n` +
            `Computation result: ${result}\\n` +
            'Test successful!'
        );
        console.log(`Wrote output to: ${outputFile}`);
        
        // Create JSON output
        const jsonOutput = '/shared/output/node_results.json';
        fs.writeFileSync(jsonOutput, JSON.stringify({
            test: 'node_execution',
            result: result,
            timestamp: Date.now(),
            success: true
        }, null, 2));
        console.log(`Wrote JSON output to: ${jsonOutput}`);
        
    } else {
        console.log('No shared volume available');
    }
    
} catch (error) {
    console.log(`File operation error: ${error.message}`);
}

console.log('=== Test Complete ===');
"""
            
            # Execute the code
            result = await wrapper.execute_code(
                code=node_code,
                template="node",
                flavor=SandboxFlavor.SMALL,
                timeout=60
            )
            
            # Verify execution results
            assert result.success, f"Node.js code execution should succeed: {result.stderr}"
            assert result.session_id, "Should have a session ID"
            assert result.template == "node", "Template should be node"
            assert "Node.js Execution Test" in result.stdout, "Should contain test header"
            assert "Sum of 0-99: 4950" in result.stdout, "Should contain correct computation result"
            assert "Test Complete" in result.stdout, "Should contain completion message"
            
            # Check if output files were created
            output_file = integration_env.output_dir / "node_test_output.txt"
            json_output = integration_env.output_dir / "node_results.json"
            
            # Wait a bit for file operations to complete
            await asyncio.sleep(1)
            
            assert output_file.exists(), "Output file should be created"
            assert json_output.exists(), "JSON output file should be created"
            
            # Verify output file content
            output_content = output_file.read_text()
            assert "Node.js test completed" in output_content, "Output file should contain completion message"
            assert "Computation result: 4950" in output_content, "Output file should contain result"
            
            # Verify JSON output
            json_data = json.loads(json_output.read_text())
            assert json_data["test"] == "node_execution", "JSON should contain test type"
            assert json_data["result"] == 4950, "JSON should contain correct result"
            assert json_data["success"] is True, "JSON should indicate success"
            
            logger.info("✓ Node.js code execution flow completed successfully")
    
    @pytest.mark.asyncio
    async def test_command_execution_complete_flow(self, integration_env, test_wrapper):
        """Test complete command execution flow."""
        logger.info("Testing complete command execution flow...")
        
        async with test_wrapper as wrapper:
            # Test various commands
            commands_to_test = [
                {
                    "command": "echo",
                    "args": ["Hello from command execution!"],
                    "expected_in_stdout": "Hello from command execution!"
                },
                {
                    "command": "pwd",
                    "args": [],
                    "expected_in_stdout": "/"
                },
                {
                    "command": "ls",
                    "args": ["-la", "/shared/input"],
                    "expected_in_stdout": "test_file.txt"
                },
                {
                    "command": "cat",
                    "args": ["/shared/input/test_file.txt"],
                    "expected_in_stdout": "Hello from host!"
                },
                {
                    "command": "python3",
                    "args": ["-c", "print('Python from command:', 2 + 2)"],
                    "expected_in_stdout": "Python from command: 4"
                },
                {
                    "command": "node",
                    "args": ["-e", "console.log('Node from command:', 3 + 3)"],
                    "expected_in_stdout": "Node from command: 6"
                }
            ]
            
            session_id = None
            
            for i, cmd_test in enumerate(commands_to_test):
                logger.info(f"Testing command {i+1}/{len(commands_to_test)}: {cmd_test['command']}")
                
                result = await wrapper.execute_command(
                    command=cmd_test["command"],
                    args=cmd_test["args"],
                    template="python",  # Use python template for commands
                    session_id=session_id,  # Reuse session
                    timeout=30
                )
                
                # Store session ID for reuse
                if session_id is None:
                    session_id = result.session_id
                
                # Verify command execution
                assert result.success, f"Command {cmd_test['command']} should succeed: {result.stderr}"
                assert result.session_id == session_id, "Should reuse the same session"
                assert result.exit_code == 0, f"Command should exit with code 0, got {result.exit_code}"
                assert cmd_test["expected_in_stdout"] in result.stdout, \
                    f"Command output should contain '{cmd_test['expected_in_stdout']}', got: {result.stdout}"
                
                logger.info(f"✓ Command {cmd_test['command']} executed successfully")
            
            # Test command that writes to shared volume
            write_result = await wrapper.execute_command(
                command="sh",
                args=["-c", "echo 'Command test output' > /shared/output/command_test.txt && echo 'File written successfully'"],
                session_id=session_id,
                timeout=30
            )
            
            assert write_result.success, "Write command should succeed"
            assert "File written successfully" in write_result.stdout, "Should confirm file write"
            
            # Verify file was created
            await asyncio.sleep(1)
            output_file = integration_env.output_dir / "command_test.txt"
            assert output_file.exists(), "Command output file should be created"
            assert "Command test output" in output_file.read_text(), "File should contain expected content"
            
            logger.info("✓ Command execution flow completed successfully")
    
    @pytest.mark.asyncio
    async def test_session_lifecycle_management(self, test_wrapper):
        """Test session lifecycle management."""
        logger.info("Testing session lifecycle management...")
        
        async with test_wrapper as wrapper:
            # Test session creation and reuse
            initial_sessions = await wrapper.get_sessions()
            initial_count = len(initial_sessions)
            
            # Execute code without specifying session ID (should create new session)
            result1 = await wrapper.execute_code(
                code="print('First execution')",
                template="python"
            )
            
            session_id = result1.session_id
            assert session_id, "Should have a session ID"
            
            # Check that a new session was created
            sessions_after_first = await wrapper.get_sessions()
            assert len(sessions_after_first) == initial_count + 1, "Should have one more session"
            
            # Execute code with the same session ID (should reuse session)
            result2 = await wrapper.execute_code(
                code="print('Second execution')",
                template="python",
                session_id=session_id
            )
            
            assert result2.session_id == session_id, "Should reuse the same session"
            assert not result2.session_created, "Should not create a new session"
            
            # Check that no new session was created
            sessions_after_second = await wrapper.get_sessions()
            assert len(sessions_after_second) == len(sessions_after_first), "Should have same number of sessions"
            
            # Test session information
            session_info = None
            for session in sessions_after_second:
                if session.session_id == session_id:
                    session_info = session
                    break
            
            assert session_info is not None, "Should find the session info"
            assert session_info.template == "python", "Session should have correct template"
            assert session_info.flavor == SandboxFlavor.SMALL, "Session should have correct flavor"
            
            # Test manual session stop
            stop_result = await wrapper.stop_session(session_id)
            assert stop_result, "Should successfully stop the session"
            
            # Verify session is stopped
            await asyncio.sleep(1)  # Give time for cleanup
            final_sessions = await wrapper.get_sessions()
            active_sessions = [s for s in final_sessions if s.session_id == session_id and s.status.value != "stopped"]
            assert len(active_sessions) == 0, "Session should be stopped"
            
            logger.info("✓ Session lifecycle management completed successfully")
    
    @pytest.mark.asyncio
    async def test_multi_volume_mapping_functionality(self, integration_env, test_wrapper):
        """Test multiple volume mapping functionality."""
        logger.info("Testing multi-volume mapping functionality...")
        
        async with test_wrapper as wrapper:
            # Get volume mappings
            volume_mappings = await wrapper.get_volume_mappings()
            assert len(volume_mappings) >= 2, "Should have at least 2 volume mappings (input and output)"
            
            # Find input and output mappings
            input_mapping = None
            output_mapping = None
            
            for mapping in volume_mappings:
                if mapping.container_path == "/shared/input":
                    input_mapping = mapping
                elif mapping.container_path == "/shared/output":
                    output_mapping = mapping
            
            assert input_mapping is not None, "Should have input volume mapping"
            assert output_mapping is not None, "Should have output volume mapping"
            
            # Test code that uses both volumes
            volume_test_code = """
import os
import json

print("=== Volume Mapping Test ===")

# Test input volume
input_dir = '/shared/input'
output_dir = '/shared/output'

print(f"Input directory exists: {os.path.exists(input_dir)}")
print(f"Output directory exists: {os.path.exists(output_dir)}")

if os.path.exists(input_dir):
    print("Input directory contents:")
    for item in sorted(os.listdir(input_dir)):
        print(f"  {item}")
        
    # Read multiple files
    files_read = {}
    for filename in ['test_file.txt', 'data.json', 'test_script.py']:
        filepath = os.path.join(input_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                files_read[filename] = f.read()
            print(f"Read {filename}: {len(files_read[filename])} characters")

if os.path.exists(output_dir):
    # Write multiple output files
    output_files = {
        'volume_test_summary.txt': f"Volume test completed successfully\\nFiles read: {len(files_read)}\\n",
        'files_inventory.json': json.dumps(list(files_read.keys()), indent=2),
        'test_results.json': json.dumps({
            'test': 'volume_mapping',
            'input_files_found': len(files_read),
            'success': True
        }, indent=2)
    }
    
    for filename, content in output_files.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Wrote {filename}")

print("=== Volume Test Complete ===")
"""
            
            result = await wrapper.execute_code(
                code=volume_test_code,
                template="python",
                timeout=60
            )
            
            assert result.success, f"Volume test code should succeed: {result.stderr}"
            assert "Volume Mapping Test" in result.stdout, "Should contain test header"
            assert "Input directory exists: True" in result.stdout, "Input directory should exist"
            assert "Output directory exists: True" in result.stdout, "Output directory should exist"
            assert "Volume Test Complete" in result.stdout, "Should complete successfully"
            
            # Verify output files were created
            await asyncio.sleep(1)
            
            expected_output_files = [
                "volume_test_summary.txt",
                "files_inventory.json", 
                "test_results.json"
            ]
            
            for filename in expected_output_files:
                output_file = integration_env.output_dir / filename
                assert output_file.exists(), f"Output file {filename} should be created"
                
                if filename.endswith('.json'):
                    # Verify JSON files are valid
                    json_data = json.loads(output_file.read_text())
                    assert isinstance(json_data, (dict, list)), f"JSON file {filename} should be valid"
            
            logger.info("✓ Multi-volume mapping functionality completed successfully")
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_verification(self, test_wrapper):
        """Test resource cleanup verification."""
        logger.info("Testing resource cleanup verification...")
        
        async with test_wrapper as wrapper:
            # Get initial resource stats
            initial_stats = await wrapper.get_resource_stats()
            initial_sessions = initial_stats.active_sessions
            
            # Create multiple sessions
            session_ids = []
            for i in range(3):
                result = await wrapper.execute_code(
                    code=f"print('Session {i+1} created')",
                    template="python"
                )
                session_ids.append(result.session_id)
            
            # Verify sessions were created
            stats_after_creation = await wrapper.get_resource_stats()
            assert stats_after_creation.active_sessions == initial_sessions + 3, \
                "Should have 3 more active sessions"
            
            # Stop sessions one by one and verify cleanup
            for i, session_id in enumerate(session_ids):
                stop_result = await wrapper.stop_session(session_id)
                assert stop_result, f"Should successfully stop session {i+1}"
                
                # Wait for cleanup
                await asyncio.sleep(1)
                
                # Verify session count decreased
                current_stats = await wrapper.get_resource_stats()
                expected_active = initial_sessions + (2 - i)  # Remaining sessions
                assert current_stats.active_sessions == expected_active, \
                    f"Should have {expected_active} active sessions after stopping session {i+1}"
            
            # Test orphan cleanup
            orphans_cleaned = await wrapper.cleanup_orphan_sandboxes()
            logger.info(f"Cleaned {orphans_cleaned} orphan sandboxes")
            
            # Verify final state
            final_stats = await wrapper.get_resource_stats()
            assert final_stats.active_sessions == initial_sessions, \
                "Should return to initial session count"
            
            logger.info("✓ Resource cleanup verification completed successfully")
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self, test_wrapper):
        """Test concurrent execution capabilities."""
        logger.info("Testing concurrent execution capabilities...")
        
        async with test_wrapper as wrapper:
            # Create multiple concurrent tasks
            async def execute_task(task_id: int):
                code = f"""
import time
import random

print(f"Task {task_id} starting")
# Simulate some work
time.sleep(random.uniform(0.1, 0.5))
result = sum(range({task_id * 10}))
print(f"Task {task_id} result: {{result}}")
print(f"Task {task_id} completed")
"""
                return await wrapper.execute_code(
                    code=code,
                    template="python",
                    timeout=30
                )
            
            # Execute multiple tasks concurrently
            num_tasks = 5
            tasks = [execute_task(i) for i in range(1, num_tasks + 1)]
            
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            execution_time = time.time() - start_time
            
            # Verify all tasks completed successfully
            for i, result in enumerate(results, 1):
                assert result.success, f"Task {i} should succeed"
                assert f"Task {i} starting" in result.stdout, f"Task {i} should start"
                assert f"Task {i} completed" in result.stdout, f"Task {i} should complete"
            
            # Verify concurrent execution was faster than sequential
            # (This is a rough check - concurrent should be significantly faster)
            logger.info(f"Concurrent execution took {execution_time:.2f} seconds for {num_tasks} tasks")
            assert execution_time < num_tasks * 2, "Concurrent execution should be faster than sequential"
            
            # Verify all sessions are different (no session reuse across concurrent tasks)
            session_ids = [result.session_id for result in results]
            unique_sessions = set(session_ids)
            assert len(unique_sessions) == num_tasks, "Each concurrent task should have its own session"
            
            logger.info("✓ Concurrent execution completed successfully")


if __name__ == "__main__":
    # Run tests when called directly
    pytest.main([__file__, "-v"])