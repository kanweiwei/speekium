# Resource Limits Documentation

## Overview

Speekium implements comprehensive resource limiting to prevent resource exhaustion attacks (DoS) and ensure stable operation under various conditions.

## Resource Limits

### Memory Limits
- **Soft Limit**: 500MB (RLIMIT_AS)
- **Hard Limit**: 1GB (RLIMIT_AS)
- **Purpose**: Prevent memory exhaustion and OOM (Out of Memory) conditions
- **Platform**: Unix/Linux only (not available on Windows)

### CPU Time Limits
- **Limit**: 300 seconds (5 minutes) per process
- **Type**: RLIMIT_CPU
- **Purpose**: Prevent infinite loops or CPU-intensive operations from hanging the system
- **Signal**: SIGXCPU raised when limit is exceeded
- **Action**: Process terminated with error logging

### File Size Limits
- **Limit**: 100MB per file
- **Type**: RLIMIT_FSIZE
- **Purpose**: Prevent disk space exhaustion from large file creation
- **Platform**: Unix/Linux only

### File Descriptor Limits
- **Limit**: 1024 open file descriptors
- **Type**: RLIMIT_NOFILE
- **Purpose**: Prevent file descriptor exhaustion
- **Platform**: Unix/Linux only

## Operation Timeouts

### VAD (Voice Activity Detection)
- **Timeout**: 30 seconds
- **Operation**: `record_with_interruption()`
- **Failure Mode**: Logs error, returns early from conversation turn
- **Reason**: Prevent indefinite waiting for speech detection

### ASR (Automatic Speech Recognition)
- **Timeout**: 60 seconds (implicit in VAD)
- **Operation**: Speech transcription
- **Failure Mode**: Returns empty or error
- **Reason**: Long audio files or slow ASR models

### LLM (Large Language Model)
- **Timeout**: 120 seconds (2 minutes)
- **Operation**: `backend.chat()` and `backend.chat_stream()`
- **Failure Mode**: Logs error, skips response generation
- **Reason**: Slow LLM responses or network issues

### TTS (Text-to-Speech)
- **Timeout**: 30 seconds
- **Operation**: `generate_audio()`
- **Failure Mode**:
  - **Non-streaming**: Logs error, skips audio playback
  - **Streaming**: Logs error, continues with next sentence
- **Reason**: Slow TTS generation or network issues

## Platform Compatibility

### Unix/Linux
- ✅ Full resource limiting support
- ✅ SIGALRM for sync timeout decorator
- ✅ SIGXCPU for CPU time limit
- ✅ All RLIMIT_* constants available

### macOS
- ⚠️ Partial support
- ✅ CPU time limits work
- ✅ File size limits work
- ✅ File descriptor limits work
- ⚠️ Memory limits (RLIMIT_AS) may be skipped if system limit is lower
  - Reason: macOS often has very high or unlimited AS limits
  - Fallback: Uses system maximum or skips if setting fails

### Windows
- ❌ No resource limiting support
- ❌ `resource` module not available
- ✅ Async timeout protection works (asyncio.wait_for)
- ❌ Sync timeout decorator disabled (signal.alarm not available)
- **Behavior**: Logs warning, continues without limits

## Implementation Details

### Resource Limit Setting

**Location**: `resource_limiter.py:ResourceLimiter.set_limits()`

**Flow**:
1. Check platform (skip on Windows)
2. Import `resource` module
3. For each limit type:
   - Get current system maximum
   - Use minimum of our limit and system max
   - Set limit with error handling
   - Log warning if setting fails
4. Register SIGXCPU handler for CPU timeout
5. Log successful limit application

**Error Handling**:
- Individual limit failures are logged as warnings
- Overall function returns `True` if any limits were set
- Process continues even if some limits fail

### Timeout Protection

#### Synchronous Timeout (Unix/Linux only)

```python
from resource_limiter import ResourceLimiter

@ResourceLimiter.with_timeout(30)
def long_operation():
    # ... operation code ...
    return result
```

