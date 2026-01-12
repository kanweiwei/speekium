import json
import os
import sys
from typing import Any

APP_NAME = "speekium"


def get_config_dir() -> str:
    """获取应用配置目录（跨平台）

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

    # 确保目录存在
    os.makedirs(config_dir, exist_ok=True)

    return config_dir


CONFIG_PATH = os.path.join(get_config_dir(), "config.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "llm_backend": "ollama",
    "ollama_model": "qwen2.5:1.5b",
    "ollama_base_url": "http://localhost:11434",
    "tts_backend": "edge",
    "tts_rate": "+0%",
    "vad_threshold": 0.7,
    "max_history": 10,
    "work_mode": "conversation",  # conversation | text
}


class ConfigManager:
    @staticmethod
    def load() -> dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(CONFIG_PATH):
            ConfigManager.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"加载配置失败: {e}", file=sys.stderr)
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config: dict[str, Any]) -> None:
        """保存配置文件"""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}", file=sys.stderr)
            raise

    @staticmethod
    def get_path() -> str:
        """获取配置文件路径"""
        return CONFIG_PATH
