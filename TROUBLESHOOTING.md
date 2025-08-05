# Troubleshooting Guide(this guide is staled, should only used as a reference to old mcp implement)

This guide helps resolve common issues with the microsandbox MCP server and its simplified interface.

## Common Issues

### Session Management Issues

#### "Session not found" Error

**Symptoms:**
- Error message: "Session 'session-xyz' was not found or has expired"
- Tools fail when trying to reuse a session ID

**Causes:**
- Session timed out due to inactivity
- Session was manually stopped
- Server was restarted
- Invalid session ID provided

**Solutions:**
1. **Create a new session** by calling tools without `session_id`
2. **Check active sessions** using `get_sessions` tool
3. **Verify session ID** for typos or formatting issues

**Example Recovery:**
```json
// Instead of reusing expired session
{
  "code": "print('hello')",
  "template": "python",
  "session_id": "expired-session-123"
}

// Create new session automatically
{
  "code": "print('hello')",
  "template": "python"
}
```

#### "Resource limit exceeded" Error

**Symptoms:**
- Cannot create new sessions
- Error about maximum concurrent sessions reached

**Causes:**
- Too many active sessions (exceeds `MSB_MAX_SESSIONS`)
- System resource constraints

**Solutions:**
1. **Stop unused sessions** with `stop_session` tool
2. **Wait for sessions to timeout** automatically
3. **Increase session limit** via `MSB_MAX_SESSIONS` environment variable
4. **Use smaller resource flavors** (`small` instead of `large`)

**Example Recovery:**
```bash
# Check active sessions
curl -X POST http://localhost:5555/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "get_sessions"}}'

# Stop specific session
curl -X POST http://localhost:5555/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "stop_session", "arguments": {"session_id": "session-to-stop"}}}'
```

### Template and Language Issues

#### "Unsupported template" Error

**Symptoms:**
- Error: "Unsupported template: xyz. Supported templates: python, node"

**Causes:**
- Typo in template name
- Using unsupported language/runtime

**Solutions:**
1. **Use supported templates:** `python` or `node`
2. **Check spelling** of template parameter
3. **Use default template** by omitting the parameter

**Supported Templates:**
- `python` → `microsandbox/python` container
- `node` → `microsandbox/node` container

#### Code Execution Errors

**Compilation Errors:**
```json
{
  "error_type": "compilation_error",
  "message": "Code compilation failed",
  "suggestions": [
    "Check for syntax errors in your code",
    "Ensure all imports and dependencies are correct",
    "Verify that your code follows the language's syntax rules"
  ]
}
```

**Runtime Errors:**
```json
{
  "error_type": "runtime_error", 
  "message": "Code execution failed at runtime",
  "suggestions": [
    "Check for logical errors in your code",
    "Verify that all variables are properly initialized",
    "Handle potential exceptions and edge cases"
  ]
}
```

### Configuration Issues

#### Shared Volume Problems

**Symptoms:**
- Files not appearing in sandbox
- Permission denied errors
- Volume path not accessible

**Diagnosis:**
```bash
# Check if shared volume path exists
ls -la "$MSB_SHARED_VOLUME_PATH"

# Check permissions
stat "$MSB_SHARED_VOLUME_PATH"

# Test volume access in sandbox
curl -X POST http://localhost:5555/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "get_volume_path"}}'
```

**Solutions:**
1. **Create directory:** `mkdir -p "$MSB_SHARED_VOLUME_PATH"`
2. **Fix permissions:** `chmod 755 "$MSB_SHARED_VOLUME_PATH"`
3. **Verify path:** Check `MSB_SHARED_VOLUME_PATH` environment variable
4. **Test access:** Create a test file and verify it appears in sandbox

#### Environment Variable Issues

**Common Problems:**
- Variables not set or exported
- Invalid values causing validation errors
- Configuration not taking effect

**Verification:**
```bash
# Check current environment
env | grep MSB_

# Validate configuration
echo "Shared volume: $MSB_SHARED_VOLUME_PATH"
echo "Guest path: $MSB_SHARED_VOLUME_GUEST_PATH"
echo "Timeout: $MSB_SESSION_TIMEOUT_SECONDS"
echo "Max sessions: $MSB_MAX_SESSIONS"
echo "Default flavor: $MSB_DEFAULT_FLAVOR"
echo "Default template: $MSB_DEFAULT_TEMPLATE"
```

### Connection Issues

#### MCP Server Not Responding

**Symptoms:**
- Connection refused errors
- Timeout when calling tools
- Server not starting

**Diagnosis:**
```bash
# Check if server is running
curl -f http://localhost:5555/health || echo "Server not responding"

# Check server logs
docker logs microsandbox-server

# Check port availability
netstat -an | grep 5555
```

**Solutions:**
1. **Start server:** `msb server start --dev`
2. **Check port conflicts:** Ensure port 5555 is available
3. **Verify Docker:** Ensure Docker daemon is running
4. **Check logs:** Look for startup errors in server logs

