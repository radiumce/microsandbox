#!/usr/bin/env python3
"""
Test script for enhanced error handling functionality.

This script tests the unified error handling system to ensure that:
1. Errors are properly categorized and formatted
2. Recovery suggestions are provided
3. Logging works correctly
4. Error serialization works
"""

import logging
import sys
import os

# Add the parent directory to the path so we can import the wrapper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from microsandbox_wrapper.exceptions import (
    SandboxCreationError,
    CodeExecutionError,
    CommandExecutionError,
    ResourceLimitError,
    ConfigurationError,
    ConnectionError,
    create_sandbox_creation_error,
    create_code_execution_error,
    create_resource_limit_error,
    create_connection_error,
    handle_sdk_exception,
    ErrorSeverity,
    ErrorCategory,
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_basic_error_creation():
    """Test basic error creation and properties."""
    print("Testing basic error creation...")
    
    # Test SandboxCreationError
    error = SandboxCreationError(
        message="Failed to create sandbox",
        template="python",
        flavor="small",
        original_error=Exception("Network timeout")
    )
    
    assert error.category == ErrorCategory.RESOURCE
    assert error.severity == ErrorSeverity.HIGH
    assert len(error.recovery_suggestions) > 0
    assert "template" in error.context
    assert "flavor" in error.context
    
    print(f"✓ SandboxCreationError: {error.error_code}")
    print(f"  Message: {error.message}")
    print(f"  Suggestions: {len(error.recovery_suggestions)}")
    
    # Test CodeExecutionError
    error = CodeExecutionError(
        message="Code execution failed",
        error_type="compilation",
        session_id="test-123",
        code_snippet="print('hello'",
        original_error=SyntaxError("Missing closing parenthesis")
    )
    
    assert error.category == ErrorCategory.EXECUTION
    print(f"  Recovery suggestions: {error.recovery_suggestions}")
    assert any("syntax" in suggestion.lower() or "compilation" in suggestion.lower() 
               for suggestion in error.recovery_suggestions)
    
    print(f"✓ CodeExecutionError: {error.error_code}")
    print(f"  Error type: {error.context.get('error_type')}")
    
    # Test ResourceLimitError
    error = ResourceLimitError(
        message="Session limit exceeded",
        resource_type="sessions",
        current_usage=10,
        limit=10
    )
    
    assert error.category == ErrorCategory.RESOURCE
    assert error.severity == ErrorSeverity.HIGH
    
    print(f"✓ ResourceLimitError: {error.error_code}")
    print(f"  Resource: {error.context.get('resource_type')}")

def test_error_helper_functions():
    """Test error creation helper functions."""
    print("\nTesting error helper functions...")
    
    # Test create_sandbox_creation_error
    original_error = ConnectionError("Connection refused")
    error = create_sandbox_creation_error("python", "small", original_error)
    
    assert "connect" in error.message.lower()
    assert error.context.get("template") == "python"
    assert error.context.get("flavor") == "small"
    
    print(f"✓ create_sandbox_creation_error: {error.message}")
    
    # Test create_code_execution_error
    error = create_code_execution_error(
        "timeout", "session-123", "time.sleep(1000)", TimeoutError("Timed out")
    )
    
    assert error.context.get("error_type") == "timeout"
    assert "optimize" in error.recovery_suggestions[0].lower()
    
    print(f"✓ create_code_execution_error: {error.context.get('error_type')}")
    
    # Test create_resource_limit_error
    error = create_resource_limit_error("memory", "2048MB", "1024MB")
    
    assert error.context.get("resource_type") == "memory"
    assert "smaller" in error.recovery_suggestions[0].lower()
    
    print(f"✓ create_resource_limit_error: {error.context.get('resource_type')}")

def test_error_serialization():
    """Test error serialization to dictionary."""
    print("\nTesting error serialization...")
    
    error = ConfigurationError(
        message="Invalid configuration",
        config_key="MSB_SERVER_URL",
        config_value="invalid-url"
    )
    
    error_dict = error.to_dict()
    
    assert "error_code" in error_dict
    assert "message" in error_dict
    assert "category" in error_dict
    assert "severity" in error_dict
    assert "recovery_suggestions" in error_dict
    assert "context" in error_dict
    
    print(f"✓ Error serialization: {len(error_dict)} fields")
    print(f"  Error code: {error_dict['error_code']}")
    print(f"  Category: {error_dict['category']}")

def test_user_friendly_messages():
    """Test user-friendly error message generation."""
    print("\nTesting user-friendly messages...")
    
    error = ConnectionError(
        message="Failed to connect to server",
        server_url="http://localhost:5555",
        retry_count=3
    )
    
    friendly_message = error.get_user_friendly_message()
    
    assert "Error:" in friendly_message
    assert "Suggested actions:" in friendly_message
    assert len(friendly_message.split('\n')) > 3  # Should have multiple lines
    
    print(f"✓ User-friendly message generated ({len(friendly_message)} chars)")
    print("Sample message:")
    print(friendly_message[:200] + "..." if len(friendly_message) > 200 else friendly_message)

def test_sdk_exception_handling():
    """Test SDK exception conversion."""
    print("\nTesting SDK exception handling...")
    
    # Test connection error conversion
    original_error = Exception("Connection timeout")
    wrapper_error = handle_sdk_exception(
        "sandbox_creation",
        original_error,
        server_url="http://localhost:5555",
        template="python",
        flavor="small"
    )
    
    assert isinstance(wrapper_error, ConnectionError)
    print(f"✓ SDK connection error converted: {type(wrapper_error).__name__}")
    
    # Test resource error conversion
    original_error = Exception("Memory limit exceeded")
    wrapper_error = handle_sdk_exception(
        "resource_check",
        original_error,
        resource_type="memory",
        current_usage="2GB",
        limit="1GB"
    )
    
    assert isinstance(wrapper_error, ResourceLimitError)
    print(f"✓ SDK resource error converted: {type(wrapper_error).__name__}")

def main():
    """Run all error handling tests."""
    print("=" * 60)
    print("Testing Enhanced Error Handling System")
    print("=" * 60)
    
    try:
        test_basic_error_creation()
        test_error_helper_functions()
        test_error_serialization()
        test_user_friendly_messages()
        test_sdk_exception_handling()
        
        print("\n" + "=" * 60)
        print("✅ All error handling tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()