# MicrosandboxWrapper

A high-level Python wrapper for the Microsandbox service, designed to simplify sandbox operations for MCP (Model Context Protocol) servers and other applications.

## Overview

The MicrosandboxWrapper provides a clean, async-first interface for executing code and commands in isolated sandbox environments. It handles session management, resource allocation, error handling, and cleanup automatically, allowing you to focus on your application logic.

### Key Features

- **🚀 Simple API**: Execute code with a single async call
- **🔄 Automatic Session Management**: Sessions are created, reused, and cleaned up automatically
- **📊 Resource Management**: Built-in resource limits, monitoring, and orphan cleanup
- **🔧 Multiple Templates**: Support for Python, Node.js, and other sandbox environments
- **📁 Volume Mapping**: Share files between host and sandbox environments
- **⚡ Concurrent Execution**: Run multiple operations in parallel
- **🛡️ Error Handling**: Comprehensive error handling with detailed error information
- **🧹 Background Cleanup**: Automatic cleanup of expired sessions and orphaned resources

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
# Start the server (from project root)
./start_msbserver_debug.sh
```

### Basic Usage

```python
import asyncio
from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor

async def main():
    async with MicrosandboxWrapper() as wrapper:
        # Execute Python code
        result = await wrapper.execute_code(
            code="print('Hello, World!')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"Output: {result.stdout}")
        print(f"Success: {result.success}")
        print(f"Execution time: {result.execution_time_ms}ms")

asyncio.run(main())
```

## Documentation

### 📚 Complete Documentation

- **[API Documentation](API_DOCUMENTATION.md)** - Complete API reference with all classes, methods, and data models
- **[Configuration Guide](CONFIGURATION_GUIDE.md)** - Comprehensive configuration options and environment setup
- **[Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)** - Common issues, diagnostics, and solutions

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

### Sessions

Sessions represent persistent sandbox environments that can be reused across multiple operations:

```python
async with MicrosandboxWrapper() as wrapper:
    # First execution creates a session
    result1 = await wrapper.execute_code("x = 42", template="python")
    session_id = result1.session_id
    
    # Reuse the session to access previous state
    result2 = await wrapper.execute_code(
        "print(f'x = {x}')", 
        template="python",
        session_id=session_id
    )
```

### Resource Flavors

Choose appropriate resource configurations for your workloads:

- **SMALL**: 1 CPU, 1GB RAM - Light workloads, quick scripts
- **MEDIUM**: 2 CPU, 2GB RAM - Moderate processing, data analysis
- **LARGE**: 4 CPU, 4GB RAM - Heavy computation, complex operations

```python
# Use appropriate flavor for your workload
result = await wrapper.execute_code(
    code="# Heavy computation here",
    flavor=SandboxFlavor.LARGE
)
```

### Volume Mapping

Share files between your host system and sandbox environments:

```python
from microsandbox_wrapper import WrapperConfig

config = WrapperConfig.from_env()
config.shared_volume_mappings = [
    "/host/data:/sandbox/input",
    "/host/results:/sandbox/output"
]

async with MicrosandboxWrapper(config=config) as wrapper:
    result = await wrapper.execute_code("""
        with open('/sandbox/input/data.txt', 'r') as f:
            data = f.read()
        
        processed = data.upper()
        
        with open('/sandbox/output/result.txt', 'w') as f:
            f.write(processed)
    """)
```

## Configuration

### Environment Variables

Configure the wrapper using environment variables:

```bash
# Server configuration
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_API_KEY="your-api-key"

# Session configuration
export MSB_SESSION_TIMEOUT="1800"  # 30 minutes
export MSB_MAX_SESSIONS="10"
export MSB_DEFAULT_FLAVOR="small"

# Volume mappings (JSON array format)
export MSB_SHARED_VOLUME_PATH='["/host/data:/sandbox/data"]'

# Resource limits
export MSB_MAX_TOTAL_MEMORY_MB="8192"  # 8GB total
```

### Programmatic Configuration

```python
from microsandbox_wrapper import WrapperConfig, SandboxFlavor

config = WrapperConfig(
    server_url="http://localhost:5555",
    max_concurrent_sessions=20,
    session_timeout=3600,  # 1 hour
    default_flavor=SandboxFlavor.MEDIUM,
    shared_volume_mappings=[
        "/data/input:/sandbox/input",
        "/data/output:/sandbox/output"
    ]
)

async with MicrosandboxWrapper(config=config) as wrapper:
    # Use wrapper with custom configuration
    pass
```

## Advanced Features

### Concurrent Execution

Execute multiple operations in parallel:

```python
import asyncio

async with MicrosandboxWrapper() as wrapper:
    tasks = [
        wrapper.execute_code("print('Task 1')", template="python"),
        wrapper.execute_code("console.log('Task 2')", template="node"),
        wrapper.execute_code("print('Task 3')", template="python"),
    ]
    
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        print(f"Task {i+1}: {result.stdout.strip()}")
```

### Resource Monitoring

Monitor resource usage and session status:

```python
async with MicrosandboxWrapper() as wrapper:
    # Get resource statistics
    stats = await wrapper.get_resource_stats()
    print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
    print(f"Memory usage: {stats.total_memory_mb} MB")
    
    # List active sessions
    sessions = await wrapper.get_sessions()
    for session in sessions:
        print(f"Session {session.session_id}: {session.template} ({session.flavor.value})")
```

### Background Task Management

Control background cleanup and maintenance tasks:

```python
async with MicrosandboxWrapper() as wrapper:
    # Pause background tasks during critical operations
    await wrapper.pause_background_tasks()
    
    # Perform critical operations
    # ...
    
    # Resume background tasks
    await wrapper.resume_background_tasks()
    
    # Check background task status
    status = await wrapper.get_background_task_status()
    print(f"Overall status: {status['overall_status']}")
```

## Error Handling

The wrapper provides comprehensive error handling with specific exception types:

```python
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError,
    ResourceLimitError,
    CodeExecutionError,
    SessionNotFoundError
)

