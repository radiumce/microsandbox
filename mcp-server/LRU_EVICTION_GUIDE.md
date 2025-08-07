# LRU Eviction Guide

This guide explains the Least Recently Used (LRU) eviction mechanism implemented in the microsandbox wrapper.

## Overview

The LRU eviction mechanism automatically removes the least recently used sandbox sessions when resource limits are reached, allowing new sessions to be created without manual intervention.

## How It Works

### 1. Session State Management

Each session tracks:
- **Last Accessed Time**: Updated whenever the session is used
- **Status**: Current state of the session (CREATING, READY, RUNNING, PROCESSING, ERROR, STOPPED)

### 2. LRU Ordering

Sessions are ordered by their `last_accessed` time:
- Sessions accessed more recently are kept
- Sessions accessed less recently are candidates for eviction

### 3. Eviction Eligibility

A session can be evicted only if:
- Status is NOT `PROCESSING` (actively handling a request)
- Status is NOT `CREATING` (still being initialized)
- It's one of the least recently used sessions

### 4. Automatic Eviction

When resource limits would be exceeded:
1. System identifies sessions that can be evicted
2. Sorts them by last accessed time (oldest first)
3. Evicts sessions until resource requirements are met
4. Creates the new session

## Configuration

### Environment Variables

```bash
# Enable/disable LRU eviction (default: true)
MSB_ENABLE_LRU_EVICTION=true

# Maximum concurrent sessions (triggers eviction when exceeded)
MSB_MAX_SESSIONS=10

# Maximum total memory in MB (triggers eviction when exceeded)
MSB_MAX_TOTAL_MEMORY_MB=8192
```

### Programmatic Configuration

```python
from microsandbox_wrapper.config import WrapperConfig

config = WrapperConfig(
    max_concurrent_sessions=5,
    max_total_memory_mb=4096,
    enable_lru_eviction=True
)
```

## Usage Examples

### Basic Usage

```python
import asyncio
from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.models import SandboxFlavor

async def example():
    async with MicrosandboxWrapper() as wrapper:
        # Create sessions - LRU eviction happens automatically
        # when limits are reached
        
        result1 = await wrapper.execute_code(
            code="print('Session 1')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        # Session is automatically touched (LRU updated) when reused
        result2 = await wrapper.execute_code(
            code="print('Reusing session 1')",
            session_id=result1.session_id,  # Reuse session
            template="python"
        )
```

### Monitoring Eviction

```python
async def monitor_eviction():
    async with MicrosandboxWrapper() as wrapper:
        # Get current resource stats
        stats = await wrapper.get_resource_stats()
        print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        print(f"Memory usage: {stats.total_memory_mb}MB")
        
        # Get session details
        sessions = await wrapper.get_sessions()
        for session in sorted(sessions, key=lambda s: s.last_accessed):
            print(f"Session {session.session_id[:8]}: "
                  f"last_accessed={session.last_accessed}, "
                  f"status={session.status.value}")
```

## Session States and Eviction

| Status | Can Be Evicted | Description |
|--------|----------------|-------------|
| `CREATING` | ❌ No | Session is being initialized |
| `READY` | ✅ Yes | Session is idle and ready for use |
| `RUNNING` | ✅ Yes | Session completed execution, now idle |
| `PROCESSING` | ❌ No | Session is actively processing a request |
| `ERROR` | ✅ Yes | Session encountered an error |
| `STOPPED` | ✅ Yes | Session has been terminated |

## Best Practices

### 1. Session Reuse

Reuse sessions when possible to maintain LRU ordering:

```python
# Good: Reuse session
session_id = None
for i in range(10):
    result = await wrapper.execute_code(
        code=f"print('Iteration {i}')",
        session_id=session_id,  # Reuse same session
        template="python"
    )
    session_id = result.session_id
```

### 2. Resource Planning

Set appropriate limits based on your workload:

```python
# For development/testing
config = WrapperConfig(
    max_concurrent_sessions=3,
    max_total_memory_mb=3072,  # 3GB
    enable_lru_eviction=True
)

# For production
config = WrapperConfig(
    max_concurrent_sessions=20,
    max_total_memory_mb=20480,  # 20GB
    enable_lru_eviction=True
)
```

### 3. Monitoring

Monitor eviction events in logs:

```
INFO - LRU eviction completed: evicted 2 sessions, freed 2048MB memory
INFO - Evicting LRU session abc12345 (last_accessed: 2024-01-01T10:30:00, flavor: small, status: ready)
```

## Troubleshooting

### No Sessions Available for Eviction

If all sessions are in `PROCESSING` or `CREATING` state:

```
WARNING - No sessions could be evicted. Current: 5 sessions, 5120MB memory
```

**Solutions:**
- Wait for processing sessions to complete
- Increase resource limits
- Optimize code execution time

### Frequent Evictions

If sessions are being evicted too frequently:

```
INFO - LRU eviction completed: evicted 1 sessions, freed 1024MB memory
```

**Solutions:**
- Increase `max_concurrent_sessions`
- Increase `max_total_memory_mb`
- Use smaller sandbox flavors
- Implement session pooling

### Disabling LRU Eviction

To disable automatic eviction:

```bash
MSB_ENABLE_LRU_EVICTION=false
```

When disabled, resource limit violations will result in immediate failures instead of eviction attempts.

## Testing

Run the LRU eviction test suite:

```bash
cd mcp-server
python test_lru_eviction.py
```

This test verifies:
- Basic LRU eviction functionality
- Protection of processing sessions
- Correct LRU ordering
- Resource limit enforcement

## Implementation Details

### Key Components

1. **ManagedSession.can_be_evicted()**: Determines if a session can be safely evicted
2. **ManagedSession.touch()**: Updates the last accessed time
3. **ResourceManager._evict_lru_sessions()**: Implements the eviction algorithm
4. **ResourceManager.check_resource_limits()**: Triggers eviction when needed

### Eviction Algorithm

```python
async def _evict_lru_sessions(self, min_sessions_to_evict, min_memory_to_free_mb):
    # 1. Get all sessions that can be evicted
    evictable_sessions = [s for s in sessions if s.can_be_evicted()]
    
    # 2. Sort by last_accessed (oldest first)
    evictable_sessions.sort(key=lambda s: s.last_accessed)
    
    # 3. Evict sessions until requirements are met
    for session in evictable_sessions:
        if requirements_met():
            break
        await stop_session(session)
```

This ensures that:
- Only safe-to-evict sessions are removed
- The least recently used sessions are evicted first
- Eviction stops once resource requirements are satisfied