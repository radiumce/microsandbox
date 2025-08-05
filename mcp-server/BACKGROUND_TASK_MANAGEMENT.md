# Background Task Management

This document describes the enhanced background task management functionality implemented in the microsandbox wrapper.

## Overview

The wrapper now provides comprehensive background task management capabilities that allow upper-level MCP servers to:

- Monitor the health and status of background tasks
- Control task lifecycle (start, stop, pause, resume)
- Perform graceful shutdowns with timeout control
- Restart unhealthy tasks automatically
- Get detailed statistics and diagnostics

## Key Features

### 1. Task Status Monitoring

The wrapper provides detailed status information about all background tasks:

```python
# Get comprehensive background task status
task_status = await wrapper.get_background_task_status()

# Example response:
{
    'overall_status': 'healthy',
    'timestamp': 1754312770.366036,
    'components': {
        'session_manager': {
            'status': 'healthy',
            'cleanup_task_healthy': True,
            'cleanup_task_exists': True,
            'cleanup_interval_seconds': 5,
            'session_timeout_seconds': 30,
            'manager_uptime_seconds': 1.0
        },
        'resource_manager': {
            'status': 'healthy',
            'orphan_cleanup_task_healthy': True,
            'orphan_cleanup_task_exists': True,
            'orphan_cleanup_interval_seconds': 10,
            'total_cleanup_cycles': 0,
            'total_orphans_cleaned': 0
        }
    }
}
```

### 2. Automatic Task Restart

The wrapper can automatically restart unhealthy background tasks:

```python
# Restart any unhealthy tasks
restart_result = await wrapper.restart_background_tasks()

# Example response:
{
    'status': 'success',
    'actions_taken': ['session_manager_cleanup_restarted'],
    'errors': [],
    'timestamp': 1754312773.374
}
```

### 3. Task Pause and Resume

For maintenance operations, tasks can be temporarily paused and resumed:

```python
# Pause all background tasks
pause_result = await wrapper.pause_background_tasks()

# Resume all background tasks
resume_result = await wrapper.resume_background_tasks()
```

### 4. Graceful Shutdown

The wrapper supports graceful shutdown with timeout control:

```python
# Graceful shutdown with 30-second timeout
shutdown_result = await wrapper.graceful_shutdown(timeout_seconds=30.0)

# Or use the enhanced stop method
await wrapper.stop(timeout_seconds=30.0)
```

### 5. Enhanced Health Checks

Health checks now include background task status:

```python
# Comprehensive health check
health_status = await wrapper.health_check()

# Check if background tasks are healthy
session_healthy = health_status['components']['session_manager']['background_task_healthy']
resource_healthy = health_status['components']['resource_manager']['background_task_healthy']
```

## Background Tasks

The wrapper manages two main background tasks:

### Session Cleanup Task (SessionManager)

- **Purpose**: Automatically cleans up expired sessions
- **Interval**: Configurable via `cleanup_interval` (default: 60 seconds)
- **Health Check**: Monitors task status and can restart if needed
- **Statistics**: Tracks cleanup cycles, sessions cleaned, and errors

### Orphan Cleanup Task (ResourceManager)

- **Purpose**: Detects and cleans up orphaned sandbox instances
- **Interval**: Configurable via `orphan_cleanup_interval` (default: 600 seconds)
- **Health Check**: Monitors task status and can restart if needed
- **Statistics**: Tracks cleanup cycles, orphans cleaned, and errors

## Configuration

Background task behavior can be configured through environment variables:

```bash
# Session cleanup interval (seconds)
export MSB_CLEANUP_INTERVAL=60

# Orphan cleanup interval (seconds)
export MSB_ORPHAN_CLEANUP_INTERVAL=600

# Session timeout (seconds)
export MSB_SESSION_TIMEOUT=1800
```

## Usage Examples

### Basic Usage

```python
from microsandbox_wrapper import MicrosandboxWrapper

async def main():
    wrapper = MicrosandboxWrapper()
    
    try:
        # Start wrapper (starts background tasks)
        await wrapper.start()
        
        # Your application logic here
        
        # Check task health periodically
        health = await wrapper.health_check()
        if health['status'] != 'healthy':
            print(f"Warning: Wrapper health is {health['status']}")
            
            # Restart unhealthy tasks
            await wrapper.restart_background_tasks()
        
    finally:
        # Graceful shutdown
        await wrapper.stop(timeout_seconds=30.0)
```

### Advanced Task Management

```python
async def maintenance_mode(wrapper):
    """Example of using pause/resume for maintenance."""
    
    # Pause background tasks during maintenance
    await wrapper.pause_background_tasks()
    
    try:
        # Perform maintenance operations
        await perform_maintenance()
    finally:
        # Resume background tasks
        await wrapper.resume_background_tasks()

async def monitor_tasks(wrapper):
    """Example of monitoring background tasks."""
    
    while True:
        # Get detailed task status
        status = await wrapper.get_background_task_status()
        
        # Check overall health
        if status['overall_status'] != 'healthy':
            print(f"Tasks unhealthy: {status}")
            
            # Attempt to restart
            restart_result = await wrapper.restart_background_tasks()
            print(f"Restart result: {restart_result}")
        
        # Wait before next check
        await asyncio.sleep(60)
```

## Error Handling

The background task management system includes comprehensive error handling:

- **Task Failures**: Automatically detected and can be restarted
- **Timeout Handling**: Graceful shutdown respects timeout limits
- **Error Reporting**: Detailed error information in status responses
- **Recovery**: Automatic restart capabilities for failed tasks

## Stateless Design

The wrapper itself remains stateless - all state is maintained by the individual managers:

- **SessionManager**: Maintains session state and cleanup statistics
- **ResourceManager**: Maintains resource state and orphan cleanup statistics
- **Wrapper**: Coordinates managers but holds no persistent state

This design ensures that the wrapper can be easily integrated into different MCP server architectures while providing robust background task management.

## Testing

The background task management functionality is thoroughly tested:

```bash
# Run background task management tests
cd mcp-server
python test_background_task_management.py
```

Tests cover:
- Task status reporting
- Restart functionality
- Pause/resume operations
- Graceful shutdown
- Health check integration

## Requirements Satisfied

This implementation satisfies the requirements from task 14:

- ✅ **5.1, 5.2**: Background tasks can be controlled by upper-level MCP server
- ✅ **4.4**: Graceful shutdown with resource cleanup
- ✅ Task status query functionality
- ✅ Stateless wrapper design with state maintained by managers
- ✅ Comprehensive error handling and recovery