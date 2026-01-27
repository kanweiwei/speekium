"""
TTS Models - Pluggable offline TTS model implementations

Supports:
- Piper: Fast, local neural TTS with multilingual voices
- Edge TTS: Online Microsoft Azure TTS (existing fallback)
"""

import asyncio
import locale
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable, Any

import aiohttp

from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    import numpy as np

# ============================================================================
# Piper Model Registry
# ============================================================================

# Available Piper models from rhasspy/piper-voices
# Source: https://huggingface.co/rhasspy/piper-voices
PIPER_AVAILABLE_MODELS: dict[str, dict] = {
    # Chinese models
    "zh_CN-huayan-medium": {
        "language": "zh",
        "display_name": "华言 (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json",
        "description": "中文女声，中等质量",
    },
    "zh_CN-huayan-low": {
        "language": "zh",
        "display_name": "华言 (低质量)",
        "size_mb": 75,
        "url": "rhasspy/piper-voices/v1/zh_CN/huayan/low/zh_CN-huayan-low.onnx",
        "config_url": "rhasspy/piper-voices/v1/zh_CN/huayan/low/zh_CN-huayan-low.onnx.json",
        "description": "中文女声，快速但质量较低",
    },
    # Japanese models
    "ja_JP-tsukuyomi-medium": {
        "language": "ja",
        "display_name": "月読 (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/ja_JP/tsukuyomi/medium/ja_JP-tsukuyomi-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/ja_JP/tsukuyomi/medium/ja_JP-tsukuyomi-medium.onnx.json",
        "description": "日语女声，中等质量",
    },
    # Korean models
    "ko_KO-kssug-medium": {
        "language": "ko",
        "display_name": "KSSUG (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/ko_KO/kssug/medium/ko_KO-kssug-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/ko_KO/kssug/medium/ko_KO-kssug-medium.onnx.json",
        "description": "韩语女声，中等质量",
    },
    # Cantonese models
    "yue_YU-multi-low": {
        "language": "yue",
        "display_name": "粤语 (低质量)",
        "size_mb": 75,
        "url": "rhasspy/piper-voices/v1/yue_YU/multi/low/yue_YU-multi-low.onnx",
        "config_url": "rhasspy/piper-voices/v1/yue_YU/multi/low/yue_YU-multi-low.onnx.json",
        "description": "粤语，快速但质量较低",
    },
    # English models
    "en_US-lessac-medium": {
        "language": "en",
        "display_name": "Lessac (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "description": "美式英语男声，中等质量",
    },
    "en_US-amy-medium": {
        "language": "en",
        "display_name": "Amy (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/en_US/amy/medium/en_US-amy-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/en_US/amy/medium/en_US-amy-medium.onnx.json",
        "description": "美式英语女声，中等质量",
    },
    "en_US-amy-low": {
        "language": "en",
        "display_name": "Amy (低质量)",
        "size_mb": 75,
        "url": "rhasspy/piper-voices/v1/en_US/amy/low/en_US-amy-low.onnx",
        "config_url": "rhasspy/piper-voices/v1/en_US/amy/low/en_US-amy-low.onnx.json",
        "description": "美式英语女声，快速",
    },
    "en_GB-lessac-medium": {
        "language": "en",
        "display_name": "Lessac UK (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/en_GB/lessac/medium/en_GB-lessac-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/en_GB/lessac/medium/en_GB-lessac-medium.onnx.json",
        "description": "英式英语男声，中等质量",
    },
    "en_GB-semaine-medium": {
        "language": "en",
        "display_name": "Semaine UK (中等)",
        "size_mb": 355,
        "url": "rhasspy/piper-voices/v1/en_GB/semaine/medium/en_GB-semaine-medium.onnx",
        "config_url": "rhasspy/piper-voices/v1/en_GB/semaine/medium/en_GB-semaine-medium.onnx.json",
        "description": "英式英语女声，中等质量",
    },
}


# ============================================================================
# Mirror Source Configuration
# ============================================================================


