# Error Handling System

This document describes the unified error handling system implemented in the microsandbox wrapper. The system provides standardized error categorization, user-friendly messages, recovery suggestions, and comprehensive logging.

## Overview

The error handling system is built around a base `MicrosandboxWrapperError` class that provides:

- **Standardized error formatting** with error codes and categories
- **Automatic logging** with appropriate severity levels
- **Recovery suggestions** to help users resolve issues
- **Context information** for debugging and troubleshooting
- **Error serialization** for API responses and logging

## Error Categories

All errors are categorized into the following types:

- `CONFIGURATION` - Configuration and environment issues
- `RESOURCE` - Resource limits and allocation problems
- `NETWORK` - Network connectivity and communication issues
- `EXECUTION` - Code and command execution failures
- `SESSION` - Session management problems
- `SYSTEM` - General system and internal errors

## Error Severity Levels

Errors are assigned severity levels that determine logging behavior:

- `LOW` - Informational errors (logged as INFO)
- `MEDIUM` - Warning-level errors (logged as WARNING)
- `HIGH` - Serious errors (logged as ERROR)
- `CRITICAL` - Critical system errors (logged as CRITICAL with stack trace)

## Exception Types

### SandboxCreationError

Raised when sandbox creation fails.

**Common causes:**
- Invalid template specification
- Resource allocation failures
- Network connectivity issues
- Server-side errors during initialization

**Recovery suggestions:**
- Verify microsandbox server is running
- Check template support (python, node)
- Ensure sufficient system resources
- Try smaller sandbox flavor
- Check network connectivity

**Example:**
```python
try:
    sandbox = await create_sandbox("python", "large")
except SandboxCreationError as e:
    print(f"Error: {e.message}")
    print(f"Template: {e.context.get('template')}")
    print(f"Suggestions: {e.recovery_suggestions}")
```

### CodeExecutionError

Raised when code execution fails within a sandbox.

**Error types:**
- `compilation` - Syntax or compilation errors
- `runtime` - Runtime execution errors
- `timeout` - Execution timeout errors

**Recovery suggestions vary by type:**
- **Compilation**: Check syntax, imports, compatibility
- **Runtime**: Check logic, dependencies, data types
- **Timeout**: Optimize code, increase timeout, break into chunks

**Example:**
```python
try:
    result = await session.execute_code("print('hello'")
except CodeExecutionError as e:
    error_type = e.context.get('error_type')
    if error_type == 'compilation':
        print("Fix syntax errors in your code")
    elif error_type == 'timeout':
        print("Code took too long to execute")
```

### CommandExecutionError

Raised when command execution fails within a sandbox.

**Common exit codes:**
- `127` - Command not found
- `126` - Permission denied
- Other non-zero codes indicate command-specific failures

**Recovery suggestions:**
- Verify command exists in sandbox
- Check command permissions
- Review command syntax and arguments
- Try in fresh session

### ResourceLimitError

Raised when resource limits are exceeded.

**Resource types:**
- `sessions` - Maximum concurrent sessions reached
- `memory` - Memory limits exceeded
- `cpu` - CPU limits exceeded

**Recovery suggestions:**
- Wait for existing sessions to complete
- Stop unused sessions
- Use smaller sandbox flavors
- Increase limits if possible

**Example:**
```python
try:
    await resource_manager.validate_resource_request(SandboxFlavor.LARGE)
except ResourceLimitError as e:
    resource_type = e.context.get('resource_type')
    current = e.context.get('current_usage')
    limit = e.context.get('limit')
    print(f"{resource_type} limit exceeded: {current} >= {limit}")
```

### ConfigurationError

Raised when configuration is invalid or incomplete.

**Common issues:**
- Missing required environment variables
- Invalid configuration values
- Malformed volume mapping specifications
- Conflicting configuration options

**Recovery suggestions:**
- Check environment variable values
- Verify configuration format
- Review documentation for valid options

### ConnectionError

Raised when network connectivity issues occur.

**Common causes:**
- Unable to connect to microsandbox server
- Network timeouts
- Authentication failures
- Server unavailable

**Recovery suggestions:**
- Check if server is running
- Verify server URL and accessibility
- Check network connectivity and firewall
- Retry after delay for temporary issues
- Verify authentication credentials

## Helper Functions

### Error Creation Helpers

The system provides helper functions for creating standardized errors:

