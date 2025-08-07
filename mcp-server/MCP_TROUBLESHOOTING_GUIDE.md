# MCP Server Troubleshooting Guide

This guide provides solutions for common issues encountered when running the HTTP Streamable MCP Server for Microsandbox.

## Quick Diagnostics

### Health Check Commands

```bash
# Check microsandbox server
curl -s http://127.0.0.1:5555/api/v1/health

# Check MCP server status
curl http://localhost:8775/

# Test MCP protocol
curl -X POST http://localhost:8775/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Check if ports are in use
netstat -tlnp | grep -E ':(8775|5555)'
lsof -i :8775
lsof -i :5555
```

### Log Analysis

```bash
# View MCP server logs with debug level
python -m mcp_server.main --log-level DEBUG

# Monitor logs in real-time
tail -f /var/log/mcp-server/mcp-server.log

# Search for specific errors
grep -i "error\|exception\|failed" /var/log/mcp-server/mcp-server.log

# Check connection attempts
grep "Connection" /var/log/mcp-server/mcp-server.log
```

## Server Startup Issues

### Issue: MCP Server Won't Start

**Symptoms:**
- Server exits immediately after startup
- "Address already in use" error
- Configuration validation errors

**Solutions:**

1. **Port Already in Use:**
   ```bash
   # Find what's using the port
   sudo lsof -i :8775
   
   # Kill the process or use a different port
   export MCP_SERVER_PORT=8001
   python -m mcp_server.main
   ```

2. **Invalid Configuration:**
   ```bash
   # Check environment variables
   env | grep MCP_
   env | grep MSB_
   
   # Validate configuration
   python -c "
   from mcp_server.main import MCPServerConfig
   config = MCPServerConfig.from_env()
   config.validate()
   print('Configuration is valid')
   "
   ```

3. **Missing Dependencies:**
   ```bash
   # Reinstall dependencies
   pip install -r requirements.txt
   
   # Check for import errors
   python -c "import mcp_server.main"
   ```

### Issue: Cannot Connect to Microsandbox Server

**Symptoms:**
- "Connection refused" errors
- "Connection timeout" errors
- MCP server starts but tools fail

**Solutions:**

1. **Verify Microsandbox Server:**
   ```bash
   # Check if microsandbox server is running
   curl -s http://127.0.0.1:5555/api/v1/health
   
   # Start microsandbox server if not running
   ./start_msbserver_debug.sh
   
   # Check microsandbox server logs
   tail -f /path/to/microsandbox/logs/server.log
   ```

2. **Check Network Configuration:**
   ```bash
   # Test connectivity
   telnet 127.0.0.1 5555
   
   # Check firewall rules
   sudo ufw status
   sudo iptables -L
   
   # Verify MSB_SERVER_URL
   echo $MSB_SERVER_URL
   ```

3. **DNS Resolution Issues:**
   ```bash
   # If using hostname instead of IP
   nslookup microsandbox-server
   ping microsandbox-server
   
   # Use IP address instead
   export MSB_SERVER_URL="http://127.0.0.1:5555"
   ```

## MCP Protocol Issues

### Issue: JSON-RPC Errors

**Symptoms:**
- "Parse error" responses
- "Invalid request" errors
- "Method not found" errors

**Solutions:**

1. **Invalid JSON Format:**
   ```bash
   # Test with valid JSON
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/list",
       "params": {}
     }'
   
   # Validate JSON format
   echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python -m json.tool
   ```

2. **Missing Content-Type Header:**
   ```bash
   # Always include Content-Type header
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

3. **Invalid Method Names:**
   ```bash
   # List available methods
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   
   # Use correct method names: tools/list, tools/call
   ```

### Issue: Tool Execution Failures

**Symptoms:**
- Tools return error responses
- "Resource limit exceeded" errors
- "Session not found" errors

**Solutions:**

1. **Resource Limit Errors:**
   ```bash
   # Check current resource usage
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}'
   
   # Increase resource limits
   export MSB_MAX_SESSIONS=20
   export MSB_MAX_TOTAL_MEMORY_MB=16384
   
   # Use smaller resource flavors
   # Use "small" instead of "large" in tool arguments
   ```

2. **Session Management Issues:**
   ```bash
   # List active sessions
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}'
   
   # Stop problematic sessions
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"stop_session","arguments":{"session_id":"session-123"}}}'
   ```

3. **Code Execution Errors:**
   ```bash
   # Test with simple code first
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "execute_code",
         "arguments": {
           "code": "print(\"Hello, World!\")",
           "template": "python",
           "flavor": "small"
         }
       }
     }'
   
   # Check for syntax errors in your code
   # Verify template matches code language
   ```

## CORS Issues

### Issue: CORS Errors in Web Clients

**Symptoms:**
- Browser console shows CORS errors
- Preflight requests fail
- "Access-Control-Allow-Origin" errors

**Solutions:**

1. **Enable CORS:**
   ```bash
   # Enable CORS support
   export MCP_ENABLE_CORS=true
   python -m mcp_server.main
   ```

2. **Test CORS Headers:**
   ```bash
   # Check CORS headers in response
   curl -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type" \
        -X OPTIONS \
        http://localhost:8775/mcp
   ```

3. **Browser-Specific Issues:**
   ```bash
   # Test with curl first to isolate browser issues
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -H "Origin: http://localhost:3000" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

