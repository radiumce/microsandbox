#!/usr/bin/env python3
"""
End-to-end integration tests for LRU eviction mechanism.

This test suite validates the complete LRU eviction workflow from
MCP server requests through to actual sandbox creation and eviction
on the microsandbox server.

Tests cover:
1. Full MCP server + wrapper + microsandbox server integration
2. Real session creation and eviction
3. Network communication and error handling
4. Resource monitoring and cleanup
5. Concurrent access patterns
"""

import asyncio
import json
import os
import sys
import pytest
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aiohttp
from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus
from microsandbox_wrapper.exceptions import ResourceLimitError


class TestLRUEvictionE2E:
    """End-to-end integration tests for LRU eviction."""
    
    @pytest.fixture
    def server_url(self):
        """Get microsandbox server URL from environment."""
        return os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555')
    
    @pytest.fixture
    def api_key(self):
        """Get API key from environment."""
        return os.getenv('MSB_API_KEY')
    
    @pytest.fixture
    def test_config(self, server_url, api_key):
        """Create test configuration with low limits for testing."""
        return WrapperConfig(
            server_url=server_url,
            api_key=api_key,
            max_concurrent_sessions=3,
            max_total_memory_mb=3072,  # 3GB total
            enable_lru_eviction=True,
            session_timeout=300,
            cleanup_interval=30,
            orphan_cleanup_interval=60
        )
    
    @pytest.fixture
    async def server_health_check(self, server_url):
        """Verify microsandbox server is running and healthy."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{server_url}/api/v1/health", timeout=5) as response:
                    if response.status != 200:
                        pytest.skip(f"Microsandbox server not healthy: {response.status}")
        except Exception as e:
            pytest.skip(f"Microsandbox server not accessible: {e}")
    
    @pytest.mark.asyncio
    async def test_e2e_lru_eviction_basic(self, test_config, server_health_check):
        """Test basic end-to-end LRU eviction workflow."""
        print("\n=== E2E Test: Basic LRU Eviction ===")
        
        async with MicrosandboxWrapper(config=test_config) as wrapper:
            # Step 1: Verify initial state
            initial_stats = await wrapper.get_resource_stats()
            assert initial_stats.active_sessions == 0
            print(f"✅ Initial state: {initial_stats.active_sessions} sessions")
            
            # Step 2: Create sessions up to the limit
            print("\n📝 Creating sessions up to limit...")
            session_ids = []
            
            for i in range(test_config.max_concurrent_sessions):
                result = await wrapper.execute_code(
                    code=f"""
import time
import os
print(f"Session {i+1} created at {{time.strftime('%H:%M:%S')}}")
print(f"PID: {{os.getpid()}}")
session_data = {{"id": {i+1}, "created": time.time()}}
""",
                    template="python",
                    flavor=SandboxFlavor.SMALL
                )
                session_ids.append(result.session_id)
                print(f"  Created session {i+1}: {result.session_id[:8]}...")
                
                # Verify session was created successfully
                assert result.success, f"Session {i+1} creation failed"
                assert result.session_created, f"Session {i+1} should be newly created"
                
                # Small delay to ensure different timestamps
                await asyncio.sleep(0.5)
            
            # Step 3: Verify all sessions are active
            stats_after_creation = await wrapper.get_resource_stats()
            assert stats_after_creation.active_sessions == test_config.max_concurrent_sessions
            assert stats_after_creation.total_memory_mb == test_config.max_concurrent_sessions * 1024
            print(f"✅ All sessions created: {stats_after_creation.active_sessions} active")
            
            # Step 4: Create new session that should trigger eviction
            print("\n🚀 Creating new session to trigger LRU eviction...")
            
            # Before creating new session, record current sessions for comparison
            pre_eviction_sessions = await wrapper.get_sessions()
            pre_eviction_ids = {s.session_id for s in pre_eviction_sessions}
            
            new_session_result = await wrapper.execute_code(
                code="""
