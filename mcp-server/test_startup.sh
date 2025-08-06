#!/bin/bash
#
# Test script to verify startup scripts work correctly
#

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[TEST]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=== MCP Server Startup Script Test ==="

# Test Python detection
log_info "Testing Python detection..."

# Test the same logic as in the startup scripts
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    log_info "✓ Found python3: $(python3 --version)"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    log_info "✓ Found python: $(python --version)"
else
    log_error "✗ No Python found"
    exit 1
fi

# Test Python imports
log_info "Testing Python imports with $PYTHON_CMD..."
if $PYTHON_CMD -c "import sys; print(f'Python {sys.version}')" 2>/dev/null; then
    log_info "✓ Python is working"
else
    log_error "✗ Python is not working"
    exit 1
fi

# Test package imports
log_info "Testing required packages..."
MISSING_PACKAGES=()

for package in fastapi uvicorn aiohttp pydantic; do
    if $PYTHON_CMD -c "import $package" 2>/dev/null; then
        log_info "✓ $package is available"
    else
        log_warn "✗ $package is missing"
        MISSING_PACKAGES+=($package)
    fi
done

if [[ ${#MISSING_PACKAGES[@]} -gt 0 ]]; then
    log_warn "Missing packages: ${MISSING_PACKAGES[*]}"
    log_info "You may need to run: pip install -r requirements.txt"
else
    log_info "✓ All required packages are available"
fi

# Test .env file loading
log_info "Testing .env file loading..."

# Create a test .env file
cat > .env.test << EOF
TEST_VAR1=value1
TEST_VAR2=value2
EOF

# Test the loading function
load_env_file() {
    local env_file="$1"
    if [[ -f "$env_file" ]]; then
        set -a && source "$env_file" && set +a
        return 0
    else
        return 1
    fi
}

if load_env_file ".env.test"; then
    if [[ "$TEST_VAR1" == "value1" ]] && [[ "$TEST_VAR2" == "value2" ]]; then
        log_info "✓ .env file loading works correctly"
    else
        log_error "✗ .env file variables not loaded correctly"
    fi
else
    log_error "✗ .env file loading failed"
fi

# Cleanup
rm -f .env.test
unset TEST_VAR1 TEST_VAR2

# Test script permissions
log_info "Testing script permissions..."
for script in start_mcp_dev.sh; do
    if [[ -x "$script" ]]; then
        log_info "✓ $script is executable"
    else
        log_warn "✗ $script is not executable (run: chmod +x $script)"
    fi
done

echo ""
log_info "=== Test Summary ==="

if [[ ${#MISSING_PACKAGES[@]} -eq 0 ]]; then
    log_info "✓ Environment is ready for MCP server"
    echo ""
    log_info "You can now start the server with:"
    echo "  ./start_mcp_dev.sh          # Start MCP server (development settings)"
    echo ""
    log_info "For production, set environment variables:"
    echo "  export MCP_SERVER_HOST=0.0.0.0"
    echo "  export MCP_SERVER_PORT=8080"
    echo "  export MSB_LOG_LEVEL=WARNING"
    echo "  ./start_mcp_dev.sh"
else
    log_warn "⚠ Environment needs package installation"
    echo ""
    log_info "Install missing packages with:"
    echo "  pip install -r requirements.txt"
fi