## Performance Issues

### Issue: Slow Response Times

**Symptoms:**
- High response latency
- Timeouts on tool calls
- Server becomes unresponsive

**Solutions:**

1. **Check Resource Usage:**
   ```bash
   # Monitor system resources
   htop
   free -h
   df -h
   
   # Check MCP server process
   ps aux | grep mcp_server
   ```

2. **Optimize Configuration:**
   ```bash
   # Reduce session timeout for faster cleanup
   export MSB_SESSION_TIMEOUT=900  # 15 minutes
   
   # Increase cleanup frequency
   export MSB_SESSION_CLEANUP_INTERVAL=60  # 1 minute
   
   # Use appropriate resource flavors
   export MSB_DEFAULT_FLAVOR=small
   ```

3. **Session Management:**
   ```bash
   # Check for session leaks
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}'
   
   # Stop unused sessions
   # Implement session reuse in your client
   ```

### Issue: Memory Leaks

**Symptoms:**
- Memory usage continuously increases
- Server crashes with out-of-memory errors
- System becomes slow over time

**Solutions:**

1. **Monitor Memory Usage:**
   ```bash
   # Monitor MCP server memory
   ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f mcp_server)
   
   # Monitor system memory
   watch -n 5 free -h
   ```

2. **Configure Memory Limits:**
   ```bash
   # Set memory limits
   export MSB_MAX_TOTAL_MEMORY_MB=4096
   export MSB_MAX_SESSIONS=10
   
   # Use systemd memory limits
   sudo systemctl edit mcp-server
   # Add: MemoryLimit=1G
   ```

3. **Session Cleanup:**
   ```bash
   # Force session cleanup
   curl -X POST http://localhost:8775/mcp \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}'
   
   # Stop all sessions if needed
   # Restart server if memory leak persists
   ```

## Network Issues

### Issue: Connection Timeouts

**Symptoms:**
- Requests timeout before completion
- "Connection reset by peer" errors
- Intermittent connectivity issues

**Solutions:**

1. **Increase Timeouts:**
   ```bash
   # Increase connection timeouts
   export MSB_CONNECTION_TIMEOUT=60
   export MSB_REQUEST_TIMEOUT=600
   
   # Set execution timeouts in tool calls
   {
     "name": "execute_code",
     "arguments": {
       "code": "long_running_code()",
       "timeout": 300
     }
   }
   ```

2. **Network Configuration:**
   ```bash
   # Check network latency
   ping -c 5 127.0.0.1
   
   # Test with different network interfaces
   export MSB_SERVER_URL="http://localhost:5555"  # vs 127.0.0.1
   ```

3. **Firewall Issues:**
   ```bash
   # Check firewall rules
   sudo ufw status verbose
   sudo iptables -L -n
   
   # Temporarily disable firewall for testing
   sudo ufw disable  # Re-enable after testing!
   ```

### Issue: SSL/TLS Errors

**Symptoms:**
- Certificate verification errors
- SSL handshake failures
- "SSL: CERTIFICATE_VERIFY_FAILED" errors

**Solutions:**

1. **Certificate Issues:**
   ```bash
   # Check certificate validity
   openssl s_client -connect mcp-server.example.com:443
   
   # Verify certificate chain
   curl -vI https://mcp-server.example.com/
   ```

2. **Self-Signed Certificates:**
   ```bash
   # For development only - disable SSL verification
   export PYTHONHTTPSVERIFY=0
   
   # Better: Add certificate to trust store
   sudo cp your-cert.crt /usr/local/share/ca-certificates/
   sudo update-ca-certificates
   ```

## Docker Issues

### Issue: Container Won't Start

**Symptoms:**
- Container exits immediately
- "Permission denied" errors
- Port binding failures

**Solutions:**

1. **Permission Issues:**
   ```bash
   # Check container logs
   docker logs mcp-server
   
   # Run with proper user
   docker run --user $(id -u):$(id -g) mcp-server
   
   # Fix file permissions
   sudo chown -R 1000:1000 /path/to/mcp-server
   ```

