"""
LLM Backend implementations for Speekium
"""

import subprocess
import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict


class LLMBackend(ABC):
    """Abstract base class for LLM backends"""

    def __init__(self, system_prompt: str, max_history: int = 10):
        self.system_prompt = system_prompt
        self.max_history = max_history  # Max conversation turns to keep
        self.history: List[Dict[str, str]] = []

    def add_message(self, role: str, content: str):
        """Add a message to history"""
        self.history.append({"role": role, "content": content})
        # Keep history within limit (each turn has user + assistant)
        while len(self.history) > self.max_history * 2:
            self.history.pop(0)

    def clear_history(self):
        """Clear conversation history"""
        self.history = []
        print("🗑️ Conversation history cleared", flush=True)

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
        print("🤖 Claude thinking...", flush=True)

        # Build prompt with history context
        history_context = self.get_history_for_prompt()
        if history_context:
            full_message = f"{history_context}\n\nUser: {message}"
        else:
            full_message = message

        try:
            result = subprocess.run(
                [
                    "claude", "-p", full_message,
                    "--dangerously-skip-permissions",
                    "--no-session-persistence",
                    "--system-prompt", self.system_prompt
                ],
                capture_output=True, text=True, timeout=120
            )
            response = result.stdout.strip()
            print(f"💬 Claude: {response}", flush=True)

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", response)

            return response
        except subprocess.TimeoutExpired:
            return "Sorry, response timed out"
        except Exception as e:
            return f"Error: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        print("🤖 Claude thinking...", flush=True)

        # Build prompt with history context
        history_context = self.get_history_for_prompt()
        if history_context:
            full_message = f"{history_context}\n\nUser: {message}"
        else:
            full_message = message

        cmd = [
            "claude", "-p", full_message,
            "--dangerously-skip-permissions",
            "--no-session-persistence",
            "--system-prompt", self.system_prompt,
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        buffer = ""
        full_response = ""
        sentence_endings = re.compile(r'([。！？\n])')

        async for line in process.stdout:
            try:
                data = json.loads(line.decode('utf-8'))

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
                                        print(f"🗣️  {sentence}", flush=True)
                                        yield sentence
                                else:
                                    break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"⚠️ Parse error: {e}", flush=True)
                continue

        if buffer.strip():
            print(f"🗣️  {buffer.strip()}", flush=True)
            full_response += buffer.strip()
            yield buffer.strip()

        await process.wait()

        # Save to history
        self.add_message("user", message)
        self.add_message("assistant", full_response)


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLMs"""

    def __init__(self, system_prompt: str, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434", max_history: int = 10):
        super().__init__(system_prompt, max_history)
        self.model = model
        self.base_url = base_url

    def _build_messages(self, message: str) -> List[Dict[str, str]]:
        """Build message list with history"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})
        return messages

    def chat(self, message: str) -> str:
        print(f"🤖 Ollama ({self.model}) thinking...", flush=True)
        try:
            import httpx

            messages = self._build_messages(message)

            # Debug: Print request data
            print(f"[DEBUG] Sending to Ollama: {len(messages)} messages", flush=True)
            for i, msg in enumerate(messages):
                print(f"[DEBUG] Message {i}: {msg}", flush=True)

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False
            }

            print(f"[DEBUG] Full payload: {json.dumps(payload, ensure_ascii=False, indent=2)}", flush=True)

            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=120
            )

            # Debug: Print response details
            print(f"[DEBUG] Response status: {response.status_code}", flush=True)
            if response.status_code != 200:
                print(f"[DEBUG] Response body: {response.text}", flush=True)

            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            print(f"💬 Ollama: {content}", flush=True)

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", content)

            return content
        except Exception as e:
            print(f"[ERROR] Ollama API error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return f"Error: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        print(f"🤖 Ollama ({self.model}) thinking...", flush=True)

        try:
            import httpx

            messages = self._build_messages(message)
            buffer = ""
            full_response = ""
            sentence_endings = re.compile(r'([。！？\n])')

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True
                    },
                    timeout=120
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
                                            print(f"🗣️  {sentence}", flush=True)
                                            yield sentence
                                    else:
                                        break
                        except json.JSONDecodeError:
                            continue

            if buffer.strip():
                print(f"🗣️  {buffer.strip()}", flush=True)
                full_response += buffer.strip()
                yield buffer.strip()

            # Save to history
            self.add_message("user", message)
            self.add_message("assistant", full_response)

        except Exception as e:
            print(f"⚠️ Ollama error: {e}", flush=True)
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
