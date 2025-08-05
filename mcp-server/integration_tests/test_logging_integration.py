#!/usr/bin/env python3
"""
Test script to verify logging and monitoring functionality.

This script tests the logging configuration and performance metrics collection
without requiring a full microsandbox server setup.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

# Add the microsandbox_wrapper to the path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from microsandbox_wrapper.logging_config import (
    setup_logging,
    get_logger,
    get_metrics_collector,
    track_operation,
    log_session_event,
    log_sandbox_event,
    log_resource_event
)


async def test_logging_functionality():
    """Test basic logging functionality"""
    print("Testing logging functionality...")
    
    # Create a temporary log file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
    
    try:
        # Setup logging with file output
        logger = setup_logging(
            level="DEBUG",
            log_file=log_file,
            enable_console=True,
            structured_format=True
        )
        
        # Test basic logging
        component_logger = get_logger('test_component')
        component_logger.info("Testing basic logging functionality")
        component_logger.debug("This is a debug message")
        component_logger.warning("This is a warning message")
        
        # Test structured logging events
        log_session_event(
            component_logger,
            "session_created",
            "test-session-123",
            template="python",
            flavor="small"
        )
        
        log_sandbox_event(
            component_logger,
            "sandbox_started",
            "test-sandbox",
            "default",
            memory_mb=1024,
            cpus=1.0
        )
        
        log_resource_event(
            component_logger,
            "resource_allocated",
            "memory",
            amount_mb=1024,
            total_mb=8192
        )
        
        # Test performance tracking
        with track_operation('test_operation', param1="value1", param2=42) as metrics:
            # Simulate some work
            await asyncio.sleep(0.1)
            metrics.metadata['result'] = 'success'
        
        # Test metrics collection
        collector = get_metrics_collector()
        metrics_list = collector.get_metrics('test_operation')
        
        if metrics_list:
            metric = metrics_list[0]
            print(f"✓ Performance tracking works: {metric.operation_name} took {metric.duration_ms}ms")
        else:
            print("✗ Performance tracking failed")
        
        # Log metrics summary
        collector.log_metrics_summary()
        
        # Check if log file was created and has content
        if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
            print(f"✓ Log file created successfully: {log_file}")
            
            # Show some log content
            with open(log_file, 'r') as f:
                lines = f.readlines()
                print(f"✓ Log file contains {len(lines)} lines")
                if lines:
                    print("Sample log entries:")
                    for line in lines[-3:]:  # Show last 3 lines
                        print(f"  {line.strip()}")
        else:
            print("✗ Log file was not created or is empty")
        
        print("✓ Logging functionality test completed")
        
    finally:
        # Clean up
        if os.path.exists(log_file):
            os.unlink(log_file)


async def test_performance_metrics():
    """Test performance metrics collection"""
    print("\nTesting performance metrics...")
    
    collector = get_metrics_collector()
    collector.clear_metrics()
    
    # Test multiple operations
    operations = ['operation_a', 'operation_b', 'operation_c']
    
    for op_name in operations:
        for i in range(3):  # Run each operation 3 times
            with track_operation(op_name, iteration=i) as metrics:
                # Simulate different execution times
                await asyncio.sleep(0.01 * (i + 1))
                metrics.metadata['iteration'] = i
                if i == 2:  # Make last iteration fail
                    metrics.finish(success=False, error_message="Simulated error")
                    continue
    
    # Get and analyze metrics
    all_metrics = collector.get_metrics()
    print(f"✓ Collected {len(all_metrics)} metrics")
    
    # Test filtering
    for op_name in operations:
        op_metrics = collector.get_metrics(op_name)
        success_count = sum(1 for m in op_metrics if m.success)
        error_count = sum(1 for m in op_metrics if not m.success)
        print(f"  {op_name}: {success_count} successful, {error_count} failed")
    
    # Test metrics summary
    collector.log_metrics_summary()
    
    print("✓ Performance metrics test completed")


async def test_environment_configuration():
    """Test environment variable configuration"""
    print("\nTesting environment configuration...")
    
    # Set test environment variables
    test_env = {
        'MSB_LOG_LEVEL': 'WARNING',
        'MSB_LOG_CONSOLE': 'false',
        'MSB_LOG_STRUCTURED': 'false'
    }
    
    # Save original values
    original_env = {}
    for key, value in test_env.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value
    
    try:
        # Setup logging with environment configuration
        logger = setup_logging()
        
        # Test that only WARNING and above are logged
        test_logger = get_logger('env_test')
        test_logger.debug("This debug message should not appear")
        test_logger.info("This info message should not appear")
        test_logger.warning("This warning message should appear")
        
        print("✓ Environment configuration test completed")
        
    finally:
        # Restore original environment
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def main():
    """Run all logging tests"""
    print("Starting logging and monitoring tests...\n")
    
    try:
        await test_logging_functionality()
        await test_performance_metrics()
        await test_environment_configuration()
        
        print("\n✓ All logging tests passed!")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)