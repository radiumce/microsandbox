# Orphan Sandbox Cleanup

This document describes the orphan sandbox detection and cleanup functionality implemented in the ResourceManager.

## Overview

Orphan sandboxes are sandbox instances that are running on the microsandbox server but are not associated with any active session in the session manager. This can happen due to:

- Application crashes or unexpected shutdowns
- Network interruptions during session cleanup
- Manual server restarts without proper cleanup
- Bugs in session management code

The ResourceManager implements automatic detection and cleanup of these orphan sandboxes to prevent resource leaks and ensure efficient resource utilization.

## How It Works

### 1. Detection Process

The orphan detection process works by comparing two lists:

1. **Running Sandboxes**: Retrieved from the microsandbox server via the `sandbox.metrics.get` JSON-RPC API
2. **Active Sessions**: Retrieved from the SessionManager, filtered to exclude stopped sessions

Any sandbox that appears in the running list but doesn't have a corresponding active session is considered an orphan.

### 2. Identification Logic

```python
# Get all running sandboxes from server
running_sandboxes = await self._get_running_sandboxes()

# Get active sessions from session manager
active_sessions = await self._session_manager.get_sessions()
active_sandbox_names = set()

for session in active_sessions:
    if session.status != SessionStatus.STOPPED:
        sandbox_key = f"{session.namespace}/{session.sandbox_name}"
        active_sandbox_names.add(sandbox_key)

# Identify orphans
orphan_sandboxes = []
for sandbox in running_sandboxes:
    sandbox_key = f"{sandbox['namespace']}/{sandbox['name']}"
    if sandbox_key not in active_sandbox_names:
        orphan_sandboxes.append(sandbox)
```

### 3. Cleanup Process

Once orphans are identified, they are cleaned up using the `sandbox.stop` JSON-RPC API:

- Multiple orphans are cleaned up concurrently (limited to 5 concurrent operations)
- Each cleanup operation is performed safely with proper error handling
- Failed cleanups are logged but don't prevent other cleanups from proceeding
- Statistics are tracked for monitoring and debugging

## API Endpoints Used

### Getting Running Sandboxes

**Method**: `sandbox.metrics.get`
**URL**: `{server_url}/api/v1/rpc`
**Request**:
```json
{
    "jsonrpc": "2.0",
    "method": "sandbox.metrics.get",
    "params": {
        "namespace": "*",
        "sandbox": null
    },
    "id": 1
}
```

**Response**:
```json
{
    "jsonrpc": "2.0",
    "result": {
        "sandboxes": [
            {
                "namespace": "default",
                "name": "session-12345678",
                "running": true,
                "cpu_usage": 15.5,
                "memory_usage": 512,
                "disk_usage": 1024000
            }
        ]
    },
    "id": 1
}
```

### Stopping Orphan Sandboxes

**Method**: `sandbox.stop`
**URL**: `{server_url}/api/v1/rpc`
**Request**:
```json
{
    "jsonrpc": "2.0",
    "method": "sandbox.stop",
    "params": {
        "sandbox": "orphan-sandbox-name",
        "namespace": "default"
    },
    "id": 1
}
```

**Response**:
```json
{
    "jsonrpc": "2.0",
    "result": "Sandbox stopped successfully",
    "id": 1
}
```

## Configuration

The orphan cleanup behavior can be configured through environment variables:

