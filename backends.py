"""
LLM Backend implementations for Speekium
"""

import subprocess
import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import AsyncIterator


class LLMBackend(ABC):
    """Abstract base class for LLM backends"""

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

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
        print("🤖 Claude 思考中...", flush=True)
        try:
            result = subprocess.run(
                [
                    "claude", "-p", message,
                    "--dangerously-skip-permissions",
                    "--system-prompt", self.system_prompt
                ],
                capture_output=True, text=True, timeout=120
            )
            response = result.stdout.strip()
            print(f"💬 Claude: {response}", flush=True)
            return response
        except subprocess.TimeoutExpired:
            return "抱歉，回复超时了"
        except Exception as e:
            return f"出错了: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        print("🤖 Claude 思考中...", flush=True)

        cmd = [
            "claude", "-p", message,
            "--dangerously-skip-permissions",
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
                print(f"⚠️ 解析错误: {e}", flush=True)
                continue

        if buffer.strip():
            print(f"🗣️  {buffer.strip()}", flush=True)
            yield buffer.strip()

        await process.wait()


class OllamaBackend(LLMBackend):
    """Ollama backend for local LLMs"""

    def __init__(self, system_prompt: str, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        super().__init__(system_prompt)
        self.model = model
        self.base_url = base_url

    def chat(self, message: str) -> str:
        print(f"🤖 Ollama ({self.model}) 思考中...", flush=True)
        try:
            import httpx

            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": message}
                    ],
                    "stream": False
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "")
            print(f"💬 Ollama: {content}", flush=True)
            return content
        except Exception as e:
            return f"出错了: {e}"

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        print(f"🤖 Ollama ({self.model}) 思考中...", flush=True)

        try:
            import httpx

            buffer = ""
            sentence_endings = re.compile(r'([。！？\n])')

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": self.system_prompt},
                            {"role": "user", "content": message}
                        ],
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
                yield buffer.strip()

        except Exception as e:
            print(f"⚠️ Ollama 错误: {e}", flush=True)
            yield f"出错了: {e}"


def create_backend(backend_type: str, system_prompt: str, **kwargs) -> LLMBackend:
    """Factory function to create LLM backend"""
    backends = {
        "claude": ClaudeBackend,
        "ollama": OllamaBackend,
    }

    if backend_type not in backends:
        raise ValueError(f"Unknown backend: {backend_type}. Available: {list(backends.keys())}")

    return backends[backend_type](system_prompt, **kwargs)
