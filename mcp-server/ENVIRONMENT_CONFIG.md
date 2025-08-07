# Environment Configuration Guide

This document provides comprehensive information about configuring the HTTP Streamable MCP Server for Microsandbox through environment variables.

## MCP Server Configuration

### Core Server Settings

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MCP_SERVER_HOST` | `localhost` | Server host address to bind to | `0.0.0.0`, `127.0.0.1` |
| `MCP_SERVER_PORT` | `8775` | Server port number | `8080`, `9000` |
| `MCP_ENABLE_CORS` | `false` | Enable CORS support for web clients | `true`, `false` |

### Example Configurations

#### Development Environment
```bash
export MCP_SERVER_HOST="localhost"
export MCP_SERVER_PORT="8775"
export MCP_ENABLE_CORS="true"
```

#### Production Environment
```bash
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT="8080"
export MCP_ENABLE_CORS="false"
```

#### Docker Environment
```bash
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT="8775"
export MCP_ENABLE_CORS="true"
```

## Microsandbox Wrapper Configuration

The MCP server inherits configuration from the underlying MicrosandboxWrapper. These settings control the behavior of sandbox operations.

### Server Connection

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MSB_SERVER_URL` | `http://127.0.0.1:5555` | Microsandbox server URL | `http://localhost:5555` |
| `MSB_API_KEY` | None | Optional API key for authentication | `your-secret-key` |
| `MSB_CONNECTION_TIMEOUT` | `30` | Connection timeout in seconds | `60`, `120` |
| `MSB_REQUEST_TIMEOUT` | `300` | Request timeout in seconds | `600`, `1200` |

### Session Management

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MSB_MAX_SESSIONS` | `10` | Maximum concurrent sessions | `20`, `50` |
| `MSB_SESSION_TIMEOUT` | `1800` | Session timeout in seconds (30 min) | `3600`, `7200` |
| `MSB_DEFAULT_FLAVOR` | `small` | Default resource flavor | `medium`, `large` |
| `MSB_SESSION_CLEANUP_INTERVAL` | `300` | Cleanup interval in seconds | `600`, `900` |

### Resource Limits

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MSB_MAX_TOTAL_MEMORY_MB` | `8192` | Total memory limit in MB | `16384`, `32768` |
| `MSB_MAX_TOTAL_CPU_CORES` | `8` | Total CPU core limit | `16`, `32` |
| `MSB_MAX_EXECUTION_TIME` | `300` | Max execution time in seconds | `600`, `1200` |

### Volume Mappings

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MSB_SHARED_VOLUME_PATH` | `[]` | JSON array of volume mappings | `["/host/data:/sandbox/data"]` |
| `MSB_ENABLE_VOLUME_MAPPING` | `true` | Enable volume mapping feature | `false` |

### Logging Configuration

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `MSB_LOG_LEVEL` | `INFO` | Logging level | `DEBUG`, `WARNING`, `ERROR` |
| `MSB_LOG_FORMAT` | `json` | Log format | `text`, `json` |
| `MSB_LOG_FILE` | None | Log file path (stdout if not set) | `/var/log/mcp-server.log` |

## Configuration Examples

### High-Throughput Setup

For handling many small, quick operations:

```bash
# MCP Server
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT="8775"
export MCP_ENABLE_CORS="false"

# Wrapper Configuration
export MSB_MAX_SESSIONS="50"
export MSB_SESSION_TIMEOUT="300"  # 5 minutes
export MSB_DEFAULT_FLAVOR="small"
export MSB_SESSION_CLEANUP_INTERVAL="60"  # 1 minute
export MSB_MAX_EXECUTION_TIME="60"  # 1 minute
```

### Resource-Intensive Setup

For handling fewer, long-running operations:

```bash
# MCP Server
export MCP_SERVER_HOST="127.0.0.1"
export MCP_SERVER_PORT="8775"
export MCP_ENABLE_CORS="false"

# Wrapper Configuration
export MSB_MAX_SESSIONS="5"
export MSB_SESSION_TIMEOUT="7200"  # 2 hours
export MSB_DEFAULT_FLAVOR="large"
export MSB_MAX_TOTAL_MEMORY_MB="16384"  # 16GB
export MSB_MAX_EXECUTION_TIME="1800"  # 30 minutes
```

### Development Setup

For local development with debugging:

```bash
# MCP Server
export MCP_SERVER_HOST="localhost"
export MCP_SERVER_PORT="8775"
export MCP_ENABLE_CORS="true"

# Wrapper Configuration
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_MAX_SESSIONS="5"
export MSB_SESSION_TIMEOUT="1800"  # 30 minutes
export MSB_DEFAULT_FLAVOR="small"
export MSB_LOG_LEVEL="DEBUG"
export MSB_LOG_FORMAT="text"

