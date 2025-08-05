"""
Exception definitions for the microsandbox wrapper.

This module defines all custom exception types used throughout the wrapper,
providing clear error categorization, helpful error messages, and recovery suggestions.
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels for categorizing exceptions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better error classification."""
    CONFIGURATION = "configuration"
    RESOURCE = "resource"
    NETWORK = "network"
    EXECUTION = "execution"
    SESSION = "session"
    SYSTEM = "system"


class MicrosandboxWrapperError(Exception):
    """
    Base exception class for all microsandbox wrapper errors.
    
    All other wrapper exceptions inherit from this class, allowing
    for easy catching of any wrapper-related errors.
    
    This base class provides standardized error formatting, logging,
    and recovery suggestion functionality.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        category: Optional[ErrorCategory] = None,
        severity: Optional[ErrorSeverity] = None,
        recovery_suggestions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        """
        Initialize the wrapper error.
        
        Args:
            message: Human-readable error message
            error_code: Unique error code for programmatic handling
            category: Error category for classification
            severity: Error severity level
            recovery_suggestions: List of suggested recovery actions
            context: Additional context information
            original_error: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.category = category or ErrorCategory.SYSTEM
        self.severity = severity or ErrorSeverity.MEDIUM
        self.recovery_suggestions = recovery_suggestions or []
        self.context = context or {}
        self.original_error = original_error
        
        # Log the error when created
        self._log_error()
    
    def _generate_error_code(self) -> str:
        """Generate a default error code based on the exception class name."""
        class_name = self.__class__.__name__
        # Convert CamelCase to UPPER_SNAKE_CASE
        import re
        error_code = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', class_name)
        error_code = re.sub('([a-z0-9])([A-Z])', r'\1_\2', error_code).upper()
        return error_code
    
    def _log_error(self):
        """Log the error with appropriate level based on severity."""
        logger = logging.getLogger(__name__)
        
        log_message = f"[{self.error_code}] {self.message}"
        if self.context:
            log_message += f" | Context: {self.context}"
        if self.original_error:
            log_message += f" | Original: {str(self.original_error)}"
        
        if self.severity == ErrorSeverity.CRITICAL:
            logger.critical(log_message, exc_info=self.original_error)
        elif self.severity == ErrorSeverity.HIGH:
            logger.error(log_message, exc_info=self.original_error)
        elif self.severity == ErrorSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "recovery_suggestions": self.recovery_suggestions,
            "context": self.context,
            "original_error": str(self.original_error) if self.original_error else None
        }
    
    def get_user_friendly_message(self) -> str:
        """Get a user-friendly error message with recovery suggestions."""
        message = f"Error: {self.message}"
        
        if self.recovery_suggestions:
            message += "\n\nSuggested actions:"
            for i, suggestion in enumerate(self.recovery_suggestions, 1):
                message += f"\n{i}. {suggestion}"
        
        return message


