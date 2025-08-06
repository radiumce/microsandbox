#!/bin/bash

# MCP Server Integration Tests Runner
# This script runs the complete MCP server integration tests

set -e

echo "=== MCP Server Integration Tests ==="
echo

# Check if we're in the right directory
if [ ! -f "mcp_server/server.py" ]; then
    echo "Error: Please run this script from the mcp-server directory"
    exit 1
fi

# Check if microsandbox server is running
echo "1. Checking microsandbox server health..."
if curl -s http://127.0.0.1:5555/api/v1/health > /dev/null 2>&1; then
    echo "✓ Microsandbox server is running"
    curl -s http://127.0.0.1:5555/api/v1/health | head -3
else
    echo "✗ Microsandbox server is not running"
    echo
    echo "Please start the microsandbox server first:"
    echo "  ./start_msbserver_debug.sh"
    echo
    echo "Then wait for the server to be ready and try again."
    exit 1
fi

echo

# Check Python environment
echo "2. Checking Python environment..."
if ! python3 -c "import pytest, aiohttp, fastapi, uvicorn" 2>/dev/null; then
    echo "✗ Missing required dependencies"
    echo "Please install dependencies:"
    echo "  pip install -r requirements.txt"
    exit 1
fi
echo "✓ Python dependencies are available"

echo

# Set up test environment
echo "3. Setting up test environment..."

# Create test directories if they don't exist
mkdir -p tmp/integration_test_input
mkdir -p tmp/integration_test_output

# Create test files
echo "Hello from host!" > tmp/integration_test_input/test_file.txt
echo '{"message": "Test data", "timestamp": "2024-01-01T00:00:00Z"}' > tmp/integration_test_input/data.json
echo 'print("Hello from Python script!")' > tmp/integration_test_input/test_script.py
echo 'console.log("Hello from Node script!");' > tmp/integration_test_input/test_script.js
echo 'requests==2.31.0
numpy==1.24.3' > tmp/integration_test_input/requirements.txt
echo '{"name": "test", "version": "1.0.0", "dependencies": {"lodash": "^4.17.21"}}' > tmp/integration_test_input/package.json

# Set environment variables for testing
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_VOLUME_INPUT_PATH="$(pwd)/tmp/integration_test_input"
export MSB_VOLUME_OUTPUT_PATH="$(pwd)/tmp/integration_test_output"

echo "✓ Test environment configured"
echo "  Input directory: $MSB_VOLUME_INPUT_PATH"
echo "  Output directory: $MSB_VOLUME_OUTPUT_PATH"

echo

# Run the integration tests
echo "4. Running MCP server integration tests..."
echo

# Run environment tests first
echo "4.1. Testing environment setup..."
python3 -m pytest integration_tests/test_mcp_server_integration.py::TestMCPServerEnvironment -v -s

echo

# Run main integration tests
echo "4.2. Running MCP server integration tests..."
python3 -m pytest integration_tests/test_mcp_server_integration.py::TestMCPServerIntegration -v -s --tb=short

echo

# Cleanup
echo "5. Cleaning up test artifacts..."
rm -rf tmp/integration_test_input
rm -rf tmp/integration_test_output
echo "✓ Cleanup completed"

echo
echo "=== MCP Server Integration Tests Complete ==="