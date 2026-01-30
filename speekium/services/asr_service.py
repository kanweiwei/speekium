"""
ASR Service

Manages Automatic Speech Recognition operations including:
- Model loading and initialization
- Audio transcription
- Language detection
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig, ServiceError

logger = get_logger(__name__)


@dataclass
class ASRServiceConfig(ServiceConfig):
    """ASR service config."""

    name: str = "asr"
    enabled: bool = True
    model_name: str = "iic/SenseVoiceSmall"
    sample_rate: int = 16000
    default_language: str = "zh"


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""

    success: bool
    text: str = ""
    language: str = "zh"
    duration: float = 0.0
    error: Optional[str] = None


class ASRService(BaseService):
    """
    Automatic Speech Recognition service.

    Manages:
    - ASR model loading (SenseVoice/FunASR)
    - Audio to text transcription
    - Language detection
    - Model status monitoring
    """

    def __init__(
        self,
        config: ASRServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)
        self.model_name = config.model_name
        self.sample_rate = config.sample_rate
        self.default_language = config.default_language

        # Model state
        self._model: Optional[Any] = None
        self._model_loading: bool = False

    @property
    def is_loaded(self) -> bool:
        """Check if ASR model is loaded."""
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._model_loading

    async def _on_initialize(self) -> None:
        """Initialize ASR service (defer model loading until needed)."""
        self._emit_progress("initializing", 0.0, "ASR service ready")
        # Model is lazy-loaded on first use
        logger.info("asr_service_initialized", model=self.model_name)

    async def _on_start(self) -> None:
        """Start ASR service."""
        # Optionally preload model here if needed
        pass

    async def _on_stop(self) -> None:
        """Stop ASR service."""
        # Keep model loaded for faster next use
        pass

    async def _on_shutdown(self) -> None:
        """Release ASR resources."""
        self._model = None
        logger.info("asr_service_shutdown")

    async def load_model(
        self,
        force_reload: bool = False,
    ) -> bool:
        """
        Load the ASR model.

        Args:
            force_reload: Force reload even if model is already loaded

        Returns:
            True if model loaded successfully
        """
        if self._model is not None and not force_reload:
            logger.debug("asr_model_already_loaded")
            return True

        if self._model_loading:
            logger.debug("asr_model_already_loading")
            return False

        self._model_loading = True
        self._emit_progress("loading", 0.0, f"Loading ASR model: {self.model_name}")

        try:
            # Import here to avoid early import
            from speekium.models.asr import check_asr_model_exists, load_asr

            # Check if model exists
            exists, path = check_asr_model_exists(self.model_name)

            if not exists:
                self._emit_progress("downloading", 0.1, "Downloading ASR model...")

            # Create progress callback for model loading
            def model_progress(progress_data: dict) -> None:
                event_type = progress_data.get("event_type", "")
                if event_type == "started":
                    self._emit_progress("download_started", 0.1, "Downloading ASR model...")
                elif event_type == "progress":
                    current = progress_data.get("current", 0)
                    total = progress_data.get("total", 1)
                    if total > 0:
                        progress = 0.1 + (current / total) * 0.8
                        msg = f"Downloading {current}/{total}"
                        self._emit_progress("downloading", progress, msg)

            # Load model in thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                self._model = await loop.run_in_executor(
                    executor,
                    load_asr,
                    None,  # asr_model
                    self.model_name,
                    model_progress,
                )

            self._emit_progress("loaded", 1.0, "ASR model loaded")
            logger.info("asr_model_loaded", model=self.model_name)
            return True

        except Exception as e:
            self._emit_progress("error", 0.0, f"ASR model load failed: {e}")
            logger.error("asr_model_load_failed", error=str(e))
            raise ServiceError(self.name, f"Failed to load ASR model: {e}") from e
        finally:
            self._model_loading = False

    async def transcribe(
        self,
        audio,
        sample_rate: Optional[int] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio: Audio numpy array (float32, normalized -1.0 to 1.0)
            sample_rate: Sample rate of the audio (uses config default if None)

        Returns:
            TranscriptionResult with text and language
        """
        if not self.is_loaded:
            await self.load_model()

        if self._model is None:
            return TranscriptionResult(success=False, error="ASR model not available")

        sr = sample_rate or self.sample_rate

        try:
            from speekium.models.asr import transcribe

            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                text, language = await loop.run_in_executor(
                    executor,
                    transcribe,
                    self._model,
                    audio,
                    sr,
                    self.model_name,
                )

            logger.info("asr_transcription_completed", language=language, text_length=len(text))
            return TranscriptionResult(
                success=True,
                text=text,
                language=language,
            )

        except Exception as e:
            logger.error("asr_transcription_failed", error=str(e))
            return TranscriptionResult(
                success=False,
                error=str(e),
            )

    async def detect_language(self, text: str) -> str:
        """
        Detect language from text content.

        Args:
            text: Text to analyze

        Returns:
            Language code: 'zh', 'en', 'ja', 'ko', or 'yue'
        """
        try:
            from speekium.models.asr import detect_text_language

            return detect_text_language(text, self.default_language)
        except Exception as e:
            logger.warning("language_detection_failed", error=str(e))
            return self.default_language

    async def get_model_status(self) -> dict[str, Any]:
        """
        Get current ASR model status.

        Returns:
            Dictionary with model status information
        """
        from speekium.models.asr import get_model_status

        # Get base status
        status = get_model_status(self._model, self.model_name)
        status["loading"] = self._model_loading

        return status

    async def check_model_exists(self) -> tuple[bool, str]:
        """
        Check if ASR model files exist in cache.

        Returns:
            Tuple of (exists, path)
        """
        from speekium.models.asr import check_asr_model_exists

        return check_asr_model_exists(self.model_name)

    async def health_check(self) -> bool:
        """Check if ASR service is healthy."""
        try:
            exists, _ = await self.check_model_exists()
            return self._is_initialized and (self._model is not None or exists)
        except Exception:
            return False
