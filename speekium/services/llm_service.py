"""
LLM Service

Manages Large Language Model operations including:
- Backend management (Ollama, OpenAI, Claude, etc.)
- Conversation history
- Message streaming
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig, ServiceError

logger = get_logger(__name__)


@dataclass
class LLMServiceConfig(ServiceConfig):
    """LLM service config."""

    name: str = "llm"
    enabled: bool = True
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    max_history: int = 10
    system_prompt: str = (
        "You are Speekium, an intelligent voice assistant. "
        "Follow these rules:\n"
        "1. Detect the user's language and respond in the same language\n"
        "2. ONLY answer the current question - do not repeat or re-answer previous topics\n"
        "3. Keep responses concise - 1-2 sentences unless more detail is requested\n"
        "4. Use natural conversational style suitable for speech output\n"
        "5. Never use markdown formatting, code blocks, or list symbols\n"
        "6. Avoid special symbols like *, #, `, - etc.\n"
        "7. Express numbers naturally (e.g., 'three point five' instead of '3.5')\n"
        "8. Be friendly, like chatting with a friend"
    )


@dataclass
class ChatResult:
    """Result of a chat operation."""

    success: bool
    response: str = ""
    was_cached: bool = False
    error: Optional[str] = None


class LLMService(BaseService):
    """
    Large Language Model service.

    Manages:
    - LLM backend creation and management
    - Conversation history
    - Chat (streaming and non-streaming)
    - Provider switching
    """

    def __init__(
        self,
        config: LLMServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)
        self.provider = config.provider
        self.model = config.model
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.max_history = config.max_history
        self.system_prompt = config.system_prompt

        # Backend state
        self._backend: Optional[Any] = None
        self._last_config: Optional[dict] = None

    @property
    def is_backend_loaded(self) -> bool:
        """Check if LLM backend is loaded."""
        return self._backend is not None

    async def _on_initialize(self) -> None:
        """Initialize LLM service."""
        self._emit_progress("initializing", 0.0, "Initializing LLM service")
        # Backend is lazy-loaded on first use
        logger.info("llm_service_initialized", provider=self.provider)
        self._emit_progress("initialized", 1.0, "LLM service ready")

    async def _on_start(self) -> None:
        """Start LLM service - load backend."""
        await self._ensure_backend()

    async def _on_stop(self) -> None:
        """Stop LLM service."""
        # Keep backend loaded for faster next use
        pass

    async def _on_shutdown(self) -> None:
        """Release LLM resources."""
        self._backend = None
        self._last_config = None
        logger.info("llm_service_shutdown")

    async def _ensure_backend(self) -> None:
        """Ensure backend is loaded, creating if necessary."""
        if self._backend is not None:
            return

        try:
            from backends import create_backend

            self._emit_progress("loading_backend", 0.0, f"Loading LLM backend: {self.provider}")

            # Create backend
            backend_kwargs: dict[str, Any] = {"max_history": self.max_history}
            if self.model:
                backend_kwargs["model"] = self.model
            if self.base_url:
                backend_kwargs["base_url"] = self.base_url
            if self.api_key:
                backend_kwargs["api_key"] = self.api_key

            self._backend = create_backend(self.provider, self.system_prompt, **backend_kwargs)

            # Store current config for comparison
            self._last_config = {
                "provider": self.provider,
                "model": self.model,
                "base_url": self.base_url,
                "api_key": self.api_key,
            }

            self._emit_progress("backend_loaded", 1.0, f"LLM backend loaded: {self.provider}")
            logger.info("llm_backend_loaded", provider=self.provider, model=self.model)

        except Exception as e:
            logger.error("llm_backend_load_failed", error=str(e))
            raise ServiceError(self.name, f"Failed to load LLM backend: {e}") from e

    async def _check_and_recreate_backend(self) -> bool:
        """Check if backend needs to be recreated due to config changes."""
        if self._backend is None:
            return True

        # Compare current config with last config
        current_config = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
        }

        if self._last_config != current_config:
            logger.info("llm_config_changed", old=self._last_config, new=current_config)
            self._backend = None
            return True

        return False

    async def update_config(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """
        Update LLM configuration.

        Args:
            provider: New provider name
            model: New model name
            base_url: New base URL
            api_key: New API key
        """
        changed = False

        if provider is not None and provider != self.provider:
            self.provider = provider
            changed = True

        if model is not None and model != self.model:
            self.model = model
            changed = True

        if base_url is not None and base_url != self.base_url:
            self.base_url = base_url
            changed = True

        if api_key is not None and api_key != self.api_key:
            self.api_key = api_key
            changed = True

        if changed:
            # Recreate backend on next use
            self._backend = None

    async def chat(self, message: str) -> ChatResult:
        """
        Send a message and get response (non-streaming).

        Args:
            message: User message

        Returns:
            ChatResult with response text
        """
        await self._ensure_backend()

        if self._backend is None:
            return ChatResult(success=False, error="LLM backend not available")

        try:
            # Run chat in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self._backend.chat,
                message,
            )

            logger.info("llm_chat_completed", response_length=len(response))
            return ChatResult(
                success=True,
                response=response,
            )

        except Exception as e:
            logger.error("llm_chat_failed", error=str(e))
            return ChatResult(
                success=False,
                error=str(e),
            )

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """
        Send a message and stream response.

        Args:
            message: User message

        Yields:
            Response text chunks (sentences)
        """
        await self._ensure_backend()

        if self._backend is None:
            yield "Error: LLM backend not available"
            return

        try:
            async for chunk in self._backend.chat_stream(message):
                yield chunk
        except Exception as e:
            logger.error("llm_chat_stream_failed", error=str(e))
            yield f"Error: {e}"

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to conversation history.

        Args:
            role: Message role ("user" or "assistant")
            content: Message content
        """
        if self._backend is not None:
            self._backend.add_message(role, content)

    def clear_history(self) -> None:
        """Clear conversation history."""
        if self._backend is not None:
            self._backend.clear_history()

    def get_history(self) -> list[dict[str, str]]:
        """
        Get conversation history.

        Returns:
            List of message dicts with 'role' and 'content'
        """
        if self._backend is not None:
            return self._backend.history.copy()
        return []

    async def get_config(self) -> dict[str, Any]:
        """
        Get current LLM configuration.

        Returns:
            Dictionary with current config
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key if self.api_key else "",
            "max_history": self.max_history,
            "backend_loaded": self._backend is not None,
        }

    async def health_check(self) -> bool:
        """Check if LLM service is healthy."""
        try:
            # Backend can be lazy-loaded, so check initialization
            return self._is_initialized
        except Exception:
            return False
