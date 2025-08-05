#!/bin/bash

# Integration Test Runner Script
# This script sets up the environment and runs integration tests for the MCP wrapper

set -e

echo "=== MCP Wrapper Integration Test Runner ==="

# Function to check if server is running
check_server() {
    local max_attempts=30
    local attempt=1
    
    echo "Checking if microsandbox server is running..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f http://127.0.0.1:5555/api/v1/health > /dev/null 2>&1; then
            echo "✓ Server is running"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: Server not ready, waiting..."
        sleep 1
        ((attempt++))
    done
    
    echo "✗ Server is not running after $max_attempts attempts"
    return 1
}

# Function to start server in background
start_server() {
    echo "Starting microsandbox server..."
    
    # Check if start script exists
    if [ ! -f "./start_msbserver_debug.sh" ]; then
        echo "✗ start_msbserver_debug.sh not found in current directory"
        echo "Please run this script from the project root directory"
        exit 1
    fi
    
    # Start server in background
    ./start_msbserver_debug.sh > mcp-server/test_data/logs/server.log 2>&1 &
    SERVER_PID=$!
    
    echo "Server started with PID: $SERVER_PID"
    echo "Server logs: mcp-server/test_data/logs/server.log"
    
    # Wait for server to be ready
    if check_server; then
        echo "✓ Server is ready for testing"
        return 0
    else
        echo "✗ Server failed to start properly"
        kill $SERVER_PID 2>/dev/null || true
        return 1
    fi
}

# Function to stop server
stop_server() {
    if [ ! -z "$SERVER_PID" ]; then
        echo "Stopping server (PID: $SERVER_PID)..."
        kill $SERVER_PID 2>/dev/null || true
        wait $SERVER_PID 2>/dev/null || true
        echo "✓ Server stopped"
    fi
}

# Function to setup test environment
setup_environment() {
    echo "Setting up test environment..."
    
    # Change to mcp-server directory
    cd mcp-server
    
    # Run environment setup
    python3 integration_tests/test_integration_environment.py
    
    # Return to project root
    cd ..
    
    echo "✓ Test environment setup complete"
}

# Function to run tests
run_tests() {
    echo "Running integration tests..."
    
    # Set PYTHONPATH to include current directory
    export PYTHONPATH="$(pwd):$PYTHONPATH"
    
    # Run specific test categories
    local test_categories=(
        "test_integration_environment.py"
        "test_end_to_end_functionality.py"
        "test_error_scenarios.py"
    )
    
    local passed=0
    local failed=0
    
    for test_file in "${test_categories[@]}"; do
        echo ""
        echo "--- Running $test_file ---"
        
        if python3 -m pytest "mcp-server/integration_tests/$test_file" -v --tb=short; then
            echo "✓ $test_file PASSED"
            ((passed++))
        else
            echo "✗ $test_file FAILED"
            ((failed++))
        fi
    done
    
    echo ""
    echo "=== Test Results ==="
    echo "Passed: $passed"
    echo "Failed: $failed"
    
    if [ $failed -eq 0 ]; then
        echo "🎉 All integration tests passed!"
        return 0
    else
        echo "❌ Some integration tests failed"
        return 1
    fi
}

# Function to cleanup
cleanup() {
    echo ""
    echo "Cleaning up..."
    stop_server
    
    # Clean up test data
    if [ -d "mcp-server/test_data" ]; then
        rm -rf mcp-server/test_data/output/*
        echo "✓ Test output cleaned up"
    fi
}

# Main execution
main() {
    local auto_start_server=false
    local run_specific_test=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto-start-server)
                auto_start_server=true
                shift
                ;;
            --test)
                run_specific_test="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --auto-start-server    Automatically start the microsandbox server"
                echo "  --test TEST_FILE       Run a specific test file"
                echo "  --help                 Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                                    # Run all tests (server must be running)"
                echo "  $0 --auto-start-server               # Start server and run all tests"
                echo "  $0 --test test_integration_environment.py  # Run specific test"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Set up trap for cleanup
    trap cleanup EXIT
    
    # Setup test environment
    setup_environment
    
    # Check if server is already running or start it
    if check_server; then
        echo "✓ Using existing server"
    elif [ "$auto_start_server" = true ]; then
        start_server
    else
        echo "✗ Server is not running"
        echo ""
        echo "Please either:"
        echo "  1. Start the server manually: ./start_msbserver_debug.sh"
        echo "  2. Use --auto-start-server flag to start automatically"
        exit 1
    fi
    
    # Run tests
    if [ ! -z "$run_specific_test" ]; then
        echo "Running specific test: $run_specific_test"
        python3 -m pytest "mcp-server/integration_tests/$run_specific_test" -v --tb=short
    else
        run_tests
    fi
}

# Run main function
main "$@"