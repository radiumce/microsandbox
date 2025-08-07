"""
Main wrapper interface for the microsandbox wrapper.

This module provides the high-level MicrosandboxWrapper class that serves as the
primary interface for MCP Server implementations. It integrates session management,
resource management, and provides simplified APIs for code and command execution.
"""

import asyncio
import time
from typing import List, Optional

from .config import WrapperConfig
from .exceptions import (
    ConfigurationError,
    ConnectionError,
    MicrosandboxWrapperError,
    handle_sdk_exception,
    log_error_with_context,
)
from .logging_config import get_logger, track_operation, log_session_event
from .models import (
    CommandResult,
    ExecutionResult,
    ResourceStats,
    SandboxFlavor,
    SessionInfo,
    VolumeMapping,
)
from .resource_manager import ResourceManager
from .session_manager import SessionManager

# Set up logging
logger = get_logger('wrapper')


class MicrosandboxWrapper:
    """
    High-level wrapper interface for microsandbox operations.
    
    This class provides a simplified API for MCP Server implementations,
    hiding the complexity of session management, resource allocation,
    and sandbox lifecycle management.
    
    Key features:
    - Automatic session creation and management
    - Resource limit checking and enforcement
    - Unified error handling
    - Asynchronous operation support
    - Background cleanup and maintenance
    """
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[WrapperConfig] = None
    ):
        """
        Initialize the microsandbox wrapper.
        
        Args:
            server_url: Optional microsandbox server URL (overrides config/env)
            api_key: Optional API key (overrides config/env)
            config: Optional configuration object (if not provided, loads from env)
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        try:
            # Load configuration from environment if not provided
            if config is None:
                config = WrapperConfig.from_env()
            
            # Override config values if explicitly provided
            if server_url is not None:
                config.server_url = server_url
            if api_key is not None:
                config.api_key = api_key
            
            self._config = config
            
            # Initialize managers
            self._session_manager = SessionManager(config)
            self._resource_manager = ResourceManager(config, self._session_manager)
            
            # Track initialization state
            self._started = False
            
            logger.info(f"Initialized MicrosandboxWrapper with config: {config}")
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(f"Failed to initialize wrapper: {str(e)}")
    
    async def start(self) -> None:
        """
        Start the wrapper and all background services.
        
        This method must be called before using any other wrapper functionality.
        It starts the session manager and resource manager background tasks.
        
        Raises:
            MicrosandboxWrapperError: If startup fails
        """
        if self._started:
            logger.warning("Wrapper is already started")
            return
        
        try:
            logger.info("Starting MicrosandboxWrapper")
            
            # Start managers in order
            await self._session_manager.start()
            await self._resource_manager.start()
            
            self._started = True
            logger.info("MicrosandboxWrapper started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start wrapper: {e}", exc_info=True)
            # Attempt cleanup if partial startup occurred
            try:
                await self._cleanup_on_error()
            except Exception as cleanup_error:
                logger.error(f"Error during startup cleanup: {cleanup_error}")
            raise MicrosandboxWrapperError(f"Failed to start wrapper: {str(e)}")
    
    async def stop(self, timeout_seconds: float = 30.0) -> None:
        """
        Stop the wrapper and clean up all resources.
        
        This method gracefully shuts down all background tasks and cleans up
        active sessions. It should be called when the wrapper is no longer needed.
        
        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown
        """
        if not self._started:
            logger.warning("Wrapper is not started")
            return
        
        try:
            logger.info("Stopping MicrosandboxWrapper")
            
            # Use graceful shutdown with timeout
            shutdown_result = await self.graceful_shutdown(timeout_seconds)
            
            if shutdown_result['status'] == 'success':
                logger.info("MicrosandboxWrapper stopped successfully")
            elif shutdown_result['status'] == 'partial_success':
                logger.warning(
                    f"MicrosandboxWrapper stopped with some issues: "
                    f"{shutdown_result['error_count']} errors occurred"
                )
            else:
                logger.error(
                    f"MicrosandboxWrapper shutdown failed: {shutdown_result.get('error', 'Unknown error')}"
                )
                raise MicrosandboxWrapperError(
                    f"Shutdown failed: {shutdown_result.get('error', 'Multiple errors occurred')}"
                )
            
        except Exception as e:
            logger.error(f"Error during wrapper shutdown: {e}", exc_info=True)
            # Mark as stopped even if there were errors
            self._started = False
            raise MicrosandboxWrapperError(f"Error during shutdown: {str(e)}")
    
    async def execute_code(
        self,
        code: str,
        template: str = "python",
        session_id: Optional[str] = None,
        flavor: SandboxFlavor = SandboxFlavor.SMALL,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute code in a sandbox session.
        
        This method provides a high-level interface for code execution,
        automatically handling session creation, resource validation,
        and error management.
        
        Args:
            code: Code to execute
            template: Sandbox template (python, node, etc.)
            session_id: Optional session ID for session reuse
            flavor: Resource configuration for the sandbox
            timeout: Optional execution timeout in seconds
            
        Returns:
            ExecutionResult: Result of code execution including output and timing
            
        Raises:
            ResourceLimitError: If resource limits would be exceeded
            SandboxCreationError: If sandbox creation fails
            CodeExecutionError: If code execution fails
            ConnectionError: If server communication fails
        """
        self._ensure_started()
        
        with track_operation(
            'execute_code',
            template=template,
            session_id=session_id,
            flavor=flavor.value,
            timeout=timeout,
            code_length=len(code)
        ) as metrics:
            try:
                logger.debug(
                    f"Executing code: template={template}, session_id={session_id}, "
                    f"flavor={flavor.value}, timeout={timeout}, code_length={len(code)}"
                )
                
                # Check resource limits before proceeding
                await self._resource_manager.validate_resource_request(flavor)
                
                # Get or create session
                session = await self._session_manager.get_or_create_session(
                    session_id=session_id,
                    template=template,
                    flavor=flavor
                )
                
                # Track whether this is a new session
                session_created = session_id is None or session_id != session.session_id
                
                # Touch the session to update LRU ordering (if reusing existing session)
                if not session_created:
                    session.touch()
                
                # Log session event
                log_session_event(
                    logger,
                    "code_execution_started",
                    session.session_id,
                    template=template,
                    flavor=flavor.value,
                    session_created=session_created
                )
                
                # Execute code in the session
                result = await session.execute_code(code, timeout)
                
                # Update the session_created flag in the result
                result.session_created = session_created
                
                # Update metrics with execution results
                metrics.metadata.update({
                    'session_id': result.session_id,
                    'execution_time_ms': result.execution_time_ms,
                    'success': result.success,
                    'session_created': session_created
                })
                
                logger.info(
                    f"Code execution completed: session_id={result.session_id}, "
                    f"success={result.success}, time={result.execution_time_ms}ms, "
                    f"session_created={session_created}"
                )
                
                # Log session event
                log_session_event(
                    logger,
                    "code_execution_completed",
                    result.session_id,
                    success=result.success,
                    execution_time_ms=result.execution_time_ms
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Code execution failed: {e}", exc_info=True)
                if isinstance(e, MicrosandboxWrapperError):
                    raise
                raise MicrosandboxWrapperError(f"Code execution failed: {str(e)}")
    
    async def execute_command(
        self,
        command: str,
        args: Optional[List[str]] = None,
        template: str = "python",
        session_id: Optional[str] = None,
        flavor: SandboxFlavor = SandboxFlavor.SMALL,
        timeout: Optional[int] = None
    ) -> CommandResult:
        """
        Execute a command in a sandbox session.
        
        This method provides a high-level interface for command execution,
        automatically handling session creation, resource validation,
        and error management.
        
        Args:
            command: Command to execute
            args: Optional command arguments
            template: Sandbox template (python, node, etc.)
            session_id: Optional session ID for session reuse
            flavor: Resource configuration for the sandbox
            timeout: Optional execution timeout in seconds
            
        Returns:
            CommandResult: Result of command execution including output and exit code
            
        Raises:
            ResourceLimitError: If resource limits would be exceeded
            SandboxCreationError: If sandbox creation fails
            CommandExecutionError: If command execution fails
            ConnectionError: If server communication fails
        """
        self._ensure_started()
        
        with track_operation(
            'execute_command',
            command=command,
            args=args,
            template=template,
            session_id=session_id,
            flavor=flavor.value,
            timeout=timeout
        ) as metrics:
            try:
                logger.debug(
                    f"Executing command: command={command}, args={args}, template={template}, "
                    f"session_id={session_id}, flavor={flavor.value}, timeout={timeout}"
                )
                
                # Check resource limits before proceeding
                await self._resource_manager.validate_resource_request(flavor)
                
                # Get or create session
                session = await self._session_manager.get_or_create_session(
                    session_id=session_id,
                    template=template,
                    flavor=flavor
                )
                
                # Track whether this is a new session
                session_created = session_id is None or session_id != session.session_id
                
                # Touch the session to update LRU ordering (if reusing existing session)
                if not session_created:
                    session.touch()
                
                # Log session event
                log_session_event(
                    logger,
                    "command_execution_started",
                    session.session_id,
                    command=command,
                    command_args=args,
                    template=template,
                    flavor=flavor.value,
                    session_created=session_created
                )
                
                # Execute command in the session
                result = await session.execute_command(command, args, timeout)
                
                # Update the session_created flag in the result
                result.session_created = session_created
                
                # Update metrics with execution results
                metrics.metadata.update({
                    'session_id': result.session_id,
                    'execution_time_ms': result.execution_time_ms,
                    'exit_code': result.exit_code,
                    'success': result.success,
                    'session_created': session_created
                })
                
                logger.info(
                    f"Command execution completed: session_id={result.session_id}, "
                    f"command={command}, exit_code={result.exit_code}, time={result.execution_time_ms}ms, "
                    f"session_created={session_created}"
                )
                
                # Log session event
                log_session_event(
                    logger,
                    "command_execution_completed",
                    result.session_id,
                    command=command,
                    exit_code=result.exit_code,
                    success=result.success,
                    execution_time_ms=result.execution_time_ms
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Command execution failed: {e}", exc_info=True)
                if isinstance(e, MicrosandboxWrapperError):
                    raise
                raise MicrosandboxWrapperError(f"Command execution failed: {str(e)}") 
   
    async def get_sessions(
        self,
        session_id: Optional[str] = None
    ) -> List[SessionInfo]:
        """
        Get information about active sessions.
        
        Args:
            session_id: Optional specific session ID to query
            
        Returns:
            List[SessionInfo]: List of session information objects
        """
        self._ensure_started()
        
        try:
            return await self._session_manager.get_sessions(session_id)
        except Exception as e:
            logger.error(f"Failed to get session info: {e}", exc_info=True)
            if isinstance(e, MicrosandboxWrapperError):
                raise
            raise MicrosandboxWrapperError(f"Failed to get session info: {str(e)}")
    
    async def stop_session(self, session_id: str) -> bool:
        """
        Stop a specific session and clean up its resources.
        
        Args:
            session_id: ID of the session to stop
            
        Returns:
            bool: True if session was found and stopped, False if not found
        """
        self._ensure_started()
        
        try:
            return await self._session_manager.stop_session(session_id)
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {e}", exc_info=True)
            if isinstance(e, MicrosandboxWrapperError):
                raise
            raise MicrosandboxWrapperError(f"Failed to stop session: {str(e)}")
    
    async def get_volume_mappings(self) -> List[VolumeMapping]:
        """
        Get configured volume mappings.
        
        Returns:
            List[VolumeMapping]: List of configured volume mappings
        """
        self._ensure_started()
        
        try:
            return self._config.get_parsed_volume_mappings()
        except Exception as e:
            logger.error(f"Failed to get volume mappings: {e}", exc_info=True)
            raise MicrosandboxWrapperError(f"Failed to get volume mappings: {str(e)}")
    
    async def get_resource_stats(self) -> ResourceStats:
        """
        Get current resource usage statistics.
        
        Returns:
            ResourceStats: Current resource utilization information
        """
        self._ensure_started()
        
        try:
            return await self._resource_manager.get_resource_stats()
        except Exception as e:
            logger.error(f"Failed to get resource stats: {e}", exc_info=True)
            if isinstance(e, MicrosandboxWrapperError):
                raise
            raise MicrosandboxWrapperError(f"Failed to get resource stats: {str(e)}")
    
    async def cleanup_orphan_sandboxes(self) -> int:
        """
        Manually trigger cleanup of orphaned sandbox instances.
        
        Orphaned sandboxes are those running on the server but not
        associated with any active session in the wrapper.
        
        Returns:
            int: Number of orphan sandboxes that were cleaned up
        """
        self._ensure_started()
        
        try:
            return await self._resource_manager.force_orphan_cleanup()
        except Exception as e:
            logger.error(f"Failed to cleanup orphan sandboxes: {e}", exc_info=True)
            if isinstance(e, MicrosandboxWrapperError):
                raise
            raise MicrosandboxWrapperError(f"Failed to cleanup orphan sandboxes: {str(e)}")
    
    def _ensure_started(self) -> None:
        """
        Ensure the wrapper has been started.
        
        Raises:
            MicrosandboxWrapperError: If wrapper has not been started
        """
        if not self._started:
            raise MicrosandboxWrapperError(
                "Wrapper has not been started. Call start() before using wrapper methods."
            )
    
    async def _cleanup_on_error(self) -> None:
        """
        Clean up resources when an error occurs during startup.
        
        This method attempts to stop any partially started services
        to prevent resource leaks.
        """
        try:
            if hasattr(self, '_resource_manager'):
                await self._resource_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping resource manager during cleanup: {e}")
        
        try:
            if hasattr(self, '_session_manager'):
                await self._session_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping session manager during cleanup: {e}")
    
    async def __aenter__(self):
        """
        Async context manager entry.
        
        Automatically starts the wrapper when entering the context.
        """
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        
        Automatically stops the wrapper when exiting the context.
        """
        await self.stop()
    
    def get_config(self) -> WrapperConfig:
        """
        Get the current wrapper configuration.
        
        Returns:
            WrapperConfig: Current configuration object
        """
        return self._config
    
    def is_started(self) -> bool:
        """
        Check if the wrapper has been started.
        
        Returns:
            bool: True if wrapper is started and ready for use
        """
        return self._started
    
    async def pause_background_tasks(self) -> dict:
        """
        Pause all background tasks temporarily.
        
        This method allows the upper-level MCP server to temporarily pause
        background maintenance tasks, useful during critical operations or
        system maintenance.
        
        Returns:
            dict: Information about which tasks were paused
        """
        self._ensure_started()
        
        try:
            pause_info = {
                'timestamp': time.time(),
                'tasks_paused': [],
                'errors': []
            }
            
            # Pause session manager cleanup task
            try:
                if (self._session_manager._cleanup_task and 
                    not self._session_manager._cleanup_task.done()):
                    self._session_manager._cleanup_task.cancel()
                    try:
                        await self._session_manager._cleanup_task
                    except asyncio.CancelledError:
                        pass
                    self._session_manager._cleanup_task = None
                    pause_info['tasks_paused'].append('session_cleanup')
                    logger.info("Session cleanup task paused")
            except Exception as e:
                error_msg = f"Failed to pause session cleanup task: {e}"
                pause_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Pause resource manager orphan cleanup task
            try:
                if (self._resource_manager._orphan_cleanup_task and 
                    not self._resource_manager._orphan_cleanup_task.done()):
                    self._resource_manager._orphan_cleanup_task.cancel()
                    try:
                        await self._resource_manager._orphan_cleanup_task
                    except asyncio.CancelledError:
                        pass
                    self._resource_manager._orphan_cleanup_task = None
                    pause_info['tasks_paused'].append('orphan_cleanup')
                    logger.info("Orphan cleanup task paused")
            except Exception as e:
                error_msg = f"Failed to pause orphan cleanup task: {e}"
                pause_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Set status
            if pause_info['errors']:
                pause_info['status'] = 'partial_success' if pause_info['tasks_paused'] else 'failed'
            elif pause_info['tasks_paused']:
                pause_info['status'] = 'success'
            else:
                pause_info['status'] = 'no_tasks_to_pause'
            
            logger.info(
                f"Background task pause completed: status={pause_info['status']}, "
                f"paused={len(pause_info['tasks_paused'])}, errors={len(pause_info['errors'])}"
            )
            
            return pause_info
            
        except Exception as e:
            logger.error(f"Failed to pause background tasks: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': time.time(),
                'tasks_paused': [],
                'errors': [str(e)]
            }
    
    async def resume_background_tasks(self) -> dict:
        """
        Resume all background tasks after they were paused.
        
        This method restarts background tasks that were previously paused,
        allowing normal maintenance operations to continue.
        
        Returns:
            dict: Information about which tasks were resumed
        """
        self._ensure_started()
        
        try:
            resume_info = {
                'timestamp': time.time(),
                'tasks_resumed': [],
                'errors': []
            }
            
            # Resume session manager cleanup task
            try:
                if self._session_manager._cleanup_task is None:
                    self._session_manager._cleanup_task = asyncio.create_task(
                        self._session_manager._cleanup_loop()
                    )
                    resume_info['tasks_resumed'].append('session_cleanup')
                    logger.info("Session cleanup task resumed")
            except Exception as e:
                error_msg = f"Failed to resume session cleanup task: {e}"
                resume_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Resume resource manager orphan cleanup task
            try:
                if self._resource_manager._orphan_cleanup_task is None:
                    self._resource_manager._orphan_cleanup_task = asyncio.create_task(
                        self._resource_manager._orphan_cleanup_loop()
                    )
                    resume_info['tasks_resumed'].append('orphan_cleanup')
                    logger.info("Orphan cleanup task resumed")
            except Exception as e:
                error_msg = f"Failed to resume orphan cleanup task: {e}"
                resume_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Set status
            if resume_info['errors']:
                resume_info['status'] = 'partial_success' if resume_info['tasks_resumed'] else 'failed'
            elif resume_info['tasks_resumed']:
                resume_info['status'] = 'success'
            else:
                resume_info['status'] = 'no_tasks_to_resume'
            
            logger.info(
                f"Background task resume completed: status={resume_info['status']}, "
                f"resumed={len(resume_info['tasks_resumed'])}, errors={len(resume_info['errors'])}"
            )
            
            return resume_info
            
        except Exception as e:
            logger.error(f"Failed to resume background tasks: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': time.time(),
                'tasks_resumed': [],
                'errors': [str(e)]
            }
    
    async def get_background_task_status(self) -> dict:
        """
        Get comprehensive status information about all background tasks.
        
        This method provides detailed information about the health and status
        of all background tasks managed by the wrapper components.
        
        Returns:
            dict: Background task status information including health,
                  runtime statistics, and error information for all components
        """
        self._ensure_started()
        
        try:
            status_info = {
                'wrapper_started': self._started,
                'timestamp': time.time(),
                'components': {}
            }
            
            # Get session manager background task status
            try:
                session_task_status = self._session_manager.get_background_task_status()
                status_info['components']['session_manager'] = {
                    'status': 'healthy' if session_task_status['cleanup_task_healthy'] else 'unhealthy',
                    **session_task_status
                }
            except Exception as e:
                status_info['components']['session_manager'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Get resource manager background task status
            try:
                resource_task_status = self._resource_manager.get_background_task_status()
                status_info['components']['resource_manager'] = {
                    'status': 'healthy' if resource_task_status['orphan_cleanup_task_healthy'] else 'unhealthy',
                    **resource_task_status
                }
            except Exception as e:
                status_info['components']['resource_manager'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Calculate overall status
            component_statuses = [
                comp.get('status', 'unknown') 
                for comp in status_info['components'].values()
            ]
            
            if 'error' in component_statuses:
                status_info['overall_status'] = 'error'
            elif 'unhealthy' in component_statuses:
                status_info['overall_status'] = 'unhealthy'
            else:
                status_info['overall_status'] = 'healthy'
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get background task status: {e}", exc_info=True)
            return {
                'overall_status': 'error',
                'error': str(e),
                'wrapper_started': self._started,
                'timestamp': time.time()
            }
    
    async def restart_background_tasks(self) -> dict:
        """
        Restart any unhealthy background tasks.
        
        This method checks the health of all background tasks and restarts
        any that are not running properly. It provides detailed information
        about what actions were taken.
        
        Returns:
            dict: Information about restart actions taken
        """
        self._ensure_started()
        
        try:
            restart_info = {
                'timestamp': time.time(),
                'actions_taken': [],
                'errors': []
            }
            
            # Check and restart session manager cleanup task if needed
            try:
                session_restarted = await self._session_manager.restart_cleanup_if_needed()
                if session_restarted:
                    restart_info['actions_taken'].append('session_manager_cleanup_restarted')
                    logger.info("Session manager cleanup task was restarted")
            except Exception as e:
                error_msg = f"Failed to restart session manager cleanup task: {e}"
                restart_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Check and restart resource manager orphan cleanup task if needed
            try:
                resource_restarted = await self._resource_manager.restart_orphan_cleanup_if_needed()
                if resource_restarted:
                    restart_info['actions_taken'].append('resource_manager_orphan_cleanup_restarted')
                    logger.info("Resource manager orphan cleanup task was restarted")
            except Exception as e:
                error_msg = f"Failed to restart resource manager orphan cleanup task: {e}"
                restart_info['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
            
            # Set overall status
            if restart_info['errors']:
                restart_info['status'] = 'partial_success' if restart_info['actions_taken'] else 'failed'
            elif restart_info['actions_taken']:
                restart_info['status'] = 'success'
            else:
                restart_info['status'] = 'no_action_needed'
            
            logger.info(
                f"Background task restart completed: status={restart_info['status']}, "
                f"actions={len(restart_info['actions_taken'])}, errors={len(restart_info['errors'])}"
            )
            
            return restart_info
            
        except Exception as e:
            logger.error(f"Failed to restart background tasks: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': time.time(),
                'actions_taken': [],
                'errors': [str(e)]
            }
    
    async def graceful_shutdown(self, timeout_seconds: float = 30.0) -> dict:
        """
        Perform a graceful shutdown with timeout control.
        
        This method provides controlled shutdown of all background tasks and
        resources with proper timeout handling and detailed status reporting.
        
        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown
            
        Returns:
            dict: Shutdown status information including timing and any issues
        """
        if not self._started:
            return {
                'status': 'not_started',
                'message': 'Wrapper was not started',
                'timestamp': time.time()
            }
        
        shutdown_start = time.time()
        shutdown_info = {
            'start_time': shutdown_start,
            'timeout_seconds': timeout_seconds,
            'components_stopped': [],
            'errors': []
        }
        
        try:
            logger.info(f"Starting graceful shutdown with {timeout_seconds}s timeout")
            
            # Create shutdown tasks for both managers
            shutdown_tasks = []
            
            # Resource manager shutdown task
            async def shutdown_resource_manager():
                try:
                    await self._resource_manager.stop()
                    shutdown_info['components_stopped'].append('resource_manager')
                    logger.debug("Resource manager stopped successfully")
                except Exception as e:
                    error_msg = f"Error stopping resource manager: {e}"
                    shutdown_info['errors'].append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            # Session manager shutdown task
            async def shutdown_session_manager():
                try:
                    await self._session_manager.stop()
                    shutdown_info['components_stopped'].append('session_manager')
                    logger.debug("Session manager stopped successfully")
                except Exception as e:
                    error_msg = f"Error stopping session manager: {e}"
                    shutdown_info['errors'].append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            shutdown_tasks.append(shutdown_resource_manager())
            shutdown_tasks.append(shutdown_session_manager())
            
            # Wait for all shutdown tasks with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                shutdown_info['errors'].append(f"Shutdown timed out after {timeout_seconds}s")
                logger.warning(f"Graceful shutdown timed out after {timeout_seconds}s")
            
            # Mark as stopped regardless of errors
            self._started = False
            
            # Calculate final status
            shutdown_time = time.time() - shutdown_start
            shutdown_info.update({
                'end_time': time.time(),
                'duration_seconds': shutdown_time,
                'components_expected': 2,
                'components_stopped_count': len(shutdown_info['components_stopped']),
                'error_count': len(shutdown_info['errors'])
            })
            
            if shutdown_info['errors']:
                if shutdown_info['components_stopped_count'] > 0:
                    shutdown_info['status'] = 'partial_success'
                else:
                    shutdown_info['status'] = 'failed'
            else:
                shutdown_info['status'] = 'success'
            
            logger.info(
                f"Graceful shutdown completed: status={shutdown_info['status']}, "
                f"duration={shutdown_time:.2f}s, components_stopped={shutdown_info['components_stopped_count']}/2"
            )
            
            return shutdown_info
            
        except Exception as e:
            shutdown_info.update({
                'status': 'error',
                'error': str(e),
                'end_time': time.time(),
                'duration_seconds': time.time() - shutdown_start
            })
            logger.error(f"Error during graceful shutdown: {e}", exc_info=True)
            # Ensure we mark as stopped even on error
            self._started = False
            return shutdown_info
    
    async def health_check(self) -> dict:
        """
        Perform a comprehensive health check of the wrapper.
        
        Returns:
            dict: Health status information including component status,
                  resource usage, and any detected issues
        """
        try:
            health_info = {
                'wrapper_started': self._started,
                'timestamp': time.time(),
                'config_valid': True,
                'components': {}
            }
            
            if not self._started:
                health_info['status'] = 'not_started'
                return health_info
            
            # Check session manager health
            try:
                session_stats = self._session_manager.get_cleanup_stats()
                session_task_status = self._session_manager.get_background_task_status()
                health_info['components']['session_manager'] = {
                    'status': 'healthy' if session_task_status['cleanup_task_healthy'] else 'unhealthy',
                    'cleanup_task_running': session_stats['cleanup_task_running'],
                    'active_sessions': session_stats['active_sessions'],
                    'total_sessions': session_stats['total_sessions'],
                    'background_task_healthy': session_task_status['cleanup_task_healthy']
                }
            except Exception as e:
                health_info['components']['session_manager'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check resource manager health
            try:
                resource_health = self._resource_manager.get_resource_health_status()
                resource_task_status = self._resource_manager.get_background_task_status()
                health_info['components']['resource_manager'] = {
                    'status': 'healthy' if resource_task_status['orphan_cleanup_task_healthy'] else 'unhealthy',
                    'background_task_healthy': resource_task_status['orphan_cleanup_task_healthy'],
                    **resource_health
                }
            except Exception as e:
                health_info['components']['resource_manager'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Overall health status
            component_statuses = [
                comp.get('status', 'unknown') 
                for comp in health_info['components'].values()
            ]
            
            if 'error' in component_statuses:
                health_info['status'] = 'error'
            elif 'unhealthy' in component_statuses:
                health_info['status'] = 'unhealthy'
            else:
                health_info['status'] = 'healthy'
            
            # Count issues
            error_components = [
                name for name, comp in health_info['components'].items()
                if comp.get('status') == 'error'
            ]
            unhealthy_components = [
                name for name, comp in health_info['components'].items()
                if comp.get('status') == 'unhealthy'
            ]
            
            if error_components:
                health_info['error_components'] = error_components
            if unhealthy_components:
                health_info['unhealthy_components'] = unhealthy_components
            
            return health_info
            
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'wrapper_started': self._started,
                'timestamp': time.time()
            }