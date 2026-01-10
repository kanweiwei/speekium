"""
Speekium LLM Backend Module for Tauri
Async-ready LLM backends with streaming support
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator, List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum


class LLMBackendType(str, Enum):
    """Supported LLM backend types"""

    CLAUDE = "claude"
    OLLAMA = "ollama"


class ChatMessageType(str, Enum):
    """Chat message types for streaming"""

    PARTIAL = "partial"
    COMPLETE = "complete"
    ERROR = "error"


# ===== LLM Backend Abstract Class =====


class LLMBackend(ABC):
    """Abstract base class for LLM backends with async support"""

    def __init__(
        self,
        system_prompt: str,
        max_history: int = 10,
        logger: Optional[logging.Logger] = None,
    ):
        self.system_prompt = system_prompt
        self.max_history = max_history
        self.history: List[Dict[str, str]] = []
        self.logger = logger or logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=2)

    def add_message(self, role: str, content: str):
        """Add a message to history"""
        self.history.append({"role": role, "content": content})
        while len(self.history) > self.max_history * 2:
            self.history.pop(0)

    def clear_history(self):
        """Clear conversation history"""
        self.history = []
        self.logger.info("Conversation history cleared")

    def get_history_for_prompt(self) -> str:
        """Format history as prompt text"""
        if not self.history:
            return ""

        lines = ["[Conversation history for context - DO NOT re-answer these:]", ""]
        for msg in self.history:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        lines.append("")
        lines.append(
            "[End of history. ONLY answer the NEW message below, not old ones:]"
        )
        return "\n".join(lines)

    @abstractmethod
    async def chat_async(self, message: str) -> str:
        """Non-streaming async chat"""
        pass

    @abstractmethod
    async def chat_stream_async(
        self, message: str
    ) -> AsyncIterator[Tuple[str, ChatMessageType]]:
        """Streaming async chat, yields (text, type) tuples"""
        pass

    async def shutdown(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.logger.info("LLM backend shut down")


# ===== Claude Backend =====


class ClaudeBackend(LLMBackend):
    """Claude Code CLI backend with async support"""

    async def chat_async(self, message: str) -> str:
        """Non-streaming async chat"""
        self.logger.info("Claude thinking...")

        history_context = self.get_history_for_prompt()
        full_message = (
            f"{history_context}\n\nUser: {message}" if history_context else message
        )

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._run_claude_command,
                full_message,
            )

            self.logger.info(f"Claude: {result}")

            self.add_message("user", message)
            self.add_message("assistant", result)

            return result
        except asyncio.TimeoutError:
            self.logger.error("Claude response timed out")
            return "Sorry, response timed out"
        except Exception as e:
            self.logger.error(f"Claude error: {e}")
            return f"Error: {e}"

    def _run_claude_command(self, message: str) -> str:
        """Blocking Claude command execution"""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    message,
                    "--dangerously-skip-permissions",
                    "--no-session-persistence",
                    "--system-prompt",
                    self.system_prompt,
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise asyncio.TimeoutError("Claude command timed out")

    async def chat_stream_async(
        self, message: str
    ) -> AsyncIterator[Tuple[str, ChatMessageType]]:
        """Streaming async chat"""
        self.logger.info("Claude thinking...")

        history_context = self.get_history_for_prompt()
        full_message = (
            f"{history_context}\n\nUser: {message}" if history_context else message
        )

        cmd = [
            "claude",
            "-p",
            full_message,
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--system-prompt",
            self.system_prompt,
            "--output-format",
            "stream-json",
            "--include-partial-messages",
            "--verbose",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        buffer = ""
        full_response = ""
        sentence_endings = re.compile(r"([。！？\n])")

        try:
            async for line in process.stdout:
                try:
                    data = json.loads(line.decode("utf-8"))

                    if data.get("type") == "stream_event":
                        event = data.get("event", {})
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                buffer += text
                                full_response += text

                                while True:
                                    match = sentence_endings.search(buffer)
                                    if match:
                                        end_pos = match.end()
                                        sentence = buffer[:end_pos].strip()
                                        buffer = buffer[end_pos:]
                                        if sentence:
                                            self.logger.info(f"[Claude] {sentence}")
                                            yield sentence, ChatMessageType.PARTIAL
                                    else:
                                        break
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    self.logger.warning(f"Parse error: {e}")
                    continue

            if buffer.strip():
                self.logger.info(f"[Claude] {buffer.strip()}")
                full_response += buffer.strip()
                yield buffer.strip(), ChatMessageType.PARTIAL

            await process.wait()

            self.add_message("user", message)
            self.add_message("assistant", full_response)

            yield full_response, ChatMessageType.COMPLETE

        except Exception as e:
            self.logger.error(f"Claude streaming error: {e}")
            yield f"Error: {e}", ChatMessageType.ERROR
            process.kill()
            await process.wait()


# ===== Ollama Backend =====


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLMs with async support"""

    def __init__(
        self,
        system_prompt: str,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        max_history: int = 10,
        logger: Optional[logging.Logger] = None,
    ):
        super().__init__(system_prompt, max_history, logger)
        self.model = model
        self.base_url = base_url

    def _build_messages(self, message: str) -> List[Dict[str, str]]:
        """Build message list with history"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})
        return messages

    async def chat_async(self, message: str) -> str:
        """Non-streaming async chat"""
        self.logger.info(f"Ollama ({self.model}) thinking...")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._run_ollama_request,
                message,
            )

            self.logger.info(f"Ollama: {result}")

            self.add_message("user", message)
            self.add_message("assistant", result)

            return result
        except Exception as e:
            self.logger.error(f"Ollama error: {e}")
            return f"Error: {e}"

    def _run_ollama_request(self, message: str) -> str:
        """Blocking Ollama HTTP request"""
        import httpx

        try:
            messages = self._build_messages(message)

            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            return content
        except httpx.TimeoutException:
            raise asyncio.TimeoutError("Ollama request timed out")

    async def chat_stream_async(
        self, message: str
    ) -> AsyncIterator[Tuple[str, ChatMessageType]]:
        """Streaming async chat"""
        self.logger.info(f"Ollama ({self.model}) thinking...")

        try:
            import httpx

            messages = self._build_messages(message)
            buffer = ""
            full_response = ""
            sentence_endings = re.compile(r"([。！？\n])")

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                    },
                    timeout=120,
                ) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                buffer += content
                                full_response += content

                                while True:
                                    match = sentence_endings.search(buffer)
                                    if match:
                                        end_pos = match.end()
                                        sentence = buffer[:end_pos].strip()
                                        buffer = buffer[end_pos:]
                                        if sentence:
                                            self.logger.info(f"[Ollama] {sentence}")
                                            yield sentence, ChatMessageType.PARTIAL
                                    else:
                                        break
                        except json.JSONDecodeError:
                            continue

            if buffer.strip():
                self.logger.info(f"[Ollama] {buffer.strip()}")
                full_response += buffer.strip()
                yield buffer.strip(), ChatMessageType.PARTIAL

            self.add_message("user", message)
            self.add_message("assistant", full_response)

            yield full_response, ChatMessageType.COMPLETE

        except Exception as e:
            self.logger.error(f"Ollama streaming error: {e}")
            yield f"Error: {e}", ChatMessageType.ERROR


# ===== Backend Factory =====


def create_backend(
    backend_type: str,
    system_prompt: str,
    **kwargs,
) -> LLMBackend:
    """Factory function to create LLM backend"""
    backends = {
        "claude": ClaudeBackend,
        "ollama": OllamaBackend,
    }

    if backend_type not in backends:
        raise ValueError(
            f"Unknown backend: {backend_type}. Available: {list(backends.keys())}"
        )

    return backends[backend_type](system_prompt, **kwargs)


# ===== Backend Manager =====


class LLMBackendManager:
    """Manages LLM backend lifecycle with config integration"""

    def __init__(
        self,
        config: Dict[str, any],
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.backend: Optional[LLMBackend] = None
        self.backend_type = config.get("llm_backend", "ollama")

    def load_backend(self, backend_type: Optional[str] = None) -> LLMBackend:
        """Load or reload LLM backend"""
        if backend_type:
            self.backend_type = backend_type

        self.logger.info(f"Loading LLM backend: {self.backend_type}")

        if self.backend:
            asyncio.create_task(self.backend.shutdown())

        system_prompt = """You are Speekium, an intelligent voice assistant. Follow these rules:
