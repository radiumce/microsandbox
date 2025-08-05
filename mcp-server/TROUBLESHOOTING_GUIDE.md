# MicrosandboxWrapper Troubleshooting Guide

This guide helps you diagnose and resolve common issues when using the MicrosandboxWrapper.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [Error Messages](#error-messages)
- [Performance Issues](#performance-issues)
- [Configuration Problems](#configuration-problems)
- [Network and Connectivity](#network-and-connectivity)
- [Resource Management](#resource-management)
- [Debugging Tools](#debugging-tools)
- [Getting Help](#getting-help)

## Quick Diagnostics

### Health Check Script

Run this script to quickly diagnose common issues:

```python
#!/usr/bin/env python3
"""Quick health check for MicrosandboxWrapper."""

import asyncio
import os
import sys
import time
from pathlib import Path

# Add mcp-server to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from microsandbox_wrapper import MicrosandboxWrapper, WrapperConfig
from microsandbox_wrapper.exceptions import MicrosandboxWrapperError

async def health_check():
    """Perform comprehensive health check."""
    print("MicrosandboxWrapper Health Check")
    print("=" * 40)
    
    # 1. Configuration check
    print("\n1. Configuration Check:")
    try:
        config = WrapperConfig.from_env()
        print(f"   ✓ Configuration loaded")
        print(f"   Server URL: {config.server_url}")
        print(f"   Max sessions: {config.max_concurrent_sessions}")
        print(f"   Session timeout: {config.session_timeout}s")
    except Exception as e:
        print(f"   ✗ Configuration error: {e}")
        return False
    
    # 2. Server connectivity
    print("\n2. Server Connectivity:")
    try:
        wrapper = MicrosandboxWrapper()
        await wrapper.start()
        print(f"   ✓ Successfully connected to server")
        
        # 3. Basic execution test
        print("\n3. Basic Execution Test:")
        result = await wrapper.execute_code(
            code="print('Health check successful')",
            template="python"
        )
        if result.success:
            print(f"   ✓ Code execution successful")
            print(f"   Session ID: {result.session_id}")
            print(f"   Execution time: {result.execution_time_ms}ms")
        else:
            print(f"   ✗ Code execution failed: {result.stderr}")
        
        # 4. Resource stats
        print("\n4. Resource Statistics:")
        stats = await wrapper.get_resource_stats()
        print(f"   Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        print(f"   Total memory: {stats.total_memory_mb} MB")
        print(f"   Total CPUs: {stats.total_cpus}")
        
        # 5. Background tasks
        print("\n5. Background Task Status:")
        task_status = await wrapper.get_background_task_status()
        print(f"   Overall status: {task_status['overall_status']}")
        for component, info in task_status['components'].items():
            print(f"   {component}: {info['status']}")
        
        await wrapper.stop()
        print(f"\n✓ Health check completed successfully")
        return True
        
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(health_check())
    sys.exit(0 if success else 1)
```

### Environment Check

```bash
#!/bin/bash
# Environment check script

echo "Environment Check"
echo "================="

echo "1. Environment Variables:"
echo "   MSB_SERVER_URL: ${MSB_SERVER_URL:-'Not set (using default)'}"
echo "   MSB_MAX_SESSIONS: ${MSB_MAX_SESSIONS:-'Not set (using default)'}"
echo "   MSB_SESSION_TIMEOUT: ${MSB_SESSION_TIMEOUT:-'Not set (using default)'}"
echo "   MSB_LOG_LEVEL: ${MSB_LOG_LEVEL:-'Not set (using default)'}"

echo -e "\n2. Server Connectivity:"
if command -v curl &> /dev/null; then
    SERVER_URL=${MSB_SERVER_URL:-"http://127.0.0.1:5555"}
    if curl -s --connect-timeout 5 "${SERVER_URL}/api/v1/health" > /dev/null; then
        echo "   ✓ Server is accessible"
    else
        echo "   ✗ Cannot connect to server at ${SERVER_URL}"
        echo "   Make sure the server is running: ./start_msbserver_debug.sh"
    fi
else
    echo "   ? curl not available, cannot test connectivity"
fi

echo -e "\n3. Python Environment:"
python3 -c "
import sys
print(f'   Python version: {sys.version.split()[0]}')
try:
    import microsandbox_wrapper
    print('   ✓ MicrosandboxWrapper module available')
except ImportError as e:
    print(f'   ✗ MicrosandboxWrapper not available: {e}')
"
```

## Common Issues

### 1. Cannot Connect to Server

**Symptoms:**
- `ConnectionError: Cannot connect to microsandbox server`
- Timeouts during wrapper initialization
- Health check failures

**Diagnosis:**
```bash
# Check if server is running
curl -s http://127.0.0.1:5555/api/v1/health

# Check server logs
tail -f microsandbox-server.log

# Check network connectivity
ping 127.0.0.1
netstat -tlnp | grep 5555
```

**Solutions:**

1. **Start the server:**
   ```bash
   ./start_msbserver_debug.sh
   ```

2. **Check server URL configuration:**
   ```bash
   export MSB_SERVER_URL="http://127.0.0.1:5555"
   ```

3. **Verify firewall settings:**
   ```bash
   # Allow port 5555
   sudo ufw allow 5555
   ```

4. **Check server status:**
   ```bash
   ps aux | grep microsandbox
   ```

### 2. Resource Limit Exceeded

**Symptoms:**
- `ResourceLimitError: Maximum concurrent sessions exceeded`
- `ResourceLimitError: Total memory limit would be exceeded`
- Slow performance or hanging operations

**Diagnosis:**
```python
async def diagnose_resources():
    async with MicrosandboxWrapper() as wrapper:
        stats = await wrapper.get_resource_stats()
        print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        print(f"Memory usage: {stats.total_memory_mb} MB")
        
        sessions = await wrapper.get_sessions()
        for session in sessions:
            print(f"Session {session.session_id}: {session.status.value}")
```

**Solutions:**

1. **Increase session limits:**
   ```bash
   export MSB_MAX_SESSIONS="20"
   export MSB_MAX_TOTAL_MEMORY_MB="16384"
   ```

2. **Clean up unused sessions:**
   ```python
   async with MicrosandboxWrapper() as wrapper:
       sessions = await wrapper.get_sessions()
       for session in sessions:
           if session.status == SessionStatus.STOPPED:
               await wrapper.stop_session(session.session_id)
   ```

3. **Use smaller sandbox flavors:**
   ```python
   result = await wrapper.execute_code(
       code="print('Hello')",
       flavor=SandboxFlavor.SMALL  # Use less memory
   )
   ```

4. **Reduce session timeout:**
   ```bash
   export MSB_SESSION_TIMEOUT="900"  # 15 minutes
   ```

### 3. Session Management Issues

**Symptoms:**
- Sessions timing out unexpectedly
- Cannot reuse sessions
- `SessionNotFoundError` exceptions

**Diagnosis:**
```python
async def diagnose_sessions():
    async with MicrosandboxWrapper() as wrapper:
        # Create a session
        result = await wrapper.execute_code("x = 42", template="python")
        session_id = result.session_id
        print(f"Created session: {session_id}")
        
        # Check session info
        sessions = await wrapper.get_sessions(session_id)
        if sessions:
            session = sessions[0]
            print(f"Session status: {session.status.value}")
            print(f"Created: {session.created_at}")
            print(f"Last accessed: {session.last_accessed}")
        else:
            print("Session not found")
```

**Solutions:**

1. **Increase session timeout:**
   ```bash
   export MSB_SESSION_TIMEOUT="3600"  # 1 hour
   ```

2. **Use explicit session management:**
   ```python
   # Keep session alive with periodic access
   async def keep_session_alive(wrapper, session_id):
       while True:
           await asyncio.sleep(300)  # 5 minutes
           try:
               await wrapper.execute_code(
                   "# Keep alive", 
                   session_id=session_id
               )
           except SessionNotFoundError:
               break
   ```

3. **Handle session recreation:**
   ```python
   async def robust_execution(wrapper, code, session_id=None):
       try:
           return await wrapper.execute_code(code, session_id=session_id)
       except SessionNotFoundError:
           # Session expired, create new one
           return await wrapper.execute_code(code)
   ```

### 4. Volume Mapping Problems

**Symptoms:**
- `FileNotFoundError` when accessing mapped files
- Permission denied errors
- Files not appearing in sandbox

**Diagnosis:**
```bash
# Check host path exists and permissions
ls -la /host/path
stat /host/path

# Check volume mapping configuration
echo $MSB_SHARED_VOLUME_PATH

# Test inside sandbox
docker run --rm -v /host/path:/sandbox/path alpine ls -la /sandbox/path
```

**Solutions:**

1. **Fix volume mapping format:**
   ```bash
   # Correct format
   export MSB_SHARED_VOLUME_PATH='["/host/data:/sandbox/data"]'
   
   # Not this
   export MSB_SHARED_VOLUME_PATH="/host/data:/sandbox/data"
   ```

2. **Check permissions:**
   ```bash
   # Make directory readable
   chmod 755 /host/data
   
   # For write access
   chmod 777 /host/output
   ```

3. **Create directories:**
   ```bash
   mkdir -p /host/input /host/output
   ```

4. **Test volume mapping:**
   ```python
   async def test_volumes():
       config = WrapperConfig.from_env()
       print(f"Volume mappings: {config.shared_volume_mappings}")
       
       async with MicrosandboxWrapper(config=config) as wrapper:
           result = await wrapper.execute_code("""
   import os
   print("Available paths:")
   for path in ['/sandbox', '/sandbox/input', '/sandbox/output']:
       if os.path.exists(path):
           print(f"  {path}: {os.listdir(path) if os.path.isdir(path) else 'file'}")
       else:
           print(f"  {path}: not found")
   """)
           print(result.stdout)
   ```

### 5. Code Execution Failures

**Symptoms:**
- Code executes but `success=False`
- Syntax errors in working code
- Import errors for standard libraries

**Diagnosis:**
```python
async def diagnose_execution():
    async with MicrosandboxWrapper() as wrapper:
        # Test basic execution
        result = await wrapper.execute_code("print('test')")
        print(f"Basic test: {result.success}")
        if not result.success:
            print(f"Error: {result.stderr}")
        
        # Test imports
        result = await wrapper.execute_code("import sys; print(sys.version)")
        print(f"Python version: {result.stdout if result.success else result.stderr}")
        
        # Test template
        result = await wrapper.execute_code(
            "console.log('Node test')", 
            template="node"
        )
        print(f"Node test: {result.success}")
```

**Solutions:**

1. **Check template compatibility:**
   ```python
   # Use correct template for language
   await wrapper.execute_code("print('Python')", template="python")
   await wrapper.execute_code("console.log('Node')", template="node")
   ```

2. **Handle execution errors gracefully:**
   ```python
   result = await wrapper.execute_code(code)
   if not result.success:
       print(f"Execution failed: {result.stderr}")
       # Handle error appropriately
   ```

3. **Check for syntax errors:**
   ```python
   # Validate Python syntax before execution
   try:
       compile(code, '<string>', 'exec')
   except SyntaxError as e:
       print(f"Syntax error: {e}")
   ```

## Error Messages

### ConnectionError Messages

#### "Cannot connect to microsandbox server"
- **Cause**: Server not running or wrong URL
- **Solution**: Start server with `./start_msbserver_debug.sh`

#### "Connection timeout"
- **Cause**: Network issues or server overload
- **Solution**: Check network connectivity, increase timeout

#### "Connection refused"
- **Cause**: Server not listening on specified port
- **Solution**: Verify server is running and port is correct

### ResourceLimitError Messages

#### "Maximum concurrent sessions (N) exceeded"
- **Cause**: Too many active sessions
- **Solution**: Increase `MSB_MAX_SESSIONS` or clean up sessions

#### "Total memory limit (N MB) would be exceeded"
- **Cause**: Memory limit reached
- **Solution**: Increase `MSB_MAX_TOTAL_MEMORY_MB` or use smaller flavors

### ConfigurationError Messages

#### "Invalid volume mapping format"
- **Cause**: Incorrect volume mapping syntax
- **Solution**: Use format `"host_path:container_path"`

#### "MSB_SHARED_VOLUME_PATH must be a JSON array"
- **Cause**: Invalid JSON in volume path configuration
- **Solution**: Use proper JSON array format

### SandboxCreationError Messages

#### "Failed to create sandbox: timeout"
- **Cause**: Sandbox startup taking too long
- **Solution**: Increase `MSB_SANDBOX_START_TIMEOUT`

#### "Unsupported template: X"
- **Cause**: Invalid template name
- **Solution**: Use supported templates (python, node)

## Performance Issues

### Slow Execution

**Symptoms:**
- Long execution times for simple code
- Timeouts on normal operations
- High CPU/memory usage

**Diagnosis:**
```python
async def performance_test():
    async with MicrosandboxWrapper() as wrapper:
        start_time = time.time()
        
        result = await wrapper.execute_code(
            "import time; start = time.time(); time.sleep(1); print(f'Elapsed: {time.time() - start:.2f}s')"
        )
        
        total_time = time.time() - start_time
        print(f"Total time: {total_time:.2f}s")
        print(f"Execution time: {result.execution_time_ms}ms")
        print(f"Overhead: {(total_time * 1000) - result.execution_time_ms:.0f}ms")
```

**Solutions:**

1. **Use session reuse:**
   ```python
   # Reuse sessions for better performance
   session_id = None
   for i in range(10):
       result = await wrapper.execute_code(
           f"print('Iteration {i}')",
           session_id=session_id
       )
       session_id = result.session_id
   ```

2. **Optimize resource allocation:**
   ```bash
   # Use appropriate flavors
   export MSB_DEFAULT_FLAVOR="small"  # For light workloads
   ```

3. **Reduce cleanup frequency:**
   ```bash
   export MSB_CLEANUP_INTERVAL="300"  # 5 minutes
   ```

### Memory Issues

**Symptoms:**
- Out of memory errors
- Slow garbage collection
- System becoming unresponsive

**Diagnosis:**
```python
async def memory_diagnosis():
    async with MicrosandboxWrapper() as wrapper:
        stats = await wrapper.get_resource_stats()
        print(f"Memory usage: {stats.total_memory_mb} MB")
        print(f"Sessions by flavor: {stats.sessions_by_flavor}")
        
        # Check individual sessions
        sessions = await wrapper.get_sessions()
        for session in sessions:
            memory_mb = session.flavor.get_memory_mb()
            print(f"Session {session.session_id}: {memory_mb} MB ({session.flavor.value})")
```

**Solutions:**

1. **Set memory limits:**
   ```bash
   export MSB_MAX_TOTAL_MEMORY_MB="8192"  # 8GB limit
   ```

2. **Use smaller flavors:**
   ```python
   result = await wrapper.execute_code(
       code="print('Hello')",
       flavor=SandboxFlavor.SMALL  # 1GB instead of 2GB or 4GB
   )
   ```

3. **Implement session pooling:**
   ```python
   class SessionPool:
       def __init__(self, wrapper, max_size=5):
           self.wrapper = wrapper
           self.max_size = max_size
           self.available = []
           self.in_use = set()
       
       async def get_session(self):
           if self.available:
               session_id = self.available.pop()
               self.in_use.add(session_id)
               return session_id
           elif len(self.in_use) < self.max_size:
               result = await self.wrapper.execute_code("# Initialize")
               session_id = result.session_id
               self.in_use.add(session_id)
               return session_id
           else:
               raise ResourceLimitError("No sessions available")
       
       def return_session(self, session_id):
           if session_id in self.in_use:
               self.in_use.remove(session_id)
               self.available.append(session_id)
   ```

## Configuration Problems

### Environment Variable Issues

**Common Problems:**
1. Variables not set
2. Wrong format (especially JSON arrays)
3. Invalid values

**Diagnosis Script:**
```python
import os
import json

def check_env_vars():
    """Check environment variable configuration."""
    vars_to_check = {
        'MSB_SERVER_URL': str,
        'MSB_SESSION_TIMEOUT': int,
        'MSB_MAX_SESSIONS': int,
        'MSB_SHARED_VOLUME_PATH': 'json_array',
        'MSB_DEFAULT_FLAVOR': ['small', 'medium', 'large'],
    }
    
    for var_name, expected_type in vars_to_check.items():
        value = os.getenv(var_name)
        if value is None:
            print(f"⚠ {var_name}: Not set (using default)")
            continue
        
        if expected_type == 'json_array':
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    print(f"✓ {var_name}: Valid JSON array with {len(parsed)} items")
                else:
                    print(f"✗ {var_name}: Not a JSON array")
            except json.JSONDecodeError:
                print(f"✗ {var_name}: Invalid JSON")
        elif isinstance(expected_type, list):
            if value in expected_type:
                print(f"✓ {var_name}: {value}")
            else:
                print(f"✗ {var_name}: Invalid value '{value}', expected one of {expected_type}")
        elif expected_type == int:
            try:
                int_val = int(value)
                print(f"✓ {var_name}: {int_val}")
            except ValueError:
                print(f"✗ {var_name}: Not a valid integer")
        else:
            print(f"✓ {var_name}: {value}")

if __name__ == "__main__":
    check_env_vars()
```

### Configuration Validation

```python
from microsandbox_wrapper import WrapperConfig

def validate_config():
    """Validate wrapper configuration."""
    try:
        config = WrapperConfig.from_env()
        
        # Check for common issues
        issues = []
        
        if config.session_timeout < 60:
            issues.append("Session timeout is very short (< 1 minute)")
        
        if config.default_execution_timeout > config.session_timeout:
            issues.append("Execution timeout is longer than session timeout")
        
        if config.max_concurrent_sessions > 50:
            issues.append("Very high max sessions (> 50) - consider resource implications")
        
        if config.cleanup_interval > config.session_timeout / 2:
            issues.append("Cleanup interval is too long compared to session timeout")
        
        # Check volume mappings
        for mapping in config.shared_volume_mappings:
            if ':' not in mapping:
                issues.append(f"Invalid volume mapping format: {mapping}")
            else:
                host_path = mapping.split(':', 1)[0]
                if not os.path.exists(host_path):
                    issues.append(f"Host path does not exist: {host_path}")
        
        if issues:
            print("Configuration issues found:")
            for issue in issues:
                print(f"  ⚠ {issue}")
        else:
            print("✓ Configuration looks good")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False
```

## Network and Connectivity

### Network Diagnostics

```bash
#!/bin/bash
# Network diagnostics script

SERVER_URL=${MSB_SERVER_URL:-"http://127.0.0.1:5555"}
HOST=$(echo $SERVER_URL | sed -E 's|^https?://([^:/]+).*|\1|')
PORT=$(echo $SERVER_URL | sed -E 's|^https?://[^:]+:?([0-9]+)?.*|\1|')
PORT=${PORT:-5555}

echo "Network Diagnostics"
echo "==================="
echo "Server URL: $SERVER_URL"
echo "Host: $HOST"
echo "Port: $PORT"

echo -e "\n1. DNS Resolution:"
if nslookup $HOST > /dev/null 2>&1; then
    echo "   ✓ DNS resolution successful"
else
    echo "   ✗ DNS resolution failed"
fi

echo -e "\n2. Network Connectivity:"
if ping -c 1 $HOST > /dev/null 2>&1; then
    echo "   ✓ Host is reachable"
else
    echo "   ✗ Host is not reachable"
fi

echo -e "\n3. Port Connectivity:"
if nc -z $HOST $PORT 2>/dev/null; then
    echo "   ✓ Port $PORT is open"
else
    echo "   ✗ Port $PORT is not accessible"
fi

echo -e "\n4. HTTP Response:"
if curl -s --connect-timeout 5 "$SERVER_URL/api/v1/health" > /dev/null; then
    echo "   ✓ HTTP endpoint is responding"
    curl -s "$SERVER_URL/api/v1/health" | head -3
else
    echo "   ✗ HTTP endpoint is not responding"
fi
```

### Firewall Issues

```bash
# Check firewall status
sudo ufw status

# Allow microsandbox port
sudo ufw allow 5555

# For iptables
sudo iptables -A INPUT -p tcp --dport 5555 -j ACCEPT
```

## Resource Management

### Resource Monitoring Script

```python
#!/usr/bin/env python3
"""Resource monitoring script."""

import asyncio
import time
from microsandbox_wrapper import MicrosandboxWrapper

async def monitor_resources(duration=60, interval=5):
    """Monitor resources for specified duration."""
    async with MicrosandboxWrapper() as wrapper:
        print(f"Monitoring resources for {duration} seconds...")
        print("Time\tSessions\tMemory(MB)\tCPUs")
        print("-" * 40)
        
        start_time = time.time()
        while time.time() - start_time < duration:
            stats = await wrapper.get_resource_stats()
            elapsed = int(time.time() - start_time)
            
            print(f"{elapsed:4d}\t{stats.active_sessions:8d}\t{stats.total_memory_mb:10d}\t{stats.total_cpus:4.1f}")
            
            await asyncio.sleep(interval)

if __name__ == "__main__":
    asyncio.run(monitor_resources())
```

### Cleanup Script

```python
#!/usr/bin/env python3
"""Manual cleanup script."""

import asyncio
from microsandbox_wrapper import MicrosandboxWrapper

async def cleanup_resources():
    """Clean up all resources."""
    async with MicrosandboxWrapper() as wrapper:
        print("Starting resource cleanup...")
        
        # Get current sessions
        sessions = await wrapper.get_sessions()
        print(f"Found {len(sessions)} active sessions")
        
        # Stop all sessions
        stopped_count = 0
        for session in sessions:
            try:
                success = await wrapper.stop_session(session.session_id)
                if success:
                    stopped_count += 1
                    print(f"Stopped session: {session.session_id}")
            except Exception as e:
                print(f"Error stopping session {session.session_id}: {e}")
        
        print(f"Stopped {stopped_count} sessions")
        
        # Clean up orphan sandboxes
        orphan_count = await wrapper.cleanup_orphan_sandboxes()
        print(f"Cleaned up {orphan_count} orphan sandboxes")
        
        # Final stats
        stats = await wrapper.get_resource_stats()
        print(f"Final stats: {stats.active_sessions} active sessions, {stats.total_memory_mb} MB memory")

if __name__ == "__main__":
    asyncio.run(cleanup_resources())
```

## Debugging Tools

### Debug Logging

Enable debug logging for detailed information:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Or set environment variable
os.environ['MSB_LOG_LEVEL'] = 'DEBUG'
```

### Wrapper State Inspector

```python
async def inspect_wrapper_state(wrapper):
    """Inspect internal wrapper state."""
    print("Wrapper State Inspection")
    print("=" * 30)
    
    print(f"Started: {wrapper.is_started()}")
    
    config = wrapper.get_config()
    print(f"Server URL: {config.server_url}")
    print(f"Max sessions: {config.max_concurrent_sessions}")
    print(f"Session timeout: {config.session_timeout}s")
    
    # Background task status
    task_status = await wrapper.get_background_task_status()
    print(f"Background tasks: {task_status['overall_status']}")
    
    # Resource stats
    stats = await wrapper.get_resource_stats()
    print(f"Active sessions: {stats.active_sessions}")
    print(f"Memory usage: {stats.total_memory_mb} MB")
    
    # Session details
    sessions = await wrapper.get_sessions()
    print(f"\nSession Details:")
    for session in sessions:
        print(f"  {session.session_id}:")
        print(f"    Template: {session.template}")
        print(f"    Flavor: {session.flavor.value}")
        print(f"    Status: {session.status.value}")
        print(f"    Created: {session.created_at}")
        print(f"    Last accessed: {session.last_accessed}")
```

### Performance Profiler

```python
import time
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def profile_operation(name):
    """Profile an async operation."""
    start_time = time.time()
    start_memory = 0  # Could use psutil for actual memory measurement
    
    print(f"Starting {name}...")
    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time
        print(f"Completed {name} in {duration:.3f}s")

# Usage
async def profile_wrapper_operations():
    async with MicrosandboxWrapper() as wrapper:
        async with profile_operation("Code execution"):
            result = await wrapper.execute_code("print('Hello')")
        
        async with profile_operation("Session reuse"):
            result = await wrapper.execute_code(
                "print('Reused')", 
                session_id=result.session_id
            )
        
        async with profile_operation("Resource stats"):
            stats = await wrapper.get_resource_stats()
```

## Getting Help

### Information to Collect

When reporting issues, please collect:

1. **Environment information:**
   ```bash
   python3 --version
   uname -a
   echo $MSB_SERVER_URL
   env | grep MSB_
   ```

2. **Server status:**
   ```bash
   curl -s http://127.0.0.1:5555/api/v1/health
   ps aux | grep microsandbox
   ```

3. **Error logs:**
   ```python
   # Enable debug logging and capture output
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Configuration:**
   ```python
   from microsandbox_wrapper import WrapperConfig
   config = WrapperConfig.from_env()
   print(config)
   ```

### Common Solutions Summary

| Issue | Quick Fix |
|-------|-----------|
| Cannot connect | Start server: `./start_msbserver_debug.sh` |
| Resource limit | Increase: `export MSB_MAX_SESSIONS="20"` |
| Session timeout | Increase: `export MSB_SESSION_TIMEOUT="3600"` |
| Volume mapping | Fix format: `export MSB_SHARED_VOLUME_PATH='["/host:/container"]'` |
| Slow performance | Use session reuse and appropriate flavors |
| Memory issues | Set limits: `export MSB_MAX_TOTAL_MEMORY_MB="8192"` |

### Support Resources

1. **Run health check script** (provided above)
2. **Check server logs** for detailed error information
3. **Review configuration** using validation scripts
4. **Test with minimal configuration** to isolate issues
5. **Use debug logging** for detailed troubleshooting

This troubleshooting guide should help you resolve most common issues with the MicrosandboxWrapper. For persistent problems, use the diagnostic scripts and collect the information specified in the "Getting Help" section.