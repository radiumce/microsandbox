"""
Logging configuration module for the microsandbox wrapper.

This module provides centralized logging configuration and performance metrics collection
for the MCP wrapper components.
"""

import logging
import logging.handlers
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime
import json


@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error_message: Optional[str] = None, **metadata):
        """Mark the operation as finished and calculate duration"""
        self.end_time = time.time()
        self.duration_ms = int((self.end_time - self.start_time) * 1000)
        self.success = success
        self.error_message = error_message
        self.metadata.update(metadata)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging"""
        return {
            'operation': self.operation_name,
            'duration_ms': self.duration_ms,
            'success': self.success,
            'error_message': self.error_message,
            'metadata': self.metadata,
            'timestamp': datetime.fromtimestamp(self.start_time).isoformat()
        }


class MetricsCollector:
    """Centralized metrics collection"""
    
    def __init__(self):
        self._metrics: List[PerformanceMetrics] = []
        self._logger = logging.getLogger(f"{__name__}.metrics")
        
    def start_operation(self, operation_name: str, **metadata) -> PerformanceMetrics:
        """Start tracking an operation"""
        metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=time.time(),
            metadata=metadata
        )
        self._metrics.append(metrics)
        
        self._logger.debug(
            f"Started operation: {operation_name}",
            extra={'metrics_metadata': metadata}
        )
        
        return metrics
        
    def get_metrics(self, operation_name: Optional[str] = None) -> List[PerformanceMetrics]:
        """Get collected metrics, optionally filtered by operation name"""
        if operation_name:
            return [m for m in self._metrics if m.operation_name == operation_name]
        return self._metrics.copy()
        
    def clear_metrics(self):
        """Clear collected metrics"""
        self._metrics.clear()
        
    def log_metrics_summary(self):
        """Log a summary of collected metrics"""
        if not self._metrics:
            return
            
        operations = {}
        for metric in self._metrics:
            if metric.operation_name not in operations:
                operations[metric.operation_name] = {
                    'count': 0,
                    'total_duration_ms': 0,
                    'success_count': 0,
                    'error_count': 0
                }
            
            op_stats = operations[metric.operation_name]
            op_stats['count'] += 1
            if metric.duration_ms:
                op_stats['total_duration_ms'] += metric.duration_ms
            if metric.success:
                op_stats['success_count'] += 1
            else:
                op_stats['error_count'] += 1
                
        # Calculate averages and log summary
        for op_name, stats in operations.items():
            avg_duration = stats['total_duration_ms'] / stats['count'] if stats['count'] > 0 else 0
            success_rate = stats['success_count'] / stats['count'] if stats['count'] > 0 else 0
            
            self._logger.info(
                f"Operation metrics - {op_name}: "
                f"count={stats['count']}, "
                f"avg_duration_ms={avg_duration:.1f}, "
                f"success_rate={success_rate:.2%}, "
                f"errors={stats['error_count']}"
            )


# Global metrics collector instance
_metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance"""
    return _metrics_collector


@contextmanager
def track_operation(operation_name: str, **metadata):
    """Context manager for tracking operation performance"""
    metrics = _metrics_collector.start_operation(operation_name, **metadata)
    logger = logging.getLogger(f"{__name__}.operations")
    
    try:
        logger.debug(f"Starting operation: {operation_name}", extra={'operation_metadata': metadata})
        yield metrics
        metrics.finish(success=True)
        logger.debug(
            f"Completed operation: {operation_name} in {metrics.duration_ms}ms",
            extra={'operation_metrics': metrics.to_dict()}
        )
    except Exception as e:
        metrics.finish(success=False, error_message=str(e))
        logger.error(
            f"Failed operation: {operation_name} after {metrics.duration_ms}ms - {str(e)}",
            extra={'operation_metrics': metrics.to_dict()},
            exc_info=True
        )
        raise


