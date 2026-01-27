"""Models subpackage - VAD, ASR, LLM, TTS model management"""

# Re-export all public APIs from model modules
from speekium.models.asr import (
    ASR_MODEL,
    DEFAULT_LANGUAGE,
    LANGUAGE_TAGS,
    SAMPLE_RATE,
    check_asr_model_exists,
    detect_text_language,
    load_asr,
    transcribe,
    transcribe_async,
)
from speekium.models.asr import get_model_status as get_asr_model_status
from speekium.models.llm import (
    CLEAR_HISTORY_KEYWORDS,
    LLM_BACKEND,
    LLM_PROVIDER,
    LLM_PROVIDERS,
    MAX_HISTORY,
    SYSTEM_PROMPT,
    create_llm_backend,
    get_clear_history_message,
    load_llm_config,
)
from speekium.models.tts import (
    PIPER_AVAILABLE_MODELS,
    PiperModel,
    TTSModelManager,
    get_mirror_source,
    get_model_url,
    synthesize_with_edge,
)
from speekium.models.vad import (
    INTERRUPT_CHECK_DURATION,
    MAX_RECORDING_DURATION,
    MIN_SPEECH_DURATION,
    SILENCE_AFTER_SPEECH,
    VAD_CONSECUTIVE_THRESHOLD,
    VAD_PRE_BUFFER,
    VAD_THRESHOLD,
    INITIAL_SPEECH_TIMEOUT,
    check_vad_model_exists,
    load_vad,
    load_vad_config,
)
from speekium.models.vad import get_model_status as get_vad_model_status

__all__ = [
    # ASR
    "ASR_MODEL",
    "DEFAULT_LANGUAGE",
    "LANGUAGE_TAGS",
    "SAMPLE_RATE",
    "check_asr_model_exists",
    "detect_text_language",
    "get_asr_model_status",
    "load_asr",
    "transcribe",
    "transcribe_async",
    # LLM
    "CLEAR_HISTORY_KEYWORDS",
    "LLM_BACKEND",
    "LLM_PROVIDER",
    "LLM_PROVIDERS",
    "MAX_HISTORY",
    "SYSTEM_PROMPT",
    "create_llm_backend",
    "get_clear_history_message",
    "load_llm_config",
    # TTS
    "PIPER_AVAILABLE_MODELS",
    "PiperModel",
    "TTSModelManager",
    "get_mirror_source",
    "get_model_url",
    "synthesize_with_edge",
    # VAD
    "INTERRUPT_CHECK_DURATION",
    "MAX_RECORDING_DURATION",
    "MIN_SPEECH_DURATION",
    "SILENCE_AFTER_SPEECH",
    "VAD_CONSECUTIVE_THRESHOLD",
    "VAD_PRE_BUFFER",
    "VAD_THRESHOLD",
    "INITIAL_SPEECH_TIMEOUT",
    "check_vad_model_exists",
    "get_vad_model_status",
    "load_vad",
    "load_vad_config",
]
