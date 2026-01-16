import json
import os
import sys
from typing import Any

APP_NAME = "speekium"


def get_config_dir() -> str:
    """Get application config directory (cross-platform)

    - macOS: ~/.config/speekium/
    - Windows: C:/Users/<user>/AppData/Roaming/speekium/
    - Linux: ~/.config/speekium/
    """
    if sys.platform == "win32":
        # Windows
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        # macOS, Linux and others - use ~/.config
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))

    config_dir = os.path.join(base, APP_NAME)

    # Ensure directory exists
    os.makedirs(config_dir, exist_ok=True)

    print(f"📂 配置目录路径: {config_dir}", file=sys.stderr)

    return config_dir


CONFIG_PATH = os.path.join(get_config_dir(), "config.json")
print(f"📄 配置文件路径: {CONFIG_PATH}", file=sys.stderr)

# NEW: Unified LLM provider configuration
DEFAULT_CONFIG: dict[str, Any] = {
    # LLM Provider Configuration
    "llm_provider": "ollama",  # Currently selected provider
    "llm_providers": [
        {
            "name": "ollama",
            "base_url": "http://localhost:11434",
            "api_key": "",
            "model": "qwen2.5:1.5b",
        },
        {
            "name": "openai",
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-4o-mini",
        },
        {
            "name": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "",
            "model": "anthropic/claude-3.5-sonnet",
        },
        {
            "name": "custom",
            "base_url": "",
            "api_key": "",
            "model": "",
        },
        {
            "name": "zhipu",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "api_key": "",
            "model": "glm-4-flash",
        },
    ],
    # TTS Configuration
    "tts_backend": "edge",
    "tts_rate": "+0%",
    # VAD Configuration
    "vad_threshold": 0.5,  # Voice detection threshold (0.0-1.0, lower = more sensitive)
    "vad_consecutive_threshold": 3,  # Consecutive detections to confirm speech start
    "vad_silence_duration": 0.8,  # Silence duration to stop recording (seconds)
    "vad_pre_buffer": 0.3,  # Pre-buffer duration to capture speech start (seconds)
    "vad_min_speech_duration": 0.4,  # Minimum speech duration (seconds)
    "vad_max_recording_duration": 30,  # Maximum recording duration (seconds)
    # Conversation Configuration
    "max_history": 10,
    "work_mode": "conversation",  # conversation | text-input
    "recording_mode": "push-to-talk",  # push-to-talk | continuous
    "system_prompt": "你是一个有帮助的语音助手。",
    # Hotkey Configuration
    "push_to_talk_hotkey": {
        "modifiers": ["Alt"],
        "key": "Digit3",
        "displayName": "⌥3",
    },
}


class ConfigManager:
    @staticmethod
    def load(silent: bool = False) -> dict[str, Any]:
        """Load configuration file

        Args:
            silent: If True, suppress log output (useful for frequent polling)
        """
        if not silent:
            print(f"📖 正在加载配置文件: {CONFIG_PATH}", file=sys.stderr)
            print(f"📖 文件是否存在: {os.path.exists(CONFIG_PATH)}", file=sys.stderr)

        if not os.path.exists(CONFIG_PATH):
            if not silent:
                print(f"📝 配置文件不存在，创建默认配置文件", file=sys.stderr)
            ConfigManager.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = json.load(f)
                # Merge with defaults to ensure all fields exist
                merged = {**DEFAULT_CONFIG, **config}
                if not silent:
                    print(f"✅ 配置文件加载成功", file=sys.stderr)
                    print(f"📊 当前 LLM 服务商: {merged.get('llm_provider')}", file=sys.stderr)
                    providers = merged.get("llm_providers", [])
                    for p in providers:
                        if p.get("name") == "zhipu":
                            print(
                                f"📊 智谱 API Key 长度: {len(p.get('api_key', ''))}",
                                file=sys.stderr,
                            )
                return merged
        except Exception as e:
            if not silent:
                print(f"❌ 配置文件加载失败: {e}", file=sys.stderr)
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config: dict[str, Any]) -> None:
        """Save configuration file"""
        print(f"💾 正在保存配置文件: {CONFIG_PATH}", file=sys.stderr)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"✅ 配置文件保存成功", file=sys.stderr)
            # Verify file was actually written
            if os.path.exists(CONFIG_PATH):
                file_size = os.path.getsize(CONFIG_PATH)
                print(f"📊 文件大小: {file_size} 字节", file=sys.stderr)
        except Exception as e:
            print(f"❌ 配置文件保存失败: {e}", file=sys.stderr)
            raise

    @staticmethod
    def get_path() -> str:
        """Get configuration file path"""
        return CONFIG_PATH
