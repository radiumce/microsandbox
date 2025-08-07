# HTTP Streamable MCP Server for Microsandbox

A Model Context Protocol (MCP) server that provides HTTP streamable transport for the Microsandbox service. This server acts as a lightweight protocol adapter, converting MCP protocol messages to Microsandbox wrapper calls while maintaining full compatibility with MCP clients.

## Overview

The HTTP Streamable MCP Server provides a standard MCP interface for executing code and commands in isolated sandbox environments. It implements the MCP HTTP streamable transport protocol and integrates seamlessly with the existing MicrosandboxWrapper for session management, resource allocation, and error handling.

### Key Features

- **🌐 MCP Protocol Compliance**: Full support for MCP HTTP streamable transport
- **🔧 Standard MCP Tools**: Execute code, run commands, manage sessions via MCP protocol
- **🚀 Lightweight Design**: Thin protocol layer that leverages existing wrapper functionality
- **🔄 Session Management**: Automatic session creation, reuse, and cleanup through MCP interface
- **📊 Resource Management**: Built-in resource limits and monitoring accessible via MCP tools
- **🔧 Multiple Templates**: Support for Python, Node.js, and other sandbox environments
- **📁 Volume Mapping**: Access to configured volume mappings through MCP tools
- **⚡ Concurrent Execution**: Handle multiple MCP requests in parallel
- **🛡️ Error Handling**: MCP-compliant error responses with detailed error information
- **🌍 CORS Support**: Optional CORS support for web-based MCP clients

## Quick Start

### Installation

```bash
# Clone the repository and navigate to mcp-server directory
cd mcp-server

# Install dependencies
pip install -r requirements.txt
```

### Start the Microsandbox Server

```bash
# Start the microsandbox server (from project root)
./start_msbserver_debug.sh

# Verify server is running
curl -s http://127.0.0.1:5555/api/v1/health
```

### Start the MCP Server

```bash
# Start the MCP server with default settings
python -m mcp_server.main

# Or with custom configuration
MCP_SERVER_HOST=0.0.0.0 MCP_SERVER_PORT=9000 MCP_ENABLE_CORS=true python -m mcp_server.main
```

### Using with MCP Clients

The server provides standard MCP tools that can be used with any MCP-compatible client:

#### Available Tools

- **execute_code**: Execute code in a sandbox
- **execute_command**: Execute complete command lines with pipes, redirections, etc.
- **get_sessions**: Get information about active sessions
- **stop_session**: Stop a specific session
- **get_volume_path**: Get configured volume mappings

#### Example MCP Client Usage

```python
import asyncio
import aiohttp
import json

async def call_mcp_tool():
    """Example of calling MCP tools via HTTP"""
    
    # MCP JSON-RPC request to execute Python code
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {
                "code": "print('Hello from MCP!')",
                "template": "python",
                "flavor": "small"
            }
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/mcp",
            json=request,
            headers={"Content-Type": "application/json"}
        ) as response:
            result = await response.json()
            print(f"Result: {result}")

asyncio.run(call_mcp_tool())
```

## Documentation

### 📚 Complete Documentation

- **[Environment Configuration](ENVIRONMENT_CONFIG.md)** - Comprehensive environment variable configuration guide
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)** - Production deployment instructions for various environments
- **[MCP Troubleshooting Guide](MCP_TROUBLESHOOTING_GUIDE.md)** - MCP-specific troubleshooting and solutions
- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference with all classes, methods, and data models
- **[Configuration Guide](CONFIGURATION_GUIDE.md)** - Wrapper configuration options and environment setup
- **[Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)** - General wrapper troubleshooting and solutions

### 📖 Examples and Guides

- **[Usage Examples](examples/README.md)** - Comprehensive examples for all features
  - [Basic Usage](examples/basic_usage.py) - Fundamental operations and patterns
  - [Advanced Usage](examples/advanced_usage.py) - Advanced features and complex scenarios
- **[Integration Tests](integration_tests/)** - Real-world usage patterns and test scenarios

### 📋 Additional Resources

- **[Error Handling Guide](ERROR_HANDLING.md)** - Detailed error handling strategies
- **[Background Task Management](BACKGROUND_TASK_MANAGEMENT.md)** - Managing background processes
- **[Orphan Cleanup Guide](ORPHAN_CLEANUP.md)** - Resource cleanup and management

## Core Concepts

### MCP Tools

The server provides standard MCP tools for sandbox operations:

