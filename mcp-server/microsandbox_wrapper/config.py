"""
Configuration management for the microsandbox wrapper.

This module handles all configuration aspects including environment variable
parsing, default value management, and configuration validation.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

from .models import SandboxFlavor, VolumeMapping
from .exceptions import ConfigurationError, log_error_with_context
import logging

logger = logging.getLogger(__name__)


@dataclass
class WrapperConfig:
    """
    Configuration settings for the microsandbox wrapper.
    
    This class centralizes all configuration options and provides
    methods for loading configuration from environment variables
    with proper validation and default value handling.
    """
    
    # Server configuration
    server_url: str = "http://127.0.0.1:5555"
    api_key: Optional[str] = None
    
    # Session configuration
    session_timeout: int = 3600  # 30 minutes in seconds
    max_concurrent_sessions: int = 10
    cleanup_interval: int = 60  # 1 minute in seconds
    
    # Sandbox configuration
    default_flavor: SandboxFlavor = SandboxFlavor.SMALL
    sandbox_start_timeout: float = 180.0  # 3 minutes in seconds
    default_execution_timeout: int = 1800  # 5 minutes in seconds
    
    # Resource configuration
    max_total_memory_mb: Optional[int] = None
    shared_volume_mappings: List[str] = field(default_factory=list)
    
    # Orphan cleanup configuration
    orphan_cleanup_interval: int = 600  # 10 minutes in seconds
    
    @classmethod
    def from_env(cls) -> 'WrapperConfig':
        """
        Create configuration from environment variables.
        
        This method reads configuration values from environment variables,
        applies proper type conversion, validates values, and provides
        sensible defaults for missing values.
        
        Environment Variables:
            MSB_SERVER_URL: Microsandbox server URL
            MSB_API_KEY: API key for authentication
            MSB_SESSION_TIMEOUT: Session timeout in seconds
            MSB_MAX_SESSIONS: Maximum concurrent sessions
            MSB_CLEANUP_INTERVAL: Session cleanup interval in seconds
            MSB_DEFAULT_FLAVOR: Default sandbox flavor (small/medium/large)
            MSB_SANDBOX_START_TIMEOUT: Sandbox startup timeout in seconds
            MSB_EXECUTION_TIMEOUT: Default execution timeout in seconds
            MSB_MAX_TOTAL_MEMORY_MB: Maximum total memory allocation in MB
            MSB_SHARED_VOLUME_PATH: Shared volume mappings (JSON array or comma-separated)
            MSB_ORPHAN_CLEANUP_INTERVAL: Orphan cleanup interval in seconds
            
        Returns:
            WrapperConfig: Configuration instance with values from environment
            
        Raises:
            ConfigurationError: If configuration validation fails
        """
        try:
            # Parse shared volume mappings with support for JSON array format
            shared_volume_mappings = cls._parse_shared_volume_mappings()
            
            # Parse and validate flavor
            default_flavor = cls._parse_default_flavor()
            
            # Parse numeric values with validation
            session_timeout = cls._parse_positive_int('MSB_SESSION_TIMEOUT', 1800)
            max_concurrent_sessions = cls._parse_positive_int('MSB_MAX_SESSIONS', 10)
            cleanup_interval = cls._parse_positive_int('MSB_CLEANUP_INTERVAL', 60)
            sandbox_start_timeout = cls._parse_positive_float('MSB_SANDBOX_START_TIMEOUT', 180.0)
            default_execution_timeout = cls._parse_positive_int('MSB_EXECUTION_TIMEOUT', 300)
            orphan_cleanup_interval = cls._parse_positive_int('MSB_ORPHAN_CLEANUP_INTERVAL', 600)
            
            # Parse optional memory limit
            max_total_memory_mb = None
            if os.getenv('MSB_MAX_TOTAL_MEMORY_MB'):
                max_total_memory_mb = cls._parse_positive_int('MSB_MAX_TOTAL_MEMORY_MB', None)
            
            config = cls(
                server_url=os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555'),
                api_key=os.getenv('MSB_API_KEY'),
                session_timeout=session_timeout,
                max_concurrent_sessions=max_concurrent_sessions,
                cleanup_interval=cleanup_interval,
                default_flavor=default_flavor,
                sandbox_start_timeout=sandbox_start_timeout,
                default_execution_timeout=default_execution_timeout,
                max_total_memory_mb=max_total_memory_mb,
                shared_volume_mappings=shared_volume_mappings,
                orphan_cleanup_interval=orphan_cleanup_interval
            )
            
            # Validate the complete configuration
            config._validate()
            
            return config
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                log_error_with_context(logger, e, {"operation": "config_loading"})
                raise
            error = ConfigurationError(
                message=f"Failed to load configuration from environment: {str(e)}",
                original_error=e
            )
            log_error_with_context(logger, error, {"operation": "config_loading"})
            raise error
    
    @classmethod
    def _parse_shared_volume_mappings(cls) -> List[str]:
        """
        Parse shared volume mappings from environment variable.
        
        Supports both JSON array format and comma-separated format:
        - JSON: ["host1:container1", "host2:container2"]
        - Comma-separated: "host1:container1,host2:container2"
        
        Returns:
            List[str]: List of volume mapping strings
            
        Raises:
            ConfigurationError: If parsing fails or format is invalid
        """
        volume_path_env = os.getenv('MSB_SHARED_VOLUME_PATH')
        if not volume_path_env:
            return []
        
        volume_path_env = volume_path_env.strip()
        if not volume_path_env:
            return []
        
        try:
            # Try to parse as JSON array first
            if volume_path_env.startswith('[') and volume_path_env.endswith(']'):
                parsed_mappings = json.loads(volume_path_env)
                if not isinstance(parsed_mappings, list):
                    raise ConfigurationError(
                        "MSB_SHARED_VOLUME_PATH JSON must be an array of strings"
                    )
                
                # Validate that all items are strings
                for i, mapping in enumerate(parsed_mappings):
                    if not isinstance(mapping, str):
                        raise ConfigurationError(
                            f"MSB_SHARED_VOLUME_PATH item {i} must be a string, got {type(mapping).__name__}"
                        )
                
                # Validate volume mapping format
                validated_mappings = []
                for mapping in parsed_mappings:
                    mapping = mapping.strip()
                    if mapping:
                        # Validate format by attempting to parse
                        try:
                            VolumeMapping.from_string(mapping)
                            validated_mappings.append(mapping)
                        except ValueError as e:
                            raise ConfigurationError(f"Invalid volume mapping in MSB_SHARED_VOLUME_PATH: {e}")
                
                return validated_mappings
            
            else:
                # Parse as comma-separated values
                mappings = [mapping.strip() for mapping in volume_path_env.split(',')]
                validated_mappings = []
                
                for mapping in mappings:
                    if mapping:
                        # Validate format by attempting to parse
                        try:
                            VolumeMapping.from_string(mapping)
                            validated_mappings.append(mapping)
                        except ValueError as e:
                            raise ConfigurationError(f"Invalid volume mapping in MSB_SHARED_VOLUME_PATH: {e}")
                
                return validated_mappings
                
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON format in MSB_SHARED_VOLUME_PATH: {e}"
            )
    
    @classmethod
    def _parse_default_flavor(cls) -> SandboxFlavor:
        """
        Parse and validate the default sandbox flavor.
        
        Returns:
            SandboxFlavor: Parsed flavor enum value
            
        Raises:
            ConfigurationError: If flavor value is invalid
        """
        flavor_str = os.getenv('MSB_DEFAULT_FLAVOR', 'small').lower().strip()
        
        try:
            return SandboxFlavor(flavor_str)
        except ValueError:
            valid_flavors = [f.value for f in SandboxFlavor]
            raise ConfigurationError(
                f"Invalid MSB_DEFAULT_FLAVOR '{flavor_str}'. "
                f"Valid options are: {', '.join(valid_flavors)}"
            )
    
    @classmethod
    def _parse_positive_int(cls, env_var: str, default: Optional[int]) -> int:
        """
        Parse a positive integer from environment variable.
        
        Args:
            env_var: Environment variable name
            default: Default value if not set
            
        Returns:
            int: Parsed positive integer
            
        Raises:
            ConfigurationError: If value is not a positive integer
        """
        value_str = os.getenv(env_var)
        if not value_str:
            if default is None:
                raise ConfigurationError(f"Required environment variable {env_var} is not set")
            return default
        
        try:
            value = int(value_str.strip())
            if value <= 0:
                raise ConfigurationError(f"{env_var} must be a positive integer, got {value}")
            return value
        except ValueError:
            raise ConfigurationError(f"{env_var} must be a valid integer, got '{value_str}'")
    
    @classmethod
    def _parse_positive_float(cls, env_var: str, default: float) -> float:
        """
        Parse a positive float from environment variable.
        
        Args:
            env_var: Environment variable name
            default: Default value if not set
            
        Returns:
            float: Parsed positive float
            
        Raises:
            ConfigurationError: If value is not a positive float
        """
        value_str = os.getenv(env_var)
        if not value_str:
            return default
        
        try:
            value = float(value_str.strip())
            if value <= 0:
                raise ConfigurationError(f"{env_var} must be a positive number, got {value}")
            return value
        except ValueError:
            raise ConfigurationError(f"{env_var} must be a valid number, got '{value_str}'")
    
    def _validate(self) -> None:
        """
        Validate the complete configuration for consistency and correctness.
        
        Raises:
            ConfigurationError: If validation fails
        """
        # Validate server URL format
        if not self.server_url.startswith(('http://', 'https://')):
            raise ConfigurationError(
                f"Invalid server URL format: {self.server_url}. "
                "Must start with http:// or https://"
            )
        
        # Validate timeout relationships
        if self.cleanup_interval >= self.session_timeout:
            raise ConfigurationError(
                f"Cleanup interval ({self.cleanup_interval}s) must be less than "
                f"session timeout ({self.session_timeout}s)"
            )
        
        # Validate memory limits
        if self.max_total_memory_mb is not None:
            min_memory_needed = self.default_flavor.get_memory_mb()
            if self.max_total_memory_mb < min_memory_needed:
                raise ConfigurationError(
                    f"Max total memory ({self.max_total_memory_mb}MB) is less than "
                    f"minimum needed for default flavor ({min_memory_needed}MB)"
                )
        
        # Validate session limits
        if self.max_concurrent_sessions < 1:
            raise ConfigurationError("Max concurrent sessions must be at least 1")
        
        # Validate shared volume mappings format
        for mapping_str in self.shared_volume_mappings:
            try:
                VolumeMapping.from_string(mapping_str)
            except ValueError as e:
                raise ConfigurationError(f"Invalid volume mapping '{mapping_str}': {e}")
    
    def get_parsed_volume_mappings(self) -> List[VolumeMapping]:
        """
        Get parsed volume mappings as VolumeMapping objects.
        
        Returns:
            List[VolumeMapping]: List of parsed volume mappings
        """
        return [VolumeMapping.from_string(mapping) for mapping in self.shared_volume_mappings]
    
    def __str__(self) -> str:
        """
        String representation of configuration (excluding sensitive data).
        
        Returns:
            str: Configuration summary
        """
        return (
            f"WrapperConfig("
            f"server_url={self.server_url}, "
            f"api_key={'***' if self.api_key else None}, "
            f"session_timeout={self.session_timeout}s, "
            f"max_sessions={self.max_concurrent_sessions}, "
            f"default_flavor={self.default_flavor.value}, "
            f"volume_mappings={len(self.shared_volume_mappings)} mappings"
            f")"
        )