def get_mirror_source() -> str:
    """Get mirror source based on system locale.

    Returns Tsinghua mirror for Chinese users, HuggingFace default otherwise.
    """
    try:
        system_lang = locale.getdefaultlocale()[0] or ""
        if system_lang.startswith("zh"):
            return "https://mirrors.tuna.tsinghua.edu.cn/hugging-face/"
    except Exception:
        pass
    return "https://huggingface.co/"


def get_model_url(hf_path: str) -> str:
    """Get full model download URL with appropriate mirror.

    Args:
        hf_path: HuggingFace path, e.g., "rhasspy/piper-voices/v1/..."

    Returns:
        Full download URL
    """
    mirror = get_mirror_source()
    # Tsinghua mirror has different path format
    if "tuna" in mirror:
        return mirror + hf_path.replace("rhasspy/piper-voices/", "rhasspy/piper-voices/blob/")
    return mirror + hf_path


# ============================================================================
# Piper Model Implementation
# ============================================================================


class PiperModel:
    """Piper TTS model implementation.

    Piper is a fast, local neural TTS that supports multiple languages.
    https://github.com/rhasspy/piper
    """

    def __init__(self, models_dir: Path, model_id: str):
        """Initialize Piper model.

        Args:
            models_dir: Base directory for all TTS models
            model_id: Model identifier from PIPER_AVAILABLE_MODELS
        """
        self.models_dir = models_dir / "piper"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.model_id = model_id
        self.model_info = PIPER_AVAILABLE_MODELS.get(model_id, {})
        self._synth: Optional[object] = None  # Lazy loaded synthesizer

        if not self.model_info:
            raise ValueError(f"Unknown model: {model_id}")

    @property
    def model_path(self) -> Path:
        """Path to the ONNX model file."""
        return self.models_dir / f"{self.model_id}.onnx"

    @property
    def config_path(self) -> Path:
        """Path to the model config JSON file."""
        return self.models_dir / f"{self.model_id}.onnx.json"

    @property
    def language(self) -> str:
        """Language code supported by this model."""
        return self.model_info.get("language", "en")

    @property
    def display_name(self) -> str:
        """Human-readable display name."""
        return self.model_info.get("display_name", self.model_id)

    @property
    def size_mb(self) -> int:
        """Model size in megabytes."""
        return self.model_info.get("size_mb", 0)

    @property
    def description(self) -> str:
        """Model description."""
        return self.model_info.get("description", "")

    def is_downloaded(self) -> bool:
        """Check if model files are downloaded."""
        return self.model_path.exists() and self.config_path.exists()

    def is_available(self) -> bool:
        """Check if model is available and can be loaded.

        This validates the model by attempting to load it.
        """
        if not self.is_downloaded():
            return False

        try:
            self._load_synthesizer()
            return True
        except Exception:
            return False

    def _load_synthesizer(self) -> Any:
        """Load Piper synthesizer (lazy loading).

        Returns:
            Loaded PiperVoice instance

        Raises:
            RuntimeError: If piper-tts is not installed or model fails to load
        """
        if self._synth is not None:
            return self._synth

        try:
            from piper import PiperVoice

            self._synth = PiperVoice.load(str(self.model_path), str(self.config_path))
            return self._synth
        except ImportError as e:
            raise RuntimeError("piper-tts not installed. Run: pip install piper-tts") from e
        except Exception as e:
            raise RuntimeError(f"Failed to load Piper model: {e}") from e

    async def download(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """Download model files.

        Args:
            progress_callback: Optional callback(downloaded_bytes, total_bytes)

        Returns:
            True if download succeeded and validation passed

        Raises:
            RuntimeError: If download fails or model validation fails
        """
        base_url = get_model_url(self.model_info["url"])
        config_url = get_model_url(self.model_info["config_url"])

        # Download model file
        await self._download_file(base_url, self.model_path, progress_callback)

        # Download config file
        await self._download_file(config_url, self.config_path, None)

        # Validate by attempting to load
        if not self.is_available():
            self.model_path.unlink(missing_ok=True)
            self.config_path.unlink(missing_ok=True)
            raise RuntimeError("Downloaded model failed validation")

        return True

    async def _download_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Download a single file.

        Args:
            url: Download URL
            dest_path: Destination file path
            progress_callback: Optional progress callback

        Raises:
            RuntimeError: If download fails
        """
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=600)  # 10 min timeout
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Download failed: HTTP {resp.status}")

                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(dest_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            progress_callback(downloaded, total)

    def synthesize(self, text: str) -> Optional[str]:
        """Synthesize speech from text.

        Args:
            text: Input text

        Returns:
            Path to generated WAV file, or None if synthesis failed
        """
        try:
            from speekium import create_secure_temp_file

            synth = self._load_synthesizer()

            # Use secure temp file
            tmp_file = create_secure_temp_file(suffix=".wav")

            # Piper synchronous synthesis
            audio, sample_rate = synth.synthesize(text)

            # Save as WAV
            import soundfile as sf

            sf.write(tmp_file, audio, sample_rate)

            return tmp_file

        except Exception as e:
            logger.error("piper_synthesize_error", model=self.model_id, error=str(e))
            return None

    def unload(self) -> None:
        """Unload model from memory."""
        self._synth = None

    def delete(self) -> bool:
        """Delete model files.

        Returns:
            True if deletion succeeded
        """
        try:
            self.unload()
            self.model_path.unlink(missing_ok=True)
            self.config_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.error("piper_delete_error", model=self.model_id, error=str(e))
            return False


# ============================================================================
# TTS Manager
# ============================================================================


class TTSModelManager:
    """TTS model manager with per-language backend selection."""

    def __init__(self, config: dict, models_dir: Path):
        """Initialize TTS model manager.

        Args:
            config: Application configuration dict
            models_dir: Directory to store TTS models
        """
        self.config = config
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._loaded_models: dict[str, PiperModel] = {}

    # ========================================================================
    # Model Discovery
    # ========================================================================

    def list_available_models(self) -> list[dict]:
        """Get all available models (including not yet downloaded).

        Returns:
            List of model info dicts
        """
        return [
            {
                "model_id": model_id,
                "backend": "piper",
                "display_name": info["display_name"],
                "language": info["language"],
                "size_mb": info["size_mb"],
                "description": info["description"],
                "downloaded": self._is_downloaded(model_id),
                "available": self._is_available(model_id),
            }
            for model_id, info in PIPER_AVAILABLE_MODELS.items()
        ]

    def list_models_by_language(self, language: str) -> list[dict]:
        """Get models for a specific language.

        Args:
            language: Language code (zh, en, ja, ko, yue)

        Returns:
            List of model info dicts for the language
        """
        return [m for m in self.list_available_models() if m["language"] == language]

    def _is_downloaded(self, model_id: str) -> bool:
        """Check if model files exist."""
        model_path = self.models_dir / "piper" / f"{model_id}.onnx"
        config_path = self.models_dir / "piper" / f"{model_id}.onnx.json"
        return model_path.exists() and config_path.exists()

    def _is_available(self, model_id: str) -> bool:
        """Check if model is downloaded and loadable."""
        if not self._is_downloaded(model_id):
            return False
        try:
            model = PiperModel(self.models_dir, model_id)
            return model.is_available()
        except Exception:
            return False

    # ========================================================================
    # Backend Configuration
    # ========================================================================

    def get_backend_config(self) -> dict:
        """Get the complete TTS backend configuration.

        Returns:
            Dict with "default" and "languages" keys
        """
        tts_config = self.config.get("tts_backend", {})

        return {
            "default": tts_config.get("default", "edge"),
            "languages": tts_config.get("languages", {}).copy(),
        }

    def get_backend_for_language(self, language: str) -> tuple[str, Optional[str]]:
        """Get the TTS backend for a specific language.

        Args:
            language: Language code

        Returns:
            Tuple of (backend_type, model_id)
            - backend_type: "edge" or "piper"
            - model_id: None for edge, model_id for piper
        """
        tts_config = self.config.get("tts_backend", {})

        # Check if language is configured
        languages = tts_config.get("languages", {})
        if language in languages:
            backend_str = languages[language]
            return self._parse_backend(backend_str)

        # Use default backend
        default = tts_config.get("default", "edge")
        return self._parse_backend(default)

    def _parse_backend(self, backend: str) -> tuple[str, Optional[str]]:
        """Parse backend string.

        Args:
            backend: "edge" or "piper:model_id"

        Returns:
            Tuple of (backend_type, model_id)
        """
        if ":" in backend:
            parts = backend.split(":", 1)
            return parts[0], parts[1]
        return backend, None

    def set_backend_for_language(self, language: str, backend: str) -> bool:
        """Set TTS backend for a specific language.

        Args:
            language: "zh", "en", "ja", "ko", "yue", or "default"
            backend: "edge" or "piper:model_id"

        Returns:
            True if successful
        """
        from config_manager import ConfigManager

        tts_config = self.config.setdefault("tts_backend", {})

        if language == "default":
            tts_config["default"] = backend
        else:
            tts_config.setdefault("languages", {})[language] = backend

        # Save configuration
        ConfigManager.save(self.config)
        return True

    # ========================================================================
    # Model Operations
    # ========================================================================

    async def download_model(
        self, model_id: str, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> tuple[bool, str]:
        """Download a TTS model.

        Args:
            model_id: Model identifier from PIPER_AVAILABLE_MODELS
            progress_callback: Optional callback(downloaded, total)

        Returns:
            Tuple of (success, message)
        """
        if model_id not in PIPER_AVAILABLE_MODELS:
            return False, "Unknown model"

        if self._is_available(model_id):
            return True, "Already downloaded"

        try:
            model = PiperModel(self.models_dir, model_id)
            await model.download(progress_callback)
            self._loaded_models[model_id] = model
            logger.info("tts_model_downloaded", model_id=model_id)
            return True, "Downloaded"
        except Exception as e:
            logger.error("tts_model_download_failed", model_id=model_id, error=str(e))
            return False, str(e)

    def delete_model(self, model_id: str) -> tuple[bool, str]:
        """Delete a TTS model.

        Args:
            model_id: Model identifier

        Returns:
            Tuple of (success, message)
        """
        # Unload if cached
        if model_id in self._loaded_models:
            self._loaded_models[model_id].unload()
            del self._loaded_models[model_id]

        try:
            model = PiperModel(self.models_dir, model_id)
            model.delete()
            logger.info("tts_model_deleted", model_id=model_id)
            return True, "Deleted"
        except Exception as e:
            logger.error("tts_model_delete_failed", model_id=model_id, error=str(e))
            return False, str(e)

    # ========================================================================
    # Audio Generation
    # ========================================================================

    def get_model(self, model_id: str) -> Optional[PiperModel]:
        """Get a model instance.

        Args:
            model_id: Model identifier

        Returns:
            PiperModel instance if available, None otherwise
        """
        if not self._is_available(model_id):
            return None

        if model_id not in self._loaded_models:
            self._loaded_models[model_id] = PiperModel(self.models_dir, model_id)

        return self._loaded_models[model_id]

    def unload_all(self) -> None:
        """Unload all cached models."""
        for model in self._loaded_models.values():
            model.unload()
        self._loaded_models.clear()


# ============================================================================
# Edge TTS Fallback
# ============================================================================


def synthesize_with_edge(
    text: str,
    voice: str = "zh-CN-XiaoxiaoNeural",
    rate: str = "+0%",
) -> Optional[str]:
    """Synthesize speech using Edge TTS (online Microsoft Azure TTS).

    Args:
        text: Input text to synthesize
        voice: Voice name (default: zh-CN-XiaoxiaoNeural)
        rate: Speech rate (default: +0%)

    Returns:
        Path to generated audio file, or None if failed
    """
    try:
        from speekium import create_secure_temp_file
        import edge_tts

        tmp_file = create_secure_temp_file(suffix=".mp3")

        communicate = edge_tts.Communicate(text, voice, rate=rate)
        asyncio.get_event_loop().run_until_complete(communicate.save(tmp_file))

        return tmp_file
    except Exception as e:
        logger.error("edge_tts_error", error=str(e))
        return None