class StructuredFormatter(logging.Formatter):
    """Custom formatter that adds structured data to log records"""
    
    def format(self, record):
        # Add timestamp if not present
        if not hasattr(record, 'timestamp'):
            record.timestamp = datetime.fromtimestamp(record.created).isoformat()
            
        # Add component name based on logger name
        if hasattr(record, 'name'):
            parts = record.name.split('.')
            if len(parts) >= 2 and parts[-2] == 'microsandbox_wrapper':
                record.component = parts[-1]
            else:
                record.component = 'wrapper'
        
        # Format the base message
        formatted = super().format(record)
        
        # Add structured data if present
        structured_data = {}
        for attr in ['operation_metadata', 'operation_metrics', 'metrics_metadata', 'session_id', 'sandbox_name']:
            if hasattr(record, attr):
                structured_data[attr] = getattr(record, attr)
                
        if structured_data:
            formatted += f" | {json.dumps(structured_data, separators=(',', ':'))}"
            
        return formatted


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_console: bool = True,
    structured_format: bool = True
) -> logging.Logger:
    """
    Setup centralized logging configuration for the microsandbox wrapper.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, uses environment variable MSB_LOG_FILE
        max_file_size: Maximum size of log file before rotation (bytes)
        backup_count: Number of backup files to keep
        enable_console: Whether to enable console logging
        structured_format: Whether to use structured logging format
        
    Returns:
        logging.Logger: Configured root logger for the wrapper
    """
    
    # Get configuration from environment variables
    level = os.getenv('MSB_LOG_LEVEL', level).upper()
    log_file = log_file or os.getenv('MSB_LOG_FILE')
    max_file_size = int(os.getenv('MSB_LOG_MAX_SIZE', str(max_file_size)))
    backup_count = int(os.getenv('MSB_LOG_BACKUP_COUNT', str(backup_count)))
    enable_console = os.getenv('MSB_LOG_CONSOLE', 'true').lower() in ('true', '1', 'yes')
    structured_format = os.getenv('MSB_LOG_STRUCTURED', 'true').lower() in ('true', '1', 'yes')
    
    # Create root logger for the wrapper
    logger = logging.getLogger('microsandbox_wrapper')
    logger.setLevel(getattr(logging, level, logging.INFO))
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    if structured_format:
        formatter = StructuredFormatter(
            fmt='%(timestamp)s | %(levelname)-8s | %(component)-12s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Setup console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, level, logging.INFO))
        logger.addHandler(console_handler)
    
    # Setup file handler with rotation
    if log_file:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)  # File gets all messages
            logger.addHandler(file_handler)
            
            logger.info(f"Logging configured - Level: {level}, File: {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to setup file logging: {e}")
    
    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific component.
    
    Args:
        name: Component name (e.g., 'session_manager', 'resource_manager')
        
    Returns:
        logging.Logger: Logger instance for the component
    """
    return logging.getLogger(f'microsandbox_wrapper.{name}')


def log_session_event(
    logger: logging.Logger,
    event: str,
    session_id: str,
    level: int = logging.INFO,
    **kwargs
):
    """
    Log a session-related event with structured data.
    
    Args:
        logger: Logger instance to use
        event: Event description
        session_id: Session ID
        level: Log level
        **kwargs: Additional metadata
    """
    logger.log(
        level,
        f"Session event: {event}",
        extra={
            'session_id': session_id,
            'event_type': 'session',
            **kwargs
        }
    )


def log_sandbox_event(
    logger: logging.Logger,
    event: str,
    sandbox_name: str,
    namespace: str = "default",
    level: int = logging.INFO,
    **kwargs
):
    """
    Log a sandbox-related event with structured data.
    
    Args:
        logger: Logger instance to use
        event: Event description
        sandbox_name: Sandbox name
        namespace: Sandbox namespace
        level: Log level
        **kwargs: Additional metadata
    """
    logger.log(
        level,
        f"Sandbox event: {event}",
        extra={
            'sandbox_name': sandbox_name,
            'namespace': namespace,
            'event_type': 'sandbox',
            **kwargs
        }
    )


def log_resource_event(
    logger: logging.Logger,
    event: str,
    resource_type: str,
    level: int = logging.INFO,
    **kwargs
):
    """
    Log a resource-related event with structured data.
    
    Args:
        logger: Logger instance to use
        event: Event description
        resource_type: Type of resource (memory, cpu, session, etc.)
        level: Log level
        **kwargs: Additional metadata
    """
    logger.log(
        level,
        f"Resource event: {event}",
        extra={
            'resource_type': resource_type,
            'event_type': 'resource',
            **kwargs
        }
    )


# Initialize default logging if not already configured
if not logging.getLogger('microsandbox_wrapper').handlers:
    setup_logging()