1. Detect the user's language and respond in the same language
2. ONLY answer the current question - do not repeat or re-answer previous topics
3. Keep responses concise - 1-2 sentences unless more detail is requested
4. Use natural conversational style suitable for speech output
5. Never use markdown formatting, code blocks, or list symbols
6. Avoid special symbols like *, #, `, - etc.
7. Express numbers naturally (e.g., "three point five" instead of "3.5")
8. Be friendly, like chatting with a friend"""

        if self.backend_type == "ollama":
            self.backend = create_backend(
                self.backend_type,
                system_prompt,
                model=self.config.get("ollama_model", "qwen2.5:1.5b"),
                base_url=self.config.get("ollama_base_url", "http://localhost:11434"),
                max_history=self.config.get("max_history", 10),
                logger=self.logger,
            )
        else:
            self.backend = create_backend(
                self.backend_type,
                system_prompt,
                max_history=self.config.get("max_history", 10),
                logger=self.logger,
            )

        self.logger.info(f"LLM backend loaded successfully")
        return self.backend

    def get_backend(self) -> LLMBackend:
        """Get current LLM backend, loading if necessary"""
        if self.backend is None:
            return self.load_backend()
        return self.backend

    async def clear_history(self):
        """Clear conversation history"""
        if self.backend:
            self.backend.clear_history()

    async def shutdown(self):
        """Cleanup resources"""
        if self.backend:
            await self.backend.shutdown()
            self.backend = None
            self.logger.info("LLM backend manager shut down")