```python
from microsandbox_wrapper.exceptions import (
    create_sandbox_creation_error,
    create_code_execution_error,
    create_resource_limit_error,
    create_connection_error
)

# Create a sandbox creation error
error = create_sandbox_creation_error(
    template="python",
    flavor="small", 
    original_error=ConnectionError("Network timeout")
)

# Create a code execution error
error = create_code_execution_error(
    error_type="compilation",
    session_id="session-123",
    code_snippet="print('hello'",
    original_error=SyntaxError("Missing parenthesis")
)
```

### SDK Exception Handling

The `handle_sdk_exception` function converts low-level SDK exceptions to appropriate wrapper exceptions:

```python
from microsandbox_wrapper.exceptions import handle_sdk_exception

try:
    # Some SDK operation
    result = await sdk_operation()
except Exception as e:
    # Convert to appropriate wrapper exception
    wrapper_error = handle_sdk_exception(
        operation="sandbox_creation",
        original_error=e,
        template="python",
        flavor="small"
    )
    raise wrapper_error
```

### Enhanced Logging

The `log_error_with_context` function provides enhanced logging with full context:

```python
from microsandbox_wrapper.exceptions import log_error_with_context
import logging

logger = logging.getLogger(__name__)

try:
    # Some operation
    pass
except MicrosandboxWrapperError as e:
    log_error_with_context(logger, e, {
        "operation": "sandbox_creation",
        "user_id": "user-123"
    })
    raise
```

## Error Serialization

All errors can be serialized to dictionaries for API responses:

```python
try:
    # Some operation
    pass
except MicrosandboxWrapperError as e:
    error_dict = e.to_dict()
    # Returns:
    # {
    #     "error_code": "SANDBOX_CREATION_ERROR",
    #     "message": "Failed to create sandbox",
    #     "category": "resource",
    #     "severity": "high",
    #     "recovery_suggestions": [...],
    #     "context": {...},
    #     "original_error": "..."
    # }
```

## User-Friendly Messages

Generate user-friendly error messages with recovery suggestions:

```python
try:
    # Some operation
    pass
except MicrosandboxWrapperError as e:
    friendly_message = e.get_user_friendly_message()
    print(friendly_message)
    # Output:
    # Error: Failed to create sandbox
    # 
    # Suggested actions:
    # 1. Verify that the microsandbox server is running
    # 2. Check if the specified template is supported
    # 3. Ensure sufficient system resources are available
    # ...
```

## Best Practices

### 1. Use Specific Exception Types

Always use the most specific exception type available:

```python
# Good
raise SandboxCreationError("Failed to create sandbox", template="python")

# Less good
raise MicrosandboxWrapperError("Failed to create sandbox")
```

### 2. Provide Context Information

Include relevant context in error creation:

```python
# Good
raise CodeExecutionError(
    message="Code execution failed",
    error_type="compilation",
    session_id=session_id,
    code_snippet=code,
    original_error=e
)

# Less good
raise CodeExecutionError("Code execution failed")
```

### 3. Use Helper Functions

Use the provided helper functions for consistent error creation:

```python
# Good
error = create_sandbox_creation_error(template, flavor, original_error)

# Less good
error = SandboxCreationError(f"Failed to create {template} sandbox")
```

### 4. Log Errors Appropriately

Use the enhanced logging function for consistent log formatting:

```python
# Good
log_error_with_context(logger, error, {"operation": "sandbox_creation"})

# Less good
logger.error(f"Error: {error}")
```

### 5. Handle Original Exceptions

Always preserve the original exception when wrapping:

```python
try:
    # SDK operation
    pass
except Exception as original_error:
    # Good - preserve original error
    wrapper_error = handle_sdk_exception("operation", original_error, **context)
    raise wrapper_error
```

## Testing Error Handling

The system includes comprehensive tests in `test_error_handling.py`:

```bash
cd mcp-server
python test_error_handling.py
```

This tests:
- Basic error creation and properties
- Error helper functions
- Error serialization
- User-friendly message generation
- SDK exception conversion
- Logging functionality

## Integration with Modules

The error handling system is integrated throughout the wrapper:

- **session_manager.py** - Uses enhanced error handling for session operations
- **resource_manager.py** - Uses resource limit errors with context
- **config.py** - Uses configuration errors with helpful suggestions
- **wrapper.py** - Uses error handling for high-level operations

All modules import and use the standardized error handling functions to ensure consistent error reporting and user experience.