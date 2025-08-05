#!/usr/bin/env python3
"""
Integration test environment setup and validation.

This module provides utilities for setting up and validating the integration test environment.
It ensures that the microsandbox server is running and the test environment is properly configured.
"""

import asyncio
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.exceptions import ConnectionError

logger = logging.getLogger(__name__)


class IntegrationTestEnvironment:
    """Manages the integration test environment setup and validation."""
    
    def __init__(self):
        self.test_data_dir = Path("test_data")
        self.shared_volumes_dir = self.test_data_dir / "shared_volumes"
        self.input_dir = self.shared_volumes_dir / "input"
        self.output_dir = self.shared_volumes_dir / "output"
        self.logs_dir = self.test_data_dir / "logs"
        
    def setup_test_directories(self) -> None:
        """Create necessary test directories."""
        logger.info("Creating test directories...")
        
        # Create directories
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✓ Created test directories at {self.test_data_dir}")
        
    def create_test_files(self) -> None:
        """Create test files for volume mapping tests."""
        logger.info("Creating test files...")
        
        # Create test files
        test_files = {
            "test_file.txt": "Hello from host!",
            "test_script.py": "print('Hello from Python!')",
            "test_script.js": "console.log('Hello from Node!');",
            "data.json": '{"message": "Test data", "timestamp": "2024-01-01T00:00:00Z"}',
            "requirements.txt": "requests==2.31.0\nnumpy==1.24.3",
            "package.json": '{"name": "test", "version": "1.0.0", "dependencies": {"lodash": "^4.17.21"}}'
        }
        
        for filename, content in test_files.items():
            file_path = self.input_dir / filename
            file_path.write_text(content)
            logger.info(f"✓ Created {filename}")
            
    def setup_environment_variables(self) -> Dict[str, str]:
        """Set up test environment variables."""
        logger.info("Setting up test environment variables...")
        
        # Get absolute paths for volume mappings
        input_path = self.input_dir.absolute()
        output_path = self.output_dir.absolute()
        
        env_vars = {
            "MSB_SERVER_URL": "http://127.0.0.1:5555",
            "MSB_API_KEY": "",
            "MSB_SESSION_TIMEOUT": "300",
            "MSB_MAX_SESSIONS": "5",
            "MSB_CLEANUP_INTERVAL": "30",
            "MSB_DEFAULT_FLAVOR": "small",
            "MSB_SHARED_VOLUME_PATH": f'["{input_path}:/shared/input", "{output_path}:/shared/output"]',
            "MSB_MAX_TOTAL_MEMORY_MB": "4096",
            "MSB_SANDBOX_START_TIMEOUT": "30.0",
            "MSB_EXECUTION_TIMEOUT": "120",
            "MSB_ORPHAN_CLEANUP_INTERVAL": "60",
            "MSB_LOG_LEVEL": "DEBUG",
            "PYTHONPATH": f"{Path.cwd()}:{os.environ.get('PYTHONPATH', '')}"
        }
        
        # Set environment variables
        for key, value in env_vars.items():
            os.environ[key] = value
            
        logger.info("✓ Environment variables set")
        return env_vars
        
    def validate_server_connection(self, max_retries: int = 30, retry_delay: float = 1.0) -> bool:
        """Validate that the microsandbox server is running and accessible."""
        logger.info("Validating server connection...")
        
        import urllib.request
        import urllib.error
        
        for attempt in range(max_retries):
            try:
                # First check if the server is responding to health checks
                try:
                    with urllib.request.urlopen("http://127.0.0.1:5555/api/v1/health", timeout=5) as response:
                        if response.status == 200:
                            logger.info("✓ Server health check passed")
                        else:
                            raise Exception(f"Health check failed with status {response.status}")
                except urllib.error.URLError as e:
                    raise Exception(f"Health check failed: {e}")
                    
                # Then test wrapper connection
                config = WrapperConfig.from_env()
                wrapper = MicrosandboxWrapper(config=config)
                
                # Try to start the wrapper (this will test server connection)
                asyncio.run(self._test_connection(wrapper))
                logger.info("✓ Server connection validated")
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to server after {max_retries} attempts: {e}")
                    return False
                    
        return False
        
    async def _test_connection(self, wrapper: MicrosandboxWrapper) -> None:
        """Test connection to the server."""
        async with wrapper:
            # Try to get resource stats to verify connection
            await wrapper.get_resource_stats()
            
    def cleanup_test_environment(self) -> None:
        """Clean up test environment."""
        logger.info("Cleaning up test environment...")
        
        # Clean up output files
        if self.output_dir.exists():
            for file_path in self.output_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    
        logger.info("✓ Test environment cleaned up")
        
    def get_server_startup_instructions(self) -> str:
        """Get instructions for starting the server."""
        return """
To start the microsandbox server for integration tests:

1. Open a terminal in the project root directory
2. Run: ./start_msbserver_debug.sh
3. Wait for the server to start (you should see debug logs)
4. In another terminal, run the integration tests

The server should be accessible at http://127.0.0.1:5555
"""

    def print_environment_summary(self) -> None:
        """Print a summary of the test environment configuration."""
        print("\n=== Integration Test Environment Summary ===")
        print(f"Test data directory: {self.test_data_dir.absolute()}")
        print(f"Input directory: {self.input_dir.absolute()}")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Logs directory: {self.logs_dir.absolute()}")
        print("\nEnvironment variables:")
        for key in sorted(os.environ.keys()):
            if key.startswith('MSB_'):
                print(f"  {key}={os.environ[key]}")
        print("=" * 50)


