"""
VAD Service

Manages Voice Activity Detection operations including:
- Model loading and initialization
- Speech detection
- Configuration management
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig, ServiceError

logger = get_logger(__name__)


@dataclass
class VADServiceConfig(ServiceConfig):
    """VAD service config."""

    name: str = "vad"
    enabled: bool = True
    threshold: float = 0.5
    consecutive_threshold: int = 3
    silence_duration: float = 0.8
    pre_buffer: float = 0.3
    min_speech_duration: float = 0.4
    max_recording_duration: float = 30.0


@dataclass
class VADConfig:
    """VAD configuration."""

    threshold: float
    consecutive_threshold: int
    silence_duration: float
    pre_buffer: float
    min_speech_duration: float
    max_recording_duration: float


class VADService(BaseService):
    """
    Voice Activity Detection service.

    Manages:
    - VAD model loading (Silero VAD)
    - Speech detection
    - Configuration management
    """

    def __init__(
        self,
        config: VADServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)

        # VAD configuration
        self.config = VADConfig(
            threshold=config.threshold,
            consecutive_threshold=config.consecutive_threshold,
            silence_duration=config.silence_duration,
            pre_buffer=config.pre_buffer,
            min_speech_duration=config.min_speech_duration,
            max_recording_duration=config.max_recording_duration,
        )

        # Model state
        self._model: Optional[Any] = None
        self._model_loading: bool = False

    @property
    def is_loaded(self) -> bool:
        """Check if VAD model is loaded."""
        return self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if model is currently loading."""
        return self._model_loading

    @property
    def threshold(self) -> float:
        """Get VAD threshold."""
        return self.config.threshold

    @property
    def consecutive_threshold(self) -> int:
        """Get consecutive threshold."""
        return self.config.consecutive_threshold

    async def _on_initialize(self) -> None:
        """Initialize VAD service (defer model loading until needed)."""
        self._emit_progress("initializing", 0.0, "VAD service ready")
        # Model is lazy-loaded on first use
        logger.info("vad_service_initialized")

    async def _on_start(self) -> None:
        """Start VAD service."""
        pass

    async def _on_stop(self) -> None:
        """Stop VAD service."""
        pass

    async def _on_shutdown(self) -> None:
        """Release VAD resources."""
        self._model = None
        logger.info("vad_service_shutdown")

    async def load_model(
        self,
        force_reload: bool = False,
    ) -> bool:
        """
        Load the VAD model.

        Args:
            force_reload: Force reload even if model is already loaded

        Returns:
            True if model loaded successfully
        """
        if self._model is not None and not force_reload:
            logger.debug("vad_model_already_loaded")
            return True

        if self._model_loading:
            logger.debug("vad_model_already_loading")
            return False

        self._model_loading = True
        self._emit_progress("loading", 0.0, "Loading VAD model...")

        try:
            # Import here to avoid early import
            from speekium.models.vad import check_vad_model_exists, load_vad

            # Check if model exists
            exists, path = check_vad_model_exists()

            if not exists:
                self._emit_progress("downloading", 0.1, "Downloading VAD model (~60MB)...")

            # Create progress callback
            def model_progress(model: str, current: int, total: int) -> None:
                if total > 0:
                    progress = 0.1 + (current / total) * 0.8
                    self._emit_progress("downloading", progress, f"Downloading {current}/{total}")

            # Load model
            self._model = load_vad(
                existing_vad_model=None,
                on_progress=model_progress,
            )

            self._emit_progress("loaded", 1.0, "VAD model loaded")
            logger.info("vad_model_loaded")
            return True

        except Exception as e:
            self._emit_progress("error", 0.0, f"VAD model load failed: {e}")
            logger.error("vad_model_load_failed", error=str(e))
            raise ServiceError(self.name, f"Failed to load VAD model: {e}") from e
        finally:
            self._model_loading = False

    async def detect_speech(
        self,
        audio_chunk,
        sample_rate: int = 16000,
    ) -> bool:
        """
        Detect if audio chunk contains speech.

        Args:
            audio_chunk: Audio numpy array
            sample_rate: Sample rate

        Returns:
            True if speech detected
        """
        if not self.is_loaded:
            await self.load_model()

        if self._model is None:
            return False

        try:
            import numpy as np
            import torch

            # Convert to tensor if needed
            if isinstance(audio_chunk, np.ndarray):
                audio_chunk = torch.from_numpy(audio_chunk)

            # Ensure float32 and normalized
            if audio_chunk.dtype != torch.float32:
                audio_chunk = audio_chunk.float()

            # Get speech probability
            prob = self._model(audio_chunk, sample_rate).item()

            return prob >= self.config.threshold

        except Exception as e:
            logger.error("vad_detection_failed", error=str(e))
            return False

    async def get_speech_probability(
        self,
        audio_chunk,
        sample_rate: int = 16000,
    ) -> float:
        """
        Get speech probability for audio chunk.

        Args:
            audio_chunk: Audio numpy array
            sample_rate: Sample rate

        Returns:
            Speech probability (0.0 to 1.0)
        """
        if not self.is_loaded:
            await self.load_model()

        if self._model is None:
            return 0.0

        try:
            import numpy as np
            import torch

            # Convert to tensor if needed
            if isinstance(audio_chunk, np.ndarray):
                audio_chunk = torch.from_numpy(audio_chunk)

            # Ensure float32
            if audio_chunk.dtype != torch.float32:
                audio_chunk = audio_chunk.float()

            # Get speech probability
            return self._model(audio_chunk, sample_rate).item()

        except Exception as e:
            logger.error("vad_probability_failed", error=str(e))
            return 0.0

    async def update_config(
        self,
        threshold: Optional[float] = None,
        consecutive_threshold: Optional[int] = None,
        silence_duration: Optional[float] = None,
        pre_buffer: Optional[float] = None,
        min_speech_duration: Optional[float] = None,
        max_recording_duration: Optional[float] = None,
    ) -> None:
        """
        Update VAD configuration.

        Args:
            threshold: Speech detection threshold (0.0-1.0)
            consecutive_threshold: Consecutive detections to confirm speech
            silence_duration: Silence duration to stop recording
            pre_buffer: Pre-buffer duration
            min_speech_duration: Minimum speech duration
            max_recording_duration: Maximum recording duration
        """
        if threshold is not None:
            self.config.threshold = max(0.0, min(1.0, threshold))

        if consecutive_threshold is not None:
            self.config.consecutive_threshold = max(1, consecutive_threshold)

        if silence_duration is not None:
            self.config.silence_duration = max(0.1, silence_duration)

        if pre_buffer is not None:
            self.config.pre_buffer = max(0.0, pre_buffer)

        if min_speech_duration is not None:
            self.config.min_speech_duration = max(0.1, min_speech_duration)

        if max_recording_duration is not None:
            self.config.max_recording_duration = max(1.0, max_recording_duration)

        logger.info("vad_config_updated", config=self.config)

    async def get_config(self) -> dict[str, Any]:
        """
        Get current VAD configuration.

        Returns:
            Dictionary with VAD config
        """
        return {
            "threshold": self.config.threshold,
            "consecutive_threshold": self.config.consecutive_threshold,
            "silence_duration": self.config.silence_duration,
            "pre_buffer": self.config.pre_buffer,
            "min_speech_duration": self.config.min_speech_duration,
            "max_recording_duration": self.config.max_recording_duration,
        }

    async def load_config_from_dict(self, config: dict) -> None:
        """
        Load VAD configuration from dict.

        Args:
            config: Configuration dictionary
        """
        await self.update_config(
            threshold=config.get("vad_threshold"),
            consecutive_threshold=config.get("vad_consecutive_threshold"),
            silence_duration=config.get("vad_silence_duration"),
            pre_buffer=config.get("vad_pre_buffer"),
            min_speech_duration=config.get("vad_min_speech_duration"),
            max_recording_duration=config.get("vad_max_recording_duration"),
        )

    async def get_model_status(self) -> dict[str, Any]:
        """
        Get current VAD model status.

        Returns:
            Dictionary with model status
        """
        from speekium.models.vad import get_model_status

        # Get base status
        status = get_model_status(self._model)
        status["loading"] = self._model_loading
        status["config"] = await self.get_config()

        return status

    async def check_model_exists(self) -> tuple[bool, str]:
        """
        Check if VAD model file exists in cache.

        Returns:
            Tuple of (exists, path)
        """
        from speekium.models.vad import check_vad_model_exists

        return check_vad_model_exists()

    async def health_check(self) -> bool:
        """Check if VAD service is healthy."""
        try:
            exists, _ = await self.check_model_exists()
            return self._is_initialized and (self._model is not None or exists)
        except Exception:
            return False
