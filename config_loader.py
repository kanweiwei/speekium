"""
Configuration loader for Speekium
Handles loading and refreshing configuration from config file
"""

import sys
from pathlib import Path
from typing import Optional

from logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Default constants (copied from speekium to avoid circular import)
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_ASR_MODEL = "iic/SenseVoiceSmall"
DEFAULT_VAD_THRESHOLD = 0.5
DEFAULT_VAD_CONSECUTIVE_THRESHOLD = 3
DEFAULT_VAD_SILENCE_DURATION = 0.8
DEFAULT_VAD_PRE_BUFFER = 0.3
DEFAULT_MIN_SPEECH_DURATION = 0.4
DEFAULT_MAX_RECORDING_DURATION = 30
DEFAULT_TTS_RATE = "+0%"


class ConfigLoader:
    """Handles loading configuration from config file"""

    def __init__(self):
        self._tts_backend: str = "edge"

    def _load_vad_config(self, config: dict) -> dict:
        """Load VAD configuration from config dict."""
        return {
            "vad_threshold": config.get("vad_threshold", DEFAULT_VAD_THRESHOLD),
            "vad_consecutive_threshold": config.get(
                "vad_consecutive_threshold", DEFAULT_VAD_CONSECUTIVE_THRESHOLD
            ),
            "vad_silence_duration": config.get("vad_silence_duration", DEFAULT_VAD_SILENCE_DURATION),
            "vad_pre_buffer": config.get("vad_pre_buffer", DEFAULT_VAD_PRE_BUFFER),
            "vad_min_speech_duration": config.get(
                "vad_min_speech_duration", DEFAULT_MIN_SPEECH_DURATION
            ),
            "vad_max_recording_duration": config.get(
                "vad_max_recording_duration", DEFAULT_MAX_RECORDING_DURATION
            ),
        }

    def _load_tts_config(self, config: dict) -> dict:
        """Load TTS backend and rate from config dict."""
        tts_backend = config.get("tts_backend", "edge")
        tts_rate = config.get("tts_rate", DEFAULT_TTS_RATE)

        return {
            "tts_backend": tts_backend,
            "tts_rate": tts_rate,
        }

    def _load_llm_config(self, config: dict) -> dict:
        """Load LLM backend configuration from config dict."""
        llm_provider = config.get("llm_provider", "ollama")
        llm_providers = config.get("llm_providers", [])

        # Find current provider config
        current_provider_config = {}
        for provider in llm_providers:
            if provider.get("name") == llm_provider:
                current_provider_config = provider
                break

        return {
            "llm_provider": llm_provider,
            "llm_providers": llm_providers,
            "llm_backend": llm_provider,
            "current_provider_config": current_provider_config,
        }

    def load_all_config(self) -> dict:
        """Load all configuration from config file."""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()

            vad_config = self._load_vad_config(config)
            tts_config = self._load_tts_config(config)
            llm_config = self._load_llm_config(config)

            self._tts_backend = tts_config["tts_backend"]

            logger.info(
                "config_loaded",
                vad_threshold=vad_config["vad_threshold"],
                tts_backend=tts_config["tts_backend"],
                llm_provider=llm_config["llm_provider"],
            )

            return {
                "vad": vad_config,
                "tts": tts_config,
                "llm": llm_config,
            }

        except Exception as e:
            logger.warning("config_load_failed", error=str(e))
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Return default configuration."""
        return {
            "vad": {
                "vad_threshold": DEFAULT_VAD_THRESHOLD,
                "vad_consecutive_threshold": DEFAULT_VAD_CONSECUTIVE_THRESHOLD,
                "vad_silence_duration": DEFAULT_VAD_SILENCE_DURATION,
                "vad_pre_buffer": DEFAULT_VAD_PRE_BUFFER,
                "vad_min_speech_duration": DEFAULT_MIN_SPEECH_DURATION,
                "vad_max_recording_duration": DEFAULT_MAX_RECORDING_DURATION,
            },
            "tts": {
                "tts_backend": "edge",
                "tts_rate": DEFAULT_TTS_RATE,
            },
            "llm": {
                "llm_provider": "ollama",
                "llm_providers": [],
                "llm_backend": "ollama",
                "current_provider_config": {},
            },
        }

    @staticmethod
    def get_size_str(path: str) -> str:
        """Get human-readable size string for a file or directory."""
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

    def get_tts_backend(self) -> str:
        """Get current TTS backend (refreshes on each call)."""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
            self._tts_backend = config.get("tts_backend", "edge")
        except Exception as e:
            logger.warning("tts_config_refresh_failed", error=str(e))
        return self._tts_backend


# Singleton instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get singleton config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader
