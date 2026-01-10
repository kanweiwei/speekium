#!/usr/bin/env python3
"""
Speekium Daemon Worker - 守护进程模式
一次启动，持续运行，快速响应

通信协议：
  - 输入：stdin 接收 JSON 命令，每行一个
  - 输出：stdout 返回 JSON 结果，每行一个
  - 日志：stderr 输出调试信息

命令格式：
  {"command": "record", "args": {"mode": "push-to-talk", "duration": 3.0}}
  {"command": "chat", "args": {"text": "hello"}}
  {"command": "tts", "args": {"text": "你好"}}
  {"command": "config", "args": {}}
  {"command": "health", "args": {}}
  {"command": "exit", "args": {}}
"""

import sys
import json
import asyncio
import traceback
from typing import Optional
import sounddevice as sd
import numpy as np

# 确保输出立即刷新
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


class SpeekiumDaemon:
    """Speekium 守护进程核心类"""

    def __init__(self):
        self.assistant = None
        self.running = True
        self.command_count = 0

        # 输出启动日志
        self._log("🚀 Speekium Daemon 初始化中...")

    def _log(self, message: str):
        """输出日志到 stderr"""
        print(f"[Daemon] {message}", file=sys.stderr, flush=True)

    async def initialize(self):
        """预加载所有模型（只在启动时执行一次）"""
        try:
            from speekium import VoiceAssistant

            self._log("📦 加载 VoiceAssistant...")
            self.assistant = VoiceAssistant()

            self._log("🔄 预加载 VAD 模型...")
            self.assistant.load_vad()

            self._log("🔄 预加载 ASR 模型...")
            self.assistant.load_asr()

            self._log("🔄 预加载 LLM 后端...")
            self.assistant.load_llm()

            self._log("✅ 所有模型加载完成，进入待命状态")
            return True

        except Exception as e:
            self._log(f"❌ 初始化失败: {e}")
            traceback.print_exc(file=sys.stderr)
            return False

    async def handle_record(self, mode: str = "push-to-talk", duration: float = 3.0) -> dict:
        """处理录音命令"""
        try:
            self._log(f"🎤 开始录音 (mode={mode}, duration={duration}s)...")

            if mode == "continuous":
                # 使用 VAD 自动检测
                audio = self.assistant.record_with_vad()
            else:
                # 按键录音模式
                audio = sd.rec(
                    int(duration * 16000),
                    samplerate=16000,
                    channels=1,
                    dtype='float32'
                )
                sd.wait()
                audio = audio[:, 0]  # 转为 1D 数组

            if audio is None or len(audio) == 0:
                return {"success": False, "error": "No audio recorded"}

            self._log("🔄 识别中...")
            text, language = self.assistant.transcribe(audio)

            self._log(f"✅ 识别完成: '{text}' ({language})")

            return {
                "success": True,
                "text": text,
                "language": language
            }

        except Exception as e:
            self._log(f"❌ 录音失败: {e}")
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_chat(self, text: str) -> dict:
        """处理 LLM 对话命令（非流式）"""
        try:
            self._log(f"💬 LLM 对话: {text[:50]}...")

            backend = self.assistant.load_llm()
            response = backend.chat(text)

            self._log(f"✅ LLM 响应: {response[:50]}...")

            return {
                "success": True,
                "content": response
            }

        except Exception as e:
            self._log(f"❌ LLM 对话失败: {e}")
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_chat_stream(self, text: str) -> None:
        """处理 LLM 流式对话命令

        流式响应格式：
        - 每个句子一行 JSON：{"type": "chunk", "content": "句子内容"}
        - 结束标记：{"type": "done"}
        - 错误标记：{"type": "error", "error": "错误信息"}
        """
        try:
            self._log(f"💬 LLM 流式对话: {text[:50]}...")

            backend = self.assistant.load_llm()

            # 检查是否支持流式
            if not hasattr(backend, 'chat_stream'):
                # 不支持流式，返回完整响应
                response = backend.chat(text)
                print(json.dumps({
                    "type": "chunk",
                    "content": response
                }), flush=True)
                print(json.dumps({"type": "done"}), flush=True)
                return

            # 流式生成
            async for sentence in backend.chat_stream(text):
                if sentence:
                    self._log(f"📤 流式输出: {sentence[:30]}...")
                    print(json.dumps({
                        "type": "chunk",
                        "content": sentence
                    }), flush=True)

            # 发送完成标记
            print(json.dumps({"type": "done"}), flush=True)
            self._log("✅ 流式对话完成")

        except Exception as e:
            self._log(f"❌ 流式对话失败: {e}")
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({
                "type": "error",
                "error": str(e)
            }), flush=True)

    async def handle_chat_tts_stream(self, text: str, auto_play: bool = True) -> None:
        """处理 LLM 流式对话 + TTS 流式生成命令

        流式响应格式：
        - 文本片段：{"type": "text_chunk", "content": "句子内容"}
        - 音频片段：{"type": "audio_chunk", "audio_path": "/tmp/xxx.mp3", "text": "对应文本"}
        - 结束标记：{"type": "done"}
        - 错误标记：{"type": "error", "error": "错误信息"}
        """
        try:
            self._log(f"💬🔊 LLM+TTS 流式: {text[:50]}...")

            backend = self.assistant.load_llm()

            # 检查是否支持流式
            if not hasattr(backend, 'chat_stream'):
                # 不支持流式，降级处理
                response = backend.chat(text)
                print(json.dumps({
                    "type": "text_chunk",
                    "content": response
                }), flush=True)

                # 生成 TTS
                audio_path = await self.assistant.generate_audio(response)
                if audio_path:
                    print(json.dumps({
                        "type": "audio_chunk",
                        "audio_path": audio_path,
                        "text": response
                    }), flush=True)

                print(json.dumps({"type": "done"}), flush=True)
                return

            # 流式生成 LLM + TTS
            async for sentence in backend.chat_stream(text):
                if sentence and sentence.strip():
                    self._log(f"📤 流式输出: {sentence[:30]}...")

                    # 发送文本片段
                    print(json.dumps({
                        "type": "text_chunk",
                        "content": sentence
                    }), flush=True)

                    # 立即生成 TTS
                    try:
                        audio_path = await self.assistant.generate_audio(sentence)
                        if audio_path:
                            self._log(f"🔊 TTS 完成: {audio_path}")
                            print(json.dumps({
                                "type": "audio_chunk",
                                "audio_path": audio_path,
                                "text": sentence
                            }), flush=True)
                    except Exception as tts_error:
                        self._log(f"⚠️ TTS 生成失败: {tts_error}")
                        # TTS 失败不影响流式对话继续

            # 发送完成标记
            print(json.dumps({"type": "done"}), flush=True)
            self._log("✅ 流式对话+TTS 完成")

        except Exception as e:
            self._log(f"❌ 流式对话+TTS 失败: {e}")
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({
                "type": "error",
                "error": str(e)
            }), flush=True)

    async def handle_tts(self, text: str, language: Optional[str] = None) -> dict:
        """处理 TTS 生成命令"""
        try:
            self._log(f"🔊 TTS 生成: {text[:50]}...")

            audio_path = await self.assistant.generate_audio(text, language)

            if audio_path:
                self._log(f"✅ TTS 完成: {audio_path}")
                return {
                    "success": True,
                    "audio_path": audio_path
                }
            else:
                return {"success": False, "error": "Failed to generate audio"}

        except Exception as e:
            self._log(f"❌ TTS 失败: {e}")
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_config(self) -> dict:
        """处理配置获取命令"""
        try:
            from config_manager import ConfigManager
            config = ConfigManager.load()
            return {"success": True, "config": config}
        except Exception as e:
            self._log(f"❌ 配置加载失败: {e}")
            return {"success": False, "error": str(e)}

    async def handle_health(self) -> dict:
        """健康检查"""
        return {
            "success": True,
            "status": "healthy",
            "command_count": self.command_count,
            "models_loaded": {
                "vad": self.assistant.vad_model is not None,
                "asr": self.assistant.asr_model is not None,
                "llm": self.assistant.llm_backend is not None
            }
        }

    async def handle_command(self, command: str, args: dict) -> dict:
        """路由命令到对应的处理函数

        注意：chat_stream 是特殊命令，不返回 dict，而是直接输出流式数据
        """
        self.command_count += 1

        if command == "record":
            return await self.handle_record(**args)
        elif command == "chat":
            return await self.handle_chat(args.get("text", ""))
        elif command == "chat_stream":
            # 流式命令：直接输出到 stdout，不返回 dict
            await self.handle_chat_stream(args.get("text", ""))
            return None  # 表示已处理，但无返回值
        elif command == "chat_tts_stream":
            # 流式对话 + TTS：直接输出到 stdout，不返回 dict
            await self.handle_chat_tts_stream(
                args.get("text", ""),
                args.get("auto_play", True)
            )
            return None
        elif command == "tts":
            return await self.handle_tts(
                args.get("text", ""),
                args.get("language")
            )
        elif command == "config":
            return await self.handle_config()
        elif command == "health":
            return await self.handle_health()
        elif command == "exit":
            self._log("👋 收到退出命令")
            self.running = False
            return {"success": True, "message": "Daemon shutting down"}
        else:
            return {
                "success": False,
                "error": f"Unknown command: {command}"
            }

    async def run_daemon(self):
        """守护进程主循环"""
        # 初始化
        if not await self.initialize():
            self._log("❌ 初始化失败，退出")
            return

        self._log("✅ 守护进程就绪，等待命令...")

        # 主循环：监听 stdin 命令
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                # 从 stdin 读取一行（阻塞操作，需要在 executor 中运行）
                line = await loop.run_in_executor(None, sys.stdin.readline)

                if not line:
                    # stdin 关闭，退出
                    self._log("📪 stdin 关闭，退出守护进程")
                    break

                line = line.strip()
                if not line:
                    continue

                # 解析 JSON 命令
                try:
                    request = json.loads(line)
                    command = request.get("command")
                    args = request.get("args", {})

                    self._log(f"📥 收到命令: {command}")

                    # 处理命令
                    result = await self.handle_command(command, args)

                    # 输出结果到 stdout
                    # 注意：流式命令 (chat_stream) 返回 None，因为已经直接输出了
                    if result is not None:
                        print(json.dumps(result), flush=True)

                except json.JSONDecodeError as e:
                    self._log(f"⚠️ JSON 解析错误: {e}")
                    error_result = {
                        "success": False,
                        "error": f"Invalid JSON: {str(e)}"
                    }
                    print(json.dumps(error_result), flush=True)

            except Exception as e:
                self._log(f"❌ 主循环错误: {e}")
                traceback.print_exc(file=sys.stderr)
                error_result = {
                    "success": False,
                    "error": f"Internal error: {str(e)}"
                }
                print(json.dumps(error_result), flush=True)

        self._log("👋 守护进程正常退出")


def main():
    """主入口"""
    # 检查是否以守护模式运行
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        daemon = SpeekiumDaemon()
        asyncio.run(daemon.run_daemon())
    else:
        print("Usage: python3 worker_daemon.py daemon", file=sys.stderr)
        print("This script runs as a long-lived daemon process.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
