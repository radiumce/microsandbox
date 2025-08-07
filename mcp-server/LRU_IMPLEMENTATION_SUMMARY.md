# LRU Eviction Implementation Summary

This document summarizes the LRU (Least Recently Used) eviction mechanism implemented for the microsandbox wrapper.

## Overview

The LRU eviction mechanism automatically removes the least recently used sandbox sessions when resource limits are reached, allowing new sessions to be created without manual intervention.

## Key Features

### 1. Automatic Resource Management
- **Session Limit Enforcement**: Automatically evicts sessions when `MSB_MAX_SESSIONS` is reached
- **Memory Limit Enforcement**: Automatically evicts sessions when `MSB_MAX_TOTAL_MEMORY_MB` is reached
- **Configurable**: Can be enabled/disabled via `MSB_ENABLE_LRU_EVICTION`

### 2. Smart Eviction Logic
- **LRU Ordering**: Sessions are evicted based on last access time (oldest first)
- **Processing Protection**: Sessions in `PROCESSING` state cannot be evicted
- **Creation Protection**: Sessions in `CREATING` state cannot be evicted
- **Minimal Eviction**: Only evicts the minimum number of sessions needed

### 3. Session State Management
- **Automatic Touch**: Sessions are automatically "touched" when accessed
- **Status Tracking**: Sessions track their current state (READY, PROCESSING, etc.)
- **Last Access Tracking**: Each session maintains its last access timestamp

## Implementation Details

### Modified Files

#### 1. `models.py`
- Added `PROCESSING` status to `SessionStatus` enum
- This status prevents sessions from being evicted while handling requests

#### 2. `session_manager.py`
- **ManagedSession.can_be_evicted()**: Determines if a session can be safely evicted
- **ManagedSession.touch()**: Updates last access time for LRU ordering
- **Modified execute_code/execute_command**: Set status to `PROCESSING` during execution

#### 3. `resource_manager.py`
- **check_resource_limits()**: Enhanced to trigger LRU eviction when limits are reached
- **_evict_lru_sessions()**: Implements the LRU eviction algorithm
- **Eviction Logic**: Sorts sessions by last access time and evicts oldest first

#### 4. `wrapper.py`
- **Enhanced execute_code/execute_command**: Automatically touch sessions when reused
- **Session Reuse Detection**: Tracks whether a session is new or reused

#### 5. `config.py`
- **enable_lru_eviction**: New configuration option to enable/disable LRU eviction
- **_parse_boolean()**: New method to parse boolean environment variables

### Configuration Options

```bash
# Enable LRU eviction (default: true)
MSB_ENABLE_LRU_EVICTION=true

# Resource limits that trigger eviction
MSB_MAX_SESSIONS=10
MSB_MAX_TOTAL_MEMORY_MB=8192
```

### Session Lifecycle

```
1. Session Created → Status: CREATING
2. Session Ready → Status: READY (can be evicted)
3. Request Received → Status: PROCESSING (cannot be evicted)
4. Request Completed → Status: READY (can be evicted)
5. Session Idle → Eligible for LRU eviction
6. Session Evicted → Status: STOPPED
```

## Eviction Algorithm

```python
async def _evict_lru_sessions(self, min_sessions_to_evict, min_memory_to_free_mb):
    # 1. Get all sessions that can be evicted
    evictable_sessions = [s for s in all_sessions if s.can_be_evicted()]
    
    # 2. Sort by last_accessed time (oldest first)
    evictable_sessions.sort(key=lambda s: s.last_accessed)
    
    # 3. Evict sessions until requirements are met
    evicted_count = 0
    memory_freed = 0
    
    for session in evictable_sessions:
        if evicted_count >= min_sessions_to_evict and memory_freed >= min_memory_to_free_mb:
            break
            
        await stop_session(session)
        evicted_count += 1
        memory_freed += session.flavor.get_memory_mb()
    
    return evicted_count
```

## Usage Examples

### Basic Usage
```python
async with MicrosandboxWrapper() as wrapper:
    # LRU eviction happens automatically when limits are reached
    result = await wrapper.execute_code(
        code="print('Hello World')",
        template="python"
    )
```

### Session Reuse (Recommended)
```python
async with MicrosandboxWrapper() as wrapper:
    session_id = None
    
    for i in range(10):
        result = await wrapper.execute_code(
            code=f"print('Iteration {i}')",
            session_id=session_id,  # Reuse session
            template="python"
        )
        session_id = result.session_id  # Keep session alive
```

### Monitoring Eviction
```python
# Check resource usage
stats = await wrapper.get_resource_stats()
print(f"Sessions: {stats.active_sessions}/{stats.max_sessions}")

# Get session details
sessions = await wrapper.get_sessions()
for session in sorted(sessions, key=lambda s: s.last_accessed):
    print(f"Session {session.session_id[:8]}: {session.last_accessed}")
```

## Testing

### Test Files Created
1. **test_lru_eviction.py**: Comprehensive test suite for LRU eviction
2. **examples/lru_eviction_example.py**: Practical demonstration of LRU eviction

### Running Tests
```bash
cd mcp-server
python test_lru_eviction.py
python examples/lru_eviction_example.py
```

## Benefits

### 1. Automatic Resource Management
- No manual session cleanup required
- Prevents resource exhaustion
- Maintains system stability

### 2. Intelligent Eviction
- Keeps frequently used sessions active
- Evicts idle sessions first
- Protects active processing sessions

### 3. Configurable Behavior
- Can be enabled/disabled as needed
- Flexible resource limits
- Suitable for different deployment scenarios

### 4. Backward Compatibility
- Existing code continues to work
- Optional feature (enabled by default)
- Graceful degradation when disabled

## Monitoring and Logging

### Log Messages
```
INFO - LRU eviction completed: evicted 2 sessions, freed 2048MB memory
INFO - Evicting LRU session abc12345 (last_accessed: 2024-01-01T10:30:00, flavor: small, status: ready)
WARNING - No sessions could be evicted. Current: 5 sessions, 5120MB memory
```

### Metrics
- Number of sessions evicted
- Memory freed through eviction
- Eviction success/failure rates
- Session access patterns

## Best Practices

### 1. Session Reuse
- Reuse sessions when possible to maintain LRU ordering
- Store session IDs for subsequent requests
- Implement session pooling for high-throughput applications

### 2. Resource Planning
- Set appropriate limits based on workload
- Monitor eviction frequency
- Adjust limits if evictions are too frequent

### 3. Error Handling
- Handle session eviction gracefully
- Implement retry logic for evicted sessions
- Monitor for unexpected session terminations

## Future Enhancements

### Potential Improvements
1. **Weighted LRU**: Consider session importance/priority
2. **Predictive Eviction**: Evict sessions likely to be unused
3. **Custom Eviction Policies**: Allow pluggable eviction strategies
4. **Session Persistence**: Save/restore session state
5. **Resource Prediction**: Predict resource needs for better planning

### Metrics and Monitoring
1. **Eviction Rate Tracking**: Monitor eviction frequency over time
2. **Session Lifetime Analysis**: Analyze session usage patterns
3. **Resource Utilization Trends**: Track resource usage patterns
4. **Performance Impact**: Measure eviction impact on performance

## Conclusion

The LRU eviction mechanism provides automatic, intelligent resource management for the microsandbox wrapper. It ensures system stability while maximizing resource utilization and maintaining good performance for frequently used sessions.

Key advantages:
- ✅ Automatic resource management
- ✅ Intelligent eviction based on usage patterns
- ✅ Protection of active sessions
- ✅ Configurable and optional
- ✅ Backward compatible
- ✅ Comprehensive logging and monitoring