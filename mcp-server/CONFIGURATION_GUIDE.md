# MicrosandboxWrapper Configuration Guide

This guide provides comprehensive information about configuring the MicrosandboxWrapper for different environments and use cases.

## Table of Contents

- [Overview](#overview)
- [Environment Variables](#environment-variables)
- [Programmatic Configuration](#programmatic-configuration)
- [Configuration Examples](#configuration-examples)
- [Advanced Configuration](#advanced-configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The MicrosandboxWrapper can be configured in two ways:

1. **Environment Variables**: The most common approach, suitable for deployment environments
2. **Programmatic Configuration**: Direct configuration via code, useful for testing and custom setups

Configuration is handled by the `WrapperConfig` class, which provides sensible defaults for all settings.

## Environment Variables

### Server Configuration

#### `MSB_SERVER_URL`
- **Description**: URL of the microsandbox server
- **Default**: `http://127.0.0.1:5555`
- **Example**: `export MSB_SERVER_URL="http://microsandbox.example.com:5555"`

#### `MSB_API_KEY`
- **Description**: API key for server authentication (if required)
- **Default**: `None`
- **Example**: `export MSB_API_KEY="your-secret-api-key"`

### Session Configuration

#### `MSB_SESSION_TIMEOUT`
- **Description**: Session timeout in seconds
- **Default**: `1800` (30 minutes)
- **Range**: `60` - `86400` (1 minute to 24 hours)
- **Example**: `export MSB_SESSION_TIMEOUT="3600"  # 1 hour`

#### `MSB_MAX_SESSIONS`
- **Description**: Maximum number of concurrent sessions
- **Default**: `10`
- **Range**: `1` - `100`
- **Example**: `export MSB_MAX_SESSIONS="20"`

#### `MSB_CLEANUP_INTERVAL`
- **Description**: Interval between session cleanup checks in seconds
- **Default**: `60` (1 minute)
- **Range**: `10` - `3600`
- **Example**: `export MSB_CLEANUP_INTERVAL="30"`

### Sandbox Configuration

#### `MSB_DEFAULT_FLAVOR`
- **Description**: Default sandbox resource configuration
- **Default**: `small`
- **Options**: `small`, `medium`, `large`
- **Example**: `export MSB_DEFAULT_FLAVOR="medium"`

#### `MSB_SANDBOX_START_TIMEOUT`
- **Description**: Timeout for sandbox startup in seconds
- **Default**: `180.0` (3 minutes)
- **Range**: `30.0` - `600.0`
- **Example**: `export MSB_SANDBOX_START_TIMEOUT="300.0"`

#### `MSB_EXECUTION_TIMEOUT`
- **Description**: Default execution timeout in seconds
- **Default**: `300` (5 minutes)
- **Range**: `10` - `3600`
- **Example**: `export MSB_EXECUTION_TIMEOUT="600"`

### Resource Configuration

#### `MSB_MAX_TOTAL_MEMORY_MB`
- **Description**: Maximum total memory usage across all sessions in MB
- **Default**: `None` (no limit)
- **Example**: `export MSB_MAX_TOTAL_MEMORY_MB="8192"  # 8GB`

#### `MSB_SHARED_VOLUME_PATH`
- **Description**: Volume mappings between host and sandbox
- **Default**: `[]` (no mappings)
- **Format**: JSON array of strings in format `"host_path:container_path"`
- **Examples**:
  ```bash
  # Single mapping
  export MSB_SHARED_VOLUME_PATH='["/host/data:/sandbox/data"]'
  
  # Multiple mappings
  export MSB_SHARED_VOLUME_PATH='["/host/input:/sandbox/input", "/host/output:/sandbox/output"]'
  
  # Comma-separated format (legacy)
  export MSB_SHARED_VOLUME_PATH="/host/data:/sandbox/data,/host/logs:/sandbox/logs"
  ```

### Cleanup Configuration

#### `MSB_ORPHAN_CLEANUP_INTERVAL`
- **Description**: Interval between orphan sandbox cleanup checks in seconds
- **Default**: `600` (10 minutes)
- **Range**: `60` - `3600`
- **Example**: `export MSB_ORPHAN_CLEANUP_INTERVAL="300"`

### Logging Configuration

#### `MSB_LOG_LEVEL`
- **Description**: Logging level for the wrapper
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Example**: `export MSB_LOG_LEVEL="DEBUG"`

## Programmatic Configuration

### Basic Configuration

```python
from microsandbox_wrapper import WrapperConfig, SandboxFlavor

# Create custom configuration
config = WrapperConfig(
    server_url="http://localhost:5555",
    session_timeout=3600,  # 1 hour
    max_concurrent_sessions=5,
    default_flavor=SandboxFlavor.MEDIUM,
    default_execution_timeout=600,  # 10 minutes
)

# Use with wrapper
async with MicrosandboxWrapper(config=config) as wrapper:
    # Use wrapper with custom configuration
    pass
```

### Advanced Configuration

```python
from microsandbox_wrapper import WrapperConfig, SandboxFlavor

config = WrapperConfig(
    # Server settings
    server_url="http://production-microsandbox:5555",
    api_key="prod-api-key-123",
    
    # Session management
    session_timeout=7200,  # 2 hours for long-running tasks
    max_concurrent_sessions=20,
    cleanup_interval=30,   # More frequent cleanup
    
    # Sandbox settings
    default_flavor=SandboxFlavor.LARGE,  # More resources by default
    sandbox_start_timeout=300.0,  # 5 minutes for slow environments
    default_execution_timeout=1800,  # 30 minutes for complex tasks
    
    # Resource limits
    max_total_memory_mb=16384,  # 16GB total limit
    
    # Volume mappings
    shared_volume_mappings=[
        "/data/input:/sandbox/input",
        "/data/output:/sandbox/output",
        "/data/shared:/sandbox/shared",
        "/logs:/sandbox/logs"
    ],
    
    # Cleanup settings
    orphan_cleanup_interval=180  # 3 minutes for aggressive cleanup
)
```

### Configuration from Environment with Overrides

```python
from microsandbox_wrapper import WrapperConfig, SandboxFlavor

# Load base configuration from environment
config = WrapperConfig.from_env()

# Override specific settings
config.max_concurrent_sessions = 15
config.default_flavor = SandboxFlavor.LARGE
config.shared_volume_mappings.append("/custom/path:/sandbox/custom")

async with MicrosandboxWrapper(config=config) as wrapper:
    # Use wrapper with modified configuration
    pass
```

## Configuration Examples

### Development Environment

```bash
# Development configuration - local server, debug logging
export MSB_SERVER_URL="http://127.0.0.1:5555"
export MSB_SESSION_TIMEOUT="1800"
export MSB_MAX_SESSIONS="5"
export MSB_DEFAULT_FLAVOR="small"
export MSB_LOG_LEVEL="DEBUG"
export MSB_CLEANUP_INTERVAL="30"
export MSB_SHARED_VOLUME_PATH='["/tmp/dev-data:/sandbox/data"]'
```

### Production Environment

```bash
# Production configuration - external server, optimized settings
export MSB_SERVER_URL="http://microsandbox-prod.internal:5555"
export MSB_API_KEY="${MICROSANDBOX_API_KEY}"
export MSB_SESSION_TIMEOUT="3600"
export MSB_MAX_SESSIONS="50"
export MSB_DEFAULT_FLAVOR="medium"
export MSB_EXECUTION_TIMEOUT="900"
export MSB_MAX_TOTAL_MEMORY_MB="32768"
export MSB_LOG_LEVEL="INFO"
export MSB_CLEANUP_INTERVAL="60"
export MSB_ORPHAN_CLEANUP_INTERVAL="300"
export MSB_SHARED_VOLUME_PATH='["/data/input:/sandbox/input", "/data/output:/sandbox/output"]'
```

### Testing Environment

```bash
# Testing configuration - fast cleanup, small limits
export MSB_SERVER_URL="http://test-microsandbox:5555"
export MSB_SESSION_TIMEOUT="300"
export MSB_MAX_SESSIONS="3"
export MSB_DEFAULT_FLAVOR="small"
export MSB_EXECUTION_TIMEOUT="60"
export MSB_LOG_LEVEL="DEBUG"
export MSB_CLEANUP_INTERVAL="10"
export MSB_ORPHAN_CLEANUP_INTERVAL="30"
```

### High-Performance Environment

```bash
# High-performance configuration - large resources, many sessions
export MSB_SERVER_URL="http://hpc-microsandbox:5555"
export MSB_SESSION_TIMEOUT="7200"
export MSB_MAX_SESSIONS="100"
export MSB_DEFAULT_FLAVOR="large"
export MSB_EXECUTION_TIMEOUT="3600"
export MSB_MAX_TOTAL_MEMORY_MB="65536"
export MSB_SANDBOX_START_TIMEOUT="600.0"
export MSB_CLEANUP_INTERVAL="120"
export MSB_ORPHAN_CLEANUP_INTERVAL="600"
```

## Advanced Configuration

### Volume Mapping Patterns

#### Simple Data Processing

```bash
# Input/output pattern for data processing
export MSB_SHARED_VOLUME_PATH='[
  "/data/raw:/sandbox/input",
  "/data/processed:/sandbox/output"
]'
```

#### Multi-Stage Pipeline

```bash
# Multiple stages with shared workspace
export MSB_SHARED_VOLUME_PATH='[
  "/pipeline/stage1:/sandbox/stage1",
  "/pipeline/stage2:/sandbox/stage2",
  "/pipeline/stage3:/sandbox/stage3",
  "/pipeline/shared:/sandbox/shared",
  "/pipeline/logs:/sandbox/logs"
]'
```

#### Development with Source Code

```bash
# Development with source code mounting
export MSB_SHARED_VOLUME_PATH='[
  "/project/src:/sandbox/src:ro",
  "/project/data:/sandbox/data",
  "/project/output:/sandbox/output"
]'
```

### Resource Optimization

#### Memory-Constrained Environment

```python
config = WrapperConfig(
    max_concurrent_sessions=5,  # Fewer sessions
    default_flavor=SandboxFlavor.SMALL,  # Smaller sandboxes
    max_total_memory_mb=4096,  # 4GB total limit
    session_timeout=900,  # Shorter timeout (15 min)
    cleanup_interval=30,  # Frequent cleanup
)
```

#### CPU-Intensive Workloads

```python
config = WrapperConfig(
    max_concurrent_sessions=8,  # Moderate concurrency
    default_flavor=SandboxFlavor.LARGE,  # More CPU per sandbox
    session_timeout=3600,  # Longer timeout for complex tasks
    default_execution_timeout=1800,  # 30 minutes per execution
)
```

#### High-Throughput Environment

```python
config = WrapperConfig(
    max_concurrent_sessions=50,  # Many concurrent sessions
    default_flavor=SandboxFlavor.SMALL,  # Keep individual footprint small
    session_timeout=600,  # Short timeout for quick turnover
    cleanup_interval=15,  # Very frequent cleanup
    orphan_cleanup_interval=60,  # Aggressive orphan cleanup
)
```

### Security Configuration

#### Restricted Environment

```python
config = WrapperConfig(
    # No volume mappings for security
    shared_volume_mappings=[],
    
    # Shorter timeouts to limit exposure
    session_timeout=600,
    default_execution_timeout=300,
    
    # Smaller resource limits
    max_concurrent_sessions=5,
    default_flavor=SandboxFlavor.SMALL,
    max_total_memory_mb=2048,
)
```

#### Audit-Friendly Configuration

```python
config = WrapperConfig(
    # Detailed logging
    # (Set MSB_LOG_LEVEL="DEBUG" in environment)
    
    # Shorter session lifetimes for audit trails
    session_timeout=1800,
    cleanup_interval=60,
    
    # Controlled resource usage
    max_concurrent_sessions=10,
    max_total_memory_mb=8192,
)
```

## Best Practices

### Environment-Specific Settings

1. **Development**:
   - Use debug logging (`MSB_LOG_LEVEL="DEBUG"`)
   - Short cleanup intervals for quick iteration
   - Small resource limits to conserve local resources

2. **Testing**:
   - Very short timeouts for fast test execution
   - Minimal resource limits
   - Frequent cleanup to prevent test interference

3. **Production**:
   - Appropriate resource limits based on expected load
   - Longer timeouts for complex operations
   - Balanced cleanup intervals

### Resource Planning

1. **Memory Planning**:
   ```
   Total Memory = (Max Sessions × Flavor Memory) + Overhead
   
   Example:
   - 20 sessions × 2GB (medium) = 40GB
   - Add 20% overhead = 48GB total
   ```

2. **Session Timeout Calculation**:
   ```
   Session Timeout = Max Expected Execution Time × 2
   
   Example:
   - Max execution: 10 minutes
   - Session timeout: 20 minutes
   ```

3. **Cleanup Interval Guidelines**:
   - High-frequency: 15-30 seconds (testing)
   - Normal: 60-120 seconds (production)
   - Low-frequency: 300+ seconds (resource-constrained)

### Security Considerations

1. **Volume Mappings**:
   - Only map necessary directories
   - Use read-only mappings when possible
   - Avoid mapping sensitive system directories

2. **Resource Limits**:
   - Set `max_total_memory_mb` to prevent resource exhaustion
   - Limit `max_concurrent_sessions` based on system capacity
   - Use appropriate execution timeouts

3. **Network Security**:
   - Use HTTPS for `MSB_SERVER_URL` in production
   - Secure API keys with proper secret management
   - Consider network isolation for sandbox server

## Troubleshooting

### Common Configuration Issues

#### 1. Server Connection Failed

**Symptoms**:
```
ConnectionError: Cannot connect to microsandbox server
```

**Solutions**:
- Verify `MSB_SERVER_URL` is correct
- Check if microsandbox server is running
- Test connectivity: `curl -s ${MSB_SERVER_URL}/api/v1/health`

#### 2. Resource Limit Exceeded

**Symptoms**:
```
ResourceLimitError: Maximum concurrent sessions (10) exceeded
```

**Solutions**:
- Increase `MSB_MAX_SESSIONS`
- Decrease `MSB_SESSION_TIMEOUT` for faster turnover
- Implement session pooling in your application

#### 3. Volume Mapping Not Working

**Symptoms**:
```
FileNotFoundError: [Errno 2] No such file or directory: '/sandbox/data/file.txt'
```

**Solutions**:
- Verify host path exists and is accessible
- Check `MSB_SHARED_VOLUME_PATH` format
- Ensure proper permissions on host directories

#### 4. Session Timeout Too Short

**Symptoms**:
```
Sessions being cleaned up before operations complete
```

**Solutions**:
- Increase `MSB_SESSION_TIMEOUT`
- Decrease `MSB_CLEANUP_INTERVAL`
- Use explicit session management in your code

#### 5. Memory Limit Exceeded

**Symptoms**:
```
ResourceLimitError: Total memory limit (8192 MB) would be exceeded
```

**Solutions**:
- Increase `MSB_MAX_TOTAL_MEMORY_MB`
- Use smaller sandbox flavors
- Reduce `MSB_MAX_SESSIONS`

### Configuration Validation

Use this script to validate your configuration:

```python
#!/usr/bin/env python3
"""Configuration validation script."""

import os
import json
from microsandbox_wrapper import WrapperConfig

def validate_config():
    """Validate current configuration."""
    try:
        config = WrapperConfig.from_env()
        print("✓ Configuration loaded successfully")
        
        # Validate server URL
        if not config.server_url.startswith(('http://', 'https://')):
            print("⚠ Server URL should start with http:// or https://")
        
        # Validate timeouts
        if config.session_timeout < 60:
            print("⚠ Session timeout is very short (< 1 minute)")
        
        if config.default_execution_timeout > config.session_timeout:
            print("⚠ Execution timeout is longer than session timeout")
        
        # Validate resource limits
        if config.max_concurrent_sessions > 100:
            print("⚠ Very high max sessions (> 100)")
        
        # Validate volume mappings
        for mapping in config.shared_volume_mappings:
            if ':' not in mapping:
                print(f"✗ Invalid volume mapping format: {mapping}")
            else:
                host_path, container_path = mapping.split(':', 1)
                if not os.path.exists(host_path):
                    print(f"⚠ Host path does not exist: {host_path}")
        
        print(f"\nConfiguration summary:")
        print(f"  Server URL: {config.server_url}")
        print(f"  Max sessions: {config.max_concurrent_sessions}")
        print(f"  Session timeout: {config.session_timeout}s")
        print(f"  Default flavor: {config.default_flavor.value}")
        print(f"  Volume mappings: {len(config.shared_volume_mappings)}")
        
    except Exception as e:
        print(f"✗ Configuration error: {e}")

if __name__ == "__main__":
    validate_config()
```

### Environment File Template

Create a `.env` file for easy configuration management:

```bash
# .env file template
# Copy this file and customize for your environment

# Server Configuration
MSB_SERVER_URL=http://127.0.0.1:5555
MSB_API_KEY=

# Session Configuration
MSB_SESSION_TIMEOUT=1800
MSB_MAX_SESSIONS=10
MSB_CLEANUP_INTERVAL=60

# Sandbox Configuration
MSB_DEFAULT_FLAVOR=small
MSB_SANDBOX_START_TIMEOUT=180.0
MSB_EXECUTION_TIMEOUT=300

# Resource Configuration
MSB_MAX_TOTAL_MEMORY_MB=
MSB_SHARED_VOLUME_PATH=[]

# Cleanup Configuration
MSB_ORPHAN_CLEANUP_INTERVAL=600

# Logging Configuration
MSB_LOG_LEVEL=INFO
```

Load the environment file:

```bash
# Load environment variables from file
set -a
source .env
set +a

# Or use with Python
pip install python-dotenv
```

```python
from dotenv import load_dotenv
load_dotenv()  # Load .env file

from microsandbox_wrapper import MicrosandboxWrapper
# Configuration will be loaded from environment
```

This configuration guide should help you set up the MicrosandboxWrapper for any environment or use case. For specific deployment scenarios, refer to the examples and adjust the configuration accordingly.