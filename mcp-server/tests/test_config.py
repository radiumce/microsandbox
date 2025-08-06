"""
Unit tests for configuration management.

Tests the MCPServerConfig class, environment variable handling,
validation, and default value setting.
"""

import os
import pytest
from unittest.mock import patch

from mcp_server.main import MCPServerConfig
from microsandbox_wrapper.exceptions import ConfigurationError


class TestMCPServerConfig:
    """Test MCPServerConfig functionality."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        with patch.dict(os.environ, {}, clear=True):
            config = MCPServerConfig()
            
            assert config.host == "localhost"
            assert config.port == 8000
            assert config.enable_cors is False
            assert config.microsandbox_server_url == "http://localhost:5555"
            assert config.microsandbox_api_key is None
            assert config.max_concurrent_sessions == 10
            assert config.session_timeout_minutes == 30
            assert config.volume_mappings == []
    
    def test_environment_variable_override(self):
        """Test that environment variables override defaults."""
        env_vars = {
            "MCP_SERVER_HOST": "0.0.0.0",
            "MCP_SERVER_PORT": "9000",
            "MCP_SERVER_ENABLE_CORS": "true",
            "MICROSANDBOX_SERVER_URL": "http://remote:5555",
            "MICROSANDBOX_API_KEY": "test-api-key",
            "MICROSANDBOX_MAX_CONCURRENT_SESSIONS": "20",
            "MICROSANDBOX_SESSION_TIMEOUT_MINUTES": "60",
            "MICROSANDBOX_VOLUME_MAPPINGS": "/host1:/container1,/host2:/container2"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = MCPServerConfig()
            
            assert config.host == "0.0.0.0"
            assert config.port == 9000
            assert config.enable_cors is True
            assert config.microsandbox_server_url == "http://remote:5555"
            assert config.microsandbox_api_key == "test-api-key"
            assert config.max_concurrent_sessions == 20
            assert config.session_timeout_minutes == 60
            assert len(config.volume_mappings) == 2
            assert config.volume_mappings[0] == "/host1:/container1"
            assert config.volume_mappings[1] == "/host2:/container2"
    
    def test_boolean_environment_variables(self):
        """Test boolean environment variable parsing."""
        # Test various true values
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES"]
        for value in true_values:
            with patch.dict(os.environ, {"MCP_SERVER_ENABLE_CORS": value}, clear=True):
                config = MCPServerConfig()
                assert config.enable_cors is True, f"Failed for value: {value}"
        
        # Test various false values
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO", ""]
        for value in false_values:
            with patch.dict(os.environ, {"MCP_SERVER_ENABLE_CORS": value}, clear=True):
                config = MCPServerConfig()
                assert config.enable_cors is False, f"Failed for value: {value}"
    
    def test_integer_environment_variables(self):
        """Test integer environment variable parsing."""
        with patch.dict(os.environ, {
            "MCP_SERVER_PORT": "8080",
            "MICROSANDBOX_MAX_CONCURRENT_SESSIONS": "15"
        }, clear=True):
            config = MCPServerConfig()
            
            assert config.port == 8080
            assert config.max_concurrent_sessions == 15
    
    def test_invalid_integer_environment_variable(self):
        """Test handling of invalid integer environment variables."""
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "invalid"}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                MCPServerConfig()
            
            assert "Invalid integer value" in str(exc_info.value)
            assert "MCP_SERVER_PORT" in str(exc_info.value)
    
    def test_volume_mappings_parsing(self):
        """Test volume mappings parsing."""
        # Test single mapping
        with patch.dict(os.environ, {
            "MICROSANDBOX_VOLUME_MAPPINGS": "/host:/container"
        }, clear=True):
            config = MCPServerConfig()
            assert len(config.volume_mappings) == 1
            assert config.volume_mappings[0] == "/host:/container"
        
        # Test multiple mappings
        with patch.dict(os.environ, {
            "MICROSANDBOX_VOLUME_MAPPINGS": "/host1:/container1,/host2:/container2,/host3:/container3"
        }, clear=True):
            config = MCPServerConfig()
            assert len(config.volume_mappings) == 3
            assert config.volume_mappings[0] == "/host1:/container1"
            assert config.volume_mappings[1] == "/host2:/container2"
            assert config.volume_mappings[2] == "/host3:/container3"
        
        # Test empty mappings
        with patch.dict(os.environ, {
            "MICROSANDBOX_VOLUME_MAPPINGS": ""
        }, clear=True):
            config = MCPServerConfig()
            assert config.volume_mappings == []
    
    def test_volume_mappings_with_whitespace(self):
        """Test volume mappings parsing with whitespace."""
        with patch.dict(os.environ, {
            "MICROSANDBOX_VOLUME_MAPPINGS": " /host1:/container1 , /host2:/container2 "
        }, clear=True):
            config = MCPServerConfig()
            assert len(config.volume_mappings) == 2
            assert config.volume_mappings[0] == "/host1:/container1"
            assert config.volume_mappings[1] == "/host2:/container2"
    
    def test_validation_valid_config(self):
        """Test validation with valid configuration."""
        with patch.dict(os.environ, {
            "MCP_SERVER_HOST": "localhost",
            "MCP_SERVER_PORT": "8000",
            "MICROSANDBOX_SERVER_URL": "http://localhost:5555"
        }, clear=True):
            config = MCPServerConfig()
            
            # Should not raise any exception
            config.validate()
    
    def test_validation_invalid_port_range(self):
        """Test validation with invalid port range."""
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "70000"}, clear=True):
            config = MCPServerConfig()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Port must be between 1 and 65535" in str(exc_info.value)
    
    def test_validation_invalid_port_zero(self):
        """Test validation with port zero."""
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "0"}, clear=True):
            config = MCPServerConfig()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Port must be between 1 and 65535" in str(exc_info.value)
    
    def test_validation_invalid_server_url(self):
        """Test validation with invalid server URL."""
        with patch.dict(os.environ, {
            "MICROSANDBOX_SERVER_URL": "invalid-url"
        }, clear=True):
            config = MCPServerConfig()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Invalid microsandbox server URL" in str(exc_info.value)
    
    def test_validation_invalid_max_sessions(self):
        """Test validation with invalid max sessions."""
        with patch.dict(os.environ, {
            "MICROSANDBOX_MAX_CONCURRENT_SESSIONS": "0"
        }, clear=True):
            config = MCPServerConfig()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Max concurrent sessions must be positive" in str(exc_info.value)
    
    def test_validation_invalid_session_timeout(self):
        """Test validation with invalid session timeout."""
        with patch.dict(os.environ, {
            "MICROSANDBOX_SESSION_TIMEOUT_MINUTES": "-1"
        }, clear=True):
            config = MCPServerConfig()
            
            with pytest.raises(ConfigurationError) as exc_info:
                config.validate()
            
            assert "Session timeout must be positive" in str(exc_info.value)
    
    def test_to_dict(self):
        """Test configuration serialization to dictionary."""
        with patch.dict(os.environ, {
            "MCP_SERVER_HOST": "0.0.0.0",
            "MCP_SERVER_PORT": "9000",
            "MCP_SERVER_ENABLE_CORS": "true",
            "MICROSANDBOX_API_KEY": "test-key"
        }, clear=True):
            config = MCPServerConfig()
            config_dict = config.to_dict()
            
            assert config_dict["host"] == "0.0.0.0"
            assert config_dict["port"] == 9000
            assert config_dict["enable_cors"] is True
            assert config_dict["microsandbox_api_key"] == "test-key"
            
            # Check that all expected keys are present
            expected_keys = {
                "host", "port", "enable_cors", "microsandbox_server_url",
                "microsandbox_api_key", "max_concurrent_sessions",
                "session_timeout_minutes", "volume_mappings"
            }
            assert set(config_dict.keys()) == expected_keys
    
    def test_str_representation(self):
        """Test string representation of configuration."""
        config = MCPServerConfig()
        config_str = str(config)
        
        assert "MCPServerConfig" in config_str
        assert "host=localhost" in config_str
        assert "port=8000" in config_str
        assert "enable_cors=False" in config_str
    
    def test_repr_representation(self):
        """Test repr representation of configuration."""
        config = MCPServerConfig()
        config_repr = repr(config)
        
        assert "MCPServerConfig" in config_repr
        assert "host='localhost'" in config_repr
        assert "port=8000" in config_repr
    
    def test_config_immutability_after_validation(self):
        """Test that configuration values can be modified after creation."""
        config = MCPServerConfig()
        
        # Should be able to modify before validation
        config.port = 9000
        assert config.port == 9000
        
        # Should still be able to modify after validation
        config.validate()
        config.port = 8080
        assert config.port == 8080
    
    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over defaults."""
        # Set environment variable
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "9999"}, clear=True):
            config = MCPServerConfig()
            assert config.port == 9999
            
            # Even if we try to set default, env var should win
            config = MCPServerConfig()
            assert config.port == 9999
    
    def test_missing_optional_environment_variables(self):
        """Test handling of missing optional environment variables."""
        # Clear all environment variables
        with patch.dict(os.environ, {}, clear=True):
            config = MCPServerConfig()
            
            # Optional variables should have None or default values
            assert config.microsandbox_api_key is None
            assert config.volume_mappings == []
            
            # Required variables should have defaults
            assert config.host == "localhost"
            assert config.port == 8000
    
    def test_url_validation_schemes(self):
        """Test URL validation with different schemes."""
        # Valid HTTP URL
        with patch.dict(os.environ, {
            "MICROSANDBOX_SERVER_URL": "http://localhost:5555"
        }, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise
        
        # Valid HTTPS URL
        with patch.dict(os.environ, {
            "MICROSANDBOX_SERVER_URL": "https://remote.example.com:5555"
        }, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise
        
        # Invalid scheme
        with patch.dict(os.environ, {
            "MICROSANDBOX_SERVER_URL": "ftp://localhost:5555"
        }, clear=True):
            config = MCPServerConfig()
            with pytest.raises(ConfigurationError):
                config.validate()
        
        # No scheme
        with patch.dict(os.environ, {
            "MICROSANDBOX_SERVER_URL": "localhost:5555"
        }, clear=True):
            config = MCPServerConfig()
            with pytest.raises(ConfigurationError):
                config.validate()
    
    def test_host_validation(self):
        """Test host validation."""
        # Valid hosts
        valid_hosts = ["localhost", "0.0.0.0", "127.0.0.1", "example.com"]
        for host in valid_hosts:
            with patch.dict(os.environ, {"MCP_SERVER_HOST": host}, clear=True):
                config = MCPServerConfig()
                config.validate()  # Should not raise
        
        # Empty host should fail
        with patch.dict(os.environ, {"MCP_SERVER_HOST": ""}, clear=True):
            config = MCPServerConfig()
            with pytest.raises(ConfigurationError):
                config.validate()
    
    def test_edge_case_values(self):
        """Test edge case values for configuration."""
        # Minimum valid port
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "1"}, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise
        
        # Maximum valid port
        with patch.dict(os.environ, {"MCP_SERVER_PORT": "65535"}, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise
        
        # Minimum sessions
        with patch.dict(os.environ, {"MICROSANDBOX_MAX_CONCURRENT_SESSIONS": "1"}, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise
        
        # Minimum timeout
        with patch.dict(os.environ, {"MICROSANDBOX_SESSION_TIMEOUT_MINUTES": "1"}, clear=True):
            config = MCPServerConfig()
            config.validate()  # Should not raise