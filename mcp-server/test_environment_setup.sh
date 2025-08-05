#!/bin/bash

# Test Environment Setup Script for MCP Server Integration Tests
# This script sets up the test environment for running integration tests

set -e

echo "=== Setting up MCP Server Test Environment ==="

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create test directories
echo "Creating test directories..."
mkdir -p "$SCRIPT_DIR/test_data/shared_volumes/input"
mkdir -p "$SCRIPT_DIR/test_data/shared_volumes/output"
mkdir -p "$SCRIPT_DIR/test_data/logs"

# Create test files for volume mapping tests
echo "Creating test files..."
echo "Hello from host!" > "$SCRIPT_DIR/test_data/shared_volumes/input/test_file.txt"
echo "print('Hello from Python!')" > "$SCRIPT_DIR/test_data/shared_volumes/input/test_script.py"
echo "console.log('Hello from Node!');" > "$SCRIPT_DIR/test_data/shared_volumes/input/test_script.js"
echo '{"message": "Test data", "timestamp": "2024-01-01T00:00:00Z"}' > "$SCRIPT_DIR/test_data/shared_volumes/input/data.json"
echo "requests==2.31.0" > "$SCRIPT_DIR/test_data/shared_volumes/input/requirements.txt"
echo '{"name": "test", "version": "1.0.0"}' > "$SCRIPT_DIR/test_data/shared_volumes/input/package.json"

# Set up test environment variables
echo "Setting up test environment variables..."
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_API_KEY=""
export MSB_SESSION_TIMEOUT="300"
export MSB_MAX_SESSIONS="5"
export MSB_CLEANUP_INTERVAL="30"
export MSB_DEFAULT_FLAVOR="small"
export MSB_SHARED_VOLUME_PATH="[\"$SCRIPT_DIR/test_data/shared_volumes/input:/shared/input\", \"$SCRIPT_DIR/test_data/shared_volumes/output:/shared/output\"]"
export MSB_MAX_TOTAL_MEMORY_MB="4096"
export MSB_SANDBOX_START_TIMEOUT="30.0"
export MSB_EXECUTION_TIMEOUT="120"
export MSB_ORPHAN_CLEANUP_INTERVAL="60"

# Set up logging
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
export MSB_LOG_LEVEL="DEBUG"

echo "✓ Test directories created"
echo "✓ Test files created"
echo "✓ Environment variables set"
echo ""

echo "Test environment configuration:"
echo "  MSB_SERVER_URL: $MSB_SERVER_URL"
echo "  MSB_SESSION_TIMEOUT: $MSB_SESSION_TIMEOUT"
echo "  MSB_MAX_SESSIONS: $MSB_MAX_SESSIONS"
echo "  MSB_DEFAULT_FLAVOR: $MSB_DEFAULT_FLAVOR"
echo "  Shared volumes: $SCRIPT_DIR/test_data/shared_volumes"
echo "  Project root: $PROJECT_ROOT"
echo ""

echo "=== Test Environment Ready ==="
echo "To run integration tests:"
echo "  1. Start the microsandbox server: $PROJECT_ROOT/start_msbserver_debug.sh"
echo "  2. In another terminal, source this script: source $SCRIPT_DIR/test_environment_setup.sh"
echo "  3. Run integration tests: python -m pytest $SCRIPT_DIR/integration_tests/ -v"
echo "  4. Or use the test runner: $SCRIPT_DIR/run_integration_tests.sh"
echo ""