#### execute_code Tool
Execute code in a sandbox with automatic session management:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "print('Hello, World!')",
      "template": "python",
      "flavor": "small",
      "session_id": "optional-session-id",
      "timeout": 30
    }
  }
}
```

#### execute_command Tool
Execute complete command lines with pipes, redirections, and complex shell constructs:

```json
{
  "jsonrpc": "2.0", 
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "execute_command",
    "arguments": {
      "command": "ls -la /tmp | grep -E '\\.(py|txt)$' | head -5",
      "template": "python",
      "session_id": "optional-session-id"
    }
  }
}
```

**Key features:**
- Support for pipes (`|`), redirections (`>`, `>>`), and command chaining (`&&`, `||`)
- Environment variables and shell expansions
- Complex command workflows in a single call
- Much more flexible than traditional command+args approach

### Sessions

Sessions represent persistent sandbox environments that can be reused across multiple MCP tool calls. Session IDs are returned in tool responses and can be used in subsequent calls:

```json
// First call creates a session
{
  "jsonrpc": "2.0",
  "result": {
    "content": [{"type": "text", "text": "42"}],
    "session_id": "session-123",
    "session_created": true
  }
}

// Reuse session in next call
{
  "name": "execute_code",
  "arguments": {
    "code": "print(x)",
    "session_id": "session-123"
  }
}
```

### Resource Flavors

Choose appropriate resource configurations for your workloads:

- **small**: 1 CPU, 1GB RAM - Light workloads, quick scripts
- **medium**: 2 CPU, 2GB RAM - Moderate processing, data analysis  
- **large**: 4 CPU, 4GB RAM - Heavy computation, complex operations

### Volume Mappings

Access configured volume mappings through the `get_volume_path` tool:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call", 
  "params": {
    "name": "get_volume_path",
    "arguments": {}
  }
}
```

## Configuration

### MCP Server Environment Variables

Configure the MCP server using environment variables:

```bash
# MCP Server Configuration
export MCP_SERVER_HOST="localhost"        # Server host address (default: localhost)
export MCP_SERVER_PORT="8000"            # Server port number (default: 8000)
export MCP_ENABLE_CORS="false"           # Enable CORS support (default: false)

# Microsandbox Wrapper Configuration (inherited)
export MSB_SERVER_URL="http://127.0.0.1:5555"  # Microsandbox server URL
export MSB_API_KEY="your-api-key"              # Optional API key
export MSB_SESSION_TIMEOUT="1800"              # Session timeout in seconds
export MSB_MAX_SESSIONS="10"                   # Maximum concurrent sessions
export MSB_DEFAULT_FLAVOR="small"              # Default resource flavor
export MSB_SHARED_VOLUME_PATH='["/host/data:/sandbox/data"]'  # Volume mappings
```

### Command Line Options

```bash
# Start server with command line options
python -m mcp_server.main --host 0.0.0.0 --port 9000 --enable-cors --log-level DEBUG

# Available options:
#   --host HOST           Server host address
#   --port PORT           Server port number  
#   --enable-cors         Enable CORS support
#   --log-level LEVEL     Set logging level (DEBUG, INFO, WARNING, ERROR)
```

### Configuration Examples

#### Development Setup
```bash
# Development with CORS enabled for web clients
export MCP_SERVER_HOST="localhost"
export MCP_SERVER_PORT="8000"
export MCP_ENABLE_CORS="true"
python -m mcp_server.main
```

#### Production Setup
```bash
# Production setup with external access
export MCP_SERVER_HOST="0.0.0.0"
export MCP_SERVER_PORT="8080"
export MCP_ENABLE_CORS="false"
export MSB_MAX_SESSIONS="50"
export MSB_SESSION_TIMEOUT="3600"
python -m mcp_server.main --log-level WARNING
```

#### Docker Deployment
```bash
# Docker environment variables
docker run -d \
  -e MCP_SERVER_HOST=0.0.0.0 \
  -e MCP_SERVER_PORT=8000 \
  -e MCP_ENABLE_CORS=true \
  -e MSB_SERVER_URL=http://microsandbox:5555 \
  -p 8000:8000 \
  mcp-server
```

## Advanced Features

### Session Management

List and manage active sessions through MCP tools:

```json
// List all active sessions
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "get_sessions",
    "arguments": {}
  }
}

// Get specific session info
{
  "jsonrpc": "2.0", 
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_sessions",
    "arguments": {
      "session_id": "session-123"
    }
  }
}

// Stop a session
{
  "jsonrpc": "2.0",
  "id": 6, 
  "method": "tools/call",
  "params": {
    "name": "stop_session",
    "arguments": {
      "session_id": "session-123"
    }
  }
}
```

### Error Handling

The server provides MCP-compliant error responses with detailed information:

```json
// Example error response
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Resource limit exceeded: Maximum memory usage reached",
    "data": {
      "error_code": "RESOURCE_LIMIT_EXCEEDED",
      "category": "resource",
      "severity": "high",
      "recovery_suggestions": [
        "Use a smaller resource flavor",
        "Reduce memory usage in your code"
      ],
      "context": {
        "current_memory_mb": 1024,
        "limit_memory_mb": 1024
      }
    }
  }
}
```

