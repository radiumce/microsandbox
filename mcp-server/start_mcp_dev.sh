#!/bin/bash
#
# MCP Server Startup Script
# 
# Comprehensive startup script with development-friendly defaults.
# Can be configured for both development and production use via environment variables.
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python command - prefer python with MCP installed
if command -v python &> /dev/null && python -c "import mcp" 2>/dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null && python3 -c "import mcp" 2>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    log_error "Python is not installed or not in PATH"
    exit 1
fi

log_info "Starting MCP Server in Development Mode"
log_info "Using Python command: $PYTHON_CMD"

# =============================================================================
# AUTOMATIC .ENV FILE LOADING
# =============================================================================

# Function to load .env file if it exists
load_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        log_info "Loading environment variables from: $env_file"
        set -a && source "$env_file" && set +a
        log_info "✓ Environment variables loaded"
    fi
}

# Load environment files in order of preference
load_env_file ".env.dev"      # Development-specific config
load_env_file ".env"          # General config
load_env_file ".env.local"    # Local overrides

# =============================================================================
# ENVIRONMENT VALIDATION
# =============================================================================

# All configuration should be defined in .env files
# The script relies on environment variables loaded from .env files
log_info "Environment variables loaded from .env files"

# =============================================================================
# SETUP DEVELOPMENT ENVIRONMENT
# =============================================================================

# Create development directories
mkdir -p "./tmp/mcp-dev"
mkdir -p "./data"
mkdir -p "./logs"

# Create sample files for testing
if [[ ! -f "./tmp/mcp-dev/README.txt" ]]; then
    cat > "./tmp/mcp-dev/README.txt" << EOF
MCP Development Shared Directory

This directory is shared between the host and sandbox containers.
- Host path: $(pwd)/tmp/mcp-dev
- Container path: /sandbox/shared

You can:
1. Create files here and access them in the sandbox
2. Create files in the sandbox and see them here
3. Test volume mapping functionality

Example usage in sandbox:
  with open('/sandbox/shared/test.txt', 'w') as f:
      f.write('Hello from sandbox!')
EOF
fi

log_info "Development environment setup complete"

# =============================================================================
# PRE-FLIGHT CHECKS
# =============================================================================

# Check microsandbox server
MSB_URL="${MSB_SERVER_URL:-http://127.0.0.1:5555}"
if ! curl -s --connect-timeout 3 "${MSB_URL}/api/v1/health" > /dev/null 2>&1; then
    log_warn "Microsandbox server not accessible at ${MSB_URL}"
    log_warn "Starting microsandbox server..."
    
    # Try to start microsandbox server if script exists
    if [[ -f "../start_msbserver_debug.sh" ]]; then
        log_info "Found microsandbox startup script, starting server..."
        (cd .. && ./start_msbserver_debug.sh &)
        
        # Wait for server to start
        log_info "Waiting for microsandbox server to start..."
        for i in {1..30}; do
            if curl -s --connect-timeout 2 "${MSB_URL}/api/v1/health" > /dev/null 2>&1; then
                log_info "✓ Microsandbox server is now running"
                break
            fi
            sleep 1
            if [[ $i -eq 30 ]]; then
                log_error "Microsandbox server failed to start within 30 seconds"
                log_error "Please start it manually: ./start_msbserver_debug.sh"
                exit 1
            fi
        done
    else
        log_error "Please start the microsandbox server first:"
        log_error "  cd .. && ./start_msbserver_debug.sh"
        exit 1
    fi
else
    log_info "✓ Microsandbox server is running"
fi

# Check if port is available
MCP_PORT="${MCP_SERVER_PORT:-8775}"
if command -v lsof &> /dev/null && lsof -i :${MCP_PORT} > /dev/null 2>&1; then
    log_error "Port ${MCP_PORT} is already in use"
    exit 1
fi

# Install requirements if needed
if ! $PYTHON_CMD -c "import fastapi, uvicorn, aiohttp, mcp" &> /dev/null; then
    log_info "Installing requirements..."
    if $PYTHON_CMD -m pip install -r requirements.txt; then
        log_info "✓ Requirements installed successfully"
    else
        log_error "Failed to install requirements"
        log_error "Please check requirements.txt and try manually: python -m pip install -r requirements.txt"
        exit 1
    fi
else
    log_info "✓ All required packages are already installed"
fi

# =============================================================================
# START SERVER
# =============================================================================

log_info "Configuration:"
echo "  Server: http://${MCP_SERVER_HOST:-localhost}:${MCP_SERVER_PORT:-8775}"
echo "  CORS: ${MCP_ENABLE_CORS:-false}"
echo "  Max Sessions: ${MSB_MAX_SESSIONS:-5}"
echo "  Log Level: ${MSB_LOG_LEVEL:-DEBUG}"

log_info "Starting MCP Server..."
log_info "Press Ctrl+C to stop"

# Change to script directory and start server
cd "$SCRIPT_DIR"
exec $PYTHON_CMD -m mcp_server.main --transport streamable-http --port ${MCP_SERVER_PORT:-8775}
