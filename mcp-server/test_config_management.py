"""
Unit tests for configuration management.

Tests the WrapperConfig class and related functionality including
environment variable parsing, validation, and VolumeMapping handling.
"""

import json
import os
import pytest
from unittest.mock import patch

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor, VolumeMapping
from microsandbox_wrapper.exceptions import ConfigurationError


class TestWrapperConfigFromEnv:
    """Test WrapperConfig.from_env() method and environment variable parsing."""
    
    def test_from_env_with_defaults(self):
        """Test configuration creation with all default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.server_url == "http://127.0.0.1:5555"
            assert config.api_key is None
            assert config.session_timeout == 1800
            assert config.max_concurrent_sessions == 10
            assert config.cleanup_interval == 60
            assert config.default_flavor == SandboxFlavor.SMALL
            assert config.sandbox_start_timeout == 180.0
            assert config.default_execution_timeout == 300
            assert config.max_total_memory_mb is None
            assert config.shared_volume_mappings == []
            assert config.orphan_cleanup_interval == 600
    
    def test_from_env_with_all_values_set(self):
        """Test configuration creation with all environment variables set."""
        env_vars = {
            'MSB_SERVER_URL': 'https://custom-server.com:8080',
            'MSB_API_KEY': 'test-api-key-123',
            'MSB_SESSION_TIMEOUT': '3600',
            'MSB_MAX_SESSIONS': '20',
            'MSB_CLEANUP_INTERVAL': '120',
            'MSB_DEFAULT_FLAVOR': 'large',
            'MSB_SANDBOX_START_TIMEOUT': '300.5',
            'MSB_EXECUTION_TIMEOUT': '600',
            'MSB_MAX_TOTAL_MEMORY_MB': '8192',
            'MSB_SHARED_VOLUME_PATH': '/host/path:/container/path,/host2:/container2',
            'MSB_ORPHAN_CLEANUP_INTERVAL': '900'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.server_url == 'https://custom-server.com:8080'
            assert config.api_key == 'test-api-key-123'
            assert config.session_timeout == 3600
            assert config.max_concurrent_sessions == 20
            assert config.cleanup_interval == 120
            assert config.default_flavor == SandboxFlavor.LARGE
            assert config.sandbox_start_timeout == 300.5
            assert config.default_execution_timeout == 600
            assert config.max_total_memory_mb == 8192
            assert config.shared_volume_mappings == ['/host/path:/container/path', '/host2:/container2']
            assert config.orphan_cleanup_interval == 900
    
    def test_from_env_with_json_volume_mappings(self):
        """Test parsing volume mappings in JSON array format."""
        env_vars = {
            'MSB_SHARED_VOLUME_PATH': '["./data:/app/data", "/tmp/shared:/tmp/container"]'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.shared_volume_mappings == ['./data:/app/data', '/tmp/shared:/tmp/container']
    
    def test_from_env_with_empty_json_array(self):
        """Test parsing empty JSON array for volume mappings."""
        env_vars = {
            'MSB_SHARED_VOLUME_PATH': '[]'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.shared_volume_mappings == []
    
    def test_from_env_with_whitespace_handling(self):
        """Test that whitespace is properly handled in environment variables."""
        env_vars = {
            'MSB_SERVER_URL': 'http://test.com',  # Valid URL without extra whitespace
            'MSB_DEFAULT_FLAVOR': '  medium  ',
            'MSB_SESSION_TIMEOUT': '  1200  ',
            'MSB_SHARED_VOLUME_PATH': '  /host:/container  ,  /host2:/container2  '
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.server_url == 'http://test.com'
            assert config.default_flavor == SandboxFlavor.MEDIUM
            assert config.session_timeout == 1200
            assert config.shared_volume_mappings == ['/host:/container', '/host2:/container2']


class TestWrapperConfigValidation:
    """Test configuration validation logic."""
    
    def test_invalid_server_url_format(self):
        """Test validation fails for invalid server URL format."""
        env_vars = {
            'MSB_SERVER_URL': 'invalid-url-format'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Invalid server URL format" in str(exc_info.value)
    
    def test_cleanup_interval_greater_than_session_timeout(self):
        """Test validation fails when cleanup interval >= session timeout."""
        env_vars = {
            'MSB_SESSION_TIMEOUT': '300',
            'MSB_CLEANUP_INTERVAL': '300'  # Equal to session timeout
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Cleanup interval" in str(exc_info.value)
            assert "must be less than session timeout" in str(exc_info.value)
    
    def test_max_memory_less_than_default_flavor_requirement(self):
        """Test validation fails when max memory is less than default flavor needs."""
        env_vars = {
            'MSB_DEFAULT_FLAVOR': 'large',  # Needs 4096MB
            'MSB_MAX_TOTAL_MEMORY_MB': '2048'  # Less than required
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Max total memory" in str(exc_info.value)
            assert "less than minimum needed" in str(exc_info.value)
    
    def test_zero_max_concurrent_sessions(self):
        """Test validation fails for zero max concurrent sessions."""
        env_vars = {
            'MSB_MAX_SESSIONS': '0'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "must be a positive integer" in str(exc_info.value)
    
    def test_invalid_volume_mapping_format(self):
        """Test validation fails for invalid volume mapping format."""
        env_vars = {
            'MSB_SHARED_VOLUME_PATH': 'invalid-mapping-without-colon'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Invalid volume mapping" in str(exc_info.value)


class TestWrapperConfigErrorHandling:
    """Test error handling in configuration parsing."""
    
    def test_invalid_integer_values(self):
        """Test error handling for invalid integer values."""
        test_cases = [
            ('MSB_SESSION_TIMEOUT', 'not-a-number'),
            ('MSB_MAX_SESSIONS', '10.5'),  # Float instead of int
            ('MSB_CLEANUP_INTERVAL', '-60'),  # Negative value
            ('MSB_EXECUTION_TIMEOUT', '0'),  # Zero value
        ]
        
        for env_var, invalid_value in test_cases:
            env_vars = {env_var: invalid_value}
            
            with patch.dict(os.environ, env_vars, clear=True):
                with pytest.raises(ConfigurationError) as exc_info:
                    WrapperConfig.from_env()
                
                assert env_var in str(exc_info.value)
    
    def test_invalid_float_values(self):
        """Test error handling for invalid float values."""
        test_cases = [
            ('MSB_SANDBOX_START_TIMEOUT', 'not-a-number'),
            ('MSB_SANDBOX_START_TIMEOUT', '-180.0'),  # Negative value
            ('MSB_SANDBOX_START_TIMEOUT', '0'),  # Zero value
        ]
        
        for env_var, invalid_value in test_cases:
            env_vars = {env_var: invalid_value}
            
            with patch.dict(os.environ, env_vars, clear=True):
                with pytest.raises(ConfigurationError) as exc_info:
                    WrapperConfig.from_env()
                
                assert env_var in str(exc_info.value)
    
    def test_invalid_flavor_value(self):
        """Test error handling for invalid flavor values."""
        env_vars = {
            'MSB_DEFAULT_FLAVOR': 'invalid-flavor'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Invalid MSB_DEFAULT_FLAVOR" in str(exc_info.value)
            assert "small, medium, large" in str(exc_info.value)
    
    def test_invalid_json_volume_mappings(self):
        """Test error handling for invalid JSON in volume mappings."""
        test_cases = [
            ('[1, 2, 3]', 'must be a string'),  # Array of numbers instead of strings
            ('["valid", 123]', 'must be a string'),  # Mixed types in array
            ('["invalid-format"]', 'Invalid volume mapping'),  # String without colon
            ('[":/empty-host"]', 'Invalid volume mapping'),  # Empty host path
            ('["/host:"]', 'Invalid volume mapping'),  # Empty container path
        ]
        
        for invalid_json, expected_error in test_cases:
            env_vars = {
                'MSB_SHARED_VOLUME_PATH': invalid_json
            }
            
            with patch.dict(os.environ, env_vars, clear=True):
                with pytest.raises(ConfigurationError) as exc_info:
                    WrapperConfig.from_env()
                
                # Should contain some indication of the error
                error_msg = str(exc_info.value)
                assert expected_error in error_msg
    

    
    def test_malformed_json_volume_mappings(self):
        """Test error handling for malformed JSON."""
        env_vars = {
            'MSB_SHARED_VOLUME_PATH': '["unclosed array'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            # The malformed JSON is treated as comma-separated, so it fails volume mapping validation
            assert "Invalid volume mapping" in str(exc_info.value)


class TestWrapperConfigUtilityMethods:
    """Test utility methods of WrapperConfig."""
    
    def test_get_parsed_volume_mappings(self):
        """Test getting parsed volume mappings as VolumeMapping objects."""
        config = WrapperConfig(
            shared_volume_mappings=['/host1:/container1', '/host2:/container2']
        )
        
        mappings = config.get_parsed_volume_mappings()
        
        assert len(mappings) == 2
        assert isinstance(mappings[0], VolumeMapping)
        assert mappings[0].host_path == '/host1'
        assert mappings[0].container_path == '/container1'
        assert mappings[1].host_path == '/host2'
        assert mappings[1].container_path == '/container2'
    
    def test_get_parsed_volume_mappings_empty(self):
        """Test getting parsed volume mappings when none are configured."""
        config = WrapperConfig()
        
        mappings = config.get_parsed_volume_mappings()
        
        assert mappings == []
    
    def test_str_representation(self):
        """Test string representation of configuration."""
        config = WrapperConfig(
            server_url='http://test.com',
            api_key='secret-key',
            session_timeout=1800,
            max_concurrent_sessions=5,
            default_flavor=SandboxFlavor.MEDIUM,
            shared_volume_mappings=['/host:/container']
        )
        
        str_repr = str(config)
        
        assert 'WrapperConfig(' in str_repr
        assert 'server_url=http://test.com' in str_repr
        assert 'api_key=***' in str_repr  # Should be masked
        assert 'session_timeout=1800s' in str_repr
        assert 'max_sessions=5' in str_repr
        assert 'default_flavor=medium' in str_repr
        assert '1 mappings' in str_repr
    
    def test_str_representation_no_api_key(self):
        """Test string representation when no API key is set."""
        config = WrapperConfig()
        
        str_repr = str(config)
        
        assert 'api_key=None' in str_repr


class TestVolumeMappingFromString:
    """Test VolumeMapping.from_string() method."""
    
    def test_valid_mapping_formats(self):
        """Test parsing valid volume mapping formats."""
        test_cases = [
            ('/host/path:/container/path', '/host/path', '/container/path'),
            ('./relative:/absolute', './relative', '/absolute'),
            ('/path with spaces:/container path', '/path with spaces', '/container path'),
            ('/host:/container:extra', '/host', '/container:extra'),  # Colon in container path
        ]
        
        for mapping_str, expected_host, expected_container in test_cases:
            mapping = VolumeMapping.from_string(mapping_str)
            
            assert mapping.host_path == expected_host
            assert mapping.container_path == expected_container
    
    def test_windows_path_mapping(self):
        """Test parsing Windows paths separately due to colon handling."""
        # Windows paths with backslashes work but the colon splits at first occurrence
        mapping = VolumeMapping.from_string('C:\\Windows:/mnt/windows')
        assert mapping.host_path == 'C'
        assert mapping.container_path == '\\Windows:/mnt/windows'
    
    def test_invalid_mapping_formats(self):
        """Test error handling for invalid volume mapping formats."""
        invalid_formats = [
            'no-colon-separator',
            ':empty-host-path',
            'empty-container-path:',
            '',
            'multiple:colons:not:supported',  # This should actually work, taking first colon
            '  :  ',  # Only whitespace
        ]
        
        for invalid_format in invalid_formats:
            if invalid_format == 'multiple:colons:not:supported':
                # This should actually work
                mapping = VolumeMapping.from_string(invalid_format)
                assert mapping.host_path == 'multiple'
                assert mapping.container_path == 'colons:not:supported'
            else:
                with pytest.raises(ValueError) as exc_info:
                    VolumeMapping.from_string(invalid_format)
                
                assert "Invalid volume mapping format" in str(exc_info.value)
    
    def test_whitespace_handling(self):
        """Test that whitespace is properly handled in volume mappings."""
        test_cases = [
            ('  /host  :  /container  ', '/host', '/container'),
            ('\t/host\t:\t/container\t', '/host', '/container'),
            ('/host with spaces : /container with spaces', '/host with spaces', '/container with spaces'),
        ]
        
        for mapping_str, expected_host, expected_container in test_cases:
            mapping = VolumeMapping.from_string(mapping_str)
            
            assert mapping.host_path == expected_host
            assert mapping.container_path == expected_container
    
    def test_volume_mapping_str_method(self):
        """Test VolumeMapping.__str__() method."""
        mapping = VolumeMapping(host_path='/host/path', container_path='/container/path')
        
        assert str(mapping) == '/host/path:/container/path'
    
    def test_volume_mapping_roundtrip(self):
        """Test that parsing and string conversion are consistent."""
        original_str = '/host/path:/container/path'
        
        mapping = VolumeMapping.from_string(original_str)
        converted_str = str(mapping)
        
        assert converted_str == original_str


class TestWrapperConfigEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_environment_variables(self):
        """Test handling of empty environment variables."""
        env_vars = {
            'MSB_SERVER_URL': '',
            'MSB_API_KEY': '',
            'MSB_SHARED_VOLUME_PATH': '',
            'MSB_DEFAULT_FLAVOR': '',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Empty flavor should raise an error
            with pytest.raises(ConfigurationError) as exc_info:
                WrapperConfig.from_env()
            
            assert "Invalid MSB_DEFAULT_FLAVOR" in str(exc_info.value)
    
    def test_very_large_numeric_values(self):
        """Test handling of very large numeric values."""
        env_vars = {
            'MSB_SESSION_TIMEOUT': '999999999',
            'MSB_MAX_SESSIONS': '1000000',
            'MSB_MAX_TOTAL_MEMORY_MB': '999999999',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.session_timeout == 999999999
            assert config.max_concurrent_sessions == 1000000
            assert config.max_total_memory_mb == 999999999
    
    def test_minimum_valid_values(self):
        """Test minimum valid values for numeric parameters."""
        env_vars = {
            'MSB_SESSION_TIMEOUT': '2',  # Must be > cleanup_interval
            'MSB_MAX_SESSIONS': '1',
            'MSB_CLEANUP_INTERVAL': '1',
            'MSB_SANDBOX_START_TIMEOUT': '0.1',
            'MSB_EXECUTION_TIMEOUT': '1',
            'MSB_MAX_TOTAL_MEMORY_MB': '1024',  # Minimum for small flavor
            'MSB_ORPHAN_CLEANUP_INTERVAL': '1',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = WrapperConfig.from_env()
            
            assert config.session_timeout == 2
            assert config.max_concurrent_sessions == 1
            assert config.cleanup_interval == 1
            assert config.sandbox_start_timeout == 0.1
            assert config.default_execution_timeout == 1
            assert config.max_total_memory_mb == 1024
            assert config.orphan_cleanup_interval == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])