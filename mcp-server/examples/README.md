# MicrosandboxWrapper Usage Examples

This directory contains comprehensive examples demonstrating how to use the MicrosandboxWrapper in various scenarios.

## Prerequisites

Before running the examples, ensure you have:

1. **Microsandbox server running**:
   ```bash
   ./start_msbserver_debug.sh
   ```

2. **Environment variables configured** (see [ENVIRONMENT_CONFIG.md](../ENVIRONMENT_CONFIG.md)):
   ```bash
   export MSB_SERVER_URL="http://127.0.0.1:5555"
   export MSB_SESSION_TIMEOUT="1800"
   export MSB_MAX_SESSIONS="10"
   # ... other variables as needed
   ```

3. **Python dependencies installed**:
   ```bash
   pip install -r requirements.txt
   ```

## Example Files

### 1. Basic Usage (`basic_usage.py`)

Demonstrates fundamental operations:
- **Code execution** (Python and Node.js)
- **Command execution**
- **Session reuse**
- **Different sandbox templates**
- **Basic error handling**
- **Session management**
- **Resource monitoring**

**Run it:**
```bash
cd mcp-server
python examples/basic_usage.py
```

**Key concepts covered:**
- Creating and using the wrapper with async context manager
- Executing code in different templates (Python, Node.js)
- Reusing sessions for stateful operations
- Handling execution errors gracefully
- Monitoring active sessions and resources

### 2. Advanced Usage (`advanced_usage.py`)

Demonstrates advanced features:
- **Volume mapping and file operations**
- **Concurrent execution**
- **Background task management**
- **Resource limits and enforcement**
- **Custom configuration**
- **Error recovery scenarios**
- **Orphan cleanup**
- **Performance monitoring**

**Run it:**
```bash
cd mcp-server
python examples/advanced_usage.py
```

**Key concepts covered:**
- Sharing files between host and sandbox using volume mappings
- Running multiple operations concurrently
- Managing background cleanup tasks
- Handling resource limits and quotas
- Custom configuration management
- Recovering from various error conditions

## Example Scenarios

### Basic Code Execution

```python
async with MicrosandboxWrapper() as wrapper:
    result = await wrapper.execute_code(
        code="print('Hello, World!')",
        template="python",
        flavor=SandboxFlavor.SMALL
    )
    print(f"Output: {result.stdout}")
```

### Session Reuse

```python
async with MicrosandboxWrapper() as wrapper:
    # First execution - creates session
    result1 = await wrapper.execute_code(
        code="x = 42",
        template="python"
    )
    
    # Second execution - reuses session
    result2 = await wrapper.execute_code(
        code="print(f'x = {x}')",
        template="python",
        session_id=result1.session_id
    )
```

### Volume Mapping

```python
config = WrapperConfig.from_env()
config.shared_volume_mappings = [
    "/host/input:/sandbox/input",
    "/host/output:/sandbox/output"
]

async with MicrosandboxWrapper(config=config) as wrapper:
    result = await wrapper.execute_code(
        code="""
        with open('/sandbox/input/data.txt', 'r') as f:
            data = f.read()
        
        with open('/sandbox/output/result.txt', 'w') as f:
            f.write(data.upper())
        """,
        template="python"
    )
```

### Concurrent Execution

```python
async with MicrosandboxWrapper() as wrapper:
    tasks = [
        wrapper.execute_code("import time; time.sleep(1); print('Task 1')", template="python"),
        wrapper.execute_code("import time; time.sleep(1); print('Task 2')", template="python"),
        wrapper.execute_code("import time; time.sleep(1); print('Task 3')", template="python"),
    ]
    
    results = await asyncio.gather(*tasks)
    for i, result in enumerate(results):
        print(f"Task {i+1}: {result.stdout.strip()}")
```

### Resource Monitoring

```python
async with MicrosandboxWrapper() as wrapper:
    # Get resource statistics
    stats = await wrapper.get_resource_stats()
    print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
    print(f"Memory usage: {stats.total_memory_mb} MB")
    print(f"CPU usage: {stats.total_cpus} cores")
    
    # List active sessions
    sessions = await wrapper.get_sessions()
    for session in sessions:
        print(f"Session {session.session_id}: {session.template} ({session.flavor.value})")
```

### Error Handling

```python
async with MicrosandboxWrapper() as wrapper:
    try:
        result = await wrapper.execute_code(
            code="x = 1 / 0",  # This will cause an error
            template="python"
        )
        if not result.success:
            print(f"Execution failed: {result.stderr}")
    except MicrosandboxWrapperError as e:
        print(f"Wrapper error: {e}")
```

## Configuration Examples

### Environment Variables

