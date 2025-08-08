"""
Resource management for the microsandbox wrapper.

This module provides resource monitoring, limit checking, and orphan sandbox
cleanup functionality to ensure efficient resource utilization and prevent
resource leaks.
"""

import asyncio
import time
from typing import Dict, List, Optional, TYPE_CHECKING

import aiohttp

from .config import WrapperConfig
from .exceptions import (
    ResourceLimitError,
    ConnectionError,
    create_resource_limit_error,
    create_connection_error,
    handle_sdk_exception,
    log_error_with_context,
)
from .logging_config import get_logger, track_operation, log_resource_event, log_sandbox_event
from .models import ResourceStats, SandboxFlavor, SessionStatus

if TYPE_CHECKING:
    from .session_manager import SessionManager

# Set up logging
logger = get_logger('resource_manager')


class ResourceManager:
    """
    Manages system resources and monitors sandbox usage.
    
    This class provides functionality for:
    - Resource limit checking before session creation
    - Resource usage statistics and monitoring
    - Orphan sandbox detection and cleanup
    - Background maintenance tasks
    """
    
    def __init__(self, config: WrapperConfig, session_manager: 'SessionManager'):
        """
        Initialize the resource manager.
        
        Args:
            config: Wrapper configuration
            session_manager: Session manager instance for coordination
        """
        self._config = config
        self._session_manager = session_manager
        self._orphan_cleanup_task: Optional[asyncio.Task] = None
        self._start_time = time.time()
        
        # Orphan cleanup statistics
        self._last_cleanup_time: Optional[float] = None
        self._total_cleanup_cycles = 0
        self._total_orphans_cleaned = 0
        self._last_cleanup_duration = 0.0
        self._cleanup_errors = 0
        
        logger.info(f"Initialized resource manager with config: {config}")
    
    async def start(self) -> None:
        """
        Start the resource manager and background tasks.
        
        This starts the orphan cleanup task that runs periodically
        to detect and clean up orphaned sandbox instances.
        """
        if self._orphan_cleanup_task is None:
            self._orphan_cleanup_task = asyncio.create_task(self._orphan_cleanup_loop())
            logger.info("Started resource manager orphan cleanup task")
        else:
            logger.warning("Resource manager orphan cleanup task is already running")
    
    async def stop(self) -> None:
        """
        Stop the resource manager and clean up background tasks.
        
        This gracefully shuts down all background tasks and ensures
        proper cleanup of resources.
        """
        logger.info("Stopping resource manager")
        
        # Cancel orphan cleanup task
        if self._orphan_cleanup_task:
            logger.debug("Cancelling orphan cleanup task")
            self._orphan_cleanup_task.cancel()
            try:
                await self._orphan_cleanup_task
            except asyncio.CancelledError:
                pass
            self._orphan_cleanup_task = None
            logger.debug("Stopped orphan cleanup task")
        
        logger.info("Resource manager stopped")
    
    async def check_resource_limits(self, flavor: SandboxFlavor) -> bool:
        """
        Check if creating a new session with the given flavor would exceed resource limits.
        
        This method validates against configured limits including:
        - Maximum concurrent sessions
        - Total memory allocation limits
        - Any other resource constraints
        
        If limits would be exceeded, attempts LRU eviction of eligible sessions.
        
        Args:
            flavor: The sandbox flavor being requested
            
        Returns:
            bool: True if resources are available (after eviction if needed), False if limits would still be exceeded
        """
        try:
            stats = await self.get_resource_stats()
            
            # Check if we need to evict sessions due to session limit
            sessions_to_evict = 0
            if stats.active_sessions >= self._config.max_concurrent_sessions:
                sessions_to_evict = max(sessions_to_evict, stats.active_sessions - self._config.max_concurrent_sessions + 1)
            
            # Check if we need to evict sessions due to memory limit
            memory_to_free = 0
            if self._config.max_total_memory_mb is not None:
                required_memory = stats.total_memory_mb + flavor.get_memory_mb()
                if required_memory > self._config.max_total_memory_mb:
                    memory_to_free = required_memory - self._config.max_total_memory_mb
            
            # If we need to evict sessions, try LRU eviction (if enabled)
            if sessions_to_evict > 0 or memory_to_free > 0:
                if not self._config.enable_lru_eviction:
                    logger.warning(
                        f"Resource limits would be exceeded but LRU eviction is disabled: "
                        f"sessions_to_evict={sessions_to_evict}, memory_to_free={memory_to_free}MB"
                    )
                    return False
                
                logger.info(
                    f"Resource limits would be exceeded, attempting LRU eviction: "
                    f"sessions_to_evict={sessions_to_evict}, memory_to_free={memory_to_free}MB"
                )
                
                evicted_count = await self._evict_lru_sessions(sessions_to_evict, memory_to_free)
                
                if evicted_count == 0:
                    logger.warning(
                        f"No sessions could be evicted. Current: {stats.active_sessions} sessions, "
                        f"{stats.total_memory_mb}MB memory"
                    )
                    return False
                
                # Re-check limits after eviction
                updated_stats = await self.get_resource_stats()
                
                # Check session limit again
                if updated_stats.active_sessions >= self._config.max_concurrent_sessions:
                    logger.warning(
                        f"Session limit still exceeded after eviction: "
                        f"{updated_stats.active_sessions}/{self._config.max_concurrent_sessions}"
                    )
                    return False
                
                # Check memory limit again
                if self._config.max_total_memory_mb is not None:
                    required_memory = updated_stats.total_memory_mb + flavor.get_memory_mb()
                    if required_memory > self._config.max_total_memory_mb:
                        logger.warning(
                            f"Memory limit still exceeded after eviction: "
                            f"{required_memory}MB > {self._config.max_total_memory_mb}MB"
                        )
                        return False
                
                logger.info(
                    f"Successfully evicted {evicted_count} sessions. "
                    f"New stats: {updated_stats.active_sessions} sessions, {updated_stats.total_memory_mb}MB memory"
                )
            
            logger.debug(
                f"Resource check passed for {flavor.value}: "
                f"sessions={stats.active_sessions}/{self._config.max_concurrent_sessions}, "
                f"memory={stats.total_memory_mb + flavor.get_memory_mb()}MB"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking resource limits: {e}", exc_info=True)
            # In case of error, be conservative and deny the request
            return False
    
    async def get_resource_stats(self) -> ResourceStats:
        """
        Get current resource usage statistics.
        
        This method collects comprehensive statistics about current
        resource utilization across all active sessions.
        
        Returns:
            ResourceStats: Current resource usage information
        """
        try:
            # Get all sessions from the session manager
            sessions = await self._session_manager.get_sessions()
            
            # Calculate statistics
            active_sessions = 0
            sessions_by_flavor: Dict[SandboxFlavor, int] = {}
            total_memory_mb = 0
            total_cpus = 0.0
            
            for session in sessions:
                # Only count non-stopped sessions as active
                if session.status != SessionStatus.STOPPED:
                    active_sessions += 1
                    
                    # Count sessions by flavor
                    flavor = session.flavor
                    sessions_by_flavor[flavor] = sessions_by_flavor.get(flavor, 0) + 1
                    
                    # Sum up resource usage
                    total_memory_mb += flavor.get_memory_mb()
                    total_cpus += flavor.get_cpus()
            
            uptime_seconds = int(time.time() - self._start_time)
            
            stats = ResourceStats(
                active_sessions=active_sessions,
                max_sessions=self._config.max_concurrent_sessions,
                sessions_by_flavor=sessions_by_flavor,
                total_memory_mb=total_memory_mb,
                total_cpus=total_cpus,
                uptime_seconds=uptime_seconds
            )
            
            logger.debug(
                f"Resource stats: {active_sessions} active sessions, "
                f"{total_memory_mb}MB memory, {total_cpus} CPUs"
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting resource stats: {e}", exc_info=True)
            # Return empty stats in case of error
            return ResourceStats(
                active_sessions=0,
                max_sessions=self._config.max_concurrent_sessions,
                sessions_by_flavor={},
                total_memory_mb=0,
                total_cpus=0.0,
                uptime_seconds=int(time.time() - self._start_time)
            )
    
    async def validate_resource_request(self, flavor: SandboxFlavor) -> None:
        """
        Validate a resource request and raise an exception if it cannot be fulfilled.
        
        This is a convenience method that checks resource limits and raises
        a descriptive exception if the request would exceed limits.
        
        Args:
            flavor: The sandbox flavor being requested
            
        Raises:
            ResourceLimitError: If the resource request cannot be fulfilled
        """
        if not await self.check_resource_limits(flavor):
            stats = await self.get_resource_stats()
            
            # Determine the specific reason for rejection
            if stats.active_sessions >= self._config.max_concurrent_sessions:
                error = create_resource_limit_error(
                    resource_type="sessions",
                    current_usage=stats.active_sessions,
                    limit=self._config.max_concurrent_sessions
                )
                log_error_with_context(logger, error, {"operation": "resource_validation"})
                raise error
            
            if (self._config.max_total_memory_mb is not None and 
                stats.total_memory_mb + flavor.get_memory_mb() > self._config.max_total_memory_mb):
                error = create_resource_limit_error(
                    resource_type="memory",
                    current_usage=f"{stats.total_memory_mb + flavor.get_memory_mb()}MB",
                    limit=f"{self._config.max_total_memory_mb}MB"
                )
                log_error_with_context(logger, error, {"operation": "resource_validation"})
                raise error
            
            # Generic resource limit error
            error = ResourceLimitError(
                message=f"Resource limits would be exceeded for flavor {flavor.value}",
                resource_type="general",
                current_usage=f"{stats.active_sessions} sessions, {stats.total_memory_mb}MB memory",
                limit="configured limits"
            )
            log_error_with_context(logger, error, {"operation": "resource_validation"})
            raise error
    
    async def cleanup_orphan_sandboxes(self) -> int:
        """
        Detect and clean up orphaned sandbox instances.
        
        Orphaned sandboxes are those that are running on the server but
        are not associated with any active session in the session manager.
        This can happen due to crashes, network issues, or other failures.
        
        Returns:
            int: Number of orphan sandboxes that were cleaned up
        """
        with track_operation('cleanup_orphan_sandboxes') as metrics:
            try:
                log_resource_event(
                    logger,
                    "orphan_cleanup_started",
                    "sandbox"
                )
                
                start_time = time.time()
                
                # Get all running sandboxes from the server
                running_sandboxes = await self._get_running_sandboxes()
                
                log_resource_event(
                    logger,
                    "running_sandboxes_discovered",
                    "sandbox",
                    count=len(running_sandboxes)
                )
                
                # Get all active sessions from session manager
                active_sessions = await self._session_manager.get_sessions()
                active_sandbox_names = set()
                
                for session in active_sessions:
                    if session.status != SessionStatus.STOPPED:
                        # Create the expected sandbox identifier
                        sandbox_key = f"{session.namespace}/{session.sandbox_name}"
                        active_sandbox_names.add(sandbox_key)
                
                log_resource_event(
                    logger,
                    "active_sessions_analyzed",
                    "session",
                    count=len(active_sandbox_names)
                )
                
                # Identify orphan sandboxes
                orphan_sandboxes = []
                for sandbox in running_sandboxes:
                    sandbox_key = f"{sandbox['namespace']}/{sandbox['name']}"
                    if sandbox_key not in active_sandbox_names:
                        orphan_sandboxes.append(sandbox)
                        log_sandbox_event(
                            logger,
                            "orphan_sandbox_identified",
                            sandbox['name'],
                            sandbox['namespace'],
                            cpu_usage=sandbox.get('cpu_usage'),
                            memory_usage=sandbox.get('memory_usage'),
                            disk_usage=sandbox.get('disk_usage')
                        )
                
                # Update metrics
                metrics.metadata.update({
                    'running_sandboxes': len(running_sandboxes),
                    'active_sessions': len(active_sandbox_names),
                    'orphan_sandboxes': len(orphan_sandboxes)
                })
                
                # Clean up orphan sandboxes
                cleaned_count = 0
                failed_count = 0
                
                if orphan_sandboxes:
                    log_resource_event(
                        logger,
                        "orphan_cleanup_batch_started",
                        "sandbox",
                        count=len(orphan_sandboxes)
                    )
                    
                    # Clean up orphans concurrently for efficiency, but limit concurrency
                    # to avoid overwhelming the server
                    max_concurrent_cleanups = min(5, len(orphan_sandboxes))
                    semaphore = asyncio.Semaphore(max_concurrent_cleanups)
                    
                    async def cleanup_with_semaphore(orphan):
                        async with semaphore:
                            return await self._stop_orphan_sandbox(orphan)
                    
                    cleanup_tasks = []
                    for orphan in orphan_sandboxes:
                        cleanup_tasks.append(cleanup_with_semaphore(orphan))
                    
                    # Wait for all cleanup tasks to complete
                    results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
                    
                    # Count successful cleanups and log any errors
                    for i, result in enumerate(results):
                        orphan = orphan_sandboxes[i]
                        orphan_key = f"{orphan['namespace']}/{orphan['name']}"
                        
                        if isinstance(result, Exception):
                            failed_count += 1
                            logger.error(
                                f"Failed to clean orphan sandbox {orphan_key}: {result}",
                                exc_info=result
                            )
                        else:
                            cleaned_count += 1
                            logger.info(f"Successfully cleaned orphan sandbox: {orphan_key}")
                    
                    # Log summary of cleanup results
                    if failed_count > 0:
                        logger.warning(
                            f"Orphan cleanup completed with some failures: "
                            f"{cleaned_count} cleaned, {failed_count} failed"
                        )
                else:
                    logger.debug("No orphan sandboxes found")
                
                # Update final metrics
                metrics.metadata.update({
                    'cleaned_count': cleaned_count,
                    'failed_count': failed_count
                })
                
                cleanup_time = time.time() - start_time
                log_resource_event(
                    logger,
                    "orphan_cleanup_completed",
                    "sandbox",
                    cleaned_count=cleaned_count,
                    failed_count=failed_count,
                    cleanup_time_ms=int(cleanup_time * 1000)
                )
                
                return cleaned_count
                
            except Exception as e:
                logger.error(f"Error during orphan sandbox cleanup: {e}", exc_info=True)
                return 0
    
    def get_resource_health_status(self) -> Dict[str, any]:
        """
        Get health status information for resource management.
        
        Returns:
            Dict[str, any]: Health status information including task status,
                          resource utilization, and any issues detected
        """
        return {
            'orphan_cleanup_task_running': (
                self._orphan_cleanup_task is not None and 
                not self._orphan_cleanup_task.done()
            ),
            'orphan_cleanup_task_healthy': self.is_orphan_cleanup_healthy(),
            'orphan_cleanup_interval': self._config.orphan_cleanup_interval,
            'max_concurrent_sessions': self._config.max_concurrent_sessions,
            'max_total_memory_mb': self._config.max_total_memory_mb,
            'manager_uptime_seconds': int(time.time() - self._start_time),
            'last_cleanup_time': self._last_cleanup_time,
            'total_cleanup_cycles': self._total_cleanup_cycles,
            'total_orphans_cleaned': self._total_orphans_cleaned,
            'last_cleanup_duration_seconds': self._last_cleanup_duration,
            'cleanup_errors': self._cleanup_errors
        }
    
    def is_orphan_cleanup_healthy(self) -> bool:
        """
        Check if the orphan cleanup system is running properly.
        
        Returns:
            bool: True if orphan cleanup task is running and healthy
        """
        if self._orphan_cleanup_task is None:
            return False
        
        if self._orphan_cleanup_task.done():
            # Task completed, check if it was cancelled or had an error
            if self._orphan_cleanup_task.cancelled():
                logger.warning("Orphan cleanup task was cancelled")
                return False
            
            try:
                # This will raise an exception if the task failed
                self._orphan_cleanup_task.result()
                logger.warning("Orphan cleanup task completed unexpectedly")
                return False
            except Exception as e:
                logger.error(f"Orphan cleanup task failed: {e}")
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
            'orphan_cleanup_task_exists': self._orphan_cleanup_task is not None,
            'orphan_cleanup_task_healthy': self.is_orphan_cleanup_healthy(),
            'orphan_cleanup_interval_seconds': self._config.orphan_cleanup_interval,
            'manager_uptime_seconds': time.time() - self._start_time,
            'total_cleanup_cycles': self._total_cleanup_cycles,
            'total_orphans_cleaned': self._total_orphans_cleaned,
            'cleanup_errors': self._cleanup_errors,
            'last_cleanup_time': self._last_cleanup_time,
            'last_cleanup_duration_seconds': self._last_cleanup_duration
        }
        
        if self._orphan_cleanup_task is not None:
            task_info.update({
                'orphan_cleanup_task_done': self._orphan_cleanup_task.done(),
                'orphan_cleanup_task_cancelled': self._orphan_cleanup_task.cancelled(),
            })
            
            if self._orphan_cleanup_task.done():
                try:
                    # Try to get the result to check for exceptions
                    self._orphan_cleanup_task.result()
                    task_info['orphan_cleanup_task_result'] = 'completed_normally'
                except asyncio.CancelledError:
                    task_info['orphan_cleanup_task_result'] = 'cancelled'
                except Exception as e:
                    task_info['orphan_cleanup_task_result'] = 'failed'
                    task_info['orphan_cleanup_task_error'] = str(e)
            else:
                task_info['orphan_cleanup_task_result'] = 'running'
        
        return task_info
    
    async def restart_orphan_cleanup_if_needed(self) -> bool:
        """
        Restart the orphan cleanup task if it's not running properly.
        
        Returns:
            bool: True if cleanup was restarted, False if it was already healthy
        """
        if self.is_orphan_cleanup_healthy():
            return False
        
        logger.warning("Orphan cleanup task is not healthy, restarting...")
        
        # Cancel existing task if it exists
        if self._orphan_cleanup_task:
            self._orphan_cleanup_task.cancel()
            try:
                await self._orphan_cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Start new cleanup task
        self._orphan_cleanup_task = asyncio.create_task(self._orphan_cleanup_loop())
        logger.info("Orphan cleanup task restarted")
        return True
    
    def get_orphan_cleanup_stats(self) -> Dict[str, any]:
        """
        Get detailed statistics about orphan cleanup operations.
        
        Returns:
            Dict[str, any]: Detailed orphan cleanup statistics
        """
        return {
            'total_cleanup_cycles': self._total_cleanup_cycles,
            'total_orphans_cleaned': self._total_orphans_cleaned,
            'cleanup_errors': self._cleanup_errors,
            'last_cleanup_time': self._last_cleanup_time,
            'last_cleanup_duration_seconds': self._last_cleanup_duration,
            'cleanup_interval_seconds': self._config.orphan_cleanup_interval,
            'average_orphans_per_cycle': (
                self._total_orphans_cleaned / max(1, self._total_cleanup_cycles)
            ),
            'cleanup_success_rate': (
                (self._total_cleanup_cycles - self._cleanup_errors) / max(1, self._total_cleanup_cycles)
            ) if self._total_cleanup_cycles > 0 else 1.0
        }
    
    async def get_running_sandboxes_info(self) -> Dict[str, any]:
        """
        Get detailed information about all running sandboxes.
        
        This method provides comprehensive information about sandboxes
        running on the server, including resource usage and orphan status.
        
        Returns:
            Dict[str, any]: Information about running sandboxes including
                          total count, orphan count, and detailed listings
        """
        try:
            logger.debug("Getting detailed running sandbox information")
            
            # Get all running sandboxes from server
            running_sandboxes = await self._get_running_sandboxes()
            
            # Get active sessions from session manager
            active_sessions = await self._session_manager.get_sessions()
            active_sandbox_names = set()
            
            for session in active_sessions:
                if session.status != SessionStatus.STOPPED:
                    sandbox_key = f"{session.namespace}/{session.sandbox_name}"
                    active_sandbox_names.add(sandbox_key)
            
            # Categorize sandboxes
            managed_sandboxes = []
            orphan_sandboxes = []
            
            for sandbox in running_sandboxes:
                sandbox_key = f"{sandbox['namespace']}/{sandbox['name']}"
                sandbox_info = {
                    'namespace': sandbox['namespace'],
                    'name': sandbox['name'],
                    'key': sandbox_key,
                    'cpu_usage': sandbox.get('cpu_usage'),
                    'memory_usage': sandbox.get('memory_usage'),
                    'disk_usage': sandbox.get('disk_usage')
                }
                
                if sandbox_key in active_sandbox_names:
                    managed_sandboxes.append(sandbox_info)
                else:
                    orphan_sandboxes.append(sandbox_info)
            
            # Calculate resource usage totals
            total_memory_usage = sum(
                s.get('memory_usage', 0) or 0 for s in running_sandboxes
            )
            total_cpu_usage = sum(
                s.get('cpu_usage', 0) or 0 for s in running_sandboxes
            )
            total_disk_usage = sum(
                s.get('disk_usage', 0) or 0 for s in running_sandboxes
            )
            
            return {
                'total_running_sandboxes': len(running_sandboxes),
                'managed_sandboxes_count': len(managed_sandboxes),
                'orphan_sandboxes_count': len(orphan_sandboxes),
                'active_sessions_count': len(active_sandbox_names),
                'resource_usage': {
                    'total_memory_mb': total_memory_usage,
                    'total_cpu_percent': total_cpu_usage,
                    'total_disk_bytes': total_disk_usage
                },
                'managed_sandboxes': managed_sandboxes,
                'orphan_sandboxes': orphan_sandboxes,
                'query_timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error getting running sandbox information: {e}", exc_info=True)
            return {
                'error': str(e),
                'total_running_sandboxes': 0,
                'managed_sandboxes_count': 0,
                'orphan_sandboxes_count': 0,
                'active_sessions_count': 0,
                'query_timestamp': time.time()
            }
    
    async def _evict_lru_sessions(self, min_sessions_to_evict: int, min_memory_to_free_mb: int) -> int:
        """
        Evict least recently used sessions to free up resources.
        
        This method implements LRU eviction by:
        1. Getting all active sessions that can be evicted
        2. Sorting them by last_accessed time (oldest first)
        3. Evicting sessions until resource requirements are met
        
        Args:
            min_sessions_to_evict: Minimum number of sessions to evict
            min_memory_to_free_mb: Minimum amount of memory to free in MB
            
        Returns:
            int: Number of sessions actually evicted
        """
        try:
            logger.info(
                f"Starting LRU eviction: min_sessions={min_sessions_to_evict}, "
                f"min_memory_mb={min_memory_to_free_mb}"
            )
            
            # Get all sessions from session manager
            all_sessions = await self._session_manager.get_sessions()
            
            # Filter sessions that can be evicted and sort by last_accessed (LRU first)
            evictable_sessions = []
            for session_info in all_sessions:
                # Get the actual managed session to check if it can be evicted
                managed_session = self._session_manager._sessions.get(session_info.session_id)
                if managed_session and managed_session.can_be_evicted():
                    evictable_sessions.append((session_info, managed_session))
            
            # Sort by last_accessed time (oldest first for LRU)
            evictable_sessions.sort(key=lambda x: x[0].last_accessed)
            
            logger.info(
                f"Found {len(evictable_sessions)} evictable sessions out of {len(all_sessions)} total sessions"
            )
            
            if not evictable_sessions:
                logger.warning("No sessions available for eviction")
                return 0
            
            # Evict sessions until requirements are met
            evicted_count = 0
            memory_freed_mb = 0
            
            for session_info, managed_session in evictable_sessions:
                # Check if we've met our eviction requirements
                if (evicted_count >= min_sessions_to_evict and 
                    memory_freed_mb >= min_memory_to_free_mb):
                    break
                
                try:
                    logger.info(
                        f"Evicting LRU session {session_info.session_id} "
                        f"(last_accessed: {session_info.last_accessed}, "
                        f"flavor: {session_info.flavor.value}, "
                        f"status: {session_info.status.value})"
                    )
                    
                    # Stop the session
                    success = await self._session_manager.stop_session(session_info.session_id)
                    
                    if success:
                        evicted_count += 1
                        memory_freed_mb += session_info.flavor.get_memory_mb()
                        
                        log_resource_event(
                            logger,
                            "session_evicted_lru",
                            "session",
                            session_id=session_info.session_id,
                            flavor=session_info.flavor.value,
                            memory_freed_mb=session_info.flavor.get_memory_mb(),
                            last_accessed=session_info.last_accessed.isoformat()
                        )
                    else:
                        logger.warning(f"Failed to evict session {session_info.session_id}")
                        
                except Exception as e:
                    logger.error(
                        f"Error evicting session {session_info.session_id}: {e}",
                        exc_info=True
                    )
                    continue
            
            logger.info(
                f"LRU eviction completed: evicted {evicted_count} sessions, "
                f"freed {memory_freed_mb}MB memory"
            )
            
            return evicted_count
            
        except Exception as e:
            logger.error(f"Error during LRU eviction: {e}", exc_info=True)
            return 0
    
    async def force_orphan_cleanup(self) -> int:
        """
        Manually trigger orphan sandbox cleanup.
        
        This method can be called to immediately clean up orphan sandboxes
        without waiting for the next scheduled cleanup cycle.
        
        Returns:
            int: Number of orphan sandboxes that were cleaned up
        """
        logger.info("Manual orphan cleanup triggered")
        try:
            start_time = time.time()
            cleaned_count = await self.cleanup_orphan_sandboxes()
            
            # Update statistics
            self._last_cleanup_time = time.time()
            self._last_cleanup_duration = self._last_cleanup_time - start_time
            self._total_cleanup_cycles += 1
            self._total_orphans_cleaned += cleaned_count
            
            logger.info(
                f"Manual orphan cleanup completed: {cleaned_count} orphans cleaned in {self._last_cleanup_duration:.2f}s"
            )
            
            return cleaned_count
        except Exception as e:
            self._cleanup_errors += 1
            logger.error(f"Error during manual orphan cleanup: {e}", exc_info=True)
            raise
    
    async def _orphan_cleanup_loop(self) -> None:
        """
        Background task that periodically cleans up orphaned sandboxes.
        
        This method runs continuously in the background, waking up at regular
        intervals to check for and clean up orphaned sandbox instances.
        """
        logger.info(
            f"Started orphan cleanup loop with interval {self._config.orphan_cleanup_interval}s"
        )
        
        while True:
            try:
                await asyncio.sleep(self._config.orphan_cleanup_interval)
                
                # Perform orphan cleanup
                start_time = time.time()
                cleaned = await self.cleanup_orphan_sandboxes()
                cleanup_time = time.time() - start_time
                
                # Update statistics
                self._total_cleanup_cycles += 1
                self._total_orphans_cleaned += cleaned
                self._last_cleanup_time = time.time()
                self._last_cleanup_duration = cleanup_time
                
                if cleaned > 0:
                    logger.info(
                        f"Orphan cleanup cycle #{self._total_cleanup_cycles}: "
                        f"cleaned {cleaned} orphans in {cleanup_time:.2f}s"
                    )
                else:
                    logger.debug(
                        f"Orphan cleanup cycle #{self._total_cleanup_cycles}: "
                        f"no orphans found (took {cleanup_time:.2f}s)"
                    )
                
                # Log periodic statistics every 10 cleanup cycles
                if self._total_cleanup_cycles % 10 == 0:
                    stats = self.get_orphan_cleanup_stats()
                    logger.info(
                        f"Orphan cleanup statistics (cycle #{self._total_cleanup_cycles}): "
                        f"total_cleaned={stats['total_orphans_cleaned']}, "
                        f"avg_per_cycle={stats['average_orphans_per_cycle']:.1f}, "
                        f"success_rate={stats['cleanup_success_rate']:.2%}, "
                        f"errors={stats['cleanup_errors']}"
                    )
                
            except asyncio.CancelledError:
                logger.info(
                    f"Orphan cleanup loop cancelled after {self._total_cleanup_cycles} cycles "
                    f"(total orphans cleaned: {self._total_orphans_cleaned})"
                )
                break
            except Exception as e:
                self._cleanup_errors += 1
                logger.error(
                    f"Error in orphan cleanup loop (cycle #{self._total_cleanup_cycles + 1}): {e}",
                    exc_info=True
                )
                # Continue running even if there's an error
                continue
    
    async def _get_running_sandboxes(self) -> List[Dict[str, str]]:
        """
        Get all running sandboxes from the microsandbox server.
        
        This method queries the server's JSON-RPC API to get a list of all currently
        running sandbox instances using the 'sandbox.metrics.get' method.
        
        Returns:
            List[Dict[str, str]]: List of sandbox information dictionaries
                                 containing 'namespace', 'name', and 'running' keys
        """
        try:
            logger.debug("Querying server for running sandboxes")
            
            # Prepare JSON-RPC request to get all sandbox metrics
            rpc_request = {
                "jsonrpc": "2.0",
                "method": "sandbox.metrics.get",
                "params": {
                    "namespace": "*",  # Get sandboxes from all namespaces
                    "sandbox": None    # Get all sandboxes (not just a specific one)
                },
                "id": 1
            }
            
            # Make the API call
            timeout = aiohttp.ClientTimeout(total=1800)  # 5 minute timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Content-Type": "application/json"
                }
                
                # Add API key if configured
                if self._config.api_key:
                    headers["Authorization"] = f"Bearer {self._config.api_key}"
                
                async with session.post(
                    f"{self._config.server_url}/api/v1/rpc",
                    json=rpc_request,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for JSON-RPC error
                        if "error" in data:
                            logger.error(f"RPC error getting sandbox metrics: {data['error']}")
                            return []
                        
                        # Extract sandbox list from response
                        result = data.get("result", {})
                        sandboxes = result.get("sandboxes", [])
                        
                        # Filter to only running sandboxes and convert to our format
                        running_sandboxes = []
                        for sandbox in sandboxes:
                            if sandbox.get("running", False):
                                running_sandboxes.append({
                                    "namespace": sandbox["namespace"],
                                    "name": sandbox["name"],
                                    "running": sandbox["running"],
                                    "cpu_usage": sandbox.get("cpu_usage"),
                                    "memory_usage": sandbox.get("memory_usage"),
                                    "disk_usage": sandbox.get("disk_usage")
                                })
                        
                        logger.debug(f"Found {len(running_sandboxes)} running sandboxes on server")
                        return running_sandboxes
                        
                    else:
                        logger.warning(
                            f"Failed to get sandbox metrics: HTTP {response.status} - {await response.text()}"
                        )
                        return []
            
        except asyncio.TimeoutError:
            logger.error("Timeout while querying server for running sandboxes")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"Network error getting running sandboxes from server: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting running sandboxes from server: {e}", exc_info=True)
            return []
    
    async def _stop_orphan_sandbox(self, sandbox_info: Dict[str, str]) -> None:
        """
        Stop an orphaned sandbox instance using the server's JSON-RPC API.
        
        This method calls the 'sandbox.stop' RPC method to cleanly stop
        the orphaned sandbox instance.
        
        Args:
            sandbox_info: Dictionary containing sandbox information with
                         'namespace' and 'name' keys
        """
        sandbox_key = f"{sandbox_info['namespace']}/{sandbox_info['name']}"
        
        try:
            logger.debug(f"Stopping orphan sandbox via RPC: {sandbox_key}")
            
            # Prepare JSON-RPC request to stop the sandbox
            rpc_request = {
                "jsonrpc": "2.0",
                "method": "sandbox.stop",
                "params": {
                    "sandbox": sandbox_info['name'],
                    "namespace": sandbox_info['namespace']
                },
                "id": 1
            }
            
            # Make the API call
            timeout = aiohttp.ClientTimeout(total=1800)  # 5 minute timeout for stop operations
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    "Content-Type": "application/json"
                }
                
                # Add API key if configured
                if self._config.api_key:
                    headers["Authorization"] = f"Bearer {self._config.api_key}"
                
                async with session.post(
                    f"{self._config.server_url}/api/v1/rpc",
                    json=rpc_request,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Check for JSON-RPC error
                        if "error" in data:
                            error_info = data["error"]
                            raise Exception(f"RPC error stopping sandbox: {error_info}")
                        
                        # Success - log the result
                        result = data.get("result", "")
                        logger.debug(f"Successfully stopped orphan sandbox {sandbox_key}: {result}")
                        
                    else:
                        response_text = await response.text()
                        raise Exception(f"HTTP {response.status}: {response_text}")
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout while stopping orphan sandbox {sandbox_key}")
            raise Exception(f"Timeout stopping sandbox {sandbox_key}")
        except aiohttp.ClientError as e:
            logger.error(f"Network error stopping orphan sandbox {sandbox_key}: {e}")
            raise Exception(f"Network error stopping sandbox {sandbox_key}: {e}")
        except Exception as e:
            logger.error(f"Failed to stop orphan sandbox {sandbox_key}: {e}", exc_info=True)
            raise