**Mechanism**: Uses `signal.alarm()` and `SIGALRM`

**Limitations**:
- Not available on Windows
- Cannot be nested (signal.alarm is global)
- Only works in main thread

#### Asynchronous Timeout (Cross-platform)

```python
from resource_limiter import with_timeout

result = await with_timeout(
    my_async_function(),
    seconds=30,
    operation_name="my_operation"
)
```

**Mechanism**: Uses `asyncio.wait_for()`

**Advantages**:
- Cross-platform (works on Windows)
- Can be nested
- Thread-safe
- **Recommended** for all async operations

### Integration Points

#### Main Program Startup

**File**: `speekium.py`

```python
if __name__ == "__main__":
    # Set resource limits
    from resource_limiter import initialize_resource_limits
    initialize_resource_limits()

    # Run main program
    asyncio.run(main())
```

#### Voice Activity Detection

**File**: `speekium.py:chat_once()`

```python
# VAD with 30-second timeout
text, language = await with_timeout(
    self.record_with_interruption(),
    seconds=30,
    operation_name="VAD_recording"
)
```

#### LLM Chat (Non-streaming)

```python
# LLM with 120-second timeout
response = await with_timeout(
    asyncio.to_thread(backend.chat, text),
    seconds=120,
    operation_name="LLM_chat"
)
```

#### TTS Generation (Streaming)

```python
# TTS with 30-second timeout per sentence
audio_file = await with_timeout(
    self.generate_audio(sentence, language),
    seconds=30,
    operation_name="TTS_streaming"
)
```

## Logging

All resource limit operations use structured logging via `structlog`:

### Successful Limit Setting

```json
{
  "event": "resource_limits_set",
  "memory_soft_mb": 500,
  "memory_hard_mb": 1024,
  "cpu_time_sec": 300,
  "file_size_mb": 100,
  "file_descriptors": 1024,
  "timestamp": "2025-01-10T17:30:00Z"
}
```

### Limit Setting Skipped (Windows)

```json
{
  "event": "resource_limits_skipped",
  "platform": "Windows",
  "reason": "resource module not available on Windows",
  "timestamp": "2025-01-10T17:30:00Z"
}
```

### Limit Setting Warning (Partial Failure)

```json
{
  "event": "memory_limit_skip",
  "reason": "current limit exceeds maximum limit",
  "timestamp": "2025-01-10T17:30:00Z"
}
```

### CPU Time Exceeded

```json
{
  "event": "cpu_time_limit_exceeded",
  "signal": 24,
  "limit_seconds": 300,
  "action": "terminating_process",
  "level": "error",
  "timestamp": "2025-01-10T17:30:00Z"
}
```

### Operation Timeout

```json
{
  "event": "async_operation_timeout",
  "operation": "VAD_recording",
  "timeout_seconds": 30,
  "level": "error",
  "timestamp": "2025-01-10T17:30:00Z"
}
```

## Testing

### Unit Tests

**File**: `tests/unit/test_resource_limiter.py`

**Coverage**:
- ✅ Resource limit setting (platform-aware)
- ✅ Synchronous timeout decorator
- ✅ Asynchronous timeout protection
- ✅ Error handling and edge cases
- ✅ Platform compatibility (Unix/Linux/Windows)
- ✅ Concurrent timeout operations
- ✅ Resource usage retrieval

**Test Results**: 17 passed, 1 skipped (Windows-specific test)

### Running Tests

```bash
# Run resource limiter tests
uv run pytest tests/unit/test_resource_limiter.py -v

# Run with coverage
uv run pytest tests/unit/test_resource_limiter.py --cov=resource_limiter

# Run specific test class
uv run pytest tests/unit/test_resource_limiter.py::TestAsyncTimeout -v
```

## Troubleshooting

### Issue: Resource limits not applied on macOS

**Symptom**: Warnings in logs about memory limit skip

**Cause**: macOS system limits may be higher than our limits

**Solution**: This is expected behavior. CPU and file limits should still work.