### CORS Support

Enable CORS for web-based MCP clients:

```bash
# Enable CORS for development
export MCP_ENABLE_CORS=true
python -m mcp_server.main

# CORS headers are automatically added to all responses
```

### Health Monitoring

Check server health and status:

```bash
# GET request to server root returns status
curl http://localhost:8000/

# Response includes server info and wrapper status
{
  "status": "healthy",
  "server": "MCP Server for Microsandbox",
  "version": "1.0.0",
  "wrapper_status": "connected"
}
```

## Error Handling

The server provides MCP-compliant error responses following JSON-RPC 2.0 standards:

### Error Code Mapping

| Wrapper Exception | JSON-RPC Code | Description |
|------------------|---------------|-------------|
| ResourceLimitError | -32600 | Invalid Request - Resource limits exceeded |
| ConfigurationError | -32603 | Internal Error - Server configuration issue |
| SandboxCreationError | -32603 | Internal Error - Failed to create sandbox |
| CodeExecutionError | -32603 | Internal Error - Code execution failed |
| CommandExecutionError | -32603 | Internal Error - Command execution failed |
| SessionNotFoundError | -32602 | Invalid Params - Session not found |
| ConnectionError | -32603 | Internal Error - Connection to microsandbox failed |

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Code execution failed: Syntax error in Python code",
    "data": {
      "error_code": "CODE_EXECUTION_ERROR",
      "category": "execution",
      "severity": "medium",
      "recovery_suggestions": [
        "Check your code syntax",
        "Verify the template matches your code language"
      ],
      "context": {
        "template": "python",
        "session_id": "session-123"
      }
    }
  }
}
```

### Client Error Handling

MCP clients should handle errors according to JSON-RPC 2.0 standards:

```python
async def handle_mcp_response(response_data):
    if "error" in response_data:
        error = response_data["error"]
        print(f"Error {error['code']}: {error['message']}")
        
        # Access additional error data if available
        if "data" in error:
            data = error["data"]
            print(f"Error category: {data.get('category')}")
            print(f"Recovery suggestions: {data.get('recovery_suggestions', [])}")
    else:
        # Handle successful response
        result = response_data["result"]
        print(f"Success: {result}")
```

## Testing

### Prerequisites

Ensure the microsandbox server is running before testing:

```bash
# Start microsandbox server
./start_msbserver_debug.sh

# Verify server health
curl -s http://127.0.0.1:5555/api/v1/health
```

### Run Unit Tests

```bash
# Run all unit tests
python -m pytest mcp-server/tests/ -v

# Run specific test categories
python -m pytest mcp-server/tests/test_protocol_compliance.py -v
python -m pytest mcp-server/tests/test_tools.py -v
python -m pytest mcp-server/tests/test_error_handling.py -v
```

### Run Integration Tests

```bash
# Set up test environment
source mcp-server/test_environment_setup.sh

# Run all integration tests
python -m pytest mcp-server/integration_tests/ -v

# Run specific integration tests
python -m pytest mcp-server/integration_tests/test_end_to_end_functionality.py -v
```

### Manual Testing with curl

```bash
# Start MCP server
python -m mcp_server.main &

# Test tools/list endpoint
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test execute_code tool
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "execute_code",
      "arguments": {
        "code": "print(\"Hello from MCP!\")",
        "template": "python"
      }
    }
  }'

# Test server status
curl http://localhost:8000/
```

## Architecture

The MCP server acts as a lightweight protocol adapter:

```
MCP Client
    ↓ (HTTP JSON-RPC)
MCP Server
├── RequestHandler      # HTTP request processing
├── ToolRegistry       # MCP tool management
├── ErrorHandler       # Exception to MCP error conversion
└── MCPServer          # Main server coordination
    ↓ (Python API)
MicrosandboxWrapper
├── SessionManager     # Sandbox session lifecycle
├── ResourceManager    # Resource limits and cleanup
├── ConfigManager      # Configuration management
└── ErrorManager       # Wrapper error handling
    ↓ (HTTP API)
Microsandbox Server
```

### Component Responsibilities

- **MCP Server**: Protocol compliance, tool routing, error conversion
- **MicrosandboxWrapper**: Session management, resource control, business logic
- **Microsandbox Server**: Low-level sandbox operations and container management

### Data Flow

1. MCP client sends JSON-RPC request over HTTP
2. RequestHandler validates and parses the request
3. ToolRegistry routes to appropriate tool implementation
4. Tool calls MicrosandboxWrapper with validated parameters
5. Wrapper executes operation and returns structured result
6. Tool formats result for MCP protocol compliance
7. Server returns JSON-RPC response to client

## Performance Considerations

### Session Reuse

Reuse sessions across MCP tool calls for better performance:

```json
// First call creates session
{
  "method": "tools/call",
  "params": {
    "name": "execute_code", 
    "arguments": {"code": "x = 42", "template": "python"}
  }
}