class SandboxCreationError(MicrosandboxWrapperError):
    """
    Raised when sandbox creation fails.
    
    This can occur due to:
    - Invalid template specification
    - Resource allocation failures
    - Network connectivity issues
    - Server-side errors during sandbox initialization
    """
    
    def __init__(
        self,
        message: str,
        template: Optional[str] = None,
        flavor: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if template:
            context["template"] = template
        if flavor:
            context["flavor"] = flavor
        
        recovery_suggestions = [
            "Verify that the microsandbox server is running and accessible",
            "Check if the specified template is supported (python, node)",
            "Ensure sufficient system resources are available",
            "Try using a smaller sandbox flavor (small instead of large)",
            "Check network connectivity to the microsandbox server"
        ]
        
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class CodeExecutionError(MicrosandboxWrapperError):
    """
    Raised when code execution fails within a sandbox.
    
    This covers:
    - Compilation errors
    - Runtime errors
    - Execution timeouts
    - Sandbox communication failures during execution
    """
    
    def __init__(
        self,
        message: str,
        error_type: Optional[str] = None,
        session_id: Optional[str] = None,
        code_snippet: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if error_type:
            context["error_type"] = error_type
        if session_id:
            context["session_id"] = session_id
        if code_snippet:
            # Truncate code snippet for logging
            context["code_snippet"] = code_snippet[:200] + "..." if len(code_snippet) > 200 else code_snippet
        
        recovery_suggestions = []
        
        # Provide specific suggestions based on error type
        if error_type == "compilation":
            recovery_suggestions.extend([
                "Check your code syntax for errors",
                "Ensure all required imports are included",
                "Verify that the code is compatible with the sandbox environment"
            ])
        elif error_type == "runtime":
            recovery_suggestions.extend([
                "Check for runtime errors in your code logic",
                "Ensure all required dependencies are available",
                "Verify input data and variable types"
            ])
        elif error_type == "timeout":
            recovery_suggestions.extend([
                "Optimize your code to run faster",
                "Increase the execution timeout if needed",
                "Break down complex operations into smaller chunks"
            ])
        else:
            recovery_suggestions.extend([
                "Review the error details and fix any code issues",
                "Try running the code in a fresh session",
                "Check if the sandbox environment supports your code requirements"
            ])
        
        super().__init__(
            message=message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.MEDIUM,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class CommandExecutionError(MicrosandboxWrapperError):
    """
    Raised when command execution fails within a sandbox.
    
    This covers:
    - Command not found errors
    - Permission errors
    - Command timeouts
    - Non-zero exit codes (when configured to raise on failure)
    """
    
    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        exit_code: Optional[int] = None,
        session_id: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if command:
            context["command"] = command
        if exit_code is not None:
            context["exit_code"] = exit_code
        if session_id:
            context["session_id"] = session_id
        
        recovery_suggestions = []
        
        # Provide specific suggestions based on exit code or error type
        if exit_code == 127:  # Command not found
            recovery_suggestions.extend([
                "Verify that the command exists in the sandbox environment",
                "Check if the command is installed or available in PATH",
                "Try using the full path to the command"
            ])
        elif exit_code == 126:  # Permission denied
            recovery_suggestions.extend([
                "Check if the command has execute permissions",
                "Verify that the command is not restricted in the sandbox"
            ])
        elif "timeout" in message.lower():
            recovery_suggestions.extend([
                "Increase the command timeout if needed",
                "Optimize the command to run faster",
                "Check if the command is hanging or waiting for input"
            ])
        else:
            recovery_suggestions.extend([
                "Check the command syntax and arguments",
                "Review the command output for specific error details",
                "Try running the command in a fresh session"
            ])
        
        super().__init__(
            message=message,
            category=ErrorCategory.EXECUTION,
            severity=ErrorSeverity.MEDIUM,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class ResourceLimitError(MicrosandboxWrapperError):
    """
    Raised when resource limits are exceeded.
    
    This includes:
    - Maximum concurrent sessions reached
    - Memory limits exceeded
    - CPU limits exceeded
    - Storage limits exceeded
    """
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        current_usage: Optional[Any] = None,
        limit: Optional[Any] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if resource_type:
            context["resource_type"] = resource_type
        if current_usage is not None:
            context["current_usage"] = current_usage
        if limit is not None:
            context["limit"] = limit
        
        recovery_suggestions = []
        
        # Provide specific suggestions based on resource type
        if resource_type == "sessions":
            recovery_suggestions.extend([
                "Wait for existing sessions to complete or timeout",
                "Manually stop unused sessions to free up resources",
                "Consider increasing the maximum concurrent sessions limit",
                "Optimize your workflow to use fewer concurrent sessions"
            ])
        elif resource_type == "memory":
            recovery_suggestions.extend([
                "Use a smaller sandbox flavor (small instead of large)",
                "Optimize your code to use less memory",
                "Stop unused sessions to free up memory",
                "Consider increasing the memory limit if possible"
            ])
        elif resource_type == "cpu":
            recovery_suggestions.extend([
                "Use a smaller sandbox flavor to reduce CPU requirements",
                "Optimize your code to be more CPU efficient",
                "Wait for other processes to complete"
            ])
        else:
            recovery_suggestions.extend([
                "Check current resource usage and clean up if possible",
                "Consider using smaller resource requirements",
                "Wait for resources to become available"
            ])
        
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.HIGH,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class SessionNotFoundError(MicrosandboxWrapperError):
    """
    Raised when attempting to access a non-existent session.
    
    Note: In most cases, the wrapper will automatically create
    new sessions instead of raising this error. This exception
    is primarily used for explicit session management operations.
    """
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if session_id:
            context["session_id"] = session_id
        
        recovery_suggestions = [
            "Verify the session ID is correct",
            "Check if the session has expired or been cleaned up",
            "Create a new session instead of trying to access the missing one",
            "List available sessions to see what's currently active"
        ]
        
        super().__init__(
            message=message,
            category=ErrorCategory.SESSION,
            severity=ErrorSeverity.LOW,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class ConfigurationError(MicrosandboxWrapperError):
    """
    Raised when configuration is invalid or incomplete.
    
    This covers:
    - Missing required environment variables
    - Invalid configuration values
    - Conflicting configuration options
    - Malformed volume mapping specifications
    """
    
    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if config_key:
            context["config_key"] = config_key
        if config_value is not None:
            context["config_value"] = str(config_value)
        
        recovery_suggestions = []
        
        # Provide specific suggestions based on configuration issue
        if config_key:
            if "URL" in config_key.upper():
                recovery_suggestions.extend([
                    f"Set the {config_key} environment variable to a valid URL",
                    "Ensure the URL includes the protocol (http:// or https://)",
                    "Verify that the server is accessible at the specified URL"
                ])
            elif "PATH" in config_key.upper():
                recovery_suggestions.extend([
                    f"Set the {config_key} environment variable to a valid path",
                    "Ensure the path exists and is accessible",
                    "Check file/directory permissions"
                ])
            elif "TIMEOUT" in config_key.upper():
                recovery_suggestions.extend([
                    f"Set the {config_key} environment variable to a positive number",
                    "Use reasonable timeout values (e.g., 30-300 seconds)"
                ])
            else:
                recovery_suggestions.extend([
                    f"Check the {config_key} configuration value",
                    "Refer to the documentation for valid configuration options"
                ])
        else:
            recovery_suggestions.extend([
                "Review all configuration settings",
                "Check environment variables for typos or invalid values",
                "Refer to the configuration documentation"
            ])
        
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


class ConnectionError(MicrosandboxWrapperError):
    """
    Raised when network connectivity issues occur.
    
    This includes:
    - Unable to connect to microsandbox server
    - Network timeouts
    - Authentication failures
    - Server unavailable errors
    """
    
    def __init__(
        self,
        message: str,
        server_url: Optional[str] = None,
        retry_count: Optional[int] = None,
        original_error: Optional[Exception] = None
    ):
        context = {}
        if server_url:
            context["server_url"] = server_url
        if retry_count is not None:
            context["retry_count"] = retry_count
        
        recovery_suggestions = [
            "Check if the microsandbox server is running",
            "Verify the server URL is correct and accessible",
            "Check network connectivity and firewall settings",
            "Try again after a short delay (network issues may be temporary)",
            "Verify authentication credentials if required"
        ]
        
        if "timeout" in message.lower():
            recovery_suggestions.extend([
                "Increase the connection timeout if the server is slow to respond",
                "Check if the server is under heavy load"
            ])
        
        if "authentication" in message.lower() or "auth" in message.lower():
            recovery_suggestions.extend([
                "Check if the API key is set correctly",
                "Verify that the API key is valid and not expired"
            ])
        
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            recovery_suggestions=recovery_suggestions,
            context=context,
            original_error=original_error
        )


# Utility functions for error handling

def create_sandbox_creation_error(
    template: str,
    flavor: str,
    original_error: Exception
) -> SandboxCreationError:
    """
    Create a standardized SandboxCreationError with appropriate context.
    
    Args:
        template: The sandbox template that failed to create
        flavor: The sandbox flavor that was requested
        original_error: The original exception that caused the failure
        
    Returns:
        SandboxCreationError: Configured error with context and suggestions
    """
    if "connection" in str(original_error).lower():
        message = f"Failed to create {template} sandbox ({flavor}): Unable to connect to microsandbox server"
    elif "timeout" in str(original_error).lower():
        message = f"Failed to create {template} sandbox ({flavor}): Server timeout during creation"
    elif "resource" in str(original_error).lower():
        message = f"Failed to create {template} sandbox ({flavor}): Insufficient resources available"
    else:
        message = f"Failed to create {template} sandbox ({flavor}): {str(original_error)}"
    
    return SandboxCreationError(
        message=message,
        template=template,
        flavor=flavor,
        original_error=original_error
    )


def create_code_execution_error(
    error_type: str,
    session_id: str,
    code_snippet: str,
    original_error: Exception
) -> CodeExecutionError:
    """
    Create a standardized CodeExecutionError with appropriate context.
    
    Args:
        error_type: Type of execution error (compilation, runtime, timeout)
        session_id: The session where the error occurred
        code_snippet: The code that failed to execute
        original_error: The original exception that caused the failure
        
    Returns:
        CodeExecutionError: Configured error with context and suggestions
    """
    if error_type == "compilation":
        message = "Code compilation failed"
    elif error_type == "runtime":
        message = "Code execution failed with runtime error"
    elif error_type == "timeout":
        message = "Code execution timed out"
    else:
        message = f"Code execution failed: {error_type}"
    
    return CodeExecutionError(
        message=message,
        error_type=error_type,
        session_id=session_id,
        code_snippet=code_snippet,
        original_error=original_error
    )


def create_resource_limit_error(
    resource_type: str,
    current_usage: Any,
    limit: Any
) -> ResourceLimitError:
    """
    Create a standardized ResourceLimitError with appropriate context.
    
    Args:
        resource_type: Type of resource that hit the limit
        current_usage: Current usage of the resource
        limit: The limit that was exceeded
        
    Returns:
        ResourceLimitError: Configured error with context and suggestions
    """
    message = f"{resource_type.title()} limit exceeded: {current_usage} >= {limit}"
    
    return ResourceLimitError(
        message=message,
        resource_type=resource_type,
        current_usage=current_usage,
        limit=limit
    )


def create_connection_error(
    server_url: str,
    original_error: Exception,
    retry_count: int = 0
) -> ConnectionError:
    """
    Create a standardized ConnectionError with appropriate context.
    
    Args:
        server_url: The server URL that failed to connect
        original_error: The original exception that caused the failure
        retry_count: Number of retries attempted
        
    Returns:
        ConnectionError: Configured error with context and suggestions
    """
    if "timeout" in str(original_error).lower():
        message = f"Connection to {server_url} timed out"
    elif "refused" in str(original_error).lower():
        message = f"Connection to {server_url} was refused - server may not be running"
    elif "unreachable" in str(original_error).lower():
        message = f"Server at {server_url} is unreachable"
    else:
        message = f"Failed to connect to {server_url}: {str(original_error)}"
    
    return ConnectionError(
        message=message,
        server_url=server_url,
        retry_count=retry_count,
        original_error=original_error
    )


def handle_sdk_exception(
    operation: str,
    original_error: Exception,
    **context
) -> MicrosandboxWrapperError:
    """
    Convert SDK exceptions to appropriate wrapper exceptions.
    
    Args:
        operation: The operation that failed (e.g., "sandbox_creation", "code_execution")
        original_error: The original SDK exception
        **context: Additional context information
        
    Returns:
        MicrosandboxWrapperError: Appropriate wrapper exception
    """
    error_str = str(original_error).lower()
    
    # Connection-related errors
    if any(keyword in error_str for keyword in ["connection", "network", "timeout", "unreachable"]):
        return create_connection_error(
            server_url=context.get("server_url", "unknown"),
            original_error=original_error,
            retry_count=context.get("retry_count", 0)
        )
    
    # Resource-related errors
    if any(keyword in error_str for keyword in ["resource", "memory", "cpu", "limit"]):
        return create_resource_limit_error(
            resource_type=context.get("resource_type", "unknown"),
            current_usage=context.get("current_usage", "unknown"),
            limit=context.get("limit", "unknown")
        )
    
    # Sandbox creation errors
    if operation == "sandbox_creation":
        return create_sandbox_creation_error(
            template=context.get("template", "unknown"),
            flavor=context.get("flavor", "unknown"),
            original_error=original_error
        )
    
    # Code execution errors
    if operation == "code_execution":
        return create_code_execution_error(
            error_type=context.get("error_type", "unknown"),
            session_id=context.get("session_id", "unknown"),
            code_snippet=context.get("code_snippet", ""),
            original_error=original_error
        )
    
    # Command execution errors
    if operation == "command_execution":
        return CommandExecutionError(
            message=f"Command execution failed: {str(original_error)}",
            command=context.get("command"),
            exit_code=context.get("exit_code"),
            session_id=context.get("session_id"),
            original_error=original_error
        )
    
    # Default to base wrapper error
    return MicrosandboxWrapperError(
        message=f"Operation '{operation}' failed: {str(original_error)}",
        category=ErrorCategory.SYSTEM,
        severity=ErrorSeverity.MEDIUM,
        context=context,
        original_error=original_error
    )


def log_error_with_context(
    logger: logging.Logger,
    error: MicrosandboxWrapperError,
    additional_context: Optional[Dict[str, Any]] = None
):
    """
    Log an error with full context information.
    
    Args:
        logger: Logger instance to use
        error: The wrapper error to log
        additional_context: Additional context to include in the log
    """
    context = error.context.copy()
    if additional_context:
        context.update(additional_context)
    
    log_message = f"[{error.error_code}] {error.message}"
    if context:
        log_message += f" | Context: {context}"
    if error.original_error:
        log_message += f" | Original: {str(error.original_error)}"
    
    if error.severity == ErrorSeverity.CRITICAL:
        logger.critical(log_message, exc_info=error.original_error)
    elif error.severity == ErrorSeverity.HIGH:
        logger.error(log_message, exc_info=error.original_error)
    elif error.severity == ErrorSeverity.MEDIUM:
        logger.warning(log_message)
    else:
        logger.info(log_message)