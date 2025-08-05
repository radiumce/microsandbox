"""
Pytest configuration and fixtures for integration tests.
"""

import asyncio
import os
import pytest
import time
from typing import AsyncGenerator

from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> WrapperConfig:
    """Create a test configuration from environment variables."""
    return WrapperConfig.from_env()


@pytest.fixture(scope="session")
async def wrapper(test_config: WrapperConfig) -> AsyncGenerator[MicrosandboxWrapper, None]:
    """Create and start a MicrosandboxWrapper instance for testing."""
    wrapper_instance = MicrosandboxWrapper(test_config)
    
    # Wait for server to be ready
    max_retries = 30
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            await wrapper_instance.start()
            break
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise Exception(f"Failed to start wrapper after {max_retries} retries: {e}")
            await asyncio.sleep(1)
    
    yield wrapper_instance
    
    # Cleanup
    await wrapper_instance.stop()


@pytest.fixture
def test_python_code():
    """Sample Python code for testing."""
    return """
import os
import sys

print("Python version:", sys.version)
print("Current directory:", os.getcwd())
print("Environment variables:")
for key, value in sorted(os.environ.items()):
    if key.startswith('MSB_') or key in ['PATH', 'PYTHONPATH']:
        print(f"  {key}={value}")

# Test basic computation
result = sum(range(10))
print(f"Sum of 0-9: {result}")

# Test file operations if shared volume is available
try:
    if os.path.exists('/shared/input'):
        print("Shared input directory contents:")
        for item in os.listdir('/shared/input'):
            print(f"  {item}")
        
        # Try to read a test file
        test_file = '/shared/input/test_file.txt'
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                content = f.read().strip()
                print(f"Test file content: {content}")
        
        # Write to output directory
        output_file = '/shared/output/python_output.txt'
        with open(output_file, 'w') as f:
            f.write(f"Python execution completed at {time.time()}")
        print(f"Wrote output to: {output_file}")
    else:
        print("No shared volume available")
except Exception as e:
    print(f"File operation error: {e}")
"""


@pytest.fixture
def test_node_code():
    """Sample Node.js code for testing."""
    return """
const fs = require('fs');
const path = require('path');

console.log('Node.js version:', process.version);
console.log('Current directory:', process.cwd());
console.log('Environment variables:');
Object.keys(process.env)
    .filter(key => key.startsWith('MSB_') || ['PATH', 'NODE_PATH'].includes(key))
    .sort()
    .forEach(key => {
        console.log(`  ${key}=${process.env[key]}`);
    });

// Test basic computation
const result = Array.from({length: 10}, (_, i) => i).reduce((a, b) => a + b, 0);
console.log(`Sum of 0-9: ${result}`);

// Test file operations if shared volume is available
try {
    const sharedInputDir = '/shared/input';
    if (fs.existsSync(sharedInputDir)) {
        console.log('Shared input directory contents:');
        fs.readdirSync(sharedInputDir).forEach(item => {
            console.log(`  ${item}`);
        });
        
        // Try to read a test file
        const testFile = path.join(sharedInputDir, 'test_file.txt');
        if (fs.existsSync(testFile)) {
            const content = fs.readFileSync(testFile, 'utf8').trim();
            console.log(`Test file content: ${content}`);
        }
        
        // Write to output directory
        const outputFile = '/shared/output/node_output.txt';
        fs.writeFileSync(outputFile, `Node.js execution completed at ${Date.now()}`);
        console.log(`Wrote output to: ${outputFile}`);
    } else {
        console.log('No shared volume available');
    }
} catch (error) {
    console.log(`File operation error: ${error.message}`);
}
"""


@pytest.fixture
def test_commands():
    """Sample shell commands for testing."""
    return [
        "echo 'Hello from shell!'",
        "pwd",
        "ls -la",
        "whoami",
        "env | grep MSB_ | sort",
        "python3 --version",
        "node --version",
        "df -h",
        "free -h",
        "ps aux | head -10"
    ]


@pytest.fixture
def shared_volume_commands():
    """Commands that test shared volume functionality."""
    return [
        "ls -la /shared/input || echo 'No shared input directory'",
        "cat /shared/input/test_file.txt || echo 'No test file found'",
        "echo 'Command output test' > /shared/output/command_output.txt || echo 'Cannot write to output'",
        "ls -la /shared/output || echo 'No shared output directory'"
    ]