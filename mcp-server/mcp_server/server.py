"""
MCP Server using Official SDK

This module implements the MCP server using the official MCP Python SDK,
replacing the custom implementation with a standards-compliant solution.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

from microsandbox_wrapper.wrapper import MicrosandboxWrapper
from microsandbox_wrapper.models import SandboxFlavor
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError,
    ResourceLimitError,
    ConfigurationError,
    SandboxCreationError,
    CodeExecutionError,
    CommandExecutionError,
    SessionNotFoundError,
    ConnectionError as WrapperConnectionError
)

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    """Application context with typed dependencies."""
    wrapper: MicrosandboxWrapper


# Global wrapper instance - shared across all sessions
_global_wrapper: Optional[MicrosandboxWrapper] = None
_wrapper_lock = asyncio.Lock()


async def get_or_create_wrapper() -> MicrosandboxWrapper:
    """Get or create the global wrapper instance."""
    global _global_wrapper
    
    async with _wrapper_lock:
        if _global_wrapper is None:
            logger.info("Creating global MicrosandboxWrapper instance")
            _global_wrapper = MicrosandboxWrapper()
            await _global_wrapper.start()
            logger.info("Global MicrosandboxWrapper started successfully")
        
        return _global_wrapper


async def shutdown_wrapper() -> None:
    """Shutdown the global wrapper instance."""
    global _global_wrapper
    
    async with _wrapper_lock:
        if _global_wrapper is not None:
            logger.info("Shutting down global MicrosandboxWrapper")
            await _global_wrapper.stop()
            logger.info("Global MicrosandboxWrapper shutdown complete")
            _global_wrapper = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with persistent MicrosandboxWrapper."""
    logger.info("Starting MCP Server with official SDK")
    
    # Get or create the global wrapper (will be created only once)
    wrapper = await get_or_create_wrapper()
    
    try:
        yield AppContext(wrapper=wrapper)
    finally:
        # Don't shutdown wrapper here - it should persist across sessions
        # The wrapper will be shut down when the server process terminates
        logger.info("MCP Server session complete")


# Create MCP server with lifespan management
mcp = FastMCP("Microsandbox Server", lifespan=app_lifespan)


# Pydantic models for tool parameters
class ExecuteCodeParams(BaseModel):
    """Parameters for code execution tool."""
    code: str = Field(description="Code to execute")
    template: str = Field(default="python", description="Sandbox template", pattern="^(python|node)$")
    session_id: Optional[str] = Field(None, description="Optional session ID for session reuse")
    flavor: str = Field(default="small", description="Resource configuration", pattern="^(small|medium|large)$")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds", ge=1, le=300)


class ExecuteCommandParams(BaseModel):
    """Parameters for command execution tool."""
    command: str = Field(description="Complete command line to execute (including arguments, pipes, redirections, etc.)")
    template: str = Field(default="python", description="Sandbox template", pattern="^(python|node)$")
    session_id: Optional[str] = Field(None, description="Optional session ID for session reuse")
    flavor: str = Field(default="small", description="Resource configuration", pattern="^(small|medium|large)$")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds", ge=1, le=300)


class GetSessionsParams(BaseModel):
    """Parameters for get sessions tool."""
    session_id: Optional[str] = Field(None, description="Optional specific session ID to query")


class StopSessionParams(BaseModel):
    """Parameters for stop session tool."""
    session_id: str = Field(description="ID of the session to stop")


# Tool implementations using the official SDK
@mcp.tool()
async def execute_code(
    params: ExecuteCodeParams,
    ctx: Context,
) -> str:
    """Execute code in a sandbox with automatic session management."""
    try:
        # Get wrapper from context
        wrapper = ctx.request_context.lifespan_context.wrapper
        
        # Convert flavor string to enum
        flavor = SandboxFlavor(params.flavor)
        
        # Execute code through wrapper
        result = await wrapper.execute_code(
            code=params.code,
            template=params.template,
            session_id=params.session_id,
            flavor=flavor,
            timeout=params.timeout
        )
        
        # Format result for MCP protocol
        output_text = result.stdout
        if result.stderr:
            if output_text:
                output_text += "\n" + result.stderr
            else:
                output_text = result.stderr
        
        # Add metadata information
        metadata = (
            f"\n[Session: {result.session_id}] "
            f"[Time: {result.execution_time_ms}ms] "
            f"[Template: {result.template}] "
            f"[Success: {result.success}]"
        )
        
        return output_text + metadata
        
    except Exception as e:
        logger.error(f"Code execution failed: {e}", exc_info=True)
        raise


