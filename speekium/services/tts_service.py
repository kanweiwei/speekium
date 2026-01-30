"""
TTS Service

Manages Text-to-Speech operations including:
- Multiple backend support (Piper, Edge TTS)
- Per-language model selection
- Model download and management
- Audio synthesis
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig

logger = get_logger(__name__)


@dataclass
class TTSServiceConfig(ServiceConfig):
    """TTS service config."""

    name: str = "tts"
    enabled: bool = True
    models_dir: Optional[Path] = None
    default_backend: str = "edge"  # "edge" or "piper"
    default_voice: str = "zh-CN-XiaoyiNeural"


@dataclass
class SynthesisResult:
    """Result of a synthesis operation."""

    success: bool
    audio_path: Optional[Path] = None
    backend: str = "edge"
    duration: float = 0.0
    error: Optional[str] = None


class TTSService(BaseService):
    """
    Text-to-Speech service.

    Manages:
    - Multiple TTS backends (Edge TTS, Piper)
    - Per-language backend selection
    - Model download and management
    - Audio synthesis
    """

    def __init__(
        self,
        config: TTSServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)
        self.models_dir = config.models_dir or Path.home() / ".cache" / "speekium" / "tts"
        self.default_backend = config.default_backend
        self.default_voice = config.default_voice

        # Model manager
        self._model_manager: Optional[Any] = None

        # Backend config: {"default": "edge", "languages": {"zh": "piper:zh_CN-huayan-medium"}}
        self._backend_config: dict[str, Any] = {
            "default": self.default_backend,
            "languages": {},
        }

        # Loaded Piper models cache
        self._loaded_models: dict[str, Any] = {}

    @property
    def model_manager(self) -> Any:
        """Get or create model manager."""
        if self._model_manager is None:
            from speekium.models.tts import TTSModelManager

            self._model_manager = TTSModelManager({}, self.models_dir)
        return self._model_manager

    async def _on_initialize(self) -> None:
        """Initialize TTS service."""
        self._emit_progress("initializing", 0.0, "Initializing TTS service")

        # Create models directory
        self.models_dir.mkdir(parents=True, exist_ok=True)

        logger.info("tts_service_initialized", models_dir=str(self.models_dir))
        self._emit_progress("initialized", 1.0, "TTS service ready")

    async def _on_start(self) -> None:
        """Start TTS service."""
        pass

    async def _on_stop(self) -> None:
        """Stop TTS service."""
        pass

    async def _on_shutdown(self) -> None:
        """Release TTS resources."""
        self.unload_all_models()
        self._model_manager = None
        logger.info("tts_service_shutdown")

    def _parse_backend(self, backend: str) -> tuple[str, Optional[str]]:
        """
        Parse backend string.

        Args:
            backend: "edge" or "piper:model_id"

        Returns:
            Tuple of (backend_type, model_id)
        """
        if ":" in backend:
            parts = backend.split(":", 1)
            return parts[0], parts[1]
        return backend, None

    async def get_backend_for_language(self, language: str) -> tuple[str, Optional[str]]:
        """
        Get the TTS backend for a specific language.

        Args:
            language: Language code (zh, en, ja, ko, yue)

        Returns:
            Tuple of (backend_type, model_id)
        """
        languages = self._backend_config.get("languages", {})

        if language in languages:
            backend_str = languages[language]
            return self._parse_backend(backend_str)

        # Use default backend
        default = self._backend_config.get("default", self.default_backend)
        return self._parse_backend(default)

    async def set_backend_for_language(
        self,
        language: str,
        backend: str,
        save: bool = True,
    ) -> None:
        """
        Set TTS backend for a specific language.

        Args:
            language: "zh", "en", "ja", "ko", "yue", or "default"
            backend: "edge" or "piper:model_id"
            save: Whether to save configuration
        """
        if language == "default":
            self._backend_config["default"] = backend
        else:
            self._backend_config.setdefault("languages", {})[language] = backend

        if save:
            await self._save_config()

        logger.info("tts_backend_updated", language=language, backend=backend)

    async def _save_config(self) -> None:
        """Save TTS configuration to file."""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
            config["tts_backend"] = self._backend_config
            ConfigManager.save(config)
        except Exception as e:
            logger.warning("tts_config_save_failed", error=str(e))

    async def load_config(self, config: dict) -> None:
        """
        Load TTS configuration from config dict.

        Args:
            config: Configuration dictionary
        """
        tts_config = config.get("tts_backend", {})

        self._backend_config = {
            "default": tts_config.get("default", self.default_backend),
            "languages": tts_config.get("languages", {}).copy(),
        }

        logger.info("tts_config_loaded", config=self._backend_config)

    async def synthesize(
        self,
        text: str,
        language: str = "zh",
        voice: Optional[str] = None,
    ) -> SynthesisResult:
        """
        Synthesize speech from text.

        Args:
            text: Input text to synthesize
            language: Language code for backend selection
            voice: Optional voice name (for Edge TTS)

        Returns:
            SynthesisResult with audio file path
        """
        if not text or not text.strip():
            return SynthesisResult(success=False, error="Empty input text")

        try:
            backend_type, model_id = await self.get_backend_for_language(language)

            if backend_type == "piper":
                return await self._synthesize_piper(text, model_id)
            else:
                return await self._synthesize_edge(text, voice or self.default_voice)

        except Exception as e:
            logger.error("tts_synthesis_failed", error=str(e))
            return SynthesisResult(
                success=False,
                error=str(e),
            )

    async def _synthesize_piper(
        self,
        text: str,
        model_id: Optional[str],
    ) -> SynthesisResult:
        """Synthesize using Piper TTS."""
        if not model_id:
            return SynthesisResult(success=False, error="No Piper model specified")

        # Get or load model
        model = self._loaded_models.get(model_id)
        if model is None:
            from speekium.models.tts import PiperModel

            model = PiperModel(self.models_dir, model_id)

            if not model.is_available():
                return SynthesisResult(
                    success=False, error=f"Piper model '{model_id}' not available"
                )

            self._loaded_models[model_id] = model

        # Synthesize
        audio_path = model.synthesize(text)

        if audio_path:
            return SynthesisResult(
                success=True,
                audio_path=Path(audio_path),
                backend="piper",
            )
        else:
            return SynthesisResult(
                success=False,
                error="Piper synthesis failed",
            )

    async def _synthesize_edge(
        self,
        text: str,
        voice: str,
    ) -> SynthesisResult:
        """Synthesize using Edge TTS."""
        try:
            from speekium.models.tts import synthesize_with_edge

            # Run in thread pool
            loop = asyncio.get_event_loop()
            audio_path = await loop.run_in_executor(
                None,
                synthesize_with_edge,
                text,
                voice,
                "+0%",  # rate
            )

            if audio_path:
                return SynthesisResult(
                    success=True,
                    audio_path=Path(audio_path),
                    backend="edge",
                )
            else:
                return SynthesisResult(
                    success=False,
                    error="Edge TTS synthesis failed",
                )

        except Exception as e:
            return SynthesisResult(
                success=False,
                error=f"Edge TTS error: {e}",
            )

    async def list_available_models(self) -> list[dict[str, Any]]:
        """
        List all available TTS models.

        Returns:
            List of model info dicts
        """
        return self.model_manager.list_available_models()

    async def list_models_by_language(self, language: str) -> list[dict[str, Any]]:
        """
        List models for a specific language.

        Args:
            language: Language code

        Returns:
            List of model info dicts
        """
        return self.model_manager.list_models_by_language(language)

    async def download_model(
        self,
        model_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[bool, str]:
        """
        Download a TTS model.

        Args:
            model_id: Model identifier
            progress_callback: Optional callback(downloaded, total)

        Returns:
            Tuple of (success, message)
        """
        self._emit_progress("download_started", 0.0, f"Downloading TTS model: {model_id}")

        try:
            success, message = await self.model_manager.download_model(model_id, progress_callback)

            if success:
                self._emit_progress("download_complete", 1.0, "TTS model downloaded")
            else:
                self._emit_progress("download_failed", 0.0, f"Download failed: {message}")

            return success, message

        except Exception as e:
            self._emit_progress("download_failed", 0.0, f"Download error: {e}")
            return False, str(e)

    async def delete_model(self, model_id: str) -> tuple[bool, str]:
        """
        Delete a TTS model.

        Args:
            model_id: Model identifier

        Returns:
            Tuple of (success, message)
        """
        # Unload from cache
        if model_id in self._loaded_models:
            self._loaded_models[model_id].unload()
            del self._loaded_models[model_id]

        return self.model_manager.delete_model(model_id)

    def unload_all_models(self) -> None:
        """Unload all cached Piper models."""
        for model in self._loaded_models.values():
            model.unload()
        self._loaded_models.clear()

    async def get_backend_config(self) -> dict[str, Any]:
        """Get current TTS backend configuration."""
        return self._backend_config.copy()

    async def health_check(self) -> bool:
        """Check if TTS service is healthy."""
        try:
            return self._is_initialized and self.models_dir.exists()
        except Exception:
            return False