// Reuse session_id from response in subsequent calls
{
  "method": "tools/call",
  "params": {
    "name": "execute_code",
    "arguments": {
      "code": "print(f'x = {x}')",
      "template": "python", 
      "session_id": "session-123"
    }
  }
}
```

### Resource Planning

Configure wrapper resources based on expected workload:

```bash
# High-throughput, low-resource workload
export MSB_MAX_SESSIONS="50"
export MSB_DEFAULT_FLAVOR="small"
export MSB_SESSION_TIMEOUT="300"  # 5 minutes

# Resource-intensive, long-running workload  
export MSB_MAX_SESSIONS="5"
export MSB_DEFAULT_FLAVOR="large"
export MSB_SESSION_TIMEOUT="3600"  # 1 hour
```

### Concurrent Requests

The server handles multiple MCP requests concurrently. Monitor resource usage:

```bash
# Monitor active sessions
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}'
```

## Best Practices

1. **Session Management**: Reuse sessions for related operations to improve performance
2. **Resource Flavors**: Choose appropriate flavors based on workload requirements
3. **Error Handling**: Implement proper JSON-RPC error handling in MCP clients
4. **Timeouts**: Set appropriate execution timeouts for long-running operations
5. **Monitoring**: Regularly check session status and resource usage
6. **CORS Configuration**: Only enable CORS when needed for web clients
7. **Logging**: Use appropriate log levels for production deployments
8. **Health Checks**: Implement health monitoring for both MCP and microsandbox servers

## Troubleshooting

### Quick Health Checks

```bash
# Check microsandbox server
curl -s http://127.0.0.1:5555/api/v1/health

# Check MCP server status
curl http://localhost:8000/

# Test MCP protocol
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Common Issues

1. **MCP Server won't start**
   - Check if microsandbox server is running first
   - Verify port is not already in use
   - Check environment variable configuration

2. **Tool calls fail with connection errors**
   - Ensure microsandbox server is accessible
   - Check MSB_SERVER_URL configuration
   - Verify network connectivity

3. **Resource limit errors**
   - Increase MSB_MAX_SESSIONS or MSB_MAX_TOTAL_MEMORY_MB
   - Use smaller resource flavors (small instead of large)
   - Stop unused sessions with stop_session tool

4. **Session not found errors**
   - Check if session_id is valid and active
   - Sessions may have expired due to timeout
   - Use get_sessions tool to list active sessions

5. **CORS issues with web clients**
   - Set MCP_ENABLE_CORS=true
   - Check browser console for CORS errors
   - Verify client is sending proper Content-Type headers

### Debug Mode

Run with debug logging for detailed troubleshooting:

```bash
python -m mcp_server.main --log-level DEBUG
```

See the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) for detailed solutions.

## Deployment

### Docker Deployment

Create a Dockerfile for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY mcp-server/ ./mcp-server/
COPY requirements.txt .

RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "-m", "mcp_server.main"]
```

Build and run:

```bash
docker build -t mcp-server .
docker run -d -p 8000:8000 \
  -e MCP_SERVER_HOST=0.0.0.0 \
  -e MSB_SERVER_URL=http://microsandbox:5555 \
  mcp-server
```

### Production Deployment

For production deployments, consider:

1. **Process Management**: Use systemd, supervisor, or similar
2. **Reverse Proxy**: Place behind nginx or similar for SSL/load balancing
3. **Monitoring**: Implement health checks and monitoring
4. **Logging**: Configure structured logging with log rotation
5. **Security**: Restrict network access and use proper authentication

Example systemd service:

```ini
[Unit]
Description=MCP Server for Microsandbox
After=network.target

[Service]
Type=simple
User=mcp-server
WorkingDirectory=/opt/mcp-server
Environment=MCP_SERVER_HOST=127.0.0.1
Environment=MCP_SERVER_PORT=8000
Environment=MSB_SERVER_URL=http://127.0.0.1:5555
ExecStart=/opt/mcp-server/venv/bin/python -m mcp_server.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run unit tests
python -m pytest mcp-server/tests/ -v

# Run integration tests (requires microsandbox server)
./start_msbserver_debug.sh
python -m pytest mcp-server/integration_tests/ -v
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: See the comprehensive guides in this directory
- **Examples**: Check examples/ directory for usage patterns  
- **Issues**: Report bugs and feature requests via GitHub issues
- **MCP Protocol**: See [MCP specification](https://spec.modelcontextprotocol.io/) for protocol details

---

**Ready to get started?** Start the microsandbox server, then run the MCP server and test with your favorite MCP client!