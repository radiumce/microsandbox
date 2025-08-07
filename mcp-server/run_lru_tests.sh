#!/bin/bash
"""
Run all LRU eviction tests.

This script runs the complete test suite for LRU eviction functionality,
including unit tests, integration tests, and examples.
"""

set -e  # Exit on any error

echo "========================================"
echo "LRU Eviction Test Suite"
echo "========================================"
echo

# Check if we're in the right directory
if [ ! -f "microsandbox_wrapper/__init__.py" ]; then
    echo "❌ Error: Please run this script from the mcp-server directory"
    echo "   cd mcp-server && ./run_lru_tests.sh"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed or not in PATH"
    exit 1
fi

echo "🔍 Checking Python environment..."
python3 -c "import sys; print(f'Python version: {sys.version}')"
echo

# Function to run a test and report results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo "🧪 Running $test_name..."
    echo "   Command: $test_command"
    
    if eval "$test_command"; then
        echo "   ✅ $test_name passed"
    else
        echo "   ❌ $test_name failed"
        return 1
    fi
    echo
}

# Run basic tests (no external dependencies)
echo "========================================"
echo "1. Basic LRU Tests (Unit Tests)"
echo "========================================"
run_test "Basic LRU functionality" "python3 test_lru_basic.py"

# Run pytest tests if pytest is available
echo "========================================"
echo "2. Advanced LRU Tests (pytest)"
echo "========================================"

if command -v pytest &> /dev/null; then
    run_test "LRU unit tests with pytest" "python3 -m pytest tests/test_lru_eviction.py -v"
else
    echo "⚠️  pytest not available, skipping advanced tests"
    echo "   Install with: pip install pytest"
    echo
fi

# Check if microsandbox server is running for integration tests
echo "========================================"
echo "3. Integration Tests (require server)"
echo "========================================"

# Try to check if server is running
if curl -s "http://localhost:5555/health" > /dev/null 2>&1; then
    echo "✅ Microsandbox server is running"
    
    run_test "LRU integration test" "python3 test_lru_eviction.py"
    run_test "LRU example demonstration" "python3 examples/lru_eviction_example.py"
    
    echo "========================================"
    echo "4. End-to-End Tests (require server)"
    echo "========================================"
    
    run_test "E2E wrapper integration" "python3 integration_tests/test_lru_eviction_e2e.py"
    run_test "E2E MCP server integration" "python3 integration_tests/test_mcp_lru_eviction_e2e.py"
    
    if command -v pytest &> /dev/null; then
        run_test "E2E pytest suite" "python3 -m pytest integration_tests/test_lru_eviction_e2e.py -v"
        run_test "E2E MCP pytest suite" "python3 -m pytest integration_tests/test_mcp_lru_eviction_e2e.py -v"
    fi
else
    echo "⚠️  Microsandbox server not running on localhost:5555"
    echo "   Start the server to run integration tests:"
    echo "   cd ../microsandbox-server && cargo run"
    echo
fi

echo "========================================"
echo "4. Configuration Tests"
echo "========================================"

# Test configuration parsing
run_test "Configuration parsing" "python3 -c '
from microsandbox_wrapper.config import WrapperConfig
import os

# Test default config
config1 = WrapperConfig()
assert config1.enable_lru_eviction is True
print(\"✅ Default LRU eviction: enabled\")

# Test environment variable parsing
os.environ[\"MSB_ENABLE_LRU_EVICTION\"] = \"false\"
config2 = WrapperConfig.from_env()
assert config2.enable_lru_eviction is False
print(\"✅ Environment variable parsing: works\")

# Clean up
del os.environ[\"MSB_ENABLE_LRU_EVICTION\"]
print(\"✅ Configuration tests passed\")
'"

echo "========================================"
echo "Test Summary"
echo "========================================"

echo "✅ Basic LRU functionality tests completed"
echo "✅ Configuration tests completed"

if command -v pytest &> /dev/null; then
    echo "✅ Advanced pytest tests completed"
else
    echo "⚠️  Advanced pytest tests skipped (pytest not installed)"
fi

if curl -s "http://localhost:5555/health" > /dev/null 2>&1; then
    echo "✅ Integration tests completed"
    echo "✅ End-to-end tests completed"
    echo "✅ MCP server integration tests completed"
else
    echo "⚠️  Integration and E2E tests skipped (server not running)"
fi

echo
echo "🎉 LRU eviction test suite completed!"
echo
echo "📚 Documentation:"
echo "   - LRU_EVICTION_GUIDE.md - User guide"
echo "   - LRU_IMPLEMENTATION_SUMMARY.md - Technical details"
echo "   - CONFIGURATION_GUIDE.md - Configuration options"
echo
echo "🔧 Configuration:"
echo "   MSB_ENABLE_LRU_EVICTION=true|false"
echo "   MSB_MAX_SESSIONS=<number>"
echo "   MSB_MAX_TOTAL_MEMORY_MB=<megabytes>"