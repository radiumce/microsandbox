# MCP Server Startup Script

This directory contains the MCP server startup script optimized for development.

## Available Script

### `start_mcp_dev.sh` - Development Startup Script

A comprehensive development-focused script with automatic configuration and health checks.

**Usage:**
```bash
./start_mcp_dev.sh
```

**Features:**
- Pre-configured development settings
- Automatic microsandbox server startup and health checks
- Creates development directories automatically
- Debug logging enabled by default
- CORS enabled for web clients
- Volume mapping to `./tmp/mcp-dev` and `./data`
- Automatic environment file loading (.env.dev, .env, .env.local)
- Python dependency checking and installation
- Port availability verification
- Comprehensive error handling and logging

## Environment Configuration

### Using .env Files (Automatic Loading)

The startup script automatically loads `.env` files! No need to manually source them.

**File Loading Priority:**
1. Development-specific file (`.env.dev`)
2. General `.env` file
3. Local overrides (`.env.local`)

**Setup:**
```bash
# Option 1: Use example file
cp .env.example .env
# Edit .env with your values
./start_mcp_dev.sh

# Option 2: Use development-specific file
cp .env.template .env.dev
# Edit .env.dev for development
./start_mcp_dev.sh

# Option 3: Create local overrides
echo "MCP_SERVER_PORT=9000" > .env.local
./start_mcp_dev.sh
```

### Direct Environment Variables

Set variables before running:
```bash
export MCP_SERVER_PORT=9000
export MSB_MAX_SESSIONS=20
./start_mcp_dev.sh
```

## Quick Start Examples

### Development Setup
```bash
# Quick development start with default settings
./start_mcp_dev.sh

# With custom port
MCP_SERVER_PORT=9000 ./start_mcp_dev.sh

# With custom microsandbox URL
MSB_SERVER_URL=http://localhost:5556 ./start_mcp_dev.sh
```

### Production Deployment
For production deployment, you can modify the environment variables in `.env` or use environment variables:

```bash
# Production-like configuration
export MCP_SERVER_HOST=0.0.0.0
export MCP_SERVER_PORT=8080
export MSB_MAX_SESSIONS=50
export MSB_LOG_LEVEL=WARNING
export MSB_LOG_FORMAT=json
./start_mcp_dev.sh
```

## Configuration Reference

See `ENVIRONMENT_CONFIG.md` for complete environment variable documentation.

## Troubleshooting

1. **Port already in use**: Change `MCP_SERVER_PORT`
2. **Microsandbox not accessible**: Ensure microsandbox server is running
3. **Permission denied**: Run `chmod +x *.sh`
4. **Missing dependencies**: Run `pip install -r requirements.txt`

For detailed troubleshooting, see `MCP_TROUBLESHOOTING_GUIDE.md`.