```bash
# Server configuration
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_API_KEY="your-api-key"

# Session configuration
export MSB_SESSION_TIMEOUT="1800"  # 30 minutes
export MSB_MAX_SESSIONS="10"
export MSB_CLEANUP_INTERVAL="60"   # 1 minute

# Sandbox configuration
export MSB_DEFAULT_FLAVOR="small"
export MSB_EXECUTION_TIMEOUT="300" # 5 minutes

# Volume mappings (JSON array format)
export MSB_SHARED_VOLUME_PATH='["/host/shared:/sandbox/shared", "/host/data:/sandbox/data"]'

# Resource limits
export MSB_MAX_TOTAL_MEMORY_MB="8192"  # 8GB total

# Cleanup configuration
export MSB_ORPHAN_CLEANUP_INTERVAL="600"  # 10 minutes
```

### Programmatic Configuration

```python
from microsandbox_wrapper import WrapperConfig, SandboxFlavor

config = WrapperConfig(
    server_url="http://127.0.0.1:5555",
    session_timeout=3600,  # 1 hour
    max_concurrent_sessions=5,
    default_flavor=SandboxFlavor.MEDIUM,
    default_execution_timeout=300,  # 5 minutes
    shared_volume_mappings=[
        "/host/input:/sandbox/input",
        "/host/output:/sandbox/output"
    ],
    cleanup_interval=30,  # 30 seconds
    orphan_cleanup_interval=600  # 10 minutes
)

async with MicrosandboxWrapper(config=config) as wrapper:
    # Use wrapper with custom configuration
    pass
```

## Common Patterns

### 1. Stateful Code Execution

When you need to maintain state between executions:

```python
async with MicrosandboxWrapper() as wrapper:
    # Initialize state
    init_result = await wrapper.execute_code(
        code="data = {'counter': 0}",
        template="python"
    )
    session_id = init_result.session_id
    
    # Use state in subsequent executions
    for i in range(5):
        result = await wrapper.execute_code(
            code=f"""
            data['counter'] += 1
            print(f'Counter: {{data["counter"]}}')
            """,
            template="python",
            session_id=session_id
        )
        print(result.stdout.strip())
```

### 2. File Processing Pipeline

When processing files through multiple steps:

```python
config = WrapperConfig.from_env()
config.shared_volume_mappings = ["/host/data:/sandbox/data"]

async with MicrosandboxWrapper(config=config) as wrapper:
    # Step 1: Read and validate data
    result1 = await wrapper.execute_code(
        code="""
        import json
        with open('/sandbox/data/input.json', 'r') as f:
            data = json.load(f)
        print(f'Loaded {len(data)} records')
        """,
        template="python"
    )
    
    # Step 2: Process data (reuse session)
    result2 = await wrapper.execute_code(
        code="""
        processed = [item for item in data if item.get('valid', True)]
        with open('/sandbox/data/processed.json', 'w') as f:
            json.dump(processed, f)
        print(f'Processed {len(processed)} valid records')
        """,
        template="python",
        session_id=result1.session_id
    )
```

### 3. Multi-Language Workflow

When combining different programming languages:

```python
async with MicrosandboxWrapper() as wrapper:
    # Python data processing
    python_result = await wrapper.execute_code(
        code="""
        import json
        data = [i**2 for i in range(10)]
        with open('/tmp/data.json', 'w') as f:
            json.dump(data, f)
        print('Data prepared by Python')
        """,
        template="python"
    )
    
    # Node.js data consumption
    node_result = await wrapper.execute_code(
        code="""
        const fs = require('fs');
        const data = JSON.parse(fs.readFileSync('/tmp/data.json', 'utf8'));
        const sum = data.reduce((a, b) => a + b, 0);
        console.log(`Sum calculated by Node.js: ${sum}`);
        """,
        template="node"
    )
```

## Troubleshooting

### Common Issues

1. **Server Connection Failed**
   ```
   Error: Cannot connect to microsandbox server
   ```
   **Solution**: Ensure the server is running with `./start_msbserver_debug.sh`

2. **Resource Limit Exceeded**
   ```
   ResourceLimitError: Maximum concurrent sessions (10) exceeded
   ```
   **Solution**: Wait for sessions to timeout or manually stop unused sessions

3. **Volume Mapping Not Working**
   ```
   FileNotFoundError: [Errno 2] No such file or directory: '/sandbox/input/file.txt'
   ```
   **Solution**: Check volume mapping configuration and ensure host paths exist

4. **Session Not Found**
   ```
   SessionNotFoundError: Session abc123 not found
   ```
   **Solution**: Session may have timed out; create a new session or check session timeout settings

### Debug Mode

Enable debug logging for more detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export MSB_LOG_LEVEL="DEBUG"
```

### Health Check

Verify server connectivity:

```bash
curl -s http://127.0.0.1:5555/api/v1/health
```

## Next Steps

After running these examples:

1. **Read the API documentation** in the main README
2. **Check configuration options** in ENVIRONMENT_CONFIG.md
3. **Review error handling** in ERROR_HANDLING.md
4. **Explore integration tests** in the integration_tests/ directory
5. **Build your own MCP Server** using the wrapper

## Support

For issues and questions:
- Check the troubleshooting guide in TROUBLESHOOTING.md
- Review the integration tests for more usage patterns
- Examine the wrapper source code for advanced customization