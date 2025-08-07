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
    
    # LRU eviction configuration
    enable_lru_eviction: bool = True  # Enable LRU eviction when resource limits are reached
    
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
            MSB_ENABLE_LRU_EVICTION: Enable LRU eviction when resource limits are reached (true/false)
            
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
            
            # Parse LRU eviction setting
            enable_lru_eviction = cls._parse_boolean('MSB_ENABLE_LRU_EVICTION', True)
            
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
                orphan_cleanup_interval=orphan_cleanup_interval,
                enable_lru_eviction=enable_lru_eviction
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
        
        Supports multiple formats:
        - JSON array: ["host1:container1", "host2:container2"]
        - Comma-separated: "host1:container1,host2:container2"
        - Single mapping: "host1:container1"
        - Empty/disabled: empty string or None
        
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
        
        logger.debug(f"Parsing MSB_SHARED_VOLUME_PATH: {repr(volume_path_env)}")
        
        try:
            # Check if it looks like JSON (array or object)
            if volume_path_env.startswith('[') or volume_path_env.startswith('{'):
                # For JSON objects, provide helpful error message
                if volume_path_env.startswith('{'):
                    raise ConfigurationError(
                        f"MSB_SHARED_VOLUME_PATH must be an array of strings, not a JSON object. "
                        f"Got: {repr(volume_path_env)}\n"
                        f"Example: ['./data:/workspace', './shared:/sandbox/shared']"
                    )
                
                # Handle JSON arrays
                if not volume_path_env.endswith(']'):
                    raise ConfigurationError(
                        f"MSB_SHARED_VOLUME_PATH appears to be JSON array but is malformed: "
                        f"missing closing bracket. Got: {repr(volume_path_env)}"
                    )
                
                # Additional validation for common JSON errors
                if volume_path_env.count('[') != volume_path_env.count(']'):
                    raise ConfigurationError(
                        f"MSB_SHARED_VOLUME_PATH has mismatched brackets. Got: {repr(volume_path_env)}"
                    )
                
                try:
                    parsed_mappings = json.loads(volume_path_env)
                except json.JSONDecodeError as e:
                    # Provide more helpful error messages for common JSON mistakes
                    error_msg = str(e)
                    helpful_msg = cls._get_helpful_json_error_message(volume_path_env, error_msg)
                    raise ConfigurationError(
                        f"Invalid JSON format in MSB_SHARED_VOLUME_PATH: {error_msg}\n{helpful_msg}"
                    )
                
                if not isinstance(parsed_mappings, list):
                    raise ConfigurationError(
                        f"MSB_SHARED_VOLUME_PATH JSON must be an array of strings, got {type(parsed_mappings).__name__}. "
                        f"Example: ['./data:/workspace', './shared:/sandbox/shared']"
                    )
                
                # Validate that all items are strings
                for i, mapping in enumerate(parsed_mappings):
                    if not isinstance(mapping, str):
                        raise ConfigurationError(
                            f"MSB_SHARED_VOLUME_PATH item {i} must be a string, got {type(mapping).__name__}. "
                            f"All volume mappings must be strings like 'host_path:container_path'"
                        )
                
                # Validate volume mapping format
                validated_mappings = cls._validate_volume_mappings(parsed_mappings)
                logger.debug(f"Successfully parsed JSON volume mappings: {validated_mappings}")
                return validated_mappings
            
            else:
                # Parse as comma-separated values or single value
                if ',' in volume_path_env:
                    mappings = [mapping.strip() for mapping in volume_path_env.split(',')]
                    logger.debug(f"Parsing as comma-separated: {mappings}")
                else:
                    mappings = [volume_path_env.strip()]
                    logger.debug(f"Parsing as single mapping: {mappings}")
                
                validated_mappings = cls._validate_volume_mappings(mappings)
                logger.debug(f"Successfully parsed volume mappings: {validated_mappings}")
                return validated_mappings
                
        except ConfigurationError:
            # Re-raise ConfigurationError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ConfigurationError(
                f"Unexpected error parsing MSB_SHARED_VOLUME_PATH '{volume_path_env}': {str(e)}"
            )
    
    @classmethod
    def _validate_volume_mappings(cls, mappings: List[str]) -> List[str]:
        """
        Validate volume mapping format and return cleaned mappings.
        
        Args:
            mappings: List of volume mapping strings to validate
            
        Returns:
            List[str]: List of validated volume mapping strings
            
        Raises:
            ConfigurationError: If any mapping is invalid
        """
        validated_mappings = []
        
        for i, mapping in enumerate(mappings):
            mapping = mapping.strip()
            if not mapping:
                continue  # Skip empty mappings
            
            # Validate format by attempting to parse
            try:
                VolumeMapping.from_string(mapping)
                validated_mappings.append(mapping)
            except ValueError as e:
                raise ConfigurationError(
                    f"Invalid volume mapping at position {i} in MSB_SHARED_VOLUME_PATH: {e}\n"
                    f"Got: '{mapping}'\n"
                    f"Expected format: 'host_path:container_path' (e.g., './data:/workspace')"
                )
        
        return validated_mappings
    
    @classmethod
    def _get_helpful_json_error_message(cls, value: str, error_msg: str) -> str:
        """
        Generate helpful error message for common JSON parsing errors.
        
        Args:
            value: The original value that failed to parse
            error_msg: The original JSON error message
            
        Returns:
            str: Helpful error message with suggestions
        """
        suggestions = []
        
        # Check for common issues
        if 'Expecting value' in error_msg and value.count('"') == 0:
            suggestions.append("- Strings in JSON arrays must be quoted with double quotes")
            suggestions.append("  Example: ['/path/to/host:/path/in/container'] should be [\"/path/to/host:/path/in/container\"]")
        
        if 'Expecting \',' in error_msg:
            suggestions.append("- Check that the JSON array is properly closed with ']'")
            suggestions.append("- Multiple items in JSON arrays must be separated by commas")
        
        if value.count('"') % 2 != 0:
            suggestions.append("- Check that all quotes are properly paired")
        
        if not suggestions:
            suggestions = [
                "- Ensure the value is valid JSON array format: [\"item1\", \"item2\"]",
                "- Or use comma-separated format: item1,item2",
                "- Or use single value format: item1"
            ]
        
        return "Helpful suggestions:\n" + "\n".join(suggestions)
    
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
    def _parse_boolean(cls, env_var: str, default: bool) -> bool:
        """
        Parse a boolean from environment variable.
        
        Args:
            env_var: Environment variable name
            default: Default value if not set
            
        Returns:
            bool: Parsed boolean value
            
        Raises:
            ConfigurationError: If value is not a valid boolean
        """
        value_str = os.getenv(env_var)
        if not value_str:
            return default
        
        value_str = value_str.strip().lower()
        if value_str in ('true', '1', 'yes', 'on', 'enabled'):
            return True
        elif value_str in ('false', '0', 'no', 'off', 'disabled'):
            return False
        else:
            raise ConfigurationError(
                f"{env_var} must be a valid boolean value (true/false, 1/0, yes/no, on/off, enabled/disabled), "
                f"got '{value_str}'"
            )
    
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