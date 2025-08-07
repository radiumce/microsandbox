#!/usr/bin/env python3
"""
Examples demonstrating the simplified execute_command tool.

The execute_command tool now accepts complete command lines,
making it much more flexible and powerful.
"""

import json
from typing import Dict, Any


def create_command_request(command: str, **kwargs) -> Dict[str, Any]:
    """Create a JSON-RPC request for the execute_command tool."""
    return {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "execute_command",
            "arguments": {
                "command": command,
                "template": kwargs.get("template", "python"),
                "flavor": kwargs.get("flavor", "small"),
                "timeout": kwargs.get("timeout", 30),
                **{k: v for k, v in kwargs.items() if k not in ["template", "flavor", "timeout"]}
            }
        },
        "id": "example"
    }


def demonstrate_command_examples():
    """Demonstrate various command line examples."""
    
    print("=== Simplified execute_command Examples ===\n")
    
    examples = [
        {
            "description": "Simple file listing with pipes",
            "command": "ls -la /tmp | head -10"
        },
        {
            "description": "Text processing pipeline", 
            "command": "echo 'Hello World' | tr '[:lower:]' '[:upper:]' | wc -c"
        },
        {
            "description": "Conditional command execution",
            "command": "python --version && echo 'Python available' || echo 'Python not found'"
        },
        {
            "description": "File operations with redirection",
            "command": "echo 'Test content' > /tmp/test.txt && cat /tmp/test.txt"
        },
        {
            "description": "System information gathering",
            "command": "uname -a && whoami && pwd"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"Example {i}: {example['description']}")
        print(f"Command: {example['command']}")
        
        request = create_command_request(example['command'])
        print(f"JSON-RPC Request:")
        print(json.dumps(request, indent=2))
        print("-" * 60)


if __name__ == "__main__":
    demonstrate_command_examples()
    print("\n✅ The simplified execute_command tool supports all shell features!")