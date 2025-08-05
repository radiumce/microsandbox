#!/usr/bin/env python3
"""
Example showing how to use the logging and monitoring features in the microsandbox wrapper.

This example demonstrates:
1. Setting up logging configuration
2. Using performance tracking
3. Structured logging events
4. Metrics collection and analysis
"""

import asyncio
import os
import tempfile
from pathlib import Path

# Add the microsandbox_wrapper to the path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from microsandbox_wrapper import (
    setup_logging,
    get_logger,
    get_metrics_collector,
    track_operation,
    log_session_event,
    log_sandbox_event,
    log_resource_event
)


async def demonstrate_logging_features():
    """Demonstrate the logging and monitoring features"""
    
    print("=== Microsandbox Wrapper Logging Demo ===\n")
    
    # 1. Setup logging with custom configuration
    print("1. Setting up logging configuration...")
    
    # Create a temporary log file for this demo
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        log_file = f.name
    
    # Setup logging with both console and file output
    logger = setup_logging(
        level="DEBUG",
        log_file=log_file,
        enable_console=True,
        structured_format=True
    )
    
    print(f"   ✓ Logging configured with file: {log_file}")
    print(f"   ✓ Log level: DEBUG")
    print(f"   ✓ Structured format enabled\n")
    
    # 2. Demonstrate component-specific logging
    print("2. Component-specific logging...")
    
    wrapper_logger = get_logger('wrapper')
    session_logger = get_logger('session_manager')
    resource_logger = get_logger('resource_manager')
    
    wrapper_logger.info("Wrapper component initialized")
    session_logger.info("Session manager started")
    resource_logger.info("Resource manager monitoring enabled")
    
    print("   ✓ Component loggers created and tested\n")
    
    # 3. Demonstrate structured event logging
    print("3. Structured event logging...")
    
    # Session events
    log_session_event(
        session_logger,
        "session_created",
        "demo-session-001",
        template="python",
        flavor="small",
        user_id="demo-user"
    )
    
    log_session_event(
        session_logger,
        "code_execution_started",
        "demo-session-001",
        code_length=150,
        timeout=30
    )
    
    # Sandbox events
    log_sandbox_event(
        resource_logger,
        "sandbox_started",
        "demo-sandbox-001",
        "default",
        memory_mb=1024,
        cpus=1.0,
        startup_time_ms=2500
    )
    
    # Resource events
    log_resource_event(
        resource_logger,
        "resource_allocated",
        "memory",
        amount_mb=1024,
        total_mb=8192,
        utilization_percent=12.5
    )
    
    print("   ✓ Session, sandbox, and resource events logged\n")
    
    # 4. Demonstrate performance tracking
    print("4. Performance tracking and metrics...")
    
    # Track a simulated code execution operation
    with track_operation(
        'demo_code_execution',
        session_id='demo-session-001',
        template='python',
        code_length=150
    ) as metrics:
        # Simulate code execution work
        await asyncio.sleep(0.05)  # 50ms execution time
        
        # Add execution results to metrics
        metrics.metadata.update({
            'stdout_length': 45,
            'stderr_length': 0,
            'success': True
        })
    
    # Track a simulated resource cleanup operation
    with track_operation(
        'demo_resource_cleanup',
        cleanup_type='orphan_sandboxes'
    ) as metrics:
        # Simulate cleanup work
        await asyncio.sleep(0.02)  # 20ms cleanup time
        
        # Add cleanup results to metrics
        metrics.metadata.update({
            'sandboxes_found': 3,
            'sandboxes_cleaned': 2,
            'sandboxes_failed': 1
        })
    
    print("   ✓ Performance operations tracked\n")
    
    # 5. Demonstrate metrics collection and analysis
    print("5. Metrics collection and analysis...")
    
    collector = get_metrics_collector()
    
    # Get all collected metrics
    all_metrics = collector.get_metrics()
    print(f"   ✓ Total metrics collected: {len(all_metrics)}")
    
    # Analyze metrics by operation type
    for metric in all_metrics:
        print(f"   - {metric.operation_name}: {metric.duration_ms}ms, success={metric.success}")
        if metric.metadata:
            print(f"     Metadata: {metric.metadata}")
    
    # Log metrics summary
    print("\n   Metrics Summary:")
    collector.log_metrics_summary()
    
    print("\n6. Log file contents preview...")
    
    # Show some content from the log file
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"   ✓ Log file contains {len(lines)} lines")
            print("   Last 5 log entries:")
            for line in lines[-5:]:
                print(f"     {line.strip()}")
    except Exception as e:
        print(f"   ✗ Error reading log file: {e}")
    
    # 7. Environment variable configuration demo
    print("\n7. Environment variable configuration...")
    
    print("   Available environment variables for logging configuration:")
    env_vars = [
        ('MSB_LOG_LEVEL', 'Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)'),
        ('MSB_LOG_FILE', 'Set log file path'),
        ('MSB_LOG_MAX_SIZE', 'Set maximum log file size in bytes'),
        ('MSB_LOG_BACKUP_COUNT', 'Set number of backup log files to keep'),
        ('MSB_LOG_CONSOLE', 'Enable/disable console logging (true/false)'),
        ('MSB_LOG_STRUCTURED', 'Enable/disable structured logging (true/false)')
    ]
    
    for var_name, description in env_vars:
        current_value = os.environ.get(var_name, 'Not set')
        print(f"   - {var_name}: {description}")
        print(f"     Current value: {current_value}")
    
    print(f"\n=== Demo completed! ===")
    print(f"Log file saved at: {log_file}")
    print("You can examine the log file to see the structured logging output.")
    
    # Clean up
    try:
        os.unlink(log_file)
        print("(Log file cleaned up)")
    except:
        pass


if __name__ == "__main__":
    asyncio.run(demonstrate_logging_features())