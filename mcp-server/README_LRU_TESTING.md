# LRU Eviction Testing Guide

This guide explains how to test the LRU (Least Recently Used) eviction mechanism in the microsandbox wrapper.

## Quick Start

### 1. Fast Validation (30 seconds)
```bash
cd mcp-server
python3 quick_lru_test.py
```

This runs a quick validation of core LRU functionality without any external dependencies.

### 2. Complete Basic Testing (1 minute)
```bash
python3 test_lru_basic.py
```

This runs comprehensive basic tests including mock scenarios and configuration validation.

### 3. Advanced Unit Tests (with pytest)
```bash
python3 -m pytest tests/test_lru_eviction.py -v
```

This runs advanced unit tests with mocking and detailed assertions.

## Full Test Suite

### Run All Tests
```bash
./run_lru_tests.sh
```

This script runs the complete test suite including:
- Basic functionality tests
- Unit tests with pytest
- Configuration validation
- Integration tests (if server is running)

## Integration Testing (Requires Server)

### 1. Start Microsandbox Server
```bash
cd ../microsandbox-server
cargo run
```

### 2. Run Integration Tests
```bash
cd ../mcp-server
python3 test_lru_eviction.py
```

### 3. Try Interactive Example
```bash
python3 examples/lru_eviction_example.py
```

## Test Files Overview

| File | Purpose | Runtime | Dependencies |
|------|---------|---------|--------------|
| `quick_lru_test.py` | Fast core validation | ~1s | None |
| `test_lru_basic.py` | Comprehensive basic tests | ~2s | None |
| `tests/test_lru_eviction.py` | Advanced unit tests | ~1s | pytest |
| `test_lru_eviction.py` | Integration tests | ~30s | Server |
| `examples/lru_eviction_example.py` | Interactive demo | ~45s | Server |

## What Gets Tested

### ✅ Core Functionality
- Session eviction eligibility
- LRU ordering logic
- Session touch mechanism
- Configuration settings

### ✅ Eviction Algorithm
- Basic LRU eviction
- Memory-based eviction
- Processing session protection
- Resource limit enforcement

### ✅ Edge Cases
- No evictable sessions
- Disabled LRU eviction
- Mixed session states
- Resource pressure scenarios

### ✅ Integration
- Real session creation/eviction
- Server communication
- End-to-end workflows

## Expected Output

### Successful Test Run
```
🚀 Quick LRU Eviction Test
==================================================
🧪 Testing LRU Core Functionality
✅ Successfully imported LRU components
✅ ready: evictable
✅ processing: protected
✅ Session touch updates last_accessed time
✅ LRU ordering works correctly
✅ LRU enabled by default
==================================================
🎉 All LRU core functionality tests PASSED!
```

### Pytest Output
```
============= test session starts ==============
tests/test_lru_eviction.py::TestLRUEviction::test_managed_session_can_be_evicted PASSED
tests/test_lru_eviction.py::TestLRUEviction::test_lru_eviction_basic PASSED
...
============== 12 passed in 0.22s ==============
```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the mcp-server directory
cd mcp-server
python3 quick_lru_test.py
```

### Server Connection Issues
```bash
# Check if server is running
curl http://localhost:5555/health

# Start server if needed
cd ../microsandbox-server
cargo run
```

### Missing Dependencies
```bash
# Install pytest for advanced tests
pip install pytest

# Install other dependencies
pip install -r requirements.txt
```

## Configuration Testing

### Test Different LRU Settings
```bash
# Test with LRU disabled
MSB_ENABLE_LRU_EVICTION=false python3 quick_lru_test.py

# Test with custom limits
MSB_MAX_SESSIONS=5 MSB_MAX_TOTAL_MEMORY_MB=4096 python3 test_lru_basic.py
```

## Performance Testing

### Measure Test Performance
```bash
# Time the quick test
time python3 quick_lru_test.py

# Time the full basic test
time python3 test_lru_basic.py

# Profile with pytest
python3 -m pytest tests/test_lru_eviction.py --durations=10
```

## Continuous Integration

### Add to CI Pipeline
```yaml
# Example GitHub Actions step
- name: Test LRU Eviction
  run: |
    cd mcp-server
    python3 quick_lru_test.py
    python3 test_lru_basic.py
    python3 -m pytest tests/test_lru_eviction.py -v
```

## Next Steps

After running the tests successfully:

1. **Read the Documentation**:
   - `LRU_EVICTION_GUIDE.md` - User guide
   - `LRU_IMPLEMENTATION_SUMMARY.md` - Technical details
   - `LRU_TEST_SUMMARY.md` - Test coverage details

2. **Try the Examples**:
   - `examples/lru_eviction_example.py` - Interactive demonstration

3. **Configure for Your Use Case**:
   - Set `MSB_ENABLE_LRU_EVICTION=true/false`
   - Adjust `MSB_MAX_SESSIONS` and `MSB_MAX_TOTAL_MEMORY_MB`
   - Review `CONFIGURATION_GUIDE.md`

4. **Monitor in Production**:
   - Watch for eviction log messages
   - Monitor resource usage patterns
   - Adjust limits based on workload

## Support

If you encounter issues with the LRU eviction tests:

1. Check the test output for specific error messages
2. Verify your Python environment and dependencies
3. Ensure the microsandbox server is running for integration tests
4. Review the troubleshooting section in `LRU_EVICTION_GUIDE.md`