# Pytest fixtures for integration tests
@pytest.fixture(scope="session")
def integration_env():
    """Set up integration test environment."""
    env = IntegrationTestEnvironment()
    env.setup_test_directories()
    env.create_test_files()
    env.setup_environment_variables()
    
    # Validate server connection
    if not env.validate_server_connection():
        pytest.skip("Microsandbox server is not running. " + env.get_server_startup_instructions())
    
    yield env
    
    # Cleanup
    env.cleanup_test_environment()


@pytest.fixture(scope="session")
def test_wrapper(integration_env):
    """Create a wrapper instance for testing."""
    config = WrapperConfig.from_env()
    wrapper = MicrosandboxWrapper(config=config)
    return wrapper


# Test functions
@pytest.mark.asyncio
async def test_environment_setup(integration_env):
    """Test that the environment is properly set up."""
    # Check directories exist
    assert integration_env.input_dir.exists(), "Input directory should exist"
    assert integration_env.output_dir.exists(), "Output directory should exist"
    assert integration_env.logs_dir.exists(), "Logs directory should exist"
    
    # Check test files exist
    test_files = ["test_file.txt", "test_script.py", "test_script.js"]
    for filename in test_files:
        file_path = integration_env.input_dir / filename
        assert file_path.exists(), f"Test file {filename} should exist"
        
    # Check environment variables
    required_env_vars = [
        "MSB_SERVER_URL", "MSB_SESSION_TIMEOUT", "MSB_MAX_SESSIONS",
        "MSB_DEFAULT_FLAVOR", "MSB_SHARED_VOLUME_PATH"
    ]
    for var in required_env_vars:
        assert os.environ.get(var), f"Environment variable {var} should be set"


@pytest.mark.asyncio
async def test_server_connectivity(test_wrapper):
    """Test that we can connect to the microsandbox server."""
    async with test_wrapper as wrapper:
        # Test basic connectivity
        stats = await wrapper.get_resource_stats()
        assert stats is not None, "Should be able to get resource stats"
        
        # Test session listing
        sessions = await wrapper.get_sessions()
        assert isinstance(sessions, list), "Should be able to get sessions list"
        
        # Test volume mappings
        volumes = await wrapper.get_volume_mappings()
        assert isinstance(volumes, list), "Should be able to get volume mappings"


if __name__ == "__main__":
    # Run environment setup when called directly
    env = IntegrationTestEnvironment()
    env.setup_test_directories()
    env.create_test_files()
    env.setup_environment_variables()
    env.print_environment_summary()
    
    print(env.get_server_startup_instructions())
    
    if env.validate_server_connection():
        print("\n✅ Integration test environment is ready!")
    else:
        print("\n❌ Server connection failed. Please start the microsandbox server.")
        sys.exit(1)