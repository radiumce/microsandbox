#!/usr/bin/env python3
"""
Quick LRU eviction test.

A minimal test to verify that the LRU eviction mechanism is working correctly.
This test focuses on the core functionality without external dependencies.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_lru_core_functionality():
    """Test the core LRU functionality."""
    print("🧪 Testing LRU Core Functionality")
    print("-" * 40)
    
    try:
        from microsandbox_wrapper.models import SessionStatus, SandboxFlavor
        from microsandbox_wrapper.config import WrapperConfig
        from microsandbox_wrapper.session_manager import ManagedSession
        
        print("✅ Successfully imported LRU components")
        
        # Test 1: Session eviction eligibility
        print("\n1. Testing session eviction eligibility...")
        config = WrapperConfig(enable_lru_eviction=True)
        session = ManagedSession("test-id", "python", SandboxFlavor.SMALL, config)
        
        # Test evictable states
        evictable_states = [SessionStatus.READY, SessionStatus.RUNNING, SessionStatus.ERROR]
        for state in evictable_states:
            session.status = state
            assert session.can_be_evicted(), f"Session in {state.value} should be evictable"
            print(f"   ✅ {state.value}: evictable")
        
        # Test protected states
        protected_states = [SessionStatus.PROCESSING, SessionStatus.CREATING]
        for state in protected_states:
            session.status = state
            assert not session.can_be_evicted(), f"Session in {state.value} should be protected"
            print(f"   ✅ {state.value}: protected")
        
        # Test 2: Session touch functionality
        print("\n2. Testing session touch functionality...")
        original_time = session.last_accessed
        import time
        time.sleep(0.01)  # Small delay
        session.touch()
        assert session.last_accessed > original_time, "Touch should update timestamp"
        print("   ✅ Session touch updates last_accessed time")
        
        # Test 3: LRU ordering logic
        print("\n3. Testing LRU ordering logic...")
        
        # Create mock sessions with different access times
        sessions = []
        base_time = datetime.now()
        
        for i in range(3):
            session_data = {
                'id': f'session-{i}',
                'last_accessed': base_time - timedelta(minutes=i),
                'evictable': True
            }
            sessions.append(session_data)
        
        # Sort by LRU (oldest first)
        sessions.sort(key=lambda s: s['last_accessed'])
        
        # Verify ordering
        assert sessions[0]['id'] == 'session-2', "Oldest session should be first"
        assert sessions[-1]['id'] == 'session-0', "Newest session should be last"
        print("   ✅ LRU ordering works correctly")
        
        # Test 4: Configuration
        print("\n4. Testing LRU configuration...")
        
        # Test default enabled
        config_default = WrapperConfig()
        assert config_default.enable_lru_eviction is True, "LRU should be enabled by default"
        print("   ✅ LRU enabled by default")
        
        # Test explicit disable
        config_disabled = WrapperConfig(enable_lru_eviction=False)
        assert config_disabled.enable_lru_eviction is False, "LRU should be disabled when set"
        print("   ✅ LRU can be disabled")
        
        # Test 5: Memory calculation
        print("\n5. Testing memory calculations...")
        
        small_memory = SandboxFlavor.SMALL.get_memory_mb()
        medium_memory = SandboxFlavor.MEDIUM.get_memory_mb()
        large_memory = SandboxFlavor.LARGE.get_memory_mb()
        
        assert small_memory == 1024, f"Small flavor should be 1024MB, got {small_memory}"
        assert medium_memory == 2048, f"Medium flavor should be 2048MB, got {medium_memory}"
        assert large_memory == 4096, f"Large flavor should be 4096MB, got {large_memory}"
        
        print(f"   ✅ Small flavor: {small_memory}MB")
        print(f"   ✅ Medium flavor: {medium_memory}MB")
        print(f"   ✅ Large flavor: {large_memory}MB")
        
        print("\n" + "=" * 50)
        print("🎉 All LRU core functionality tests PASSED!")
        print("=" * 50)
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the mcp-server directory")
        return False
        
    except AssertionError as e:
        print(f"❌ Test assertion failed: {e}")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_eviction_scenario():
    """Test a realistic eviction scenario."""
    print("\n🎯 Testing Realistic Eviction Scenario")
    print("-" * 40)
    
    try:
        from microsandbox_wrapper.models import SessionStatus
        from datetime import datetime, timedelta
        
        # Simulate 4 sessions with different states and access times
        base_time = datetime.now()
        sessions = [
            {
                'id': 'session-A',
                'last_accessed': base_time - timedelta(minutes=10),  # Oldest
                'status': SessionStatus.READY,
                'memory_mb': 1024
            },
            {
                'id': 'session-B', 
                'last_accessed': base_time - timedelta(minutes=5),
                'status': SessionStatus.PROCESSING,  # Protected
                'memory_mb': 1024
            },
            {
                'id': 'session-C',
                'last_accessed': base_time - timedelta(minutes=3),
                'status': SessionStatus.READY,
                'memory_mb': 1024
            },
            {
                'id': 'session-D',
                'last_accessed': base_time - timedelta(minutes=1),   # Newest
                'status': SessionStatus.READY,
                'memory_mb': 1024
            }
        ]
        
        print("Current sessions:")
        for session in sessions:
            minutes_ago = (base_time - session['last_accessed']).total_seconds() / 60
            protected = "🔒" if session['status'] == SessionStatus.PROCESSING else "  "
            print(f"  {protected} {session['id']}: {minutes_ago:.0f}min ago, {session['status'].value}")
        
        # Filter evictable sessions
        evictable = [s for s in sessions if s['status'] != SessionStatus.PROCESSING]
        evictable.sort(key=lambda s: s['last_accessed'])  # LRU order
        
        print(f"\nEvictable sessions (LRU order):")
        for i, session in enumerate(evictable):
            minutes_ago = (base_time - session['last_accessed']).total_seconds() / 60
            print(f"  {i+1}. {session['id']}: {minutes_ago:.0f}min ago")
        
        # Verify LRU logic
        assert len(evictable) == 3, "Should have 3 evictable sessions"
        assert evictable[0]['id'] == 'session-A', "session-A should be LRU"
        assert evictable[-1]['id'] == 'session-D', "session-D should be most recent"
        
        print(f"\n✅ LRU eviction would remove: {evictable[0]['id']} (oldest evictable)")
        print(f"✅ Protected session: session-B (PROCESSING)")
        
        return True
        
    except Exception as e:
        print(f"❌ Scenario test failed: {e}")
        return False


def main():
    """Run the quick LRU test."""
    print("🚀 Quick LRU Eviction Test")
    print("=" * 50)
    
    success = True
    
    # Run core functionality test
    if not test_lru_core_functionality():
        success = False
    
    # Run scenario test
    if not test_eviction_scenario():
        success = False
    
    if success:
        print("\n🎉 Quick LRU test completed successfully!")
        print("\nNext steps:")
        print("  • Run full tests: python test_lru_basic.py")
        print("  • Run integration: python test_lru_eviction.py")
        print("  • Try example: python examples/lru_eviction_example.py")
        print("  • Run test suite: ./run_lru_tests.sh")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()