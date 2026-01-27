"""
Large Language Model (LLM) module.

Provides LLM configuration loading and backend management.
"""

import sys
from typing import TYPE_CHECKING

from backends import create_backend
from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    pass

# ===== LLM Backend =====
LLM_BACKEND = "ollama"  # Options: "claude", "ollama", "openai", "openrouter", "custom"

# ===== LLM Provider Configuration =====
# New unified structure: llm_provider (name) + llm_providers (array)
LLM_PROVIDER = "ollama"  # Currently selected provider name
LLM_PROVIDERS = []  # Array of provider configs: [{name, base_url, api_key, model}, ...]

# ===== Conversation Memory =====
MAX_HISTORY = 10  # Max conversation turns to keep (each turn = user + assistant)
CLEAR_HISTORY_KEYWORDS = [
    "clear history",
    "start over",
    "forget everything",
    "清空对话",
    "重新开始",
]  # Keywords to trigger history clear

# ===== System Prompt (optimized for voice output) =====
SYSTEM_PROMPT = """You are Speekium, an intelligent voice assistant. Follow these rules:
1. Detect the user's language and respond in the same language
2. ONLY answer the current question - do not repeat or re-answer previous topics
3. Keep responses concise - 1-2 sentences unless more detail is requested
4. Use natural conversational style suitable for speech output
5. Never use markdown formatting, code blocks, or list symbols
6. Avoid special symbols like *, #, `, - etc.
7. Express numbers naturally (e.g., "three point five" instead of "3.5")
8. Be friendly, like chatting with a friend"""


def load_llm_config() -> dict:
    """
    Load LLM backend configuration from config file.

    Returns:
        Dictionary with current provider config:
        {
            "provider": str,
            "base_url": str,
            "api_key": str,
            "model": str,
            "providers": list  # Full LLM_PROVIDERS array
        }
    """
    try:
        from config_manager import ConfigManager

        config = ConfigManager.load()

        # Load current provider and providers array
        provider = config.get("llm_provider", "ollama")
        providers = config.get("llm_providers", [])

        # Find current provider config
        current_provider_config = {}
        for p in providers:
            if p.get("name") == provider:
                current_provider_config = p
                break

        return {
            "provider": provider,
            "base_url": current_provider_config.get("base_url", ""),
            "api_key": current_provider_config.get("api_key", ""),
            "model": current_provider_config.get("model", ""),
            "providers": providers,
        }
    except Exception as e:
        logger.warning("llm_config_load_failed", error=str(e), fallback="default")
        return {
            "provider": "ollama",
            "base_url": "",
            "api_key": "",
            "model": "",
            "providers": [],
        }


def create_llm_backend(
    llm_backend=None,
    last_config: dict | None = None,
    config: dict | None = None,
) -> tuple[object, dict]:
    """
    Create or reuse LLM backend based on configuration.

    Args:
        llm_backend: Existing LLM backend instance
        last_config: Last used configuration dict
        config: New configuration dict (from load_llm_config)

    Returns:
        Tuple of (backend, updated_last_config)
    """
    if config is None:
        config = load_llm_config()

    provider = config["provider"]
    model = config["model"]
    base_url = config["base_url"]
    api_key = config["api_key"]

    # Current config values
    current_config = {
        "provider": provider,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
    }

    # Check if backend needs to be recreated
    needs_recreate = False

    if llm_backend is not None:
        # Check if provider type changed
        backend_class = getattr(llm_backend, "__class__", None)
        current_backend_type: str | None = (
            backend_class.__name__ if backend_class is not None else None
        )
        backend_type_map = {
            "OllamaBackend": "ollama",
            "OpenAIBackend_Official": "openai",
            "OpenRouterBackend": "openrouter",
            "CustomBackend": "custom",
            "ZhipuBackend": "zhipu",
        }
        current_backend = backend_type_map.get(current_backend_type or "", "")

        # Check if any config changed
        if current_backend != current_config["provider"]:
            logger.info(
                "backend_provider_changed",
                from_backend=current_backend,
                to_backend=current_config["provider"],
            )
            needs_recreate = True
        elif last_config and last_config.get("model") != current_config["model"]:
            logger.info(
                "backend_model_changed",
                from_model=last_config.get("model"),
                to_model=current_config["model"],
            )
            needs_recreate = True
        elif last_config and last_config.get("base_url") != current_config["base_url"]:
            logger.info("backend_base_url_changed")
            needs_recreate = True
        elif last_config and last_config.get("api_key") != current_config["api_key"]:
            logger.info("backend_api_key_changed")
            needs_recreate = True
    else:
        # No backend exists, need to create
        needs_recreate = True

    if needs_recreate:
        from logger import set_component

        set_component("LLM")
        logger.info(
            "backend_initializing",
            provider=current_config["provider"],
            model=current_config["model"],
        )
        print(
            f"🔄 正在创建 LLM backend: 服务商={current_config['provider']}, "
            f"模型={current_config['model']}",
            file=sys.stderr,
        )

        # Create backend with unified config
        backend_kwargs = {"max_history": MAX_HISTORY}
        if current_config["model"]:
            backend_kwargs["model"] = current_config["model"]
        if current_config["base_url"]:
            backend_kwargs["base_url"] = current_config["base_url"]
        if current_config["api_key"]:
            backend_kwargs["api_key"] = current_config["api_key"]

        llm_backend = create_backend(
            current_config["provider"],
            SYSTEM_PROMPT,
            **backend_kwargs,
        )

        logger.info(
            "backend_initialized",
            provider=current_config["provider"],
            model=current_config["model"],
        )
        print(
            f"✅ LLM backend 已创建: {current_config['provider']} + {current_config['model']}",
            file=sys.stderr,
        )
    else:
        # Reusing existing backend
        print(
            f"♻️  复用现有 LLM backend: {current_config['provider']} + {current_config['model']}",
            file=sys.stderr,
        )

    return llm_backend, current_config


def get_clear_history_message(language: str) -> str:
    """
    Get the message to play when history is cleared.

    Args:
        language: Language code ('zh', 'en', 'ja', 'ko', 'yue')

    Returns:
        Message text in the specified language
    """
    clear_messages = {
        "zh": "好的，已清空对话记录，重新开始。",
        "en": "OK, conversation cleared. Let's start fresh.",
        "ja": "会話履歴をクリアしました。",
        "ko": "대화 기록을 지웠습니다.",
        "yue": "好，已清空對話記錄。",
    }
    return clear_messages.get(language, clear_messages["en"])