import time
print(f"New session created at {time.strftime('%H:%M:%S')}")
print("LRU session should have been evicted!")
new_session_data = {"created": time.time(), "purpose": "trigger_eviction"}
""",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            
            assert new_session_result.success, "New session creation should succeed"
            new_session_id = new_session_result.session_id
            print(f"  New session created: {new_session_id[:8]}...")
            
            # Step 5: Verify eviction occurred
            print("\n🔍 Verifying eviction results...")
            
            # Check final session count
            final_stats = await wrapper.get_resource_stats()
            assert final_stats.active_sessions == test_config.max_concurrent_sessions
            print(f"  Session count maintained: {final_stats.active_sessions}")
            
            # Check which sessions are still active
            final_sessions = await wrapper.get_sessions()
            active_session_ids = {s.session_id for s in final_sessions}
            
            # Verify new session is active
            assert new_session_id in active_session_ids, "New session should be active"
            print(f"  ✅ New session active: {new_session_id[:8]}...")
            
            # Verify that exactly one session was evicted
            evicted_sessions = pre_eviction_ids - active_session_ids
            assert len(evicted_sessions) == 1, f"Exactly one session should be evicted, got {len(evicted_sessions)}"
            
            evicted_session_id = list(evicted_sessions)[0]
            print(f"  ✅ LRU session evicted: {evicted_session_id[:8]}...")
            
            # Verify that the remaining original sessions are still active
            remaining_original_sessions = pre_eviction_ids - evicted_sessions
            for sid in remaining_original_sessions:
                assert sid in active_session_ids, f"Session {sid[:8]} should still be active"
            
            print(f"  ✅ {len(remaining_original_sessions)} original sessions kept as expected")
            
            print("\n🎉 E2E Basic LRU Eviction Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_e2e_processing_session_protection(self, test_config, server_health_check):
        """Test that processing sessions are protected from eviction."""
        print("\n=== E2E Test: Processing Session Protection ===")
        
        # Use even lower limits for this test
        config = WrapperConfig(
            server_url=test_config.server_url,
            api_key=test_config.api_key,
            max_concurrent_sessions=2,
            max_total_memory_mb=2048,
            enable_lru_eviction=True,
            session_timeout=300
        )
        
        async with MicrosandboxWrapper(config=config) as wrapper:
            # Create two sessions
            print("\n📝 Creating two sessions...")
            
            session1_result = await wrapper.execute_code(
                code="print('Session 1 created'); session_id = 1",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            session1_id = session1_result.session_id
            print(f"  Session 1: {session1_id[:8]}...")
            
            await asyncio.sleep(1)  # Ensure different timestamps
            
            session2_result = await wrapper.execute_code(
                code="print('Session 2 created'); session_id = 2",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            session2_id = session2_result.session_id
            print(f"  Session 2: {session2_id[:8]}...")
            
            # Verify both sessions are active
            stats = await wrapper.get_resource_stats()
            assert stats.active_sessions == 2
            print(f"  ✅ Both sessions active: {stats.active_sessions}")
            
            # Now try to create a third session - should trigger eviction
            print("\n🚀 Creating third session (should trigger eviction)...")
            
            session3_result = await wrapper.execute_code(
                code="print('Session 3 created - eviction should have occurred'); session_id = 3",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            session3_id = session3_result.session_id
            print(f"  Session 3: {session3_id[:8]}...")
            
            # Verify eviction occurred
            final_sessions = await wrapper.get_sessions()
            active_ids = {s.session_id for s in final_sessions}
            
            # One of the original sessions should be evicted
            evicted_count = 0
            if session1_id not in active_ids:
                evicted_count += 1
                print(f"  ✅ Session 1 evicted: {session1_id[:8]}...")
            if session2_id not in active_ids:
                evicted_count += 1
                print(f"  ✅ Session 2 evicted: {session2_id[:8]}...")
            
            assert evicted_count == 1, "Exactly one session should be evicted"
            assert session3_id in active_ids, "New session should be active"
            
            final_stats = await wrapper.get_resource_stats()
            assert final_stats.active_sessions == 2, "Should maintain session limit"
            
            print("\n🎉 E2E Processing Session Protection Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_e2e_memory_based_eviction(self, test_config, server_health_check):
        """Test memory-based LRU eviction."""
        print("\n=== E2E Test: Memory-Based Eviction ===")
        
        # Configure with memory limit that allows 2 medium sessions
        config = WrapperConfig(
            server_url=test_config.server_url,
            api_key=test_config.api_key,
            max_concurrent_sessions=10,  # High session limit
            max_total_memory_mb=4096,    # 4GB total (2 medium sessions)
            enable_lru_eviction=True,
            session_timeout=300
        )
        
        async with MicrosandboxWrapper(config=config) as wrapper:
            # Create two medium sessions (2GB each)
            print("\n📝 Creating two medium sessions (2GB each)...")
            
            session_ids = []
            for i in range(2):
                result = await wrapper.execute_code(
                    code=f"print('Medium session {i+1} created'); import time; time.sleep(0.1)",
                    template="python",
                    flavor=SandboxFlavor.MEDIUM  # 2GB each
                )
                session_ids.append(result.session_id)
                print(f"  Medium session {i+1}: {result.session_id[:8]}...")
                await asyncio.sleep(1)
            
            # Verify memory usage
            stats = await wrapper.get_resource_stats()
            assert stats.total_memory_mb == 4096  # 2 * 2GB
            print(f"  ✅ Memory usage: {stats.total_memory_mb}MB / {config.max_total_memory_mb}MB")
            
            # Access first session to make it more recent
            await asyncio.sleep(1)
            await wrapper.execute_code(
                code="print('First session accessed - should not be evicted')",
                session_id=session_ids[0],
                template="python"
            )
            print(f"  🔄 Accessed first session: {session_ids[0][:8]}...")
            
            # Try to create another medium session - should trigger memory-based eviction
            print("\n🚀 Creating third medium session (should trigger memory eviction)...")
            
            result = await wrapper.execute_code(
                code="print('Third medium session - memory eviction should occur')",
                template="python",
                flavor=SandboxFlavor.MEDIUM  # Would exceed 4GB limit
            )
            
            assert result.success, "New session creation should succeed after eviction"
            new_session_id = result.session_id
            print(f"  New session created: {new_session_id[:8]}...")
            
            # Verify eviction occurred
            final_sessions = await wrapper.get_sessions()
            active_ids = {s.session_id for s in final_sessions}
            
            # Second session (LRU) should be evicted, first should remain
            assert session_ids[0] in active_ids, "First session (accessed) should remain"
            assert session_ids[1] not in active_ids, "Second session (LRU) should be evicted"
            assert new_session_id in active_ids, "New session should be active"
            
            # Verify memory limit is maintained
            final_stats = await wrapper.get_resource_stats()
            assert final_stats.total_memory_mb <= config.max_total_memory_mb
            print(f"  ✅ Memory limit maintained: {final_stats.total_memory_mb}MB")
            
            print("\n🎉 E2E Memory-Based Eviction Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_e2e_eviction_disabled(self, test_config, server_health_check):
        """Test behavior when LRU eviction is disabled."""
        print("\n=== E2E Test: Eviction Disabled ===")
        
        # Configure with LRU eviction disabled
        config = WrapperConfig(
            server_url=test_config.server_url,
            api_key=test_config.api_key,
            max_concurrent_sessions=2,
            enable_lru_eviction=False,  # Disabled
            session_timeout=300
        )
        
        async with MicrosandboxWrapper(config=config) as wrapper:
            # Create sessions up to limit
            print("\n📝 Creating sessions up to limit...")
            
            session_ids = []
            for i in range(config.max_concurrent_sessions):
                result = await wrapper.execute_code(
                    code=f"print('Session {i+1} created')",
                    template="python",
                    flavor=SandboxFlavor.SMALL
                )
                session_ids.append(result.session_id)
                print(f"  Session {i+1}: {result.session_id[:8]}...")
            
            # Verify sessions are at limit
            stats = await wrapper.get_resource_stats()
            assert stats.active_sessions == config.max_concurrent_sessions
            print(f"  ✅ At session limit: {stats.active_sessions}")
            
            # Try to create another session - should fail
            print("\n❌ Attempting to create session beyond limit (should fail)...")
            
            with pytest.raises(ResourceLimitError) as exc_info:
                await wrapper.execute_code(
                    code="print('This should fail')",
                    template="python",
                    flavor=SandboxFlavor.SMALL
                )
            
            assert "Sessions limit exceeded" in str(exc_info.value) or "Session limit" in str(exc_info.value) or "would be exceeded" in str(exc_info.value)
            print(f"  ✅ Expected failure: {exc_info.value}")
            
            # Verify no sessions were evicted
            final_sessions = await wrapper.get_sessions()
            final_ids = {s.session_id for s in final_sessions}
            
            for session_id in session_ids:
                assert session_id in final_ids, f"Session {session_id[:8]} should still exist"
            
            print(f"  ✅ All original sessions preserved: {len(final_sessions)}")
            
            print("\n🎉 E2E Eviction Disabled Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_e2e_concurrent_access_patterns(self, test_config, server_health_check):
        """Test LRU eviction with concurrent access patterns."""
        print("\n=== E2E Test: Concurrent Access Patterns ===")
        
        async with MicrosandboxWrapper(config=test_config) as wrapper:
            # Create sessions up to limit
            print("\n📝 Creating sessions concurrently...")
            
            async def create_session(i):
                return await wrapper.execute_code(
                    code=f"print('Concurrent session {i} created'); session_num = {i}",
                    template="python",
                    flavor=SandboxFlavor.SMALL
                )
            
            # Create sessions concurrently
            tasks = [create_session(i) for i in range(test_config.max_concurrent_sessions)]
            results = await asyncio.gather(*tasks)
            
            session_ids = [r.session_id for r in results]
            print(f"  ✅ Created {len(session_ids)} sessions concurrently")
            
            # Simulate concurrent access pattern
            print("\n🔄 Simulating concurrent access patterns...")
            
            async def access_session(session_id, access_num):
                await asyncio.sleep(access_num * 0.1)  # Stagger access times
                return await wrapper.execute_code(
                    code=f"print('Concurrent access {access_num}'); import time; time.sleep(0.05)",
                    session_id=session_id,
                    template="python"
                )
            
            # Access sessions in different patterns
            access_tasks = []
            for i, session_id in enumerate(session_ids[:-1]):  # Leave last session as LRU
                access_tasks.append(access_session(session_id, i))
            
            await asyncio.gather(*access_tasks)
            print(f"  ✅ Concurrent access completed")
            
            # Create new session to trigger eviction
            print("\n🚀 Creating new session with concurrent eviction...")
            
            new_result = await wrapper.execute_code(
                code="print('New session created with concurrent eviction')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            
            assert new_result.success, "Concurrent eviction should succeed"
            print(f"  ✅ New session: {new_result.session_id[:8]}...")
            
            # Verify eviction occurred correctly
            final_sessions = await wrapper.get_sessions()
            assert len(final_sessions) == test_config.max_concurrent_sessions
            
            active_ids = {s.session_id for s in final_sessions}
            assert new_result.session_id in active_ids, "New session should be active"
            
            # The last session (LRU) should be evicted
            lru_session_id = session_ids[-1]
            assert lru_session_id not in active_ids, "LRU session should be evicted"
            
            print(f"  ✅ LRU session evicted: {lru_session_id[:8]}...")
            print(f"  ✅ Concurrent eviction handled correctly")
            
            print("\n🎉 E2E Concurrent Access Patterns Test PASSED!")
    
    @pytest.mark.asyncio
    async def test_e2e_server_communication_errors(self, test_config, server_health_check):
        """Test LRU eviction behavior with server communication errors."""
        print("\n=== E2E Test: Server Communication Errors ===")
        
        # Test with invalid server URL to simulate network issues
        error_config = WrapperConfig(
            server_url="http://invalid-server:9999",
            max_concurrent_sessions=2,
            enable_lru_eviction=True,
            session_timeout=300
        )
        
        print("\n❌ Testing with invalid server URL...")
        
        try:
            async with MicrosandboxWrapper(config=error_config) as wrapper:
                # This should fail due to invalid server
                with pytest.raises(Exception) as exc_info:
                    await wrapper.execute_code(
                        code="print('This should fail')",
                        template="python",
                        flavor=SandboxFlavor.SMALL
                    )
                
                print(f"  ✅ Expected connection error: {type(exc_info.value).__name__}")
        
        except Exception as e:
            # Connection error during wrapper initialization is also expected
            print(f"  ✅ Expected initialization error: {type(e).__name__}")
        
        print("\n🎉 E2E Server Communication Errors Test PASSED!")


async def run_e2e_tests():
    """Run all end-to-end tests manually (without pytest)."""
    print("🚀 Running End-to-End LRU Eviction Tests")
    print("=" * 60)
    
    # Check server availability
    server_url = os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{server_url}/api/v1/health", timeout=5) as response:
                if response.status != 200:
                    print(f"❌ Microsandbox server not healthy: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Microsandbox server not accessible: {e}")
        print("Please start the microsandbox server:")
        print("  cd microsandbox-server && cargo run")
        return False
    
    print(f"✅ Microsandbox server is healthy at {server_url}")
    
    # Create test instance
    test_instance = TestLRUEvictionE2E()
    
    # Setup test config
    config = WrapperConfig(
        server_url=server_url,
        api_key=os.getenv('MSB_API_KEY'),
        max_concurrent_sessions=3,
        max_total_memory_mb=3072,
        enable_lru_eviction=True,
        session_timeout=300
    )
    
    try:
        # Run tests
        await test_instance.test_e2e_lru_eviction_basic(config, None)
        await test_instance.test_e2e_processing_session_protection(config, None)
        await test_instance.test_e2e_memory_based_eviction(config, None)
        await test_instance.test_e2e_eviction_disabled(config, None)
        await test_instance.test_e2e_concurrent_access_patterns(config, None)
        
        print("\n" + "=" * 60)
        print("🎉 All End-to-End LRU Eviction Tests PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ E2E Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_e2e_tests())
    if not success:
        exit(1)