async with MicrosandboxWrapper() as wrapper:
    try:
        result = await wrapper.execute_code("potentially_failing_code()")
    except ResourceLimitError as e:
        print(f"Resource limit exceeded: {e}")
    except CodeExecutionError as e:
        print(f"Code execution failed: {e}")
    except SessionNotFoundError as e:
        print(f"Session not found: {e}")
    except MicrosandboxWrapperError as e:
        print(f"General wrapper error: {e}")
```

## Testing

### Run Integration Tests

```bash
# Set up test environment
source mcp-server/test_environment_setup.sh

# Run all integration tests
python -m pytest mcp-server/integration_tests/ -v

# Run specific test categories
python -m pytest mcp-server/integration_tests/test_end_to_end_functionality.py -v
```

### Run Examples

```bash
# Basic usage examples
python mcp-server/examples/basic_usage.py

# Advanced usage examples
python mcp-server/examples/advanced_usage.py
```

## Architecture

The wrapper consists of several key components:

```
MicrosandboxWrapper
├── SessionManager      # Manages sandbox sessions and lifecycle
├── ResourceManager     # Handles resource limits and cleanup
├── ConfigManager       # Manages configuration and environment
└── ErrorManager        # Provides unified error handling

Integration with:
├── Microsandbox SDK    # Low-level sandbox operations
├── Background Tasks    # Cleanup and maintenance
└── Logging System     # Comprehensive logging and monitoring
```

## Performance Considerations

### Session Reuse

Reuse sessions for better performance:

```python
# Good: Reuse session for related operations
session_id = None
for i in range(10):
    result = await wrapper.execute_code(
        f"print('Operation {i}')",
        session_id=session_id
    )
    session_id = result.session_id  # Reuse for next operation
```

### Resource Planning

Plan resources based on your workload:

```python
# For high-throughput, low-resource operations
config = WrapperConfig(
    max_concurrent_sessions=50,
    default_flavor=SandboxFlavor.SMALL,
    session_timeout=300  # 5 minutes
)

# For resource-intensive, long-running operations
config = WrapperConfig(
    max_concurrent_sessions=5,
    default_flavor=SandboxFlavor.LARGE,
    session_timeout=3600  # 1 hour
)
```

## Best Practices

1. **Use Context Managers**: Always use `async with` for automatic cleanup
2. **Reuse Sessions**: Reuse sessions for related operations to improve performance
3. **Choose Appropriate Flavors**: Match resource allocation to workload requirements
4. **Handle Errors Gracefully**: Implement proper error handling for production use
5. **Monitor Resources**: Keep track of resource usage to prevent limits
6. **Configure Timeouts**: Set appropriate timeouts for your use case
7. **Use Volume Mappings**: Share data efficiently between host and sandbox

## Troubleshooting

### Quick Health Check

```bash
# Check if server is running
curl -s http://127.0.0.1:5555/api/v1/health

# Run health check script
python mcp-server/examples/health_check.py
```

### Common Issues

1. **Cannot connect to server**: Ensure microsandbox server is running
2. **Resource limits exceeded**: Increase limits or use smaller flavors
3. **Session timeouts**: Increase session timeout or implement keep-alive
4. **Volume mapping issues**: Check paths and permissions

See the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) for detailed solutions.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/ -v

# Run integration tests
./mcp-server/run_integration_tests.sh
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: See the docs/ directory for comprehensive guides
- **Examples**: Check examples/ directory for usage patterns
- **Issues**: Report bugs and feature requests via GitHub issues
- **Discussions**: Join community discussions for questions and ideas

---

**Ready to get started?** Check out the [Basic Usage Examples](examples/basic_usage.py) or dive into the [API Documentation](API_DOCUMENTATION.md)!