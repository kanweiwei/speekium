"""
Speekium - Voice Assistant Module

This module provides voice assistant functionality including:
- Voice Activity Detection (VAD)
- Automatic Speech Recognition (ASR)
- Large Language Model (LLM) integration
- Text-to-Speech (TTS)
"""

# Import VoiceAssistant class
try:
    from .voice_assistant import VoiceAssistant
except ImportError:
    VoiceAssistant = None  # type: ignore

# Import utility functions for backward compatibility
from .utils import cleanup_temp_files, create_secure_temp_file

# Import commonly used constants from models
# These are defined in their respective model modules and re-exported here
# for backward compatibility with external code and tests.
from .models import (
    ASR_MODEL,
    DEFAULT_LANGUAGE,
    INITIAL_SPEECH_TIMEOUT,
    SAMPLE_RATE,
)

__all__ = [
    # Main class
    "VoiceAssistant",
    # Utilities
    "create_secure_temp_file",
    "cleanup_temp_files",
    # Constants (for backward compatibility)
    "ASR_MODEL",
    "DEFAULT_LANGUAGE",
    "INITIAL_SPEECH_TIMEOUT",
    "SAMPLE_RATE",
]
