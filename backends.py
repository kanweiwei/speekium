"""
LLM Backend implementations for Speekium
"""

import asyncio
import json
import re
import subprocess
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from logger import get_logger, set_component

# Initialize logger for backends
logger = get_logger(__name__)

# Security: Input validation constants
MAX_INPUT_LENGTH = 10000  # Maximum characters per message
MAX_SYSTEM_PROMPT_LENGTH = 5000
BLOCKED_PATTERNS = [
    r"<script",  # XSS prevention
    r"javascript:",  # URL injection
    r"\x00",  # Null byte injection
]


def validate_input(text: str, max_length: int = MAX_INPUT_LENGTH) -> str:
    """
    Validate and sanitize user input

    Args:
        text: Input text to validate
        max_length: Maximum allowed length

    Returns:
        Validated text

    Raises:
        ValueError: If input is invalid
    """
    if not isinstance(text, str):
        raise ValueError("Input must be a string")

    if len(text) > max_length:
        raise ValueError(f"Input too long: {len(text)} > {max_length} characters")

    if len(text.strip()) == 0:
        raise ValueError("Input cannot be empty")

    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError(f"Input contains blocked pattern: {pattern}")

    # Remove null bytes and other control characters
    text = "".join(char for char in text if ord(char) >= 32 or char in "\n\r\t")

    return text


class LLMBackend(ABC):
    """Abstract base class for LLM backends"""

    def __init__(self, system_prompt: str, max_history: int = 10):
        self.system_prompt = system_prompt
        self.max_history = max_history  # Max conversation turns to keep
        self.history: list[dict[str, str]] = []

    def add_message(self, role: str, content: str):
        """Add a message to history"""
        self.history.append({"role": role, "content": content})
        # Keep history within limit (each turn has user + assistant)
        while len(self.history) > self.max_history * 2:
            self.history.pop(0)

    def clear_history(self):
        """Clear conversation history"""
        self.history = []
        logger.info("conversation_history_cleared", history_length=0)

    def get_history_for_prompt(self) -> str:
        """Format history as prompt text (for backends that don't support message lists)"""
        if not self.history:
            return ""

        lines = ["[Conversation history for context - DO NOT re-answer these:]", ""]
        for msg in self.history:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        lines.append("")
        lines.append("[End of history. ONLY answer the NEW message below, not old ones:]")
        return "\n".join(lines)

    @abstractmethod
    def chat(self, message: str) -> str:
        """Non-streaming chat"""
        pass

    @abstractmethod
    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """Streaming chat, yields sentences"""
        pass


class ClaudeBackend(LLMBackend):
    """Claude Code CLI backend"""

    def chat(self, message: str) -> str:
        logger.info("llm_processing", backend="claude")

        # Security: Validate input
        try:
            message = validate_input(message)
        except ValueError as e:
            logger.warning("input_validation_failed", error=str(e))
            return f"Error: {e}"

        # Build prompt with history context
        history_context = self.get_history_for_prompt()
        if history_context:
            full_message = f"{history_context}\n\nUser: {message}"
        else:
            full_message = message

        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    full_message,
                    "--no-session-persistence",
                    "--system-prompt",
                    self.system_prompt,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            response = result.stdout.strip()
            logger.info("llm_response_received", backend="claude", response_preview=response[:100])

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", response)

            return response
        except subprocess.TimeoutExpired:
            return "Sorry, response timed out"
        except Exception as e:
            return f"Error: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        logger.info("llm_processing", backend="claude")

        # Build prompt with history context
        history_context = self.get_history_for_prompt()
        if history_context:
            full_message = f"{history_context}\n\nUser: {message}"
        else:
            full_message = message

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
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        buffer = ""
        full_response = ""
        sentence_endings = re.compile(r"([。！？\n])")

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
                                        logger.debug("sentence_generated", sentence=sentence)
                                        yield sentence
                                else:
                                    break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning("parse_error", error=str(e))
                continue

        if buffer.strip():
            logger.debug("buffer_output", text=buffer.strip())
            full_response += buffer.strip()
            yield buffer.strip()

        await process.wait()

        # Save to history
        self.add_message("user", message)
        self.add_message("assistant", full_response)


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLMs"""

    def __init__(
        self,
        system_prompt: str,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        max_history: int = 10,
    ):
        super().__init__(system_prompt, max_history)
        self.model = model
        self.base_url = base_url

    def _build_messages(self, message: str) -> list[dict[str, str]]:
        """Build message list with history"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})
        return messages

    def chat(self, message: str) -> str:
        logger.info("llm_processing", backend="ollama", model=self.model)

        # Security: Validate input
        try:
            message = validate_input(message)
        except ValueError as e:
            logger.warning("input_validation_failed", error=str(e))
            return f"Error: {e}"

        try:
            import httpx

            messages = self._build_messages(message)

            # Debug: Print request data
            logger.debug("ollama_request_sent", message_count=len(messages))
            for i, msg in enumerate(messages):
                logger.debug("ollama_message_detail", index=i, message=msg)

            payload = {"model": self.model, "messages": messages, "stream": False}

            logger.debug("ollama_request_payload", payload=payload)

            response = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120)

            # Debug: Print response details
            logger.debug("ollama_response_status", status_code=response.status_code)
            if response.status_code != 200:
                logger.debug("ollama_response_body", body=response.text)

            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            logger.info("llm_response_received", backend="ollama", response_preview=content[:100])

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", content)

            return content
        except Exception as e:
            logger.error("ollama_api_error", error=str(e), error_type=type(e).__name__)
            import traceback

            traceback.print_exc()
            return f"Error: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        logger.info("llm_processing", backend="ollama", model=self.model)

        try:
            import httpx

            messages = self._build_messages(message)
            buffer = ""
            full_response = ""
            sentence_endings = re.compile(r"([。！？\n])")

            async with (
                httpx.AsyncClient() as client,
                client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": True},
                    timeout=120,
                ) as response,
            ):
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
                                        logger.debug("sentence_generated", sentence=sentence)
                                        yield sentence
                                else:
                                    break
                    except json.JSONDecodeError:
                        continue

            if buffer.strip():
                logger.debug("buffer_output", text=buffer.strip())
                full_response += buffer.strip()
                yield buffer.strip()

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", full_response)

        except Exception as e:
            logger.error("ollama_stream_error", error=str(e), error_type=type(e).__name__)
            yield f"Error: {e}"


def create_backend(backend_type: str, system_prompt: str, **kwargs) -> LLMBackend:
    """Factory function to create LLM backend"""
    backends = {
        "claude": ClaudeBackend,
        "ollama": OllamaBackend,
    }

    if backend_type not in backends:
        raise ValueError(f"Unknown backend: {backend_type}. Available: {list(backends.keys())}")

    return backends[backend_type](system_prompt, **kwargs)