@mcp.tool()
async def execute_command(
    params: ExecuteCommandParams,
    ctx: Context,
) -> str:
    """Execute a command line in a sandbox with automatic session management."""
    try:
        # Get wrapper from context
        wrapper = ctx.request_context.lifespan_context.wrapper
        
        # Convert flavor string to enum
        flavor = SandboxFlavor(params.flavor)
        
        # Execute command line through shell using wrapper
        result = await wrapper.execute_command(
            command="sh",
            args=["-c", params.command],
            template=params.template,
            session_id=params.session_id,
            flavor=flavor,
            timeout=params.timeout
        )
        
        # Format result for MCP protocol
        output_text = result.stdout
        if result.stderr:
            if output_text:
                output_text += "\n" + result.stderr
            else:
                output_text = result.stderr
        
        # Add metadata information
        metadata = (
            f"\n[Session: {result.session_id}] "
            f"[Command: {params.command}] "
            f"[Exit Code: {result.exit_code}] "
            f"[Time: {result.execution_time_ms}ms] "
            f"[Success: {result.success}]"
        )
        
        return output_text + metadata
        
    except Exception as e:
        logger.error(f"Command execution failed: {e}", exc_info=True)
        raise


@mcp.tool()
async def get_sessions(
    params: GetSessionsParams,
    ctx: Context,
) -> str:
    """Get information about active sandbox sessions."""
    try:
        # Get wrapper from context
        wrapper = ctx.request_context.lifespan_context.wrapper
        
        # Get sessions through wrapper
        sessions = await wrapper.get_sessions(params.session_id)
        
        # Format sessions information
        if not sessions:
            return "No active sessions found."
        
        session_info = []
        for session in sessions:
            info = (
                f"Session ID: {session.session_id}\n"
                f"  Template: {session.template}\n"
                f"  Flavor: {session.flavor.value}\n"
                f"  Status: {session.status.value}\n"
                f"  Created: {session.created_at.isoformat()}\n"
                f"  Last Accessed: {session.last_accessed.isoformat()}\n"
                f"  Namespace: {session.namespace}\n"
                f"  Sandbox Name: {session.sandbox_name}"
            )
            session_info.append(info)
        
        return "\n\n".join(session_info)
        
    except Exception as e:
        logger.error(f"Get sessions failed: {e}", exc_info=True)
        raise


@mcp.tool()
async def stop_session(
    params: StopSessionParams,
    ctx: Context,
) -> str:
    """Stop a specific sandbox session and clean up its resources."""
    try:
        # Get wrapper from context
        wrapper = ctx.request_context.lifespan_context.wrapper
        
        # Stop session through wrapper
        success = await wrapper.stop_session(params.session_id)
        
        if success:
            return f"Session {params.session_id} stopped successfully"
        else:
            return f"Session {params.session_id} not found or already stopped"
        
    except Exception as e:
        logger.error(f"Stop session failed: {e}", exc_info=True)
        raise


@mcp.tool()
async def get_volume_mappings(ctx: Context) -> str:
    """Get configured volume mappings between host and container paths."""
    try:
        # Get wrapper from context
        wrapper = ctx.request_context.lifespan_context.wrapper
        
        # Get volume mappings through wrapper
        mappings = await wrapper.get_volume_mappings()
        
        if not mappings:
            return "No volume mappings configured."
        
        mapping_info = []
        for mapping in mappings:
            info = f"Host: {mapping.host_path} -> Container: {mapping.container_path}"
            mapping_info.append(info)
        
        return "\n".join(mapping_info)
        
    except Exception as e:
        logger.error(f"Get volume mappings failed: {e}", exc_info=True)
        raise


def create_server_app() -> FastMCP:
    """Create and return the configured MCP server."""
    return mcp
