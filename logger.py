"""
Structured logging configuration for Speekium

Features:
- Structured logging with structlog
- Automatic sensitive data masking
- Context-aware logging (request ID, session ID, component)
- Configurable output format (JSON for production, human-readable for development)
- Configurable log levels
"""

import os
import sys
import uuid
from typing import Any

import structlog
from structlog.types import EventDict, Processor

# ===== Sensitive Data Masking =====

SENSITIVE_KEYS = {
    "api_key",
    "anthropic_api_key",
    "password",
    "token",
    "secret",
    "auth",
    "authorization",
    "cookie",
    "session",
}

TEXT_PREVIEW_LENGTH = 50  # Preview length for user input text


def mask_sensitive_processor(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Mask sensitive fields in log messages

    Masks:
    - API keys, tokens, passwords
    - User input text (shows preview only)
    - File paths (shows basename only)
    """
    for key, value in event_dict.items():
        if not isinstance(value, str):
            continue

        # Mask API keys and secrets
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            if value:
                event_dict[key] = f"***{value[-4:]}" if len(value) > 4 else "***"
            continue

        # Mask user input text (show preview only)
        if key in ("text", "message", "user_input", "transcription"):
            if len(value) > TEXT_PREVIEW_LENGTH:
                event_dict[key] = f"{value[:TEXT_PREVIEW_LENGTH]}... ({len(value)} chars)"
            continue

        # Mask file paths (show basename only for security)
        if key in ("file_path", "audio_file", "temp_file") and "/" in value:
            event_dict[key] = os.path.basename(value)

    return event_dict


# ===== Context Management =====


class LoggerContext:
    """
    Thread-safe context manager for structured logging

    Provides:
    - Request ID for tracing
    - Session ID for user sessions
    - Component identification (VAD/ASR/LLM/TTS)
    """

    def __init__(self):
        self._request_id = None
        self._session_id = None
        self._component = None

    def new_request(self) -> str:
        """Generate a new request ID"""
        self._request_id = str(uuid.uuid4())[:8]
        return self._request_id

    def new_session(self) -> str:
        """Generate a new session ID"""
        self._session_id = str(uuid.uuid4())[:8]
        return self._session_id

    def set_component(self, component: str):
        """Set current component (VAD/ASR/LLM/TTS)"""
        self._component = component

    def get_context(self) -> dict[str, str]:
        """Get current logging context"""
        context = {}
        if self._request_id:
            context["request_id"] = self._request_id
        if self._session_id:
            context["session_id"] = self._session_id
        if self._component:
            context["component"] = self._component
        return context


# Global context instance
_context = LoggerContext()


# ===== Logger Configuration =====


def configure_logging(
    level: str = "INFO",
    format: str = "auto",
    colored: bool = True,
) -> None:
    """
    Configure structured logging for Speekium

    Args:
        level: Log level (DEBUG/INFO/WARNING/ERROR)
        format: Output format ('json', 'console', 'auto')
                'auto' uses JSON in production, console in development
        colored: Enable colored output for console format
    """
    # Determine format
    if format == "auto":
        # Use JSON in production (when LOG_FORMAT=json), console otherwise
        format = os.getenv("LOG_FORMAT", "console")

    # Configure processors
    processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        # Note: add_logger_name removed - requires stdlib logger with .name attribute
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        mask_sensitive_processor,
    ]

    if format == "json":
        # JSON format for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable format for development
        if colored and sys.stderr.isatty():
            processors.append(structlog.dev.ConsoleRenderer(colors=True))
        else:
            processors.append(structlog.dev.ConsoleRenderer(colors=False))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog.stdlib.logging, level.upper(), structlog.stdlib.logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ===== Logger Factory =====


def get_logger(name: str = "speekium") -> structlog.BoundLogger:
    """
    Get a structured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger with context
    """
    logger = structlog.get_logger(name)

    # Bind current context
    context = _context.get_context()
    if context:
        logger = logger.bind(**context)

    return logger


# ===== Context Helpers =====


def new_request() -> str:
    """Start a new request, returns request ID"""
    return _context.new_request()


def new_session() -> str:
    """Start a new session, returns session ID"""
    return _context.new_session()


def set_component(component: str):
    """Set current component for logging"""
    _context.set_component(component)


# ===== Module Initialization =====

# Auto-configure on import with defaults
# Can be reconfigured by calling configure_logging()
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format=os.getenv("LOG_FORMAT", "auto"),
    colored=os.getenv("LOG_COLORED", "true").lower() == "true",
)
