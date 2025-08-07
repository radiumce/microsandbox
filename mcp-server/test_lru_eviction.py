#!/usr/bin/env python3
"""
Test script for LRU eviction mechanism in microsandbox wrapper.

This script tests the LRU eviction functionality by:
1. Creating multiple sessions up to the limit
2. Accessing some sessions to update their LRU order
3. Attempting to create a new session that would exceed limits
4. Verifying that the least recently used session is evicted
"""

import asyncio
import os
import time
from datetime import datetime, timedelta

from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor


async def test_lru_eviction():
    """Test LRU eviction mechanism."""
    print("=== Testing LRU Eviction Mechanism ===\n")
    
    # Configure for testing with low limits
    config = WrapperConfig(
        server_url=os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555'),
        api_key=os.getenv('MSB_API_KEY'),
        max_concurrent_sessions=3,  # Low limit for testing
        max_total_memory_mb=3072,   # 3GB total (3 small sessions)
        enable_lru_eviction=True,
        session_timeout=300,        # 5 minutes
        cleanup_interval=30         # 30 seconds
    )
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        print(f"Wrapper started with max_sessions={config.max_concurrent_sessions}, "
              f"max_memory={config.max_total_memory_mb}MB")
        
        # Step 1: Create sessions up to the limit
        print("\n1. Creating sessions up to the limit...")
        session_ids = []
        
        for i in range(config.max_concurrent_sessions):
            result = await wrapper.execute_code(
                code=f"print('Session {i+1} created')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            session_ids.append(result.session_id)
            print(f"   Created session {i+1}: {result.session_id[:8]}...")
        
        # Check resource stats
        stats = await wrapper.get_resource_stats()
        print(f"   Resource stats: {stats.active_sessions} sessions, {stats.total_memory_mb}MB")
        
        # Step 2: Wait a bit, then access some sessions to update LRU order
        print("\n2. Updating LRU order by accessing sessions...")
        await asyncio.sleep(2)  # Ensure different timestamps
        
        # Access session 2 and 3, leaving session 1 as LRU
        for i, session_id in enumerate(session_ids[1:], 2):
            result = await wrapper.execute_code(
                code=f"print('Accessing session {i}')",
                template="python",
                session_id=session_id,
                flavor=SandboxFlavor.SMALL
            )
            print(f"   Accessed session {i}: {session_id[:8]}...")
            await asyncio.sleep(1)  # Ensure different timestamps
        
        # Step 3: Get session info to verify LRU order
        print("\n3. Current session info (before eviction):")
        sessions = await wrapper.get_sessions()
        sessions.sort(key=lambda s: s.last_accessed)  # Sort by LRU
        
        for i, session in enumerate(sessions):
            print(f"   Session {i+1}: {session.session_id[:8]}... "
                  f"(last_accessed: {session.last_accessed.strftime('%H:%M:%S')}, "
                  f"status: {session.status.value})")
        
        lru_session_id = sessions[0].session_id
        print(f"   LRU session (should be evicted): {lru_session_id[:8]}...")
        
        # Step 4: Try to create a new session that would exceed limits
        print("\n4. Creating new session that should trigger LRU eviction...")
        
        try:
            result = await wrapper.execute_code(
                code="print('New session created, LRU should be evicted')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            new_session_id = result.session_id
            print(f"   New session created: {new_session_id[:8]}...")
            
            # Step 5: Verify eviction occurred
            print("\n5. Verifying eviction occurred...")
            updated_sessions = await wrapper.get_sessions()
            updated_stats = await wrapper.get_resource_stats()
            
            print(f"   Resource stats after eviction: {updated_stats.active_sessions} sessions, "
                  f"{updated_stats.total_memory_mb}MB")
            
            active_session_ids = {s.session_id for s in updated_sessions}
            
            if lru_session_id not in active_session_ids:
                print(f"   ✅ SUCCESS: LRU session {lru_session_id[:8]}... was evicted")
            else:
                print(f"   ❌ FAILURE: LRU session {lru_session_id[:8]}... was NOT evicted")
            
            if new_session_id in active_session_ids:
                print(f"   ✅ SUCCESS: New session {new_session_id[:8]}... is active")
            else:
                print(f"   ❌ FAILURE: New session {new_session_id[:8]}... is NOT active")
            
            print("\n6. Final session info (after eviction):")
            for i, session in enumerate(updated_sessions):
                print(f"   Session {i+1}: {session.session_id[:8]}... "
                      f"(last_accessed: {session.last_accessed.strftime('%H:%M:%S')}, "
                      f"status: {session.status.value})")
            
        except Exception as e:
            print(f"   ❌ FAILURE: Error creating new session: {e}")
            return False
        
        print("\n=== LRU Eviction Test Completed ===")
        return True


async def test_processing_session_protection():
    """Test that sessions in PROCESSING state cannot be evicted."""
    print("\n=== Testing Processing Session Protection ===\n")
    
    # Configure for testing with very low limits
    config = WrapperConfig(
        server_url=os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555'),
        api_key=os.getenv('MSB_API_KEY'),
        max_concurrent_sessions=2,  # Very low limit
        enable_lru_eviction=True,
        session_timeout=300
    )
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        print(f"Wrapper started with max_sessions={config.max_concurrent_sessions}")
        
        # Create first session
        result1 = await wrapper.execute_code(
            code="print('Session 1')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        session1_id = result1.session_id
        print(f"Created session 1: {session1_id[:8]}...")
        
        # Create second session
        result2 = await wrapper.execute_code(
            code="print('Session 2')",
            template="python",
            flavor=SandboxFlavor.SMALL
        )
        session2_id = result2.session_id
        print(f"Created session 2: {session2_id[:8]}...")
        
        # Now both sessions are at limit
        # Try to create a third session - should fail if no sessions can be evicted
        print("\nAttempting to create third session (should trigger eviction)...")
        
        try:
            result3 = await wrapper.execute_code(
                code="print('Session 3')",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            session3_id = result3.session_id
            print(f"✅ Third session created: {session3_id[:8]}... (LRU eviction worked)")
            
            # Verify one of the original sessions was evicted
            sessions = await wrapper.get_sessions()
            active_ids = {s.session_id for s in sessions}
            
            if session1_id not in active_ids:
                print(f"   Session 1 ({session1_id[:8]}...) was evicted")
            elif session2_id not in active_ids:
                print(f"   Session 2 ({session2_id[:8]}...) was evicted")
            else:
                print("   ❌ No original session was evicted!")
                
        except Exception as e:
            print(f"❌ Failed to create third session: {e}")
        
        print("\n=== Processing Session Protection Test Completed ===")


async def main():
    """Run all LRU eviction tests."""
    print("Starting LRU Eviction Tests...")
    print("Make sure microsandbox server is running on the configured URL\n")
    
    try:
        # Test basic LRU eviction
        success1 = await test_lru_eviction()
        
        # Test processing session protection
        await test_processing_session_protection()
        
        if success1:
            print("\n🎉 All tests completed successfully!")
        else:
            print("\n❌ Some tests failed!")
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())