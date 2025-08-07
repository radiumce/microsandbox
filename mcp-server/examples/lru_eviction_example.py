#!/usr/bin/env python3
"""
Example demonstrating LRU eviction mechanism in microsandbox wrapper.

This example shows how to:
1. Configure LRU eviction
2. Create sessions up to resource limits
3. Observe automatic eviction behavior
4. Monitor session lifecycle
"""

import asyncio
import os
from datetime import datetime

from microsandbox_wrapper import MicrosandboxWrapper
from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor


async def demonstrate_lru_eviction():
    """Demonstrate LRU eviction with a practical example."""
    print("=== LRU Eviction Demonstration ===\n")
    
    # Configure wrapper with low limits for demonstration
    config = WrapperConfig(
        server_url=os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555'),
        api_key=os.getenv('MSB_API_KEY'),
        max_concurrent_sessions=3,  # Low limit for demo
        max_total_memory_mb=3072,   # 3GB total
        enable_lru_eviction=True,   # Enable LRU eviction
        session_timeout=300         # 5 minutes
    )
    
    print(f"Configuration:")
    print(f"  Max sessions: {config.max_concurrent_sessions}")
    print(f"  Max memory: {config.max_total_memory_mb}MB")
    print(f"  LRU eviction: {config.enable_lru_eviction}")
    print()
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        # Step 1: Create sessions up to the limit
        print("1. Creating sessions up to the limit...")
        sessions = []
        
        for i in range(config.max_concurrent_sessions):
            result = await wrapper.execute_code(
                code=f"""
import time
print(f"Session {i+1} created at {{time.strftime('%H:%M:%S')}}")
session_id = "{i+1}"
""",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            sessions.append(result.session_id)
            print(f"   Created session {i+1}: {result.session_id[:8]}...")
            await asyncio.sleep(1)  # Ensure different timestamps
        
        # Show current resource usage
        stats = await wrapper.get_resource_stats()
        print(f"   Resource usage: {stats.active_sessions} sessions, {stats.total_memory_mb}MB")
        print()
        
        # Step 2: Access some sessions to update LRU order
        print("2. Accessing sessions to update LRU order...")
        
        # Access session 2 and 3, leaving session 1 as LRU
        for i in [1, 2]:  # Access sessions 2 and 3 (indices 1 and 2)
            result = await wrapper.execute_code(
                code=f"""
import time
print(f"Session {i+2} accessed at {{time.strftime('%H:%M:%S')}}")
print(f"This session will be kept (not LRU)")
""",
                session_id=sessions[i],
                template="python"
            )
            print(f"   Accessed session {i+2}: {sessions[i][:8]}...")
            await asyncio.sleep(1)
        
        print()
        
        # Step 3: Show current session order
        print("3. Current session order (by last access time):")
        session_infos = await wrapper.get_sessions()
        session_infos.sort(key=lambda s: s.last_accessed)
        
        for i, session_info in enumerate(session_infos):
            status = "LRU (will be evicted)" if i == 0 else "Recently used"
            print(f"   {i+1}. {session_info.session_id[:8]}... "
                  f"(accessed: {session_info.last_accessed.strftime('%H:%M:%S')}) - {status}")
        
        lru_session = session_infos[0].session_id
        print()
        
        # Step 4: Create a new session that triggers eviction
        print("4. Creating new session (should trigger LRU eviction)...")
        
        try:
            result = await wrapper.execute_code(
                code="""
import time
print(f"New session created at {time.strftime('%H:%M:%S')}")
print("LRU session should have been evicted to make room for me!")
""",
                template="python",
                flavor=SandboxFlavor.SMALL
            )
            
            new_session = result.session_id
            print(f"   New session created: {new_session[:8]}...")
            print()
            
            # Step 5: Verify eviction occurred
            print("5. Verifying eviction results...")
            updated_sessions = await wrapper.get_sessions()
            updated_stats = await wrapper.get_resource_stats()
            
            print(f"   Resource usage after eviction: {updated_stats.active_sessions} sessions, "
                  f"{updated_stats.total_memory_mb}MB")
            
            active_session_ids = {s.session_id for s in updated_sessions}
            
            if lru_session not in active_session_ids:
                print(f"   ✅ SUCCESS: LRU session {lru_session[:8]}... was evicted")
            else:
                print(f"   ❌ FAILURE: LRU session {lru_session[:8]}... was NOT evicted")
            
            if new_session in active_session_ids:
                print(f"   ✅ SUCCESS: New session {new_session[:8]}... is active")
            else:
                print(f"   ❌ FAILURE: New session {new_session[:8]}... is NOT active")
            
            print()
            print("6. Final session list:")
            for i, session_info in enumerate(updated_sessions):
                print(f"   {i+1}. {session_info.session_id[:8]}... "
                      f"(accessed: {session_info.last_accessed.strftime('%H:%M:%S')}, "
                      f"status: {session_info.status.value})")
            
        except Exception as e:
            print(f"   ❌ Error creating new session: {e}")
    
    print("\n=== Demonstration Complete ===")


async def demonstrate_session_reuse():
    """Demonstrate how session reuse affects LRU ordering."""
    print("\n=== Session Reuse and LRU Ordering ===\n")
    
    config = WrapperConfig(
        server_url=os.getenv('MSB_SERVER_URL', 'http://127.0.0.1:5555'),
        api_key=os.getenv('MSB_API_KEY'),
        max_concurrent_sessions=2,
        enable_lru_eviction=True
    )
    
    async with MicrosandboxWrapper(config=config) as wrapper:
        print("1. Creating two sessions...")
        
        # Create first session
        result1 = await wrapper.execute_code(
            code="print('First session created')",
            template="python"
        )
        session1 = result1.session_id
        print(f"   Session 1: {session1[:8]}...")
        await asyncio.sleep(1)
        
        # Create second session
        result2 = await wrapper.execute_code(
            code="print('Second session created')",
            template="python"
        )
        session2 = result2.session_id
        print(f"   Session 2: {session2[:8]}...")
        await asyncio.sleep(1)
        
        print("\n2. Reusing first session (updates its LRU position)...")
        await wrapper.execute_code(
            code="print('First session reused - now most recently used!')",
            session_id=session1,  # Reuse session 1
            template="python"
        )
        
        print("\n3. Creating third session (should evict session 2, not session 1)...")
        result3 = await wrapper.execute_code(
            code="print('Third session created')",
            template="python"
        )
        session3 = result3.session_id
        print(f"   Session 3: {session3[:8]}...")
        
        # Check which sessions are still active
        active_sessions = await wrapper.get_sessions()
        active_ids = {s.session_id for s in active_sessions}
        
        print("\n4. Results:")
        print(f"   Session 1 active: {'✅' if session1 in active_ids else '❌'} "
              f"(should be active - was reused)")
        print(f"   Session 2 active: {'❌' if session2 not in active_ids else '✅'} "
              f"(should be evicted - was LRU)")
        print(f"   Session 3 active: {'✅' if session3 in active_ids else '❌'} "
              f"(should be active - newly created)")


async def main():
    """Run all LRU eviction demonstrations."""
    print("LRU Eviction Examples")
    print("====================")
    print("Make sure microsandbox server is running before starting.\n")
    
    try:
        # Basic LRU eviction demonstration
        await demonstrate_lru_eviction()
        
        # Session reuse demonstration
        await demonstrate_session_reuse()
        
        print("\n🎉 All demonstrations completed successfully!")
        print("\nKey takeaways:")
        print("- LRU eviction automatically manages resource limits")
        print("- Sessions are evicted based on last access time")
        print("- Reusing sessions keeps them active longer")
        print("- Processing sessions cannot be evicted")
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())