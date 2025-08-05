# MicrosandboxWrapper API Documentation

This document provides comprehensive API documentation for the MicrosandboxWrapper, including all classes, methods, data models, and configuration options.

## Table of Contents

- [Overview](#overview)
- [Main Classes](#main-classes)
- [Data Models](#data-models)
- [Configuration](#configuration)
- [Exceptions](#exceptions)
- [Usage Patterns](#usage-patterns)
- [Examples](#examples)

## Overview

The MicrosandboxWrapper provides a high-level, async-first interface for interacting with microsandbox instances. It abstracts away the complexity of session management, resource allocation, and error handling while providing powerful features like automatic cleanup, resource monitoring, and concurrent execution support.

### Key Features

- **Automatic Session Management**: Sessions are created, reused, and cleaned up automatically
- **Resource Management**: Built-in resource limits, monitoring, and orphan cleanup
- **Async/Await Support**: All operations are async-first for optimal performance
- **Multiple Templates**: Support for Python, Node.js, and other sandbox templates
- **Volume Mapping**: Share files between host and sandbox environments
- **Error Handling**: Comprehensive error handling with detailed error information
- **Background Tasks**: Automatic cleanup and maintenance tasks

## Main Classes

### MicrosandboxWrapper

The primary interface for all microsandbox operations.

#### Constructor

```python
def __init__(
    self,
    server_url: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[WrapperConfig] = None
)
```

**Parameters:**
- `server_url` (str, optional): Microsandbox server URL. Overrides config/environment.
- `api_key` (str, optional): API key for authentication. Overrides config/environment.
- `config` (WrapperConfig, optional): Configuration object. If not provided, loads from environment.

**Raises:**
- `ConfigurationError`: If configuration is invalid.

#### Lifecycle Methods

##### `async start() -> None`

Start the wrapper and all background services. Must be called before using other methods.

**Raises:**
- `MicrosandboxWrapperError`: If startup fails.

##### `async stop(timeout_seconds: float = 30.0) -> None`

Stop the wrapper and clean up all resources gracefully.

**Parameters:**
- `timeout_seconds` (float): Maximum time to wait for graceful shutdown.

**Raises:**
- `MicrosandboxWrapperError`: If shutdown fails.

#### Core Execution Methods

##### `async execute_code(...) -> ExecutionResult`

Execute code in a sandbox session.

```python
async def execute_code(
    self,
    code: str,
    template: str = "python",
    session_id: Optional[str] = None,
    flavor: SandboxFlavor = SandboxFlavor.SMALL,
    timeout: Optional[int] = None
) -> ExecutionResult
```

**Parameters:**
- `code` (str): Code to execute.
- `template` (str): Sandbox template ("python", "node", etc.). Default: "python".
- `session_id` (str, optional): Session ID for reuse. If None, creates new session.
- `flavor` (SandboxFlavor): Resource configuration. Default: SMALL.
- `timeout` (int, optional): Execution timeout in seconds. Uses config default if None.

**Returns:**
- `ExecutionResult`: Result object with output, timing, and metadata.

**Raises:**
- `ResourceLimitError`: If resource limits would be exceeded.
- `SandboxCreationError`: If sandbox creation fails.
- `CodeExecutionError`: If code execution fails.
- `ConnectionError`: If server communication fails.

##### `async execute_command(...) -> CommandResult`

Execute a command in a sandbox session.

```python
async def execute_command(
    self,
    command: str,
    args: Optional[List[str]] = None,
    template: str = "python",
    session_id: Optional[str] = None,
    flavor: SandboxFlavor = SandboxFlavor.SMALL,
    timeout: Optional[int] = None
) -> CommandResult
```

**Parameters:**
- `command` (str): Command to execute.
- `args` (List[str], optional): Command arguments.
- `template` (str): Sandbox template. Default: "python".
- `session_id` (str, optional): Session ID for reuse.
- `flavor` (SandboxFlavor): Resource configuration. Default: SMALL.
- `timeout` (int, optional): Execution timeout in seconds.

**Returns:**
- `CommandResult`: Result object with output, exit code, and metadata.

**Raises:**
- Same exceptions as `execute_code`.

#### Session Management Methods

##### `async get_sessions(session_id: Optional[str] = None) -> List[SessionInfo]`

Get information about active sessions.

**Parameters:**
- `session_id` (str, optional): Specific session ID to query. If None, returns all sessions.

**Returns:**
- `List[SessionInfo]`: List of session information objects.

##### `async stop_session(session_id: str) -> bool`

Stop a specific session and clean up its resources.

**Parameters:**
- `session_id` (str): ID of the session to stop.

**Returns:**
- `bool`: True if session was found and stopped, False if not found.

#### Resource Management Methods

##### `async get_resource_stats() -> ResourceStats`

Get current resource usage statistics.

**Returns:**
- `ResourceStats`: Current resource utilization information.

##### `async get_volume_mappings() -> List[VolumeMapping]`

Get configured volume mappings.

**Returns:**
- `List[VolumeMapping]`: List of configured volume mappings.

##### `async cleanup_orphan_sandboxes() -> int`

Manually trigger cleanup of orphaned sandbox instances.

**Returns:**
- `int`: Number of orphan sandboxes that were cleaned up.

#### Background Task Management Methods

##### `async pause_background_tasks() -> dict`

Pause all background tasks temporarily.

**Returns:**
- `dict`: Information about which tasks were paused.

##### `async resume_background_tasks() -> dict`

Resume all background tasks after they were paused.

**Returns:**
- `dict`: Information about which tasks were resumed.

##### `async get_background_task_status() -> dict`

Get comprehensive status information about all background tasks.

**Returns:**
- `dict`: Background task status information.

#### Utility Methods

##### `get_config() -> WrapperConfig`

Get the current wrapper configuration.

**Returns:**
- `WrapperConfig`: Current configuration object.

##### `is_started() -> bool`

Check if the wrapper has been started.

**Returns:**
- `bool`: True if wrapper is started and ready for use.

#### Context Manager Support

The wrapper supports async context manager protocol:

```python
async with MicrosandboxWrapper() as wrapper:
    # Automatically calls start()
    result = await wrapper.execute_code("print('Hello')")
    # Automatically calls stop() on exit
```

## Data Models

### SandboxFlavor

Enumeration defining sandbox resource configurations.

```python
class SandboxFlavor(Enum):
    SMALL = "small"   # 1 CPU, 1GB RAM
    MEDIUM = "medium" # 2 CPU, 2GB RAM
    LARGE = "large"   # 4 CPU, 4GB RAM
```

**Methods:**
- `get_memory_mb() -> int`: Get memory limit in MB.
- `get_cpus() -> float`: Get CPU limit.

### ExecutionResult

Result of code execution.

```python
@dataclass
class ExecutionResult:
    session_id: str              # Session ID used for execution
    stdout: str                  # Standard output
    stderr: str                  # Standard error
    success: bool                # Whether execution succeeded
    execution_time_ms: int       # Execution time in milliseconds
    session_created: bool        # Whether a new session was created
    template: str                # Template used for execution
```

### CommandResult

Result of command execution.

```python
@dataclass
class CommandResult:
    session_id: str              # Session ID used for execution
    stdout: str                  # Standard output
    stderr: str                  # Standard error
    exit_code: int               # Command exit code
    success: bool                # Whether command succeeded (exit_code == 0)
    execution_time_ms: int       # Execution time in milliseconds
    session_created: bool        # Whether a new session was created
    command: str                 # Command that was executed
    args: List[str]              # Command arguments
```

### SessionInfo

Information about a sandbox session.

```python
@dataclass
class SessionInfo:
    session_id: str              # Unique session identifier
    template: str                # Sandbox template (python, node, etc.)
    flavor: SandboxFlavor        # Resource configuration
    created_at: datetime         # Session creation timestamp
    last_accessed: datetime      # Last access timestamp
    status: SessionStatus        # Current session status
    namespace: str               # Kubernetes namespace
    sandbox_name: str            # Sandbox instance name
```

### SessionStatus

Enumeration of session states.

```python
class SessionStatus(Enum):
    CREATING = "creating"        # Session is being created
    READY = "ready"             # Session is ready for use
    RUNNING = "running"         # Session is executing code/commands
    ERROR = "error"             # Session encountered an error
    STOPPED = "stopped"         # Session has been stopped
```

### ResourceStats

Resource usage statistics.

```python
@dataclass
class ResourceStats:
    active_sessions: int                    # Number of active sessions
    max_sessions: int                       # Maximum allowed sessions
    sessions_by_flavor: Dict[SandboxFlavor, int]  # Session count by flavor
    total_memory_mb: int                    # Total memory usage in MB
    total_cpus: float                       # Total CPU usage
    uptime_seconds: int                     # Wrapper uptime in seconds
```

### VolumeMapping

Volume mapping configuration.

```python
@dataclass
class VolumeMapping:
    host_path: str               # Path on host system
    container_path: str          # Path in sandbox container
    
    @classmethod
    def from_string(cls, mapping_str: str) -> 'VolumeMapping':
        """Parse volume mapping from string format 'host_path:container_path'"""
```

## Configuration

### WrapperConfig

Main configuration class for the wrapper.

```python
@dataclass
class WrapperConfig:
    # Server configuration
    server_url: str = "http://127.0.0.1:5555"
    api_key: Optional[str] = None
    
    # Session configuration
    session_timeout: int = 1800              # Session timeout in seconds (30 min)
    max_concurrent_sessions: int = 10        # Maximum concurrent sessions
    cleanup_interval: int = 60               # Cleanup interval in seconds (1 min)
    
    # Sandbox configuration
    default_flavor: SandboxFlavor = SandboxFlavor.SMALL
    sandbox_start_timeout: float = 180.0     # Sandbox start timeout in seconds
    default_execution_timeout: int = 300     # Default execution timeout (5 min)
    
    # Resource configuration
    max_total_memory_mb: Optional[int] = None  # Maximum total memory usage
    shared_volume_mappings: List[str] = field(default_factory=list)
    
    # Orphan cleanup configuration
    orphan_cleanup_interval: int = 600       # Orphan cleanup interval (10 min)
```

#### Configuration Methods

##### `@classmethod from_env(cls) -> 'WrapperConfig'`

Create configuration from environment variables.

**Environment Variables:**
- `MSB_SERVER_URL`: Server URL
- `MSB_API_KEY`: API key
- `MSB_SESSION_TIMEOUT`: Session timeout in seconds
- `MSB_MAX_SESSIONS`: Maximum concurrent sessions
- `MSB_CLEANUP_INTERVAL`: Cleanup interval in seconds
- `MSB_DEFAULT_FLAVOR`: Default sandbox flavor (small/medium/large)
- `MSB_SANDBOX_START_TIMEOUT`: Sandbox start timeout in seconds
- `MSB_EXECUTION_TIMEOUT`: Default execution timeout in seconds
- `MSB_MAX_TOTAL_MEMORY_MB`: Maximum total memory in MB
- `MSB_SHARED_VOLUME_PATH`: Volume mappings (JSON array or comma-separated)
- `MSB_ORPHAN_CLEANUP_INTERVAL`: Orphan cleanup interval in seconds

##### `get_parsed_volume_mappings(self) -> List[VolumeMapping]`

Get parsed volume mappings as VolumeMapping objects.

**Returns:**
- `List[VolumeMapping]`: Parsed volume mappings.

## Exceptions

### Exception Hierarchy

```
MicrosandboxWrapperError (base)
├── ConfigurationError
├── SandboxCreationError
├── CodeExecutionError
├── CommandExecutionError
├── ResourceLimitError
├── SessionNotFoundError
└── ConnectionError
```

### Exception Details

#### `MicrosandboxWrapperError`

Base exception for all wrapper-related errors.

#### `ConfigurationError`

Raised when configuration is invalid or missing.

#### `SandboxCreationError`

Raised when sandbox creation fails.

#### `CodeExecutionError`

Raised when code execution fails.

#### `CommandExecutionError`

Raised when command execution fails.

#### `ResourceLimitError`

Raised when resource limits are exceeded.

#### `SessionNotFoundError`

Raised when a requested session is not found.

#### `ConnectionError`

Raised when server communication fails.

## Usage Patterns

### Basic Usage Pattern

```python
from microsandbox_wrapper import MicrosandboxWrapper, SandboxFlavor

async def basic_usage():
    async with MicrosandboxWrapper() as wrapper:
        result = await wrapper.execute_code(
            code="print('Hello, World!')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        print(result.stdout)
```

### Session Reuse Pattern

```python
async def session_reuse():
    async with MicrosandboxWrapper() as wrapper:
        # Create session with initial state
        result1 = await wrapper.execute_code(
            code="x = 42",
            template="python"
        )
        
        # Reuse session to access state
        result2 = await wrapper.execute_code(
            code="print(f'x = {x}')",
            template="python",
            session_id=result1.session_id
        )
```

### Configuration Pattern

```python
from microsandbox_wrapper import WrapperConfig

async def custom_config():
    config = WrapperConfig(
        server_url="http://localhost:5555",
        max_concurrent_sessions=5,
        default_flavor=SandboxFlavor.MEDIUM,
        shared_volume_mappings=[
            "/host/data:/sandbox/data"
        ]
    )
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        # Use wrapper with custom configuration
        pass
```

### Error Handling Pattern

```python
from microsandbox_wrapper.exceptions import (
    MicrosandboxWrapperError,
    ResourceLimitError,
    CodeExecutionError
)

async def error_handling():
    async with MicrosandboxWrapper() as wrapper:
        try:
            result = await wrapper.execute_code(
                code="potentially_failing_code()",
                template="python"
            )
        except ResourceLimitError as e:
            print(f"Resource limit exceeded: {e}")
        except CodeExecutionError as e:
            print(f"Code execution failed: {e}")
        except MicrosandboxWrapperError as e:
            print(f"General wrapper error: {e}")
```

### Concurrent Execution Pattern

```python
import asyncio

async def concurrent_execution():
    async with MicrosandboxWrapper() as wrapper:
        tasks = [
            wrapper.execute_code("task_1_code", template="python"),
            wrapper.execute_code("task_2_code", template="python"),
            wrapper.execute_code("task_3_code", template="node"),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Task {i+1} failed: {result}")
            else:
                print(f"Task {i+1} output: {result.stdout}")
```

### Resource Monitoring Pattern

```python
async def resource_monitoring():
    async with MicrosandboxWrapper() as wrapper:
        # Monitor resources before execution
        stats = await wrapper.get_resource_stats()
        print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        
        # Execute code
        result = await wrapper.execute_code("print('Hello')", template="python")
        
        # Monitor resources after execution
        stats = await wrapper.get_resource_stats()
        print(f"Active sessions: {stats.active_sessions}/{stats.max_sessions}")
        
        # List active sessions
        sessions = await wrapper.get_sessions()
        for session in sessions:
            print(f"Session: {session.session_id} ({session.template})")
```

## Examples

### Complete Example: File Processing Pipeline

```python
import asyncio
from pathlib import Path
from microsandbox_wrapper import MicrosandboxWrapper, WrapperConfig, SandboxFlavor

async def file_processing_pipeline():
    """Complete example showing file processing with volume mapping."""
    
    # Setup volume mapping
    config = WrapperConfig.from_env()
    config.shared_volume_mappings = [
        "/host/input:/sandbox/input",
        "/host/output:/sandbox/output"
    ]
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        # Step 1: Data validation
        validation_code = """
import json
import os

input_file = '/sandbox/input/data.json'
if os.path.exists(input_file):
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    valid_records = [r for r in data if 'id' in r and 'value' in r]
    print(f'Validated {len(valid_records)} out of {len(data)} records')
    
    # Store validation results
    validation_results = {
        'total_records': len(data),
        'valid_records': len(valid_records),
        'data': valid_records
    }
else:
    print('Input file not found')
    validation_results = {'error': 'Input file not found'}
"""
        
        validation_result = await wrapper.execute_code(
            code=validation_code,
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        
        if not validation_result.success:
            print(f"Validation failed: {validation_result.stderr}")
            return
        
        print(f"Validation output: {validation_result.stdout}")
        
        # Step 2: Data processing (reuse session)
        processing_code = """
# Process the validated data
if 'error' not in validation_results:
    processed_data = []
    for record in validation_results['data']:
        processed_record = {
            'id': record['id'],
            'value': record['value'],
            'processed_value': record['value'] * 2,
            'category': 'high' if record['value'] > 50 else 'low'
        }
        processed_data.append(processed_record)
    
    # Save processed data
    with open('/sandbox/output/processed_data.json', 'w') as f:
        json.dump(processed_data, f, indent=2)
    
    print(f'Processed {len(processed_data)} records')
    
    # Generate summary
    summary = {
        'total_processed': len(processed_data),
        'high_value_count': len([r for r in processed_data if r['category'] == 'high']),
        'low_value_count': len([r for r in processed_data if r['category'] == 'low']),
        'average_value': sum(r['value'] for r in processed_data) / len(processed_data)
    }
    
    with open('/sandbox/output/summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f'Summary: {summary}')
else:
    print('Skipping processing due to validation error')
"""
        
        processing_result = await wrapper.execute_code(
            code=processing_code,
            template="python",
            session_id=validation_result.session_id,  # Reuse session
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"Processing output: {processing_result.stdout}")
        
        # Step 3: Generate report using Node.js
        report_code = """
const fs = require('fs');
const path = require('path');

try {
    // Read processed data
    const processedData = JSON.parse(
        fs.readFileSync('/sandbox/output/processed_data.json', 'utf8')
    );
    
    const summary = JSON.parse(
        fs.readFileSync('/sandbox/output/summary.json', 'utf8')
    );
    
    // Generate HTML report
    const html = `
<!DOCTYPE html>
<html>
<head>
    <title>Data Processing Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .summary { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Data Processing Report</h1>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>Total Records Processed: ${summary.total_processed}</p>
        <p>High Value Records: ${summary.high_value_count}</p>
        <p>Low Value Records: ${summary.low_value_count}</p>
        <p>Average Value: ${summary.average_value.toFixed(2)}</p>
    </div>
    
    <h2>Processed Data</h2>
    <table>
        <tr>
            <th>ID</th>
            <th>Original Value</th>
            <th>Processed Value</th>
            <th>Category</th>
        </tr>
        ${processedData.map(record => `
        <tr>
            <td>${record.id}</td>
            <td>${record.value}</td>
            <td>${record.processed_value}</td>
            <td>${record.category}</td>
        </tr>
        `).join('')}
    </table>
</body>
</html>
    `;
    
    fs.writeFileSync('/sandbox/output/report.html', html);
    console.log('HTML report generated successfully');
    
} catch (error) {
    console.error('Error generating report:', error.message);
}
"""
        
        report_result = await wrapper.execute_code(
            code=report_code,
            template="node",
            flavor=SandboxFlavor.SMALL
        )
        
        print(f"Report generation output: {report_result.stdout}")
        
        # Get final resource stats
        stats = await wrapper.get_resource_stats()
        print(f"\nFinal resource stats:")
        print(f"  Active sessions: {stats.active_sessions}")
        print(f"  Total memory: {stats.total_memory_mb} MB")

if __name__ == "__main__":
    asyncio.run(file_processing_pipeline())
```

This comprehensive API documentation covers all aspects of the MicrosandboxWrapper. For more examples and usage patterns, see the examples directory and integration tests.