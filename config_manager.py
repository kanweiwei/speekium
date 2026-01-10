import json
import os
from typing import Optional, Dict, Any

CONFIG_PATH = "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "llm_backend": "ollama",
    "ollama_model": "qwen2.5:1.5b",
    "ollama_base_url": "http://localhost:11434",
    "tts_backend": "edge",
    "tts_rate": "+0%",
    "vad_threshold": 0.7,
    "max_history": 10,
}


class ConfigManager:
    @staticmethod
    def load() -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(CONFIG_PATH):
            ConfigManager.save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"加载配置失败: {e}")
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config: Dict[str, Any]) -> None:
        """保存配置文件"""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")
            raise
