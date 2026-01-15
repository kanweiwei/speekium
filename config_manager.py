import json
import os
import sys
from typing import Any

APP_NAME = "speekium"


def get_config_dir() -> str:
    """Get application config directory (cross-platform)

    - macOS: ~/Library/Application Support/speekium/
    - Windows: C:/Users/<user>/AppData/Roaming/speekium/
    - Linux: ~/.config/speekium/
    """
    if sys.platform == "darwin":
        # macOS
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        # Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        # Linux and others
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))

    config_dir = os.path.join(base, APP_NAME)

    # Ensure directory exists
    os.makedirs(config_dir, exist_ok=True)

    return config_dir


CONFIG_PATH = os.path.join(get_config_dir(), "config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "llm_backend": "ollama",
    "ollama_model": "qwen2.5:1.5b",
    "ollama_base_url": "http://localhost:11434",
    "tts_backend": "edge",
    "tts_rate": "+0%",
    "vad_threshold": 0.5,  # Voice detection threshold (0.0-1.0, lower = more sensitive)
    "vad_consecutive_threshold": 3,  # Consecutive detections to confirm speech start (lower = faster response)
    "vad_silence_duration": 0.8,  # Silence duration to stop recording (seconds)
    "vad_pre_buffer": 0.3,  # Pre-buffer duration to capture speech start (seconds)
    "vad_min_speech_duration": 0.4,  # Minimum speech duration (seconds)
    "vad_max_recording_duration": 30,  # Maximum recording duration (seconds)
    "max_history": 10,
    "work_mode": "conversation",  # conversation | text-input
    "push_to_talk_hotkey": {
        "modifiers": ["CmdOrCtrl"],
        "key": "Digit3",
        "displayName": "⌘3",
    },
}


class ConfigManager:
    @staticmethod
    def load() -> dict[str, Any]:
        """Load configuration file"""
        if not os.path.exists(CONFIG_PATH):
            ConfigManager.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"Failed to load configuration: {e}", file=sys.stderr)
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config: dict[str, Any]) -> None:
        """Save configuration file"""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save configuration: {e}", file=sys.stderr)
            raise

    @staticmethod
    def get_path() -> str:
        """Get configuration file path"""
        return CONFIG_PATH
