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
try:
    from .models import (
        ASR_MODEL,
        DEFAULT_LANGUAGE,
        INITIAL_SPEECH_TIMEOUT,
        SAMPLE_RATE,
    )
except ImportError:
    # Fallback values if models not available
    ASR_MODEL: str = "iic/SenseVoiceSmall"  # type: ignore
    DEFAULT_LANGUAGE: str = "zh"  # type: ignore
    INITIAL_SPEECH_TIMEOUT: int = 60  # type: ignore
    SAMPLE_RATE: int = 16000  # type: ignore

__all__ = [
    # Main class
    "VoiceAssistant",
    # Utilities
    "create_secure_temp_file",
    "cleanup_temp_files",
    # Constants (for backward compatibility with tests)
    "ASR_MODEL",
    "DEFAULT_LANGUAGE",
    "INITIAL_SPEECH_TIMEOUT",
    "SAMPLE_RATE",
]
