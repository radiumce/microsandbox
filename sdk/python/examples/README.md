# Microsandbox Python SDK Examples

This directory contains examples demonstrating various features of the Microsandbox Python SDK.

## Volume Mapping Example

The `volume_example.py` script demonstrates how to use volume mappings to share files between the host filesystem and the sandbox container.

### Features Demonstrated

- Creating a sandbox with volume mappings
- Reading files from the host filesystem within the sandbox
- Writing files from the sandbox to the host filesystem
- Bidirectional file sharing

### Usage

```bash
cd sdk/python/examples
python volume_example.py
```

### Volume Mapping Format

Volumes are specified as a list of strings in the format `"host_path:container_path"`:

```python
volumes = [
    "/path/on/host:/path/in/container",
    "./relative/path:/shared",
    "/absolute/path:/data"
]
```

### Example Code

```python
import asyncio
from microsandbox import PythonSandbox

async def main():
    # Create sandbox with volume mapping
    async with PythonSandbox.create(
        name="my-sandbox",
        volumes=["/tmp/shared:/shared"],
        memory=512,
        cpus=1.0
    ) as sandbox:
        # Write a file from sandbox to host
        code = """
with open("/shared/hello.txt", "w") as f:
    f.write("Hello from sandbox!")
print("File written to shared volume")
"""
        
        execution = await sandbox.run(code)
        print(execution.stdout)

asyncio.run(main())
```

## Requirements

- Python 3.7+
- aiohttp
- python-dotenv
- Microsandbox server running (default: http://127.0.0.1:5555)

## Environment Variables

- `MSB_SERVER_URL`: Microsandbox server URL (default: http://127.0.0.1:5555)
- `MSB_API_KEY`: API key for authentication (optional)