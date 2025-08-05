# Volume Support Added to Python SDK

## Summary

Added volume mapping support to the Microsandbox Python SDK, allowing users to share files between the host filesystem and sandbox containers.

## Changes Made

### 1. Updated `BaseSandbox` class (`sdk/python/microsandbox/base_sandbox.py`)

#### Modified `start()` method:
- Added `volumes: Optional[list] = None` parameter
- Updated method signature and docstring
- Added volume configuration to the request payload when volumes are provided

#### Modified `create()` class method:
- Added volume-related parameters: `volumes`, `image`, `memory`, `cpus`, `timeout`
- Updated method signature and docstring
- Pass volume parameters to the `start()` method

### 2. Created Examples and Documentation

#### Volume Example (`sdk/python/examples/volume_example.py`)
- Comprehensive example demonstrating volume functionality
- Shows bidirectional file sharing between host and sandbox
- Demonstrates multiple use cases and best practices

#### Examples README (`sdk/python/examples/README.md`)
- Documentation for volume mapping format and usage
- Code examples and requirements

#### Test Script (`sdk/python/test_volume_functionality.py`)
- Automated test to verify volume functionality
- Tests both single and multiple volume mappings
- Includes error handling and validation

### 3. Updated Documentation

#### Main Usage Examples (`USAGE_EXAMPLES.md`)
- Added Python SDK volume mapping section
- Examples for basic usage, multiple volumes, and manual start
- Integration with existing documentation structure

#### Python SDK README (`sdk/python/README.md`)
- Added volume mapping section with examples
- Advanced configuration examples
- Updated examples section with volume use cases

## Volume Mapping Format

Volumes are specified as a list of strings in the format `"host_path:container_path"`:

```python
volumes = [
    "/absolute/path/on/host:/path/in/container",
    "./relative/path:/shared",
    "/home/user/data:/data"
]
```

## Usage Examples

### Basic Usage with Context Manager

```python
async with PythonSandbox.create(
    volumes=["/tmp/shared:/shared"]
) as sandbox:
    await sandbox.run('print("Volume mapping active!")')
```

### Manual Start with Volumes

```python
sandbox = PythonSandbox()
sandbox._session = aiohttp.ClientSession()

await sandbox.start(
    volumes=["./data:/data", "/tmp/output:/results"],
    memory=512,
    cpus=1.0
)
```

### Multiple Volume Mappings

```python
volumes = [
    "/home/user/data:/data",      # Data directory
    "/home/user/config:/config",  # Configuration files
    "./output:/results"           # Results output
]

async with PythonSandbox.create(volumes=volumes) as sandbox:
    # Use multiple mounted volumes
    pass
```

## Server-Side Support

The volume functionality leverages the existing server-side implementation in `microsandbox-server/lib/handler.rs`:

- `SandboxConfig` struct already includes `volumes: Vec<String>` field
- `sandbox_start_impl` function processes volume configurations
- Volumes are written to the sandbox YAML configuration
- Firecracker VM receives volume mappings via `--mapped-dir` parameters

## Path Handling

The server supports both relative and absolute paths:
- **Relative paths**: Resolved relative to the project directory
- **Absolute paths**: Used directly as specified
- **Format**: `"host_path:container_path"` (standard Docker volume format)

## Testing

Run the test script to verify functionality:

```bash
cd sdk/python
python test_volume_functionality.py
```

The test verifies:
- Basic volume mapping functionality
- File sharing between host and sandbox
- Multiple volume mappings
- Error handling and edge cases

## Backward Compatibility

All changes are backward compatible:
- Volume parameter is optional (defaults to `None`)
- Existing code continues to work without modification
- No breaking changes to existing API

## Files Modified/Created

### Modified:
- `sdk/python/microsandbox/base_sandbox.py`
- `USAGE_EXAMPLES.md`
- `sdk/python/README.md`

### Created:
- `sdk/python/examples/volume_example.py`
- `sdk/python/examples/README.md`
- `sdk/python/test_volume_functionality.py`
- `VOLUME_SUPPORT_SUMMARY.md`

## Next Steps

1. Test the implementation with a running Microsandbox server
2. Consider adding volume support to other SDK languages (Node.js, Ruby, etc.)
3. Add volume mapping validation and error handling
4. Consider adding volume-specific utility methods
5. Update API documentation to include volume parameters