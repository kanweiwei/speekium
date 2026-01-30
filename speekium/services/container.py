"""
Service Container

Dependency injection container for managing service lifecycle and dependencies.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Optional

from logger import get_logger

from .asr_service import ASRService, ASRServiceConfig
from .base import BaseService, ProgressEvent, ServiceError
from .config_service import ConfigService, ConfigServiceConfig
from .llm_service import LLMService, LLMServiceConfig
from .recording_service import RecordingService, RecordingServiceConfig
from .tts_service import TTSService, TTSServiceConfig
from .vad_service import VADService, VADServiceConfig

logger = get_logger(__name__)


class ServiceContainer:
    """
    Dependency injection container for Speekium services.

    Manages:
    - Service instantiation and dependency injection
    - Unified lifecycle (initialize, start, stop, shutdown)
    - Service lookup by type
    - Progress callback aggregation
    """

    def __init__(
        self,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
        config_path: Optional[Path] = None,
        models_dir: Optional[Path] = None,
    ):
        """
        Initialize the service container.

        Args:
            progress_callback: Optional callback for service progress events
            config_path: Path to configuration file
            models_dir: Directory for TTS models
        """
        self._progress_callback = progress_callback
        self._config_path = config_path
        self._models_dir = models_dir or Path.home() / ".cache" / "speekium" / "tts"

        # Service instances
        self._config_service: Optional[ConfigService] = None
        self._recording_service: Optional[RecordingService] = None
        self._asr_service: Optional[ASRService] = None
        self._llm_service: Optional[LLMService] = None
        self._tts_service: Optional[TTSService] = None
        self._vad_service: Optional[VADService] = None

        # State
        self._initialized = False
        self._running = False

    @property
    def config(self) -> ConfigService:
        """Get configuration service."""
        if self._config_service is None:
            raise ServiceError("Container", "ConfigService not available")
        return self._config_service

    @property
    def recording(self) -> RecordingService:
        """Get recording service."""
        if self._recording_service is None:
            raise ServiceError("Container", "RecordingService not available")
        return self._recording_service

    @property
    def asr(self) -> ASRService:
        """Get ASR service."""
        if self._asr_service is None:
            raise ServiceError("Container", "ASRService not available")
        return self._asr_service

    @property
    def llm(self) -> LLMService:
        """Get LLM service."""
        if self._llm_service is None:
            raise ServiceError("Container", "LLMService not available")
        return self._llm_service

    @property
    def tts(self) -> TTSService:
        """Get TTS service."""
        if self._tts_service is None:
            raise ServiceError("Container", "TTSService not available")
        return self._tts_service

    @property
    def vad(self) -> VADService:
        """Get VAD service."""
        if self._vad_service is None:
            raise ServiceError("Container", "VADService not available")
        return self._vad_service

    def _create_progress_wrapper(
        self,
        service_name: str,
    ) -> Optional[Callable[[ProgressEvent], None]]:
        """Create a progress callback wrapper that adds service name context."""
        if self._progress_callback is None:
            return None

        def wrapper(event: ProgressEvent) -> None:
            # Add service name to event if not already present
            if not event.service:
                event = ProgressEvent(
                    service=service_name,
                    stage=event.stage,
                    progress=event.progress,
                    message=event.message,
                )
            self._progress_callback(event)

        return wrapper

    async def initialize(self) -> None:
        """
        Initialize all services.

        Services are initialized in dependency order:
        1. ConfigService (no dependencies)
        2. VADService (no dependencies)
        3. ASRService (no dependencies)
        4. LLMService (depends on Config)
        5. TTSService (depends on Config)
        6. RecordingService (no dependencies)
        """
        if self._initialized:
            logger.debug("container_already_initialized")
            return

        logger.info("container_initializing")

        # Create ConfigService first
        self._config_service = ConfigService(
            ConfigServiceConfig(
                name="config",
                enabled=True,
                config_path=self._config_path,
            ),
            progress_callback=self._create_progress_wrapper("config"),
        )
        await self._config_service.initialize()

        # Load configuration for other services
        config = await self._config_service.get_all()

        # Create VADService
        self._vad_service = VADService(
            VADServiceConfig(
                name="vad",
                enabled=True,
                threshold=config.get("vad_threshold", 0.5),
                consecutive_threshold=config.get("vad_consecutive_threshold", 3),
                silence_duration=config.get("vad_silence_duration", 0.8),
                pre_buffer=config.get("vad_pre_buffer", 0.3),
                min_speech_duration=config.get("vad_min_speech_duration", 0.4),
                max_recording_duration=config.get("vad_max_recording_duration", 30.0),
            ),
            progress_callback=self._create_progress_wrapper("vad"),
        )
        await self._vad_service.initialize()

        # Create ASRService
        self._asr_service = ASRService(
            ASRServiceConfig(
                name="asr",
                enabled=True,
                model_name=config.get("asr_model", "iic/SenseVoiceSmall"),
                sample_rate=config.get("sample_rate", 16000),
                default_language=config.get("asr_language", "auto"),
            ),
            progress_callback=self._create_progress_wrapper("asr"),
        )
        await self._asr_service.initialize()

        # Create LLMService
        self._llm_service = LLMService(
            LLMServiceConfig(
                name="llm",
                enabled=True,
                provider=config.get("llm_provider", "ollama"),
                model=config.get("llm_model", "qwen2.5:7b"),
                base_url=config.get("llm_base_url", "http://localhost:11434"),
                api_key=config.get("llm_api_key", ""),
                max_history=10,
            ),
            progress_callback=self._create_progress_wrapper("llm"),
        )
        await self._llm_service.initialize()

        # Create TTSService
        self._tts_service = TTSService(
            TTSServiceConfig(
                name="tts",
                enabled=True,
                models_dir=self._models_dir,
                default_backend=config.get("tts_backend", "edge"),
                default_voice=config.get("tts_voice", "zh-CN-XiaoyiNeural"),
            ),
            progress_callback=self._create_progress_wrapper("tts"),
        )
        await self._tts_service.initialize()
        # Load TTS backend config
        await self._tts_service.load_config(config)

        # Create RecordingService
        self._recording_service = RecordingService(
            RecordingServiceConfig(
                name="recording",
                enabled=True,
                sample_rate=config.get("sample_rate", 16000),
                channels=config.get("channels", 1),
                max_duration=config.get("max_recording_duration", 300.0),
            ),
            progress_callback=self._create_progress_wrapper("recording"),
        )
        await self._recording_service.initialize()

        self._initialized = True
        logger.info("container_initialized")

    async def start(self) -> None:
        """Start all services."""
        if not self._initialized:
            await self.initialize()

        if self._running:
            logger.debug("container_already_running")
            return

        logger.info("container_starting")

        # Start services in order
        services = [
            self._config_service,
            self._vad_service,
            self._asr_service,
            self._llm_service,
            self._tts_service,
            self._recording_service,
        ]

        for service in services:
            if service and service.config.enabled:
                await service.start()

        self._running = True
        logger.info("container_started")

    async def stop(self) -> None:
        """Stop all services (reverse order)."""
        if not self._running:
            return

        logger.info("container_stopping")

        # Stop services in reverse order
        services = [
            self._recording_service,
            self._tts_service,
            self._llm_service,
            self._asr_service,
            self._vad_service,
            self._config_service,
        ]

        for service in services:
            if service:
                await service.stop()

        self._running = False
        logger.info("container_stopped")

    async def shutdown(self) -> None:
        """Shutdown all services and release resources."""
        if not self._initialized:
            return

        logger.info("container_shutting_down")

        # Stop if running
        if self._running:
            await self.stop()

        # Shutdown services in reverse order
        services = [
            self._recording_service,
            self._tts_service,
            self._llm_service,
            self._asr_service,
            self._vad_service,
            self._config_service,
        ]

        for service in services:
            if service:
                await service.shutdown()

        self._initialized = False
        logger.info("container_shutdown")

    async def reload_config(self) -> None:
        """
        Reload configuration and update services.

        This is called when configuration changes are detected.
        """
        if self._config_service is None:
            return

        # Reload config from file
        await self._config_service.reload()
        config = await self._config_service.get_all()

        # Update LLM service
        if self._llm_service:
            await self._llm_service.update_config(
                provider=config.get("llm_provider"),
                model=config.get("llm_model"),
                base_url=config.get("llm_base_url"),
                api_key=config.get("llm_api_key"),
            )

        # Update TTS service
        if self._tts_service:
            await self._tts_service.load_config(config)

        # Update VAD service
        if self._vad_service:
            await self._vad_service.load_config_from_dict(config)

        logger.info("container_config_reloaded")

    async def health_check(self) -> dict[str, bool]:
        """
        Check health of all services.

        Returns:
            Dictionary mapping service name to health status
        """
        services = {
            "config": self._config_service,
            "recording": self._recording_service,
            "asr": self._asr_service,
            "llm": self._llm_service,
            "tts": self._tts_service,
            "vad": self._vad_service,
        }

        results = {}
        for name, service in services.items():
            if service:
                try:
                    results[name] = await service.health_check()
                except Exception:
                    results[name] = False
            else:
                results[name] = False

        return results

    def get_service(self, service_name: str) -> Optional[BaseService]:
        """
        Get service by name.

        Args:
            service_name: Name of service (config, recording, asr, llm, tts, vad)

        Returns:
            Service instance or None if not found
        """
        services = {
            "config": self._config_service,
            "recording": self._recording_service,
            "asr": self._asr_service,
            "llm": self._llm_service,
            "tts": self._tts_service,
            "vad": self._vad_service,
        }
        return services.get(service_name)


# Singleton instance for easy access
_default_container: Optional[ServiceContainer] = None


def get_container(
    progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    config_path: Optional[Path] = None,
    models_dir: Optional[Path] = None,
) -> ServiceContainer:
    """
    Get or create the default service container.

    Args:
        progress_callback: Optional callback for service progress events
        config_path: Path to configuration file
        models_dir: Directory for TTS models

    Returns:
        ServiceContainer instance
    """
    global _default_container

    if _default_container is None:
        _default_container = ServiceContainer(
            progress_callback=progress_callback,
            config_path=config_path,
            models_dir=models_dir,
        )

    return _default_container


async def shutdown_default_container() -> None:
    """Shutdown the default container."""
    global _default_container

    if _default_container is not None:
        await _default_container.shutdown()
        _default_container = None
