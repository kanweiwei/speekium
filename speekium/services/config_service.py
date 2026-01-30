"""
Configuration Service

Manages application configuration loading, saving, and access.
Provides a single source of truth for configuration data.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig, ServiceError

logger = get_logger(__name__)


@dataclass
class ConfigServiceConfig(ServiceConfig):
    """Configuration service config."""

    name: str = "config"
    enabled: bool = True
    config_path: Optional[Path] = None


class ConfigService(BaseService):
    """
    Configuration management service.

    Provides:
    - Configuration loading from JSON file
    - Configuration saving to JSON file
    - Thread-safe configuration access
    - Configuration change notifications
    """

    def __init__(
        self,
        config: ConfigServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)
        self._config_path = config.config_path
        self._config: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._change_listeners: list[Callable[[dict[str, Any]], None]] = []

    async def _on_initialize(self) -> None:
        """Load configuration from file."""
        self._emit_progress("loading", 0.0, "Loading configuration")
        await self.reload()
        self._emit_progress("loaded", 1.0, "Configuration loaded")

    async def _on_start(self) -> None:
        """Start configuration monitoring (for future file watcher support)."""
        pass

    async def _on_stop(self) -> None:
        """Stop configuration monitoring."""
        pass

    async def _on_shutdown(self) -> None:
        """Save configuration before shutdown."""
        try:
            await self.save()
        except Exception as e:
            logger.warning("config_save_failed_during_shutdown", error=str(e))

    async def reload(self) -> None:
        """Reload configuration from file."""
        try:
            if self._config_path and self._config_path.exists():
                import json

                content = self._config_path.read_text(encoding="utf-8")
                self._config = json.loads(content)
                logger.info("config_loaded", path=str(self._config_path))
            else:
                logger.warning("config_file_not_found", path=str(self._config_path))
                self._config = self._get_default_config()
        except Exception as e:
            logger.error("config_load_failed", error=str(e))
            self._config = self._get_default_config()

    async def save(self) -> None:
        """Save configuration to file."""
        if not self._config_path:
            logger.warning("cannot_save_config_no_path")
            return

        try:
            import json

            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(self._config, indent=2, ensure_ascii=False)
            self._config_path.write_text(content, encoding="utf-8")
            logger.info("config_saved", path=str(self._config_path))
        except Exception as e:
            logger.error("config_save_failed", error=str(e))
            raise ServiceError(self.name, f"Failed to save config: {e}") from e

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (supports nested keys with dots)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        async with self._lock:
            return self._get_sync(key, default)

    def _get_sync(self, key: str, default: Any = None) -> Any:
        """Synchronous get for internal use."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    async def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key (supports nested keys with dots)
            value: Value to set
        """
        async with self._lock:
            keys = key.split(".")
            config = self._config
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            config[keys[-1]] = value

        # Notify listeners
        await self._notify_change(key, value)

    async def set_multiple(self, updates: dict[str, Any]) -> None:
        """
        Set multiple configuration values at once.

        Args:
            updates: Dictionary of key-value pairs to set
        """
        async with self._lock:
            for key, value in updates.items():
                keys = key.split(".")
                config = self._config
                for k in keys[:-1]:
                    if k not in config:
                        config[k] = {}
                    config = config[k]
                config[keys[-1]] = value

        # Notify listeners once for all changes
        await self._notify_change("multiple", updates)

    async def get_all(self) -> dict[str, Any]:
        """Get all configuration as a dictionary."""
        async with self._lock:
            return self._config.copy()

    async def update(self, updates: dict[str, Any]) -> None:
        """
        Update configuration with new values.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        await self.set_multiple(updates)
        await self.save()

    def register_change_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """
        Register a callback to be called when configuration changes.

        Args:
            callback: Async callback to receive configuration dict
        """
        self._change_listeners.append(callback)

    async def _notify_change(self, key: str, value: Any) -> None:
        """Notify all registered listeners of configuration change."""
        for listener in self._change_listeners:
            try:
                # If listener is async function, await it
                if asyncio.iscoroutinefunction(listener):
                    await listener(self._config.copy())
                else:
                    listener(self._config.copy())
            except Exception as e:
                logger.warning(
                    "config_listener_error",
                    listener=listener.__name__,
                    error=str(e),
                )

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration."""
        return {
            # Work mode
            "work_mode": "conversation",
            "recording_mode": "push-to-talk",
            # Language
            "language": "zh",
            "input_language": "zh",
            "output_language": "zh",
            # LLM Backend
            "llm_backend": "ollama",
            "llm_model": "qwen2.5:7b",
            "llm_base_url": "http://localhost:11434",
            "llm_api_key": "",
            # ASR Model
            "asr_model": "SenseVoiceSmall",
            "asr_language": "auto",
            # TTS Backend
            "tts_backend": "edge",
            "tts_model": "default",
            "tts_voice": "zh-CN-XiaoyiNeural",
            "tts_speed": "+0%",
            # VAD
            "vad_threshold": 0.5,
            "vad_consecutive_threshold": 2,
            # PTT
            "ptt_shortcut": "Cmd+Shift+R",
            # Recording
            "max_recording_duration": 300,
            # Audio
            "sample_rate": 16000,
            "channels": 1,
        }

    async def health_check(self) -> bool:
        """Check if configuration service is healthy."""
        try:
            return bool(self._config) and self._is_initialized
        except Exception:
            return False
