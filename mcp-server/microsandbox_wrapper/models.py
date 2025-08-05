"""
Data models for the microsandbox wrapper.

This module defines all data structures used throughout the wrapper,
including enums, dataclasses, and utility methods for data handling.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SandboxFlavor(Enum):
    """
    Predefined sandbox resource configurations.
    
    Each flavor represents a specific combination of CPU and memory
    resources, allowing for easy resource management without manual
    specification of individual limits.
    """
    SMALL = "small"   # 1 CPU, 1GB RAM - suitable for light tasks
    MEDIUM = "medium" # 2 CPU, 2GB RAM - suitable for moderate workloads  
    LARGE = "large"   # 4 CPU, 4GB RAM - suitable for heavy computations
    
    def get_memory_mb(self) -> int:
        """
        Get the memory limit in megabytes for this flavor.
        
        Returns:
            int: Memory limit in MB
        """
        return {
            self.SMALL: 1024,
            self.MEDIUM: 2048,
            self.LARGE: 4096
        }[self]
        
    def get_cpus(self) -> float:
        """
        Get the CPU limit for this flavor.
        
        Returns:
            float: Number of CPU cores allocated
        """
        return {
            self.SMALL: 1.0,
            self.MEDIUM: 2.0,
            self.LARGE: 4.0
        }[self]


class SessionStatus(Enum):
    """
    Possible states of a sandbox session.
    
    Sessions progress through these states during their lifecycle,
    allowing for proper state tracking and management.
    """
    CREATING = "creating"  # Session is being initialized
    READY = "ready"       # Session is ready for use
    RUNNING = "running"   # Session is currently executing code/commands
    ERROR = "error"       # Session encountered an error
    STOPPED = "stopped"   # Session has been terminated


@dataclass
class ExecutionResult:
    """
    Result of code execution within a sandbox.
    
    Contains all relevant information about the execution,
    including output, timing, and session details.
    """
    session_id: str              # ID of the session that executed the code
    stdout: str                  # Standard output from execution
    stderr: str                  # Standard error from execution  
    success: bool                # Whether execution completed successfully
    execution_time_ms: int       # Execution time in milliseconds
    session_created: bool        # Whether a new session was created for this execution
    template: str                # Template used (python, node, etc.)


@dataclass
class CommandResult:
    """
    Result of command execution within a sandbox.
    
    Similar to ExecutionResult but includes command-specific
    information like exit codes and command arguments.
    """
    session_id: str              # ID of the session that executed the command
    stdout: str                  # Standard output from command
    stderr: str                  # Standard error from command
    exit_code: int               # Command exit code
    success: bool                # Whether command completed successfully (exit_code == 0)
    execution_time_ms: int       # Execution time in milliseconds
    session_created: bool        # Whether a new session was created for this execution
    command: str                 # The command that was executed
    args: List[str]              # Arguments passed to the command


@dataclass
class SessionInfo:
    """
    Information about a sandbox session.
    
    Provides comprehensive details about session state,
    configuration, and lifecycle timing.
    """
    session_id: str              # Unique session identifier
    template: str                # Template used (python, node, etc.)
    flavor: SandboxFlavor        # Resource configuration
    created_at: datetime         # When the session was created
    last_accessed: datetime      # When the session was last used
    status: SessionStatus        # Current session state
    namespace: str               # Kubernetes namespace (if applicable)
    sandbox_name: str            # Name of the underlying sandbox instance


@dataclass
class ResourceStats:
    """
    Current resource usage statistics.
    
    Provides insight into system resource utilization
    and helps with capacity planning and monitoring.
    """
    active_sessions: int                           # Number of currently active sessions
    max_sessions: int                              # Maximum allowed concurrent sessions
    sessions_by_flavor: Dict[SandboxFlavor, int]   # Session count grouped by flavor
    total_memory_mb: int                           # Total memory allocated across all sessions
    total_cpus: float                              # Total CPU cores allocated across all sessions
    uptime_seconds: int                            # How long the wrapper has been running


@dataclass
class VolumeMapping:
    """
    Represents a volume mapping between host and container paths.
    
    Used for sharing files and directories between the host system
    and sandbox containers.
    """
    host_path: str               # Path on the host system
    container_path: str          # Path inside the container
    
    @classmethod
    def from_string(cls, mapping_str: str) -> 'VolumeMapping':
        """
        Parse a volume mapping from a string format.
        
        Expected format: "host_path:container_path"
        
        Args:
            mapping_str: String in the format "host_path:container_path"
            
        Returns:
            VolumeMapping: Parsed volume mapping
            
        Raises:
            ValueError: If the mapping string format is invalid
        """
        parts = mapping_str.split(':', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid volume mapping format: {mapping_str}. Expected 'host_path:container_path'")
        
        host_path, container_path = parts
        if not host_path.strip() or not container_path.strip():
            raise ValueError(f"Invalid volume mapping format: {mapping_str}. Both paths must be non-empty")
            
        return cls(host_path=host_path.strip(), container_path=container_path.strip())
    
    def __str__(self) -> str:
        """
        Convert the volume mapping back to string format.
        
        Returns:
            str: Volume mapping in "host_path:container_path" format
        """
        return f"{self.host_path}:{self.container_path}"