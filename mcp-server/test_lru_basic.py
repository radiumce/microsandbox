#!/usr/bin/env python3
"""
Basic test for LRU eviction mechanism.

This is a simple, standalone test that can be run directly without pytest.
It tests the core LRU eviction functionality with minimal setup.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add the parent directory to the path so we can import the wrapper
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from microsandbox_wrapper.config import WrapperConfig
from microsandbox_wrapper.models import SandboxFlavor, SessionStatus
from microsandbox_wrapper.session_manager import ManagedSession


def test_session_can_be_evicted():
    """Test that sessions can be correctly identified as evictable."""
    print("Testing session eviction eligibility...")
    
    config = WrapperConfig(
        server_url="http://localhost:5555",
        max_concurrent_sessions=3,
        enable_lru_eviction=True
    )
    
    session = ManagedSession("test-session", "python", SandboxFlavor.SMALL, config)
    
    # Test evictable statuses
    evictable_statuses = [
        SessionStatus.READY,
        SessionStatus.RUNNING,
        SessionStatus.ERROR,
        SessionStatus.STOPPED
    ]
    
    for status in evictable_statuses:
        session.status = status
        assert session.can_be_evicted(), f"Session with status {status.value} should be evictable"
        print(f"  ✅ {status.value} status: evictable")
    
    # Test non-evictable statuses
    non_evictable_statuses = [
        SessionStatus.PROCESSING,
        SessionStatus.CREATING
    ]
    
    for status in non_evictable_statuses:
        session.status = status
        assert not session.can_be_evicted(), f"Session with status {status.value} should NOT be evictable"
        print(f"  ✅ {status.value} status: protected")
    
    print("✅ Session eviction eligibility test passed!\n")


def test_session_touch():
    """Test that session touch updates last accessed time."""
    print("Testing session touch functionality...")
    
    config = WrapperConfig(
        server_url="http://localhost:5555",
        max_concurrent_sessions=3,
        enable_lru_eviction=True
    )
    
    session = ManagedSession("test-session", "python", SandboxFlavor.SMALL, config)
    original_time = session.last_accessed
    
    # Wait a tiny bit to ensure different timestamp
    import time
    time.sleep(0.01)
    
    # Touch the session
    session.touch()
    
    assert session.last_accessed > original_time, "Touch should update last_accessed time"
    print(f"  ✅ Original time: {original_time}")
    print(f"  ✅ After touch:   {session.last_accessed}")
    print("✅ Session touch test passed!\n")


def test_lru_ordering():
    """Test LRU ordering logic."""
    print("Testing LRU ordering logic...")
    
    # Create mock session data with different access times
    base_time = datetime.now()
    sessions = []
    
    for i in range(4):
        session_data = {
            'id': f"session-{i}",
            'last_accessed': base_time - timedelta(minutes=i),
            'age_minutes': i
        }
        sessions.append(session_data)
    
    print("  Sessions before sorting:")
    for session in sessions:
        print(f"    {session['id']}: {session['age_minutes']} minutes ago")
    
    # Sort by LRU (oldest first)
    sessions.sort(key=lambda s: s['last_accessed'])
    
    print("  Sessions after LRU sorting (oldest first):")
    for i, session in enumerate(sessions):
        print(f"    {i+1}. {session['id']}: {session['age_minutes']} minutes ago")
    
    # Verify ordering
    assert sessions[0]['id'] == 'session-3', "Oldest session should be first"
    assert sessions[-1]['id'] == 'session-0', "Newest session should be last"
    
    print("✅ LRU ordering test passed!\n")


def test_config_lru_setting():
    """Test LRU configuration setting."""
    print("Testing LRU configuration...")
    
    # Test enabled by default
    config1 = WrapperConfig()
    assert config1.enable_lru_eviction is True, "LRU should be enabled by default"
    print("  ✅ LRU enabled by default")
    
    # Test explicit enable
    config2 = WrapperConfig(enable_lru_eviction=True)
    assert config2.enable_lru_eviction is True, "LRU should be enabled when set to True"
    print("  ✅ LRU can be explicitly enabled")
    
    # Test explicit disable
    config3 = WrapperConfig(enable_lru_eviction=False)
    assert config3.enable_lru_eviction is False, "LRU should be disabled when set to False"
    print("  ✅ LRU can be disabled")
    
    print("✅ LRU configuration test passed!\n")


async def test_mock_eviction_scenario():
    """Test a mock eviction scenario."""
    print("Testing mock eviction scenario...")
    
    # Simulate having 3 sessions at the limit
    sessions = [
        {
            'id': 'session-1',
            'last_accessed': datetime.now() - timedelta(minutes=5),
            'status': SessionStatus.READY,
            'can_evict': True
        },
        {
            'id': 'session-2', 
            'last_accessed': datetime.now() - timedelta(minutes=2),
            'status': SessionStatus.PROCESSING,
            'can_evict': False  # Processing, cannot evict
        },
        {
            'id': 'session-3',
            'last_accessed': datetime.now() - timedelta(minutes=3),
            'status': SessionStatus.READY,
            'can_evict': True
        }
    ]
    
    print("  Current sessions:")
    for session in sessions:
        minutes_ago = (datetime.now() - session['last_accessed']).total_seconds() / 60
        print(f"    {session['id']}: {minutes_ago:.1f}min ago, {session['status'].value}, "
              f"evictable: {session['can_evict']}")
    
    # Filter evictable sessions and sort by LRU
    evictable = [s for s in sessions if s['can_evict']]
    evictable.sort(key=lambda s: s['last_accessed'])
    
    print("  Evictable sessions (LRU order):")
    for i, session in enumerate(evictable):
        minutes_ago = (datetime.now() - session['last_accessed']).total_seconds() / 60
        print(f"    {i+1}. {session['id']}: {minutes_ago:.1f}min ago")
    
    # The oldest evictable session should be session-1 (5 minutes ago)
    if evictable:
        lru_session = evictable[0]
        assert lru_session['id'] == 'session-1', "session-1 should be the LRU evictable session"
        print(f"  ✅ Would evict: {lru_session['id']} (oldest evictable)")
    
    print("✅ Mock eviction scenario test passed!\n")


def main():
    """Run all basic LRU tests."""
    print("=" * 50)
    print("Basic LRU Eviction Tests")
    print("=" * 50)
    print()
    
    try:
        # Run synchronous tests
        test_session_can_be_evicted()
        test_session_touch()
        test_lru_ordering()
        test_config_lru_setting()
        
        # Run async test
        asyncio.run(test_mock_eviction_scenario())
        
        print("=" * 50)
        print("🎉 All basic LRU tests passed!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("1. Run the full test suite: python -m pytest tests/test_lru_eviction.py -v")
        print("2. Run integration tests: python test_lru_eviction.py")
        print("3. Try the example: python examples/lru_eviction_example.py")
        
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()