2. **Port Conflicts:**
   ```bash
   # Check port usage
   docker ps
   netstat -tlnp | grep :8775
   
   # Use different port
   docker run -p 8001:8775 mcp-server
   ```

3. **Environment Variables:**
   ```bash
   # Check environment in container
   docker exec mcp-server env | grep MCP_
   
   # Pass environment variables correctly
   docker run -e MCP_SERVER_HOST=0.0.0.0 mcp-server
   ```

### Issue: Container Networking

**Symptoms:**
- Cannot reach microsandbox server from container
- DNS resolution failures
- Network isolation issues

**Solutions:**

1. **Docker Network Configuration:**
   ```bash
   # Create custom network
   docker network create mcp-network
   
   # Run containers on same network
   docker run --network mcp-network --name microsandbox microsandbox:latest
   docker run --network mcp-network -e MSB_SERVER_URL=http://microsandbox:5555 mcp-server
   ```

2. **Host Network Mode:**
   ```bash
   # Use host networking for testing
   docker run --network host mcp-server
   ```

3. **DNS Issues:**
   ```bash
   # Test DNS resolution in container
   docker exec mcp-server nslookup microsandbox
   
   # Use IP addresses instead of hostnames
   docker run -e MSB_SERVER_URL=http://172.17.0.2:5555 mcp-server
   ```

## Debugging Tools

### Enable Debug Logging

```bash
# Maximum verbosity
export MSB_LOG_LEVEL=DEBUG
python -m mcp_server.main --log-level DEBUG

# Structured logging
export MSB_LOG_FORMAT=json
```

### Network Debugging

```bash
# Monitor network traffic
sudo tcpdump -i lo port 8775
sudo tcpdump -i lo port 5555

# Test with netcat
nc -zv localhost 8775
nc -zv localhost 5555

# HTTP debugging with curl
curl -v -X POST http://localhost:8775/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Process Debugging

```bash
# Monitor process activity
strace -p $(pgrep -f mcp_server)

# Check file descriptors
lsof -p $(pgrep -f mcp_server)

# Monitor system calls
sudo perf trace -p $(pgrep -f mcp_server)
```

### Memory Debugging

```bash
# Python memory profiling
pip install memory-profiler
python -m memory_profiler mcp_server/main.py

# System memory monitoring
sudo iotop
sudo htop
vmstat 5
```

## Recovery Procedures

### Graceful Restart

```bash
# Send SIGTERM for graceful shutdown
kill -TERM $(pgrep -f mcp_server)

# Wait for shutdown, then restart
sleep 10
python -m mcp_server.main

# Or use systemd
sudo systemctl restart mcp-server
```

### Emergency Recovery

```bash
# Force kill if unresponsive
kill -KILL $(pgrep -f mcp_server)

# Clean up resources
# Stop all sessions through microsandbox server
curl -X DELETE http://127.0.0.1:5555/api/v1/sessions

# Restart with clean state
python -m mcp_server.main
```

### Data Recovery

```bash
# Backup session data (if applicable)
curl -X POST http://localhost:8775/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_sessions","arguments":{}}}' \
  > sessions_backup.json

# Restore from backup (manual process)
# Review sessions and recreate if necessary
```

## Prevention Strategies

### Monitoring Setup

```bash
# Set up health checks
*/5 * * * * curl -f http://localhost:8775/ || systemctl restart mcp-server

# Log rotation
sudo logrotate -f /etc/logrotate.d/mcp-server

# Resource monitoring
watch -n 30 'ps aux | grep mcp_server'
```

### Configuration Best Practices

1. **Resource Limits**: Always set appropriate resource limits
2. **Timeouts**: Configure reasonable timeouts for your use case
3. **Session Management**: Implement proper session cleanup
4. **Error Handling**: Handle errors gracefully in client code
5. **Monitoring**: Set up comprehensive monitoring and alerting

### Regular Maintenance

```bash
# Weekly maintenance script
#!/bin/bash
# Check server health
curl -f http://localhost:8775/ || exit 1

# Clean up old logs
find /var/log/mcp-server -name "*.log" -mtime +7 -delete

# Check resource usage
df -h | grep -E '9[0-9]%' && echo "Disk space warning"

# Restart if memory usage is high
MEM_USAGE=$(ps -o %mem -p $(pgrep -f mcp_server) | tail -1 | tr -d ' ')
if (( $(echo "$MEM_USAGE > 80" | bc -l) )); then
    systemctl restart mcp-server
fi
```

This troubleshooting guide covers the most common issues you may encounter with the MCP server. For issues not covered here, enable debug logging and examine the detailed error messages for more specific guidance.