# Volume mapping for development
export MSB_SHARED_VOLUME_PATH='["/tmp/mcp-dev:/sandbox/shared"]'
```

### Docker Compose Setup

Example docker-compose.yml environment configuration:

```yaml
version: '3.8'
services:
  mcp-server:
    image: mcp-server:latest
    ports:
      - "8775:8775"
    environment:
      # MCP Server
      MCP_SERVER_HOST: "0.0.0.0"
      MCP_SERVER_PORT: "8775"
      MCP_ENABLE_CORS: "true"
      
      # Wrapper Configuration
      MSB_SERVER_URL: "http://microsandbox:5555"
      MSB_MAX_SESSIONS: "20"
      MSB_SESSION_TIMEOUT: "3600"
      MSB_DEFAULT_FLAVOR: "medium"
      MSB_LOG_LEVEL: "INFO"
      MSB_LOG_FORMAT: "json"
      
      # Volume mappings
      MSB_SHARED_VOLUME_PATH: '["/data/input:/sandbox/input", "/data/output:/sandbox/output"]'
    
    volumes:
      - ./data/input:/data/input
      - ./data/output:/data/output
    
    depends_on:
      - microsandbox
  
  microsandbox:
    image: microsandbox:latest
    ports:
      - "5555:5555"
```

## Configuration Validation

The server validates configuration on startup and will exit with an error if invalid values are provided:

### Port Validation
- Must be between 1 and 65535
- Must not be already in use

### Host Validation
- Must be a valid IP address or hostname
- Cannot be empty

### Resource Limits
- Memory limits must be positive integers
- CPU limits must be positive integers
- Timeouts must be positive integers

### Volume Mappings
- Must be valid JSON array format
- Paths must be absolute
- Host paths must exist (if validation is enabled)

## Environment File Support

You can use a `.env` file to manage configuration:

```bash
# .env file
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8775
MCP_ENABLE_CORS=true

MSB_SERVER_URL=http://127.0.0.1:5555
MSB_MAX_SESSIONS=10
MSB_SESSION_TIMEOUT=1800
MSB_DEFAULT_FLAVOR=small
MSB_LOG_LEVEL=INFO
```

Load the environment file before starting:

```bash
# Load environment and start server
set -a && source .env && set +a
python -m mcp_server.main
```

## Security Considerations

### Network Security
- Bind to `127.0.0.1` for local-only access
- Use `0.0.0.0` only when external access is required
- Consider using a reverse proxy for SSL termination

### Resource Security
- Set appropriate resource limits to prevent abuse
- Monitor resource usage regularly
- Use session timeouts to prevent resource leaks

### CORS Security
- Only enable CORS when necessary
- Consider restricting CORS origins in production
- Validate all client requests regardless of CORS settings

## Troubleshooting Configuration

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using the port
   lsof -i :8775
   
   # Use a different port
   export MCP_SERVER_PORT=8001
   ```

2. **Cannot connect to microsandbox server**
   ```bash
   # Verify microsandbox server is running
   curl -s http://127.0.0.1:5555/api/v1/health
   
   # Check MSB_SERVER_URL configuration
   echo $MSB_SERVER_URL
   ```

3. **Resource limit errors**
   ```bash
   # Increase limits
   export MSB_MAX_SESSIONS=20
   export MSB_MAX_TOTAL_MEMORY_MB=16384
   ```

4. **Volume mapping issues**
   ```bash
   # Verify paths exist
   ls -la /host/path
   
   # Check JSON format
   echo $MSB_SHARED_VOLUME_PATH | python -m json.tool
   ```

### Debug Configuration

Enable debug logging to troubleshoot configuration issues:

```bash
export MSB_LOG_LEVEL=DEBUG
python -m mcp_server.main --log-level DEBUG
```

This will show detailed information about:
- Configuration loading and validation
- Server startup process
- Connection attempts to microsandbox server
- Resource allocation and limits
- Session management operations

## Configuration Best Practices

1. **Use Environment-Specific Configs**: Maintain separate configurations for development, staging, and production
2. **Document Your Settings**: Keep a record of why specific values were chosen
3. **Monitor Resource Usage**: Regularly check if limits are appropriate
4. **Test Configuration Changes**: Validate changes in a non-production environment first
5. **Use Configuration Management**: Consider tools like Ansible, Terraform, or Kubernetes ConfigMaps for production deployments
6. **Secure Sensitive Values**: Use secrets management for API keys and sensitive configuration
7. **Version Control**: Keep configuration files in version control (excluding secrets)
8. **Health Monitoring**: Implement monitoring to detect configuration-related issues