- `MSB_ORPHAN_CLEANUP_INTERVAL`: Interval between cleanup cycles in seconds (default: 600)
- `MSB_SERVER_URL`: Microsandbox server URL (default: http://127.0.0.1:5555)
- `MSB_API_KEY`: API key for server authentication (optional)

## Usage

### Automatic Cleanup

The ResourceManager automatically starts a background cleanup task when started:

```python
resource_manager = ResourceManager(config, session_manager)
await resource_manager.start()  # Starts background cleanup task
```

### Manual Cleanup

You can trigger manual cleanup at any time:

```python
# Force immediate cleanup
cleaned_count = await resource_manager.force_orphan_cleanup()
print(f"Cleaned {cleaned_count} orphan sandboxes")
```

### Getting Cleanup Statistics

```python
# Get detailed cleanup statistics
stats = resource_manager.get_orphan_cleanup_stats()
print(f"Total cleanup cycles: {stats['total_cleanup_cycles']}")
print(f"Total orphans cleaned: {stats['total_orphans_cleaned']}")
print(f"Success rate: {stats['cleanup_success_rate']:.2%}")
```

### Getting Running Sandbox Information

```python
# Get detailed information about all running sandboxes
info = await resource_manager.get_running_sandboxes_info()
print(f"Total running: {info['total_running_sandboxes']}")
print(f"Managed: {info['managed_sandboxes_count']}")
print(f"Orphans: {info['orphan_sandboxes_count']}")
```

## Error Handling

The cleanup system is designed to be robust and handle various error conditions:

### Network Errors
- Connection timeouts are handled gracefully
- Failed API calls return empty results rather than crashing
- Cleanup continues even if some operations fail

### RPC Errors
- JSON-RPC errors are logged and handled appropriately
- Invalid responses are treated as empty results
- Authentication errors are logged with clear messages

### Concurrent Operations
- Cleanup operations are limited to prevent server overload
- Failed individual cleanups don't affect other operations
- Statistics track both successes and failures

## Monitoring and Logging

### Log Levels

- **INFO**: Successful cleanups, periodic statistics
- **DEBUG**: Detailed operation information, sandbox details
- **WARNING**: Partial failures, resource issues
- **ERROR**: Failed operations, network errors

### Key Log Messages

```
INFO: Orphan cleanup cycle #10: cleaned 3 orphans in 2.45s
DEBUG: Identified orphan sandbox: default/orphan-sandbox-1
ERROR: Failed to clean orphan sandbox default/orphan-2: Network error
```

### Statistics Tracking

The system tracks comprehensive statistics:

- Total cleanup cycles performed
- Total orphans cleaned across all cycles
- Number of cleanup errors encountered
- Average orphans per cleanup cycle
- Cleanup success rate
- Last cleanup time and duration

## Testing

The orphan cleanup functionality includes comprehensive tests:

### Unit Tests
- `test_orphan_simple.py`: Tests core orphan identification logic
- Covers various scenarios: no orphans, all orphans, mixed scenarios
- Tests statistics tracking and error handling

### Integration Tests
- `test_rpc_integration.py`: Tests JSON-RPC API integration
- Verifies correct request formatting and response parsing
- Tests error handling for network and RPC errors

### Running Tests

```bash
cd mcp-server
python test_orphan_simple.py
python test_rpc_integration.py
```

## Performance Considerations

### Cleanup Frequency
- Default 10-minute interval balances resource cleanup with server load
- Configurable based on environment needs
- More frequent cleanup for high-churn environments

### Concurrent Operations
- Limited to 5 concurrent stop operations to prevent server overload
- Can be adjusted based on server capacity
- Cleanup operations are performed asynchronously

### Resource Usage
- Minimal memory footprint for tracking statistics
- Network calls are made only during cleanup cycles
- No persistent storage required

## Troubleshooting

### Common Issues

1. **No orphans detected but sandboxes are running**
   - Check that session manager is properly tracking active sessions
   - Verify namespace and sandbox name matching logic
   - Enable DEBUG logging to see detailed comparison

2. **Cleanup operations failing**
   - Check server connectivity and API key configuration
   - Verify server has `sandbox.stop` API available
   - Check server logs for authentication or permission issues

3. **High cleanup frequency with many orphans**
   - May indicate issues with session cleanup in application code
   - Check for proper session stopping in error conditions
   - Consider reducing cleanup interval temporarily

### Debug Commands

```python
# Get detailed running sandbox information
info = await resource_manager.get_running_sandboxes_info()
print(json.dumps(info, indent=2))

# Get health status
health = resource_manager.get_resource_health_status()
print(json.dumps(health, indent=2))

# Force cleanup with detailed logging
import logging
logging.getLogger('microsandbox_wrapper.resource_manager').setLevel(logging.DEBUG)
cleaned = await resource_manager.force_orphan_cleanup()
```

## Future Enhancements

Potential improvements to the orphan cleanup system:

1. **Configurable cleanup strategies**: Different cleanup policies based on sandbox age, resource usage, etc.
2. **Metrics export**: Integration with monitoring systems like Prometheus
3. **Cleanup notifications**: Alerts when large numbers of orphans are detected
4. **Graceful shutdown**: Attempt to save sandbox state before cleanup
5. **Cleanup scheduling**: More sophisticated scheduling based on server load