#### MCP Client Configuration

**Common Issues:**
- Wrong URL or port
- Incorrect transport type
- Authentication problems

**Correct Configuration:**
```json
{
  "transport": "http",
  "url": "http://localhost:5555/mcp",
  "method": "streamable"
}
```

### Performance Issues

#### Slow Session Creation

**Symptoms:**
- Long delays when creating new sessions
- Timeouts during sandbox startup

**Causes:**
- Container image not cached locally
- Resource constraints
- Network issues downloading images

**Solutions:**
1. **Pre-pull images:**
   ```bash
   docker pull microsandbox/python
   docker pull microsandbox/node
   ```

2. **Use smaller flavors:** Start with `small` flavor
3. **Check system resources:** Ensure adequate CPU/memory
4. **Monitor Docker:** `docker stats` to check resource usage

#### Session Cleanup Issues

**Symptoms:**
- Sessions not timing out
- Resource leaks
- Growing number of containers

**Diagnosis:**
```bash
# Check running containers
docker ps | grep microsandbox

# Check session status
curl -X POST http://localhost:5555/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "get_sessions"}}'
```

**Solutions:**
1. **Manual cleanup:** Stop sessions with `stop_session` tool
2. **Restart server:** Cleans up all sessions
3. **Check timeout settings:** Verify `MSB_SESSION_TIMEOUT_SECONDS`
4. **Force cleanup:** `docker stop $(docker ps -q --filter "label=microsandbox")`

## Debugging Tools

### Health Check

```bash
#!/bin/bash
# microsandbox-health-check.sh

echo "=== Microsandbox Health Check ==="

# Check server status
echo "1. Server Status:"
if curl -f -s http://localhost:5555/health > /dev/null; then
    echo "   ✓ Server is responding"
else
    echo "   ✗ Server is not responding"
fi

# Check environment
echo "2. Environment Configuration:"
echo "   Shared volume: ${MSB_SHARED_VOLUME_PATH:-'Not set'}"
echo "   Guest path: ${MSB_SHARED_VOLUME_GUEST_PATH:-'/shared (default)'}"
echo "   Timeout: ${MSB_SESSION_TIMEOUT_SECONDS:-'1800 (default)'} seconds"
echo "   Max sessions: ${MSB_MAX_SESSIONS:-'10 (default)'}"

# Check Docker
echo "3. Docker Status:"
if docker info > /dev/null 2>&1; then
    echo "   ✓ Docker is running"
    echo "   Containers: $(docker ps -q | wc -l) running"
else
    echo "   ✗ Docker is not accessible"
fi

# Check images
echo "4. Container Images:"
for image in microsandbox/python microsandbox/node; do
    if docker images -q "$image" > /dev/null; then
        echo "   ✓ $image is available"
    else
        echo "   ✗ $image is not available"
    fi
done

# Check active sessions
echo "5. Active Sessions:"
SESSIONS=$(curl -s -X POST http://localhost:5555/mcp \
    -H "Content-Type: application/json" \
    -d '{"method": "tools/call", "params": {"name": "get_sessions"}}' \
    2>/dev/null | jq -r '.result.content[0].text | fromjson | .sessions | length' 2>/dev/null)

if [ "$SESSIONS" != "null" ] && [ "$SESSIONS" != "" ]; then
    echo "   Active sessions: $SESSIONS"
else
    echo "   Could not retrieve session information"
fi

echo "=== Health Check Complete ==="
```

### Session Monitor

```bash
#!/bin/bash
# session-monitor.sh

watch -n 5 'curl -s -X POST http://localhost:5555/mcp \
    -H "Content-Type: application/json" \
    -d "{\"method\": \"tools/call\", \"params\": {\"name\": \"get_sessions\"}}" \
    | jq -r ".result.content[0].text | fromjson | .sessions[] | \"\(.id) | \(.language) | \(.status) | \(.uptime_seconds)s\""'
```

### Log Analysis

```bash
#!/bin/bash
# analyze-logs.sh

echo "Recent errors in microsandbox logs:"
docker logs microsandbox-server --since=1h 2>&1 | grep -i error | tail -10

echo -e "\nSession-related events:"
docker logs microsandbox-server --since=1h 2>&1 | grep -i session | tail -10

echo -e "\nResource-related events:"
docker logs microsandbox-server --since=1h 2>&1 | grep -i "resource\|memory\|cpu" | tail -10
```

## Getting Help

If you continue to experience issues:

1. **Check server logs:** `docker logs microsandbox-server`
2. **Run health check:** Use the health check script above
3. **Verify configuration:** Ensure all environment variables are correct
4. **Test with minimal setup:** Try with default configuration first
5. **Check system resources:** Ensure adequate CPU, memory, and disk space

For additional support, include the following information:
- Server version and configuration
- Environment variables
- Error messages and logs
- Steps to reproduce the issue
- System specifications (OS, Docker version, etc.)