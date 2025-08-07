"""
Session management for the microsandbox wrapper.

This module provides session management functionality including automatic
session creation, lifecycle management, timeout handling, and resource cleanup.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp

from .config import WrapperConfig
from .exceptions import (
    CodeExecutionError,
    CommandExecutionError,
    SandboxCreationError,
    create_code_execution_error,
    create_sandbox_creation_error,
    handle_sdk_exception,
    log_error_with_context,
)
from .logging_config import get_logger, track_operation, log_session_event, log_sandbox_event
from .models import (
    CommandResult,
    ExecutionResult,
    SandboxFlavor,
    SessionInfo,
    SessionStatus,
)

# Set up logging
logger = get_logger('session_manager')


class ManagedSession:
    """
    A managed sandbox session that encapsulates the underlying SDK sandbox.
    
    This class provides a higher-level interface for sandbox operations,
    including automatic lifecycle management, state tracking, and error handling.
    """
    
    def __init__(
        self,
        session_id: str,
        template: str,
        flavor: SandboxFlavor,
        config: WrapperConfig
    ):
        """
        Initialize a managed session.
        
        Args:
            session_id: Unique identifier for this session
            template: Sandbox template (python, node, etc.)
            flavor: Resource configuration for the sandbox
            config: Wrapper configuration
        """
        self.session_id = session_id
        self.template = template.lower()
        self.flavor = flavor
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.status = SessionStatus.CREATING
        self.namespace = "default"
        self.sandbox_name = f"session-{session_id[:8]}"
        
        # Configuration
        self._config = config
        
        # Underlying sandbox instance and HTTP session
        self._sandbox = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Concurrency control
        self._lock = asyncio.Lock()
        
        logger.info(
            f"Created managed session {session_id} with template={template}, "
            f"flavor={flavor.value}, sandbox_name={self.sandbox_name}"
        )
    
    async def ensure_started(self) -> None:
        """
        Ensure the sandbox is started and ready for use.
        
        This method is idempotent - it can be called multiple times safely.
        If the sandbox is already started, this method returns immediately.
        
        Raises:
            SandboxCreationError: If sandbox creation fails
        """
        async with self._lock:
            if self._sandbox is None or not self._sandbox._is_started:
                await self._create_sandbox()
    
    async def execute_code(
        self,
        code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute code in the managed session.
        
        Args:
            code: Code to execute
            timeout: Optional timeout in seconds
            
        Returns:
            ExecutionResult: Result of code execution
            
        Raises:
            CodeExecutionError: If code execution fails
        """
        with track_operation(
            'session_execute_code',
            session_id=self.session_id,
            template=self.template,
            flavor=self.flavor.value,
            timeout=timeout,
            code_length=len(code)
        ) as metrics:
            await self.ensure_started()
            self.last_accessed = datetime.now()
            self.status = SessionStatus.PROCESSING  # Mark as processing to prevent eviction
            
            log_session_event(
                logger,
                "code_execution_started",
                self.session_id,
                template=self.template,
                flavor=self.flavor.value,
                code_length=len(code),
                timeout=timeout
            )
            
            try:
                start_time = time.time()
                
                # Use timeout if specified, otherwise use default
                execution_timeout = timeout or self._config.default_execution_timeout
                
                # Execute code with timeout
                if execution_timeout:
                    result = await asyncio.wait_for(
                        self._sandbox.run(code),
                        timeout=execution_timeout
                    )
                else:
                    result = await self._sandbox.run(code)
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # Get output and error from the execution result
                stdout = await result.output()
                stderr = await result.error()
                success = not result.has_error()
                
                self.status = SessionStatus.READY
                
                # Update metrics
                metrics.metadata.update({
                    'execution_time_ms': execution_time_ms,
                    'success': success,
                    'stdout_length': len(stdout),
                    'stderr_length': len(stderr)
                })
                
                log_session_event(
                    logger,
                    "code_execution_completed",
                    self.session_id,
                    success=success,
                    execution_time_ms=execution_time_ms,
                    stdout_length=len(stdout),
                    stderr_length=len(stderr)
                )
                
                return ExecutionResult(
                    session_id=self.session_id,
                    stdout=stdout,
                    stderr=stderr,
                    success=success,
                    execution_time_ms=execution_time_ms,
                    session_created=False,  # Session was already created
                    template=self.template
                )
                
            except asyncio.TimeoutError:
                self.status = SessionStatus.ERROR
                error = create_code_execution_error(
                    error_type="timeout",
                    session_id=self.session_id,
                    code_snippet=code,
                    original_error=asyncio.TimeoutError(f"Execution timed out after {execution_timeout} seconds")
                )
                log_error_with_context(logger, error, {"operation": "code_execution"})
                raise error
            except Exception as e:
                self.status = SessionStatus.ERROR
                # Determine error type based on the exception
                error_type = "runtime"
                if "compilation" in str(e).lower() or "syntax" in str(e).lower():
                    error_type = "compilation"
                
                error = create_code_execution_error(
                    error_type=error_type,
                    session_id=self.session_id,
                    code_snippet=code,
                    original_error=e
                )
                log_error_with_context(logger, error, {"operation": "code_execution"})
                raise error
    
    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None
    ) -> CommandResult:
        """
        Execute a command in the managed session.
        
        Args:
            command: Command to execute
            args: Optional command arguments
            timeout: Optional timeout in seconds
            
        Returns:
            CommandResult: Result of command execution
            
        Raises:
            CommandExecutionError: If command execution fails
        """
        await self.ensure_started()
        self.last_accessed = datetime.now()
        self.status = SessionStatus.PROCESSING  # Mark as processing to prevent eviction
        
        try:
            start_time = time.time()
            
            # Use timeout if specified, otherwise use default
            execution_timeout = timeout or self._config.default_execution_timeout
            args = args or []
            
            # Execute command with timeout
            if execution_timeout:
                result = await asyncio.wait_for(
                    self._sandbox.command.run(command, args, execution_timeout),
                    timeout=execution_timeout + 5  # Add buffer for network overhead
                )
            else:
                result = await self._sandbox.command.run(command, args)
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Get output and error from the command result
            stdout = await result.output()
            stderr = await result.error()
            exit_code = result.exit_code
            success = result.success
            
            self.status = SessionStatus.READY
            
            logger.debug(
                f"Command execution completed in session {self.session_id}: "
                f"command='{command}', exit_code={exit_code}, time={execution_time_ms}ms"
            )
            
            return CommandResult(
                session_id=self.session_id,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                success=success,
                execution_time_ms=execution_time_ms,
                session_created=False,  # Session was already created
                command=command,
                args=args
            )
            
        except asyncio.TimeoutError:
            self.status = SessionStatus.ERROR
            error = CommandExecutionError(
                message=f"Command execution timed out after {execution_timeout} seconds",
                command=command,
                session_id=self.session_id,
                original_error=asyncio.TimeoutError(f"Command timed out after {execution_timeout} seconds")
            )
            log_error_with_context(logger, error, {"operation": "command_execution"})
            raise error
        except Exception as e:
            self.status = SessionStatus.ERROR
            error = handle_sdk_exception(
                operation="command_execution",
                original_error=e,
                command=command,
                session_id=self.session_id
            )
            log_error_with_context(logger, error, {"operation": "command_execution"})
            raise error
    
    async def stop(self) -> None:
        """
        Stop the managed session and clean up resources.
        
        This method is idempotent and can be called multiple times safely.
        """
        async with self._lock:
            logger.info(f"Stopping managed session {self.session_id}")
            
            # Stop the underlying sandbox
            if self._sandbox and self._sandbox._is_started:
                try:
                    await self._sandbox.stop()
                    logger.debug(f"Stopped sandbox for session {self.session_id}")
                except Exception as e:
                    logger.error(f"Error stopping sandbox for session {self.session_id}: {e}")
            
            # Close the HTTP session
            if self._session:
                try:
                    await self._session.close()
                    logger.debug(f"Closed HTTP session for session {self.session_id}")
                except Exception as e:
                    logger.error(f"Error closing HTTP session for session {self.session_id}: {e}")
                finally:
                    self._session = None
            
            self.status = SessionStatus.STOPPED
            logger.info(f"Successfully stopped managed session {self.session_id}")
    
    def get_info(self) -> SessionInfo:
        """
        Get information about this session.
        
        Returns:
            SessionInfo: Current session information
        """
        return SessionInfo(
            session_id=self.session_id,
            template=self.template,
            flavor=self.flavor,
            created_at=self.created_at,
            last_accessed=self.last_accessed,
            status=self.status,
            namespace=self.namespace,
            sandbox_name=self.sandbox_name
        )
    
    def is_expired(self, timeout_seconds: int) -> bool:
        """
        Check if this session has expired based on last access time.
        
        A session is considered expired if:
        1. It has been explicitly stopped, or
        2. The time since last access exceeds the timeout threshold
        
        Args:
            timeout_seconds: Session timeout in seconds
            
        Returns:
            bool: True if session has expired
        """
        # Stopped sessions are always considered expired
        if self.status == SessionStatus.STOPPED:
            return True
        
        # Check if session has been idle too long
        elapsed = (datetime.now() - self.last_accessed).total_seconds()
        is_expired = elapsed > timeout_seconds
        
        # Log detailed expiration info for debugging
        if is_expired:
            logger.debug(
                f"Session {self.session_id} expired: elapsed={elapsed:.1f}s > timeout={timeout_seconds}s, "
                f"last_accessed={self.last_accessed}, status={self.status.value}"
            )
        
        return is_expired
    
    def can_be_evicted(self) -> bool:
        """
        Check if this session can be evicted for LRU cleanup.
        
        A session can be evicted if:
        1. It is not currently processing a request (status != PROCESSING)
        2. It is not in an error state that needs investigation
        3. It is not currently being created
        
        Returns:
            bool: True if session can be safely evicted
        """
        # Cannot evict sessions that are currently processing requests
        if self.status == SessionStatus.PROCESSING:
            return False
        
        # Cannot evict sessions that are being created
        if self.status == SessionStatus.CREATING:
            return False
        
        # Can evict sessions in READY, RUNNING, ERROR, or STOPPED states
        return True
    
    def touch(self) -> None:
        """
        Update the last accessed time to current time.
        
        This method should be called whenever the session is accessed
        to maintain accurate LRU ordering.
        """
        self.last_accessed = datetime.now()
    
    async def _create_sandbox(self) -> None:
        """
        Create and start the underlying sandbox instance.
        
        Raises:
            SandboxCreationError: If sandbox creation fails
        """
        try:
            logger.info(
                f"Creating sandbox for session {self.session_id} with template={self.template}"
            )
            
            # Import the appropriate sandbox class based on template
            if self.template in ["python"]:
                from microsandbox import PythonSandbox
                self._sandbox = PythonSandbox(
                    server_url=self._config.server_url,
                    namespace=self.namespace,
                    name=self.sandbox_name,
                    api_key=self._config.api_key
                )
            elif self.template in ["node", "nodejs", "javascript"]:
                from microsandbox import NodeSandbox
                self._sandbox = NodeSandbox(
                    server_url=self._config.server_url,
                    namespace=self.namespace,
                    name=self.sandbox_name,
                    api_key=self._config.api_key
                )
            else:
                raise SandboxCreationError(f"Unsupported template: {self.template}")
            
            # Create HTTP session for the sandbox
            self._session = aiohttp.ClientSession()
            self._sandbox._session = self._session
            
            # Prepare volume mappings
            volumes = []
            if self._config.shared_volume_mappings:
                volumes = self._config.shared_volume_mappings.copy()
            
            logger.debug(
                f"Starting sandbox {self.sandbox_name} with memory={self.flavor.get_memory_mb()}MB, "
                f"cpus={self.flavor.get_cpus()}, volumes={len(volumes)} mappings"
            )
            
            # Start the sandbox with configured resources
            await self._sandbox.start(
                memory=self.flavor.get_memory_mb(),
                cpus=self.flavor.get_cpus(),
                timeout=self._config.sandbox_start_timeout,
                volumes=volumes
            )
            
            self.status = SessionStatus.READY
            logger.info(f"Successfully created and started sandbox for session {self.session_id}")
            
        except Exception as e:
            self.status = SessionStatus.ERROR
            
            # Clean up any partially created resources
            if self._session:
                try:
                    await self._session.close()
                except Exception:
                    pass
                self._session = None
            
            error = create_sandbox_creation_error(
                template=self.template,
                flavor=self.flavor.value,
                original_error=e
            )
            log_error_with_context(logger, error, {
                "operation": "sandbox_creation",
                "session_id": self.session_id
            })
            raise error


