# Structured Logging Guide

Speekium uses [structlog](https://www.structlog.org/) for structured logging with automatic sensitive data masking and context tracking.

## Quick Start

```python
from logger import get_logger, new_request, set_component

# Get a logger
logger = get_logger(__name__)

# Log events with key-value pairs
logger.info("model_loaded", model_name="SenseVoice", load_time=1.5)
logger.warning("high_latency", latency_ms=500, threshold_ms=200)
logger.error("api_error", error=str(e), retry_count=3)
```

## Core Features

### 1. Structured Event Logging

Instead of string messages, log events with structured data:

```python
# ❌ Old way (unstructured)
print(f"User {user_id} logged in from {ip}")

# ✅ New way (structured)
logger.info("user_login", user_id=user_id, ip=ip)
```

**Benefits**:
- Parseable by log aggregation systems
- Easy filtering and querying
- Automatic JSON serialization for production

### 2. Automatic Sensitive Data Masking

The following fields are automatically masked:

#### API Keys and Secrets
```python
logger.info("api_call", api_key="sk-1234567890abcdef")
# Output: api_key="***cdef" (shows last 4 chars only)
```

**Masked fields**: `api_key`, `anthropic_api_key`, `password`, `token`, `secret`, `auth`, `authorization`, `cookie`, `session`

#### User Input Text
```python
logger.info("user_input", text="a" * 100)
# Output: text="aaaaaaaaaa... (100 chars)" (50 char preview)
```

**Masked fields**: `text`, `message`, `user_input`, `transcription`

#### File Paths
```python
logger.info("file_processed", file_path="/home/user/secret/data.txt")
# Output: file_path="data.txt" (basename only)
```

**Masked fields**: `file_path`, `audio_file`, `temp_file`

### 3. Context Tracking

Track requests, sessions, and components automatically:

```python
from logger import new_request, new_session, set_component

# Start a new request (generates 8-char UUID)
request_id = new_request()  # "a1b2c3d4"

# Start a new session
session_id = new_session()  # "e5f6g7h8"

# Set current component
set_component("ASR")

# All subsequent logs include this context
logger.info("transcription_complete", text="hello")
# Output includes: request_id="a1b2c3d4", session_id="e5f6g7h8", component="ASR"
```

## Configuration

### Environment Variables

```bash
# Log level (DEBUG, INFO, WARNING, ERROR)
export LOG_LEVEL=INFO

# Output format (console, json, auto)
export LOG_FORMAT=console

# Enable colored output (true, false)
export LOG_COLORED=true
```

### Programmatic Configuration

```python
from logger import configure_logging

# Development: human-readable console output
configure_logging(level="DEBUG", format="console", colored=True)

# Production: JSON output for log aggregation
configure_logging(level="INFO", format="json", colored=False)

# Auto: console for TTY, JSON for pipes
configure_logging(level="INFO", format="auto", colored=True)
```

## Output Formats

### Console Format (Development)

```
2025-01-10T12:34:56.789Z [info     ] model_loaded [speekium.asr] model_name=SenseVoice load_time=1.5 component=ASR
```

### JSON Format (Production)

```json
{"event": "model_loaded", "level": "info", "logger": "speekium.asr", "timestamp": "2025-01-10T12:34:56.789Z", "model_name": "SenseVoice", "load_time": 1.5, "component": "ASR"}
```

## Best Practices

### 1. Use Descriptive Event Names

```python
# ❌ Vague
logger.info("done")

# ✅ Specific
logger.info("asr_transcription_complete", duration_ms=150)
```

### 2. Include Relevant Context

```python
# ❌ Minimal
logger.error("failed")

# ✅ Rich context
logger.error("api_request_failed",
    endpoint="/v1/chat",
    status_code=500,
    retry_count=3,
    error=str(e))
```

### 3. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational events (default)
- **WARNING**: Warning conditions that should be reviewed
- **ERROR**: Error conditions that need attention

```python
logger.debug("cache_hit", key="model_weights")
logger.info("model_loaded", model="SenseVoice")
logger.warning("high_latency", latency_ms=500)
logger.error("model_load_failed", error=str(e))
```

### 4. Set Component Context

```python
from logger import set_component

# In VAD code
set_component("VAD")
logger.info("vad_detected_speech", duration_ms=2500)

# In ASR code
set_component("ASR")
logger.info("transcription_started")

# In LLM code
set_component("LLM")
logger.info("chat_response_generated", tokens=150)

# In TTS code
set_component("TTS")
logger.info("audio_generated", duration_sec=3.5)
```

### 5. Don't Log Sensitive Data Directly

The masking processor catches common fields, but be careful:

```python
# ❌ Custom sensitive field (not auto-masked)
logger.info("user_data", credit_card="1234-5678-9012-3456")

# ✅ Mask manually or use safe fields
logger.info("payment_processed",
    user_id=user_id,  # Safe
    last_4_digits="3456")  # Safe
```

## Migration from print()

### Before (Unstructured)
```python
print("🔄 Loading SenseVoice model...", flush=True)
print(f"✅ Recording complete ({duration:.1f}s)", flush=True)
print(f"❌ Error: {e}", flush=True)
```

### After (Structured)
```python
logger.info("model_loading", model="SenseVoice")
logger.info("recording_complete", duration=duration)
logger.error("operation_failed", error=str(e))
```

## Testing

Test logging functionality:

```bash
# Run logging tests
uv run pytest tests/unit/test_logging.py -v

# Test specific category
uv run pytest tests/unit/test_logging.py::TestSensitiveDataMasking -v
```

## Common Patterns

### Error Handling
```python
try:
    result = risky_operation()
    logger.info("operation_success", result=result)
except Exception as e:
    logger.error("operation_failed",
        error=str(e),
        error_type=type(e).__name__,
        traceback=traceback.format_exc())
```

### Performance Monitoring
```python
import time

start = time.time()
process_data()
duration = time.time() - start

logger.info("data_processed",
    duration_ms=duration * 1000,
    items_count=len(items))
```

### Request Tracking
```python
from logger import new_request, get_logger

def handle_request(data):
    request_id = new_request()
    logger = get_logger(__name__)

    logger.info("request_started", data_size=len(data))

    try:
        result = process(data)
        logger.info("request_completed", result_size=len(result))
        return result
    except Exception as e:
        logger.error("request_failed", error=str(e))
        raise
```

## Troubleshooting

### Issue: Logs not appearing

**Check log level**:
```python
# Ensure level is set correctly
configure_logging(level="DEBUG")
```

### Issue: Sensitive data not masked

**Check field name** - masking is based on field names. Use standard names:
- API keys: `api_key`, `anthropic_api_key`
- Passwords: `password`, `secret`
- Tokens: `token`, `auth`
- User text: `text`, `message`, `user_input`
- Files: `file_path`, `audio_file`

### Issue: JSON format not working

**Check configuration**:
```python
# Explicitly set JSON format
configure_logging(level="INFO", format="json", colored=False)
```

### Issue: Context not showing

**Ensure context is set** before logging:
```python
from logger import new_request, set_component

new_request()  # Generate request ID
set_component("VAD")  # Set component

# Now logs will include context
logger.info("event")
```

## Reference

### Logger Module API

```python
# Configuration
configure_logging(level="INFO", format="auto", colored=True)

# Logger factory
logger = get_logger(name="my_module")

# Context management
request_id = new_request()  # Returns: "a1b2c3d4"
session_id = new_session()  # Returns: "e5f6g7h8"
set_component(component="ASR")

# Logging methods
logger.debug(event, **kwargs)
logger.info(event, **kwargs)
logger.warning(event, **kwargs)
logger.error(event, **kwargs)
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `level` | str | "INFO" | Log level (DEBUG/INFO/WARNING/ERROR) |
| `format` | str | "auto" | Output format (console/json/auto) |
| `colored` | bool | True | Enable colored console output |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | "INFO" | Minimum log level to output |
| `LOG_FORMAT` | "auto" | Output format selection |
| `LOG_COLORED` | "true" | Enable/disable colors |

## See Also

- [structlog documentation](https://www.structlog.org/)
- [Logging best practices](https://www.structlog.org/en/stable/best-practices.html)
- [Test suite](../tests/unit/test_logging.py)
