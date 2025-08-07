"""
MCP Server Package

A lightweight HTTP streamable transport implementation for the Model Context Protocol (MCP)
that integrates with the existing MicrosandboxWrapper.
"""

from .main import main

__version__ = "0.1.0"
__all__ = ["main"]

# MCPServer will be imported once it's implemented in task 3
# from .server import MCPServer