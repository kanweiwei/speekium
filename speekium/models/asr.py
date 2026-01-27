"""
Automatic Speech Recognition (ASR) module.

Provides ASR model loading, transcription, and ModelScope integration.
"""

import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write as write_wav

from logger import get_logger
from speekium.progress import ModelScopeProgressCallback
from speekium.utils import create_secure_temp_file

logger = get_logger(__name__)

# ===== ASR Config =====
SAMPLE_RATE = 16000
ASR_MODEL = "iic/SenseVoiceSmall"  # SenseVoice model
DEFAULT_LANGUAGE = "zh"

# Language tags used by SenseVoice
LANGUAGE_TAGS = ["zh", "en", "ja", "ko", "yue"]


def check_asr_model_exists(model_name: str = ASR_MODEL) -> tuple[bool, str]:
    """
    Check if ASR model files exist in cache.

    Args:
        model_name: Name of the ASR model

    Returns:
        Tuple of (exists, path) where exists is True if model is found,
        and path is the model directory path
    """
    # FunASR uses ModelScope cache (not HuggingFace)
    # ModelScope cache structure: ~/.cache/modelscope/hub/models/iic/SenseVoiceSmall
    cache_dir = Path.home() / ".cache" / "modelscope" / "hub" / "models"
    model_dir = cache_dir / model_name.replace("/", "/")

    if model_dir.exists() and list(model_dir.glob("*")):
        # Model files exist
        return True, str(model_dir)

    # Also check HuggingFace format (for compatibility)
    hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    hf_model_dir = hf_cache_dir / f"models--{model_name.replace('/', '--')}"
    if hf_model_dir.exists():
        snapshots = list(hf_model_dir.glob("snapshots/*"))
        if snapshots:
            for snapshot in snapshots:
                if snapshot.is_dir() and list(snapshot.glob("*")):
                    return True, str(snapshot)

    return False, str(model_dir)


def load_asr(
    asr_model=None,
    model_name: str = ASR_MODEL,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> object:
    """
    Load the SenseVoice ASR model.

    Args:
        asr_model: Existing ASR model instance (will be returned if not None)
        model_name: Name of the ASR model to load
        on_progress: Optional callback for progress updates

    Returns:
        Loaded ASR model
    """
    if asr_model is not None:
        return asr_model

    from logger import set_component

    set_component("ASR")
    from funasr import AutoModel

    # Check if model is already downloaded
    model_exists, model_path = check_asr_model_exists(model_name)

    if not model_exists:
        # Emit download started event
        logger.info("download_started", model="SenseVoice ASR", status="downloading")

        # Pre-download model using ModelScope with custom progress callback
        # This ensures progress events are emitted in JSON format for the frontend
        try:
            from modelscope.hub.snapshot_download import snapshot_download
            from modelscope.utils.constant import Invoke, ThirdParty

            # Create a factory for progress callbacks
            def create_progress_callback(filename: str, file_size: int):
                return ModelScopeProgressCallback(filename, file_size, "SenseVoice ASR")

            # Download with progress tracking
            logger.info("model_loading", model="SenseVoice")
            model_cache_dir = snapshot_download(
                model_name,
                revision="master",
                user_agent={Invoke.KEY: Invoke.PIPELINE, ThirdParty.KEY: "funasr"},
                progress_callbacks=[create_progress_callback],
            )
            logger.info("asr_model_download_completed", path=model_cache_dir)
        except Exception as e:
            logger.warning("asr_preload_failed", error=str(e))
            # Fallback: let FunASR handle download (without progress tracking)
            logger.info("model_loading", model="SenseVoice")

    else:
        logger.info("asr_model_found_in_cache", path=model_path)

    logger.info("model_loading", model="SenseVoice")
    asr_model = AutoModel(model=model_name, device="cpu")
    logger.info("model_loaded", model="SenseVoice")
    return asr_model


def transcribe(
    asr_model,
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    model_name: str = ASR_MODEL,
) -> tuple[str, str]:
    """
    Transcribe audio and detect language.

    Args:
        asr_model: Loaded ASR model
        audio: Audio numpy array (float32, normalized -1.0 to 1.0)
        sample_rate: Sample rate of the audio
        model_name: Name of the ASR model (for logging)

    Returns:
        Tuple of (text, language) where language is one of:
        'zh', 'en', 'ja', 'ko', 'yue'
    """
    from logger import set_component

    set_component("ASR")
    logger.info("asr_processing")

    # Security: Use secure temp file
    tmp_file = create_secure_temp_file(suffix=".wav")

    try:
        audio_int16 = (audio * 32767).astype(np.int16)
        write_wav(tmp_file, sample_rate, audio_int16)
        result = asr_model.generate(input=tmp_file)
        raw_text = result[0]["text"] if result else ""
    finally:
        if tmp_file and os.path.exists(tmp_file):
            os.remove(tmp_file)

    # Extract language from SenseVoice tags like <|zh|>, <|en|>, <|yue|>
    lang_match = re.search(r"<\|(" + "|".join(LANGUAGE_TAGS) + r")\|>", raw_text)
    language = lang_match.group(1) if lang_match else DEFAULT_LANGUAGE

    # Clean all tags from text
    text = re.sub(r"<\|[^|]+\|>", "", raw_text).strip()

    logger.info("asr_result", language=language, text=text)
    return text, language


async def transcribe_async(
    asr_model,
    audio: np.ndarray,
    sample_rate: int = SAMPLE_RATE,
    model_name: str = ASR_MODEL,
) -> tuple[str, str]:
    """
    Async wrapper for transcribe using thread executor.

    Args:
        asr_model: Loaded ASR model
        audio: Audio numpy array
        sample_rate: Sample rate of the audio
        model_name: Name of the ASR model

    Returns:
        Tuple of (text, language)
    """
    import asyncio

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor, transcribe, asr_model, audio, sample_rate, model_name
        )
    return result


