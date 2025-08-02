# <sub><img height="18" src="https://octicons-col.vercel.app/plug/A770EF">&nbsp;&nbsp;MODEL CONTEXT PROTOCOL</sub>

microsandbox server is also a **Model Context Protocol (MCP) server**, enabling seamless integration with AI tools and agents that support MCP.

<div align="center">
  <video src="https://github.com/user-attachments/assets/d8f8d854-aebe-4385-b447-3e22a065296b" width="800" controls>
  </video>
</div>

#### What is MCP?

The Model Context Protocol (MCP) is an open standard that allows AI models to securely connect to external data sources and tools. It provides a standardized way for AI assistants to access and interact with various services through a unified interface.

With MCP, your AI can:

- Execute code in secure sandboxes
- Access real-time data and services
- Perform complex operations safely
- Maintain context across interactions

##

#### Connection Details

microsandbox server supports MCP connections via **Streamable HTTP transport only**.

- **Transport**: HTTP
- **URL**: `http://localhost:5555/mcp`
- **Method**: Streamable HTTP

##### Server Configuration

When running your microsandbox server, it automatically exposes MCP endpoints at:

```
http://localhost:5555/mcp
```

> [!NOTE]
> The MCP endpoint uses the same host and port as your main microsandbox server.

##

#### Simplified Interface

The simplified MCP interface provides an easier way to work with sandboxes through automatic session management and predefined configurations.

##### Key Features

- **Automatic Session Management**: Sessions are created automatically when needed and reused across calls
- **Predefined Resource Flavors**: Choose from `small`, `medium`, or `large` resource configurations
- **Template-Based Environments**: Simply specify `python` or `node` for the appropriate runtime
- **Shared Volume Support**: Automatic file sharing between host and sandbox via environment configuration
- **Intelligent Error Handling**: User-friendly error messages with recovery suggestions

##### Resource Flavors

| Flavor | CPU | Memory | Use Case |
|--------|-----|--------|----------|
| `small` | 1 CPU | 1GB RAM | Basic scripts, simple tasks |
| `medium` | 2 CPUs | 2GB RAM | Moderate workloads, data processing |
| `large` | 4 CPUs | 4GB RAM | Intensive tasks, complex computations |

##### Supported Templates

- `python` - Python runtime environment (uses `microsandbox/python` image)
- `node` - Node.js/JavaScript runtime (uses `microsandbox/node` image)

##

#### Getting Started

1. **Start your microsandbox server**:

   ```sh
   msb server start --dev
   ```

2. **Configure your MCP client** with the connection details above

3. **Begin using sandbox tools** through your AI assistant

   Try these example prompts with automatic session management:

   ```
   "Execute this Python code: print('Hello from microsandbox!')"
   ```

   ```
   "Run this Node.js code: console.log('Hello from Node.js sandbox!')"
   ```

   ```
   "Execute this shell command: curl -s https://api.github.com/users/octocat"
   ```

   ```
   "Create a Python sandbox and run a simple hello world program"
   ```

   ```
   "Start a Node.js sandbox, install express, and create a basic web server"
   ```

##

#### Available Tools

The microsandbox MCP server provides the following tools with automatic session management and simplified configuration:

- `execute_code` - Execute code with automatic session management
- `execute_command` - Run shell commands with automatic session management  
- `get_sessions` - List and monitor active sessions
- `stop_session` - Stop specific sessions and clean up resources
- `get_volume_path` - Get shared volume path for file access

##

#### Simplified Tool Reference

##### execute_code

Execute code in a sandbox with automatic session management.

**Parameters:**
- `code` (required): The code to execute
- `template` (optional): Runtime template (`python` or `node`)
- `session_id` (optional): Reuse existing session, or create new if omitted
- `flavor` (optional): Resource flavor (`small`, `medium`, `large`) - defaults to `small`

**Example:**
```json
{
  "code": "print('Hello World!')",
  "template": "python",
  "flavor": "small"
}
```

**Response:**
```json
{
  "session_id": "session-abc123",
  "stdout": "Hello World!\n",
  "stderr": "",
  "exit_code": null,
  "execution_time_ms": 150,
  "session_created": true
}
```

##### execute_command

Execute shell commands in a sandbox with automatic session management.

**Parameters:**
- `command` (required): The command to execute
- `args` (optional): Array of command arguments
- `template` (optional): Runtime template (`python` or `node`)
- `session_id` (optional): Reuse existing session, or create new if omitted
- `flavor` (optional): Resource flavor - defaults to `small`

**Example:**
```json
{
  "command": "curl",
  "args": ["-s", "https://api.github.com/users/octocat"],
  "template": "python"
}
```

##### get_sessions

List active sandbox sessions and their status.

**Parameters:**
- `session_id` (optional): Get info for specific session, or list all if omitted

**Response:**
```json
{
  "sessions": [
    {
      "id": "session-abc123",
      "language": "python",
      "flavor": "small",
      "status": "ready",
      "created_at": "2024-01-15T10:30:00Z",
      "last_accessed": "2024-01-15T10:35:00Z",
      "uptime_seconds": 300
    }
  ]
}
```

##### stop_session

Stop a specific session and clean up its resources.

**Parameters:**
- `session_id` (required): The session ID to stop

**Response:**
```json
{
  "session_id": "session-abc123",
  "success": true,
  "message": "Session stopped successfully"
}
```

##### get_volume_path

Get the shared volume path inside sandbox containers.

**Parameters:**
- `session_id` (optional): Session context (currently unused)

**Response:**
```json
{
  "volume_path": "/shared",
  "description": "Shared volume for file exchange between host and sandbox",
  "available": true
}
```

##

#### Additional Documentation

For comprehensive guides and examples:

- **[Environment Configuration Guide](ENVIRONMENT_CONFIG.md)** - Complete environment variable setup and configuration options
- **[Usage Examples](USAGE_EXAMPLES.md)** - Detailed examples for all tools and common workflows  
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Solutions for common issues and debugging tips

##

#### Key Benefits

The microsandbox MCP interface provides:
- **Automatic session creation and management** - No need to manually start/stop sandboxes
- **Predefined resource configurations** - Simple `small`, `medium`, `large` flavors
- **Template-based environments** - Just specify `python` or `node`
- **Better error handling** - User-friendly messages with recovery suggestions
- **Consistent tool interface** - All operations follow the same pattern
