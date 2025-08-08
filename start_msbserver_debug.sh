#!/bin/bash

# Microsandbox Server Debug Startup Script
# This script starts msbserver with debug logging and bypasses proxy for localhost connections

echo "=== Starting Microsandbox Server with Debug Logging ==="
echo "Setting up environment variables..."

# Bypass proxy for localhost connections to avoid VPN/proxy interference
export NO_PROXY=127.0.0.1,localhost

# Enable selective debug logging - exclude sqlx to reduce noise
export RUST_LOG=microsandbox_core=debug,microsandbox_cli=debug,msbserver=debug,sqlx=warn

# Set library path for libkrun
export DYLD_LIBRARY_PATH="$(pwd)/build:$DYLD_LIBRARY_PATH"

echo "✓ NO_PROXY set to: $NO_PROXY"
echo "✓ RUST_LOG set to: $RUST_LOG"
echo "✓ DYLD_LIBRARY_PATH set to: $DYLD_LIBRARY_PATH"
echo ""

echo "Starting msbserver in development mode..."
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Start the server
msbserver --dev
