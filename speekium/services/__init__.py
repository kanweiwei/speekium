"""
Speekium Service Layer

This module provides service abstractions for the voice assistant.
Each service encapsulates a specific domain of functionality.

Services:
- BaseService: Abstract base class for all services
- RecordingService: Audio recording management
- ASRService: Automatic Speech Recognition
- LLMService: Large Language Model integration
- TTSService: Text-to-Speech conversion
- VADService: Voice Activity Detection
- ConfigService: Configuration management
"""

from .asr_service import ASRService, TranscriptionResult
from .base import (
    BaseService,
    ProgressEvent,
    ServiceConfig,
    ServiceError,
    ServiceInitializationError,
)
from .config_service import ConfigService
from .llm_service import ChatResult, LLMService
from .recording_service import RecordingResult, RecordingService, RecordingState
from .tts_service import SynthesisResult, TTSService
from .vad_service import VADConfig, VADService

__all__ = [
    # Base
    "BaseService",
    "ServiceConfig",
    "ServiceError",
    "ServiceInitializationError",
    "ProgressEvent",
    # Recording
    "RecordingService",
    "RecordingState",
    "RecordingResult",
    # ASR
    "ASRService",
    "TranscriptionResult",
    # LLM
    "LLMService",
    "ChatResult",
    # TTS
    "TTSService",
    "SynthesisResult",
    # VAD
    "VADService",
    "VADConfig",
    # Config
    "ConfigService",
]
