#!/usr/bin/env python3
"""
Example demonstrating volume mapping functionality in the Microsandbox Python SDK.

This example shows how to:
1. Create a sandbox with volume mappings
2. Write files from the sandbox to the host filesystem
3. Read files from the host filesystem in the sandbox
"""

import asyncio
import os
import tempfile
from pathlib import Path

from microsandbox import PythonSandbox


async def volume_example():
    """Demonstrate volume mapping functionality."""
    
    # Create a temporary directory on the host for sharing files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Created temporary directory: {temp_dir}")
        
        # Create a sample file on the host
        host_file = Path(temp_dir) / "input.txt"
        host_file.write_text("Hello from the host filesystem!\nThis file was created on the host.")
        print(f"Created input file: {host_file}")
        
        # Define volume mapping: host_path:container_path
        volumes = [f"{temp_dir}:/shared"]
        
        print(f"Volume mapping: {volumes[0]}")
        
        # Create and start sandbox with volume mapping
        async with PythonSandbox.create(
            name="volume-demo",
            volumes=volumes,
            memory=512,
            cpus=1.0
        ) as sandbox:
            print("Sandbox started with volume mapping")
            
            # Test 1: Read the host file from within the sandbox
            read_code = """
import os

# List contents of shared directory
print("Contents of /shared directory:")
for item in os.listdir("/shared"):
    print(f"  {item}")

# Read the input file created on the host
try:
    with open("/shared/input.txt", "r") as f:
        content = f.read()
    print("\\nContent of input.txt (from host):")
    print(content)
except FileNotFoundError:
    print("input.txt not found in /shared")
"""
            
            print("\n--- Test 1: Reading host file from sandbox ---")
            execution = await sandbox.run(read_code)
            print("Output:", execution.stdout)
            if execution.stderr:
                print("Errors:", execution.stderr)
            
            # Test 2: Write a file from sandbox to host
            write_code = """
import json
import datetime

# Create some data in the sandbox
data = {
    "message": "Hello from the Python sandbox!",
    "timestamp": datetime.datetime.now().isoformat(),
    "python_version": __import__("sys").version,
    "working_directory": __import__("os").getcwd(),
    "environment_vars": dict(__import__("os").environ)
}

# Write to the shared volume (accessible on host)
with open("/shared/output.json", "w") as f:
    json.dump(data, f, indent=2)

print("Created output.json in shared volume")

# Also create a simple text file
with open("/shared/sandbox_output.txt", "w") as f:
    f.write("This file was created inside the Python sandbox.\\n")
    f.write("It should be accessible on the host filesystem.\\n")
    f.write(f"Generated at: {data['timestamp']}\\n")

print("Created sandbox_output.txt in shared volume")

# List all files in shared directory
import os
print("\\nAll files in /shared:")
for item in os.listdir("/shared"):
    print(f"  {item}")
"""
            
            print("\n--- Test 2: Writing files from sandbox to host ---")
            execution = await sandbox.run(write_code)
            print("Output:", execution.stdout)
            if execution.stderr:
                print("Errors:", execution.stderr)
            
            # Test 3: Verify files were created on the host
            print("\n--- Test 3: Verifying files on host filesystem ---")
            output_json = Path(temp_dir) / "output.json"
            output_txt = Path(temp_dir) / "sandbox_output.txt"
            
            if output_json.exists():
                print(f"✓ output.json created successfully")
                content = output_json.read_text()
                print(f"Content preview: {content[:100]}...")
            else:
                print("✗ output.json not found")
            
            if output_txt.exists():
                print(f"✓ sandbox_output.txt created successfully")
                content = output_txt.read_text()
                print(f"Content: {content}")
            else:
                print("✗ sandbox_output.txt not found")
            
            # Test 4: Demonstrate bidirectional file sharing
            print("\n--- Test 4: Bidirectional file sharing ---")
            
            # Create another file on the host
            host_config = Path(temp_dir) / "config.json"
            config_data = {
                "app_name": "Volume Demo",
                "version": "1.0.0",
                "settings": {
                    "debug": True,
                    "max_items": 100
                }
            }
            host_config.write_text(json.dumps(config_data, indent=2))
            print(f"Created config.json on host")
            
            # Read and modify it in the sandbox
            modify_code = """
import json

# Read config created on host
with open("/shared/config.json", "r") as f:
    config = json.load(f)

print("Original config:")
print(json.dumps(config, indent=2))

# Modify the config
config["settings"]["debug"] = False
config["settings"]["modified_in_sandbox"] = True
config["last_modified"] = "from Python sandbox"

# Write back to shared volume
with open("/shared/config_modified.json", "w") as f:
    json.dump(config, f, indent=2)

print("\\nModified config saved as config_modified.json")
"""
            
            execution = await sandbox.run(modify_code)
            print("Output:", execution.stdout)
            if execution.stderr:
                print("Errors:", execution.stderr)
            
            # Verify the modified file on host
            modified_config = Path(temp_dir) / "config_modified.json"
            if modified_config.exists():
                print(f"✓ Modified config file created on host")
                content = modified_config.read_text()
                print(f"Modified content: {content}")
            else:
                print("✗ Modified config file not found")
        
        print("\n--- Summary ---")
        print("Volume mapping demonstration completed successfully!")
        print("Key points demonstrated:")
        print("1. Files created on host are accessible in sandbox")
        print("2. Files created in sandbox are accessible on host")
        print("3. Bidirectional file sharing works seamlessly")
        print("4. Volume mapping format: 'host_path:container_path'")


if __name__ == "__main__":
    asyncio.run(volume_example())