def detect_text_language(text: str, default_language: str = DEFAULT_LANGUAGE) -> str:
    """
    Detect language from text content using character analysis.

    Args:
        text: Text to analyze
        default_language: Default language if detection fails

    Returns:
        Language code: 'zh', 'en', 'ja', 'ko', or default
    """
    # Count character types
    cjk_count = 0
    ja_specific = 0
    ko_specific = 0
    latin_count = 0

    for char in text:
        code = ord(char)
        # CJK Unified Ideographs (Chinese/Japanese/Korean shared)
        if 0x4E00 <= code <= 0x9FFF:
            cjk_count += 1
        # Hiragana/Katakana (Japanese specific)
        elif 0x3040 <= code <= 0x30FF:
            ja_specific += 1
        # Hangul (Korean specific)
        elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
            ko_specific += 1
        # Basic Latin letters
        elif 0x0041 <= code <= 0x007A:
            latin_count += 1

    total = len(text.replace(" ", ""))
    if total == 0:
        return default_language

    # Japanese has hiragana/katakana
    if ja_specific > 0:
        return "ja"
    # Korean has hangul
    if ko_specific > 0:
        return "ko"
    # Chinese if mostly CJK
    if cjk_count > latin_count:
        return "zh"
    # Default to English for Latin text
    if latin_count > 0:
        return "en"

    return default_language


def get_model_status(asr_model, model_name: str = ASR_MODEL) -> dict:
    """
    Get status information for ASR model.

    Args:
        asr_model: Current ASR model instance
        model_name: Name of the ASR model

    Returns:
        Dictionary with model status
    """
    exists, path = check_asr_model_exists(model_name)

    # Build fallback path
    hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    fallback_path = hf_cache_dir / f"models--{model_name.replace('/', '--')}"

    status = {
        "loaded": asr_model is not None,
        "name": model_name,
        "exists": exists,
        "path": path if exists else str(fallback_path),
    }

    if exists:
        status["size"] = _get_size_str(path)
    else:
        status["size"] = "0 B"

    return status


def _get_size_str(path: str) -> str:
    """Get human-readable size string for a file or directory."""
    from pathlib import Path

    path_obj = Path(path)
    if not path_obj.exists():
        return "0 B"

    if path_obj.is_file():
        size = path_obj.stat().st_size
    elif path_obj.is_dir():
        size = sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())
    else:
        return "0 B"

    # Convert to human-readable format
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
