#!/bin/bash

# Microsandbox Server Debug Startup Script
# This script starts msbserver with debug logging and bypasses proxy for localhost connections

echo "=== Starting Microsandbox Server with Debug Logging ==="
echo "Setting up environment variables..."

# Bypass proxy for localhost connections to avoid VPN/proxy interference
export NO_PROXY=127.0.0.1,localhost

# Enable debug logging for detailed output
export RUST_LOG=debug

echo "✓ NO_PROXY set to: $NO_PROXY"
echo "✓ RUST_LOG set to: $RUST_LOG"
echo ""

echo "Starting msbserver in development mode..."
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Start the server
msbserver --dev