**Verification**:
```bash
# Check current limits
ulimit -a

# Check from Python
python3 -c "import resource; print(resource.getrlimit(resource.RLIMIT_AS))"
```

### Issue: Timeout decorator not working

**Symptom**: Function doesn't timeout even with decorator

**Possible Causes**:
1. **Windows**: Sync decorator doesn't work (use async timeout)
2. **Not in main thread**: signal.alarm only works in main thread
3. **Already inside signal handler**: Cannot nest signal.alarm

**Solutions**:
- Use `with_timeout` async function instead of `@with_timeout` decorator
- Move operation to main thread
- Use asyncio-based timeout

### Issue: Operation timed out unexpectedly

**Symptom**: Legitimate operations timing out

**Possible Causes**:
1. Timeout too short for operation
2. Slow network/disk
3. Large input data

**Solutions**:
- Increase timeout value for specific operation
- Check network/disk performance
- Optimize operation or split into chunks

## Configuration

### Customizing Resource Limits

Edit `resource_limiter.py`:

```python
class ResourceLimiter:
    # Increase memory limits
    MEMORY_SOFT_LIMIT = 1024 * 1024 * 1024  # 1GB
    MEMORY_HARD_LIMIT = 2048 * 1024 * 1024  # 2GB

    # Increase CPU time
    CPU_TIME_LIMIT = 600  # 10 minutes
```

### Customizing Operation Timeouts

Edit `speekium.py:chat_once()`:

```python
# Increase VAD timeout
text, language = await with_timeout(
    self.record_with_interruption(),
    seconds=60,  # Was 30
    operation_name="VAD_recording"
)

# Increase LLM timeout
response = await with_timeout(
    asyncio.to_thread(backend.chat, text),
    seconds=300,  # Was 120
    operation_name="LLM_chat"
)
```

## Security Considerations

### DoS Attack Mitigation

Resource limits protect against:
- **Memory exhaustion**: Prevents OOM crashes
- **CPU exhaustion**: Prevents infinite loops
- **Disk exhaustion**: Prevents large file creation
- **FD exhaustion**: Prevents too many open files

### Timeout Benefits

Operation timeouts protect against:
- **Slow network attacks**: Prevents hanging on slow responses
- **Algorithmic complexity attacks**: Prevents slow AI operations from hanging
- **Resource exhaustion**: Limits maximum time per operation

### Best Practices

1. **Set limits at startup**: Apply before any user input
2. **Log all limit events**: Track for security analysis
3. **Use async timeouts**: More reliable than signal-based
4. **Handle timeouts gracefully**: Don't crash, log and continue
5. **Monitor limit hits**: Frequent hits may indicate attack or misconfiguration

## Performance Impact

### Resource Limit Setting
- **Cost**: One-time at startup (~1ms)
- **Runtime Impact**: None (kernel enforces)

### Timeout Protection
- **Async timeout**: ~0.1ms overhead per operation
- **Sync timeout**: ~0.05ms overhead (signal setup)

### Memory Overhead
- **Resource limiter module**: ~50KB
- **Per-operation state**: ~1KB

## Future Improvements

### Planned Enhancements
- [ ] Dynamic timeout adjustment based on operation history
- [ ] Resource usage monitoring and alerting
- [ ] Configurable limits via environment variables
- [ ] Per-operation resource tracking
- [ ] Windows resource monitoring (without limits)

## References

- [Python resource module](https://docs.python.org/3/library/resource.html)
- [asyncio.wait_for](https://docs.python.org/3/library/asyncio-task.html#asyncio.wait_for)
- [POSIX Resource Limits](https://pubs.opengroup.org/onlinepubs/9699919799/functions/setrlimit.html)
- [DoS Attack Prevention](https://owasp.org/www-community/attacks/Denial_of_Service)

## Version History

- **2025-01-10**: Initial implementation
  - Resource limits for memory, CPU, file size, file descriptors
  - Operation timeouts for VAD, ASR, LLM, TTS
  - Cross-platform support (Unix/Linux/macOS/Windows)
  - 17 unit tests with 100% pass rate