class SessionManager:
    """
    Manages the lifecycle of sandbox sessions.
    
    This class handles session creation, retrieval, cleanup, and resource management.
    It provides automatic session timeout handling and cleanup of expired sessions.
    """
    
    def __init__(self, config: WrapperConfig):
        """
        Initialize the session manager.
        
        Args:
            config: Wrapper configuration
        """
        self._config = config
        self._sessions: Dict[str, ManagedSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_time = time.time()
        
        logger.info(f"Initialized session manager with config: {config}")
    
    async def start(self) -> None:
        """
        Start the session manager and background cleanup task.
        """
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Started session manager cleanup task")
        else:
            logger.warning("Session manager cleanup task is already running")
    
    async def stop(self) -> None:
        """
        Stop the session manager and clean up all sessions.
        
        This method performs a graceful shutdown by:
        1. Stopping the background cleanup task
        2. Concurrently stopping all active sessions
        3. Clearing the session registry
        4. Providing detailed logging for monitoring
        """
        logger.info("Stopping session manager")
        start_time = time.time()
        
        # Cancel cleanup task
        if self._cleanup_task:
            logger.debug("Cancelling cleanup task")
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.debug("Stopped cleanup task")
        
        # Stop all active sessions concurrently for faster shutdown
        sessions_to_stop = list(self._sessions.values())
        if sessions_to_stop:
            logger.info(f"Stopping {len(sessions_to_stop)} active sessions")
            
            # Create stop tasks for all sessions
            stop_tasks = []
            for session in sessions_to_stop:
                stop_tasks.append(self._stop_session_safe(session))
            
            # Wait for all sessions to stop
            results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            # Count successful stops and log any errors
            successful_stops = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error stopping session {sessions_to_stop[i].session_id}: {result}",
                        exc_info=result
                    )
                else:
                    successful_stops += 1
            
            logger.info(f"Successfully stopped {successful_stops}/{len(sessions_to_stop)} sessions")
        
        # Clear the session registry
        self._sessions.clear()
        
        shutdown_time = time.time() - start_time
        logger.info(f"Session manager stopped in {shutdown_time:.2f}s")
    
    async def _stop_session_safe(self, session: ManagedSession) -> None:
        """
        Safely stop a single session with error handling.
        
        Args:
            session: Session to stop
        """
        try:
            await session.stop()
        except Exception as e:
            logger.error(f"Error stopping session {session.session_id}: {e}", exc_info=True)
            raise
    
    async def get_or_create_session(
        self,
        session_id: Optional[str],
        template: str,
        flavor: SandboxFlavor
    ) -> ManagedSession:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: Optional session ID. If None, creates a new session
            template: Sandbox template (python, node, etc.)
            flavor: Resource configuration
            
        Returns:
            ManagedSession: The requested or newly created session
        """
        # If no session ID provided, create a new session
        if session_id is None:
            session_id = str(uuid.uuid4())
            logger.debug(f"Generated new session ID: {session_id}")
        
        # Check if session already exists
        if session_id in self._sessions:
            session = self._sessions[session_id]
            
            # Check if session is still valid
            if not session.is_expired(self._config.session_timeout):
                session.last_accessed = datetime.now()
                logger.debug(f"Reusing existing session {session_id}")
                return session
            else:
                # Session expired, remove it and create a new one
                logger.info(f"Session {session_id} expired, creating new session")
                await self._cleanup_session(session)
        
        # Create new session
        session = ManagedSession(
            session_id=session_id,
            template=template,
            flavor=flavor,
            config=self._config
        )
        
        self._sessions[session_id] = session
        logger.info(f"Created new session {session_id}")
        
        return session
    
    async def touch_session(self, session_id: str) -> None:
        """
        Update the last accessed time for a session.
        
        Args:
            session_id: ID of the session to touch
        """
        if session_id in self._sessions:
            self._sessions[session_id].last_accessed = datetime.now()
            logger.debug(f"Touched session {session_id}")
    
    async def stop_session(self, session_id: str) -> bool:
        """
        Stop and remove a specific session.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            bool: True if session was found and stopped, False otherwise
        """
        if session_id not in self._sessions:
            logger.warning(f"Attempted to stop non-existent session {session_id}")
            return False
        
        session = self._sessions[session_id]
        await self._cleanup_session(session)
        logger.info(f"Stopped session {session_id}")
        return True
    
    async def get_sessions(
        self,
        session_id: Optional[str] = None
    ) -> List[SessionInfo]:
        """
        Get information about sessions.
        
        Args:
            session_id: Optional specific session ID to get info for
            
        Returns:
            List[SessionInfo]: List of session information
        """
        if session_id is not None:
            # Return info for specific session
            if session_id in self._sessions:
                return [self._sessions[session_id].get_info()]
            else:
                return []
        
        # Return info for all sessions
        return [session.get_info() for session in self._sessions.values()]
    
    def get_cleanup_stats(self) -> dict:
        """
        Get statistics about the cleanup process and session management.
        
        Returns:
            dict: Statistics including active sessions, cleanup status, etc.
        """
        current_time = datetime.now()
        active_sessions = 0
        expired_sessions = 0
        sessions_by_status = {}
        oldest_session_age = 0
        
        for session in self._sessions.values():
            # Count by status
            status = session.status.value
            sessions_by_status[status] = sessions_by_status.get(status, 0) + 1
            
            # Count active vs expired
            if session.is_expired(self._config.session_timeout):
                expired_sessions += 1
            else:
                active_sessions += 1
            
            # Track oldest session
            session_age = (current_time - session.created_at).total_seconds()
            oldest_session_age = max(oldest_session_age, session_age)
        
        return {
            'total_sessions': len(self._sessions),
            'active_sessions': active_sessions,
            'expired_sessions': expired_sessions,
            'sessions_by_status': sessions_by_status,
            'cleanup_task_running': self._cleanup_task is not None and not self._cleanup_task.done(),
            'session_timeout': self._config.session_timeout,
            'cleanup_interval': self._config.cleanup_interval,
            'oldest_session_age_seconds': oldest_session_age,
            'manager_uptime_seconds': time.time() - self._start_time
        }
    
    async def force_cleanup(self) -> int:
        """
        Manually trigger cleanup of expired sessions.
        
        This method can be called to immediately clean up expired sessions
        without waiting for the next scheduled cleanup cycle.
        
        Returns:
            int: Number of sessions that were cleaned up
        """
        logger.info("Manual cleanup triggered")
        start_time = time.time()
        
        try:
            cleaned_count = await self._cleanup_expired_sessions()
            cleanup_time = time.time() - start_time
            
            logger.info(
                f"Manual cleanup completed: {cleaned_count} sessions cleaned up in {cleanup_time:.2f}s"
            )
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during manual cleanup: {e}", exc_info=True)
            raise
    
    async def cleanup_session_by_id(self, session_id: str) -> bool:
        """
        Clean up a specific session by ID.
        
        This method allows for targeted cleanup of individual sessions,
        useful for administrative purposes or error recovery.
        
        Args:
            session_id: ID of the session to clean up
            
        Returns:
            bool: True if session was found and cleaned up, False if not found
        """
        if session_id not in self._sessions:
            logger.warning(f"Attempted to clean up non-existent session {session_id}")
            return False
        
        session = self._sessions[session_id]
        logger.info(f"Cleaning up session {session_id} by request")
        
        try:
            await self._cleanup_session_safe(session)
            logger.info(f"Successfully cleaned up session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clean up session {session_id}: {e}", exc_info=True)
            return False
    
    def is_cleanup_healthy(self) -> bool:
        """
        Check if the cleanup system is running properly.
        
        Returns:
            bool: True if cleanup task is running and healthy
        """
        if self._cleanup_task is None:
            return False
        
        if self._cleanup_task.done():
            # Task completed, check if it was cancelled or had an error
            if self._cleanup_task.cancelled():
                logger.warning("Cleanup task was cancelled")
                return False
            
            try:
                # This will raise an exception if the task failed
                self._cleanup_task.result()
                logger.warning("Cleanup task completed unexpectedly")
                return False
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}")
                return False
        
        return True
    
    def get_background_task_status(self) -> dict:
        """
        Get detailed status information about background tasks.
        
        Returns:
            dict: Background task status information including health,
                  runtime statistics, and error information
        """
        task_info = {
            'cleanup_task_exists': self._cleanup_task is not None,
            'cleanup_task_healthy': self.is_cleanup_healthy(),
            'cleanup_interval_seconds': self._config.cleanup_interval,
            'session_timeout_seconds': self._config.session_timeout,
            'manager_uptime_seconds': time.time() - self._start_time
        }
        
        if self._cleanup_task is not None:
            task_info.update({
                'cleanup_task_done': self._cleanup_task.done(),
                'cleanup_task_cancelled': self._cleanup_task.cancelled(),
            })
            
            if self._cleanup_task.done():
                try:
                    # Try to get the result to check for exceptions
                    self._cleanup_task.result()
                    task_info['cleanup_task_result'] = 'completed_normally'
                except asyncio.CancelledError:
                    task_info['cleanup_task_result'] = 'cancelled'
                except Exception as e:
                    task_info['cleanup_task_result'] = 'failed'
                    task_info['cleanup_task_error'] = str(e)
            else:
                task_info['cleanup_task_result'] = 'running'
        
        return task_info
    
    async def restart_cleanup_if_needed(self) -> bool:
        """
        Restart the cleanup task if it's not running properly.
        
        Returns:
            bool: True if cleanup was restarted, False if it was already healthy
        """
        if self.is_cleanup_healthy():
            return False
        
        logger.warning("Cleanup task is not healthy, restarting...")
        
        # Cancel existing task if it exists
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Start new cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup task restarted")
        return True
    
    async def _cleanup_loop(self) -> None:
        """
        Background task that periodically cleans up expired sessions.
        
        This method runs continuously in the background, waking up at regular
        intervals to check for and clean up expired sessions. It handles errors
        gracefully and provides detailed logging for monitoring purposes.
        """
        logger.info(
            f"Started session cleanup loop with interval {self._config.cleanup_interval}s, "
            f"session timeout {self._config.session_timeout}s"
        )
        
        cleanup_count = 0
        
        while True:
            try:
                await asyncio.sleep(self._config.cleanup_interval)
                
                # Perform cleanup and track statistics
                start_time = time.time()
                expired_count = await self._cleanup_expired_sessions()
                cleanup_time = time.time() - start_time
                
                cleanup_count += 1
                
                # Log periodic statistics
                if cleanup_count % 10 == 0:  # Every 10 cleanup cycles
                    active_sessions = len(self._sessions)
                    logger.info(
                        f"Cleanup cycle #{cleanup_count}: {active_sessions} active sessions, "
                        f"last cleanup took {cleanup_time:.2f}s"
                    )
                
            except asyncio.CancelledError:
                logger.info(f"Session cleanup loop cancelled after {cleanup_count} cycles")
                break
            except Exception as e:
                logger.error(f"Error in session cleanup loop (cycle #{cleanup_count}): {e}", exc_info=True)
                # Continue running even if there's an error
                continue
    
    async def _cleanup_expired_sessions(self) -> int:
        """
        Clean up sessions that have exceeded the timeout.
        
        Returns:
            int: Number of sessions that were cleaned up
        """
        expired_sessions = []
        current_time = datetime.now()
        
        # Find expired sessions with detailed logging
        for session_id, session in self._sessions.items():
            if session.is_expired(self._config.session_timeout):
                elapsed_time = (current_time - session.last_accessed).total_seconds()
                logger.debug(
                    f"Session {session_id} expired: last_accessed={session.last_accessed}, "
                    f"elapsed={elapsed_time:.1f}s, timeout={self._config.session_timeout}s"
                )
                expired_sessions.append(session)
        
        # Clean up expired sessions
        cleaned_count = 0
        if expired_sessions:
            logger.info(f"Found {len(expired_sessions)} expired sessions to clean up")
            
            # Use asyncio.gather for concurrent cleanup, but with error handling
            cleanup_tasks = []
            for session in expired_sessions:
                cleanup_tasks.append(self._cleanup_session_safe(session))
            
            # Wait for all cleanup tasks to complete
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Count successful cleanups and log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Error cleaning up expired session {expired_sessions[i].session_id}: {result}",
                        exc_info=result
                    )
                else:
                    cleaned_count += 1
            
            logger.info(f"Successfully cleaned up {cleaned_count}/{len(expired_sessions)} expired sessions")
        
        # Log session statistics
        active_count = len(self._sessions)
        if active_count > 0 or cleaned_count > 0:
            logger.debug(f"Session cleanup completed. Active sessions: {active_count}, cleaned: {cleaned_count}")
        
        return cleaned_count
    
    async def _cleanup_session(self, session: ManagedSession) -> None:
        """
        Clean up a single session and remove it from the manager.
        
        Args:
            session: Session to clean up
        """
        try:
            await session.stop()
        finally:
            # Always remove from sessions dict, even if stop failed
            self._sessions.pop(session.session_id, None)
    
    async def _cleanup_session_safe(self, session: ManagedSession) -> None:
        """
        Safely clean up a single session with detailed error handling.
        
        This method wraps _cleanup_session with additional error handling
        and logging for use in concurrent cleanup operations.
        
        Args:
            session: Session to clean up
        """
        session_id = session.session_id
        try:
            logger.debug(f"Starting cleanup for session {session_id}")
            await self._cleanup_session(session)
            logger.debug(f"Successfully cleaned up session {session_id}")
        except Exception as e:
            logger.error(f"Failed to clean up session {session_id}: {e}", exc_info=True)
            # Re-raise the exception so it can be handled by the caller
            raise