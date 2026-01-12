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

import asyncio
import json
import resource  # NEW: For resource limits
import signal  # NEW: For signal handling
import sys
import traceback

import sounddevice as sd

from logger import configure_logging, get_logger

# Configure logging for daemon (JSON format)
configure_logging(level="INFO", format="json", colored=False)
logger = get_logger(__name__)

# 确保输出立即刷新
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)


# ===== Security: Resource Limits =====
def set_resource_limits():
    """
    Set resource limits to prevent resource exhaustion attacks

    Limits:
    - Memory: 2GB virtual memory (soft), 4GB (hard)
    - CPU: 600 seconds per process (10 minutes)
    - File size: 1GB max file size
    - Open files: 1024 max file descriptors
    """
    try:
        # Memory limit: 2GB soft, 4GB hard
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, 4 * 1024 * 1024 * 1024))

        # CPU time limit: 600 seconds (10 minutes)
        resource.setrlimit(resource.RLIMIT_CPU, (600, 600))

        # File size limit: 1GB
        resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024 * 1024, 1024 * 1024 * 1024))

        # File descriptor limit: 1024
        resource.setrlimit(resource.RLIMIT_NOFILE, (1024, 1024))

        logger.info("resource_limits_set")
    except Exception as e:
        logger.warning("resource_limits_failed", error=str(e))


def handle_timeout(signum, frame):
    """Handle CPU timeout signal"""
    logger.error("cpu_timeout", action="shutdown")
    sys.exit(1)


# Set up signal handler for CPU timeout
signal.signal(signal.SIGXCPU, handle_timeout)

# Apply resource limits
set_resource_limits()


class SpeekiumDaemon:
    """Speekium 守护进程核心类"""

    def __init__(self):
        self.assistant = None
        self.running = True
        self.command_count = 0

        # PTT (Push-to-Talk) state
        self.ptt_recording = False
        self.ptt_audio_frames = []
        self.ptt_stream = None

        # Hotkey manager for PTT
        self.hotkey_manager = None

        # Event loop reference for PTT callbacks (set during initialization)
        self.loop = None

        # 输出启动日志
        logger.info("daemon_initializing")

    def _log(self, message: str):
        """Legacy logging method - deprecated, use logger directly"""
        # Parse common emoji patterns for structured logging
        if "🔄" in message:
            logger.info("daemon_processing", message=message.replace("🔄 ", ""))
        elif "✅" in message:
            logger.info("daemon_success", message=message.replace("✅ ", ""))
        elif "❌" in message:
            logger.error("daemon_error", message=message.replace("❌ ", ""))
        elif "⚠️" in message:
            logger.warning("daemon_warning", message=message.replace("⚠️ ", ""))
        elif "🎤" in message:
            logger.info("daemon_recording", message=message.replace("🎤 ", ""))
        elif "💬" in message:
            logger.info("daemon_chat", message=message.replace("💬 ", ""))
        else:
            logger.info("daemon_log", message=message)

    def _emit_ptt_event(self, event_type: str, data: dict = None):
        """Emit PTT event to stderr for Tauri to capture (stdout is for command responses)"""
        event = {"ptt_event": event_type}
        if data:
            event.update(data)
        # Use stderr to avoid interfering with command responses on stdout
        print(json.dumps(event), file=sys.stderr, flush=True)

    def _on_hotkey_press(self):
        """Callback when PTT hotkey is pressed"""
        self._log("🎤 PTT: Hotkey pressed - starting recording")
        self._emit_ptt_event("recording")

        # Start recording in background (use stored loop reference for thread safety)
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.handle_record_start(), self.loop)

    def _on_hotkey_release(self):
        """Callback when PTT hotkey is released"""
        self._log("🎤 PTT: Hotkey released - stopping recording")
        self._emit_ptt_event("processing")

        # Stop recording and process in background (use stored loop reference for thread safety)
        if not self.loop:
            return

        future = asyncio.run_coroutine_threadsafe(
            self.handle_record_stop(auto_chat=True, use_tts=True),
            self.loop
        )

        # Handle result in another thread to not block
        def handle_result(fut):
            try:
                result = fut.result()
                if result.get("success"):
                    self._emit_ptt_event("idle", {"text": result.get("text", "")})
                else:
                    self._emit_ptt_event("error", {"error": result.get("error", "Unknown error")})
            except Exception as e:
                self._emit_ptt_event("error", {"error": str(e)})

        future.add_done_callback(handle_result)

    async def initialize(self):
        """预加载所有模型（只在启动时执行一次）"""
        try:
            # Store event loop reference for PTT callbacks (called from different thread)
            self.loop = asyncio.get_running_loop()

            from speekium import VoiceAssistant

            logger.info("loading_voice_assistant")
            self.assistant = VoiceAssistant()

            logger.info("preloading_vad_model")
            self.assistant.load_vad()

            logger.info("preloading_asr_model")
            self.assistant.load_asr()

            self._log("🔄 预加载 LLM 后端...")
            self.assistant.load_llm()

            # Initialize and start hotkey manager for PTT
            try:
                from hotkey_manager import HotkeyManager
                self.hotkey_manager = HotkeyManager()
                self.hotkey_manager.start(
                    on_press=self._on_hotkey_press,
                    on_release=self._on_hotkey_release
                )
                self._log("✅ PTT 快捷键监听已启动 (Cmd+Alt)")
            except Exception as e:
                self._log(f"⚠️ PTT 快捷键监听启动失败: {e}")
                # Continue without hotkey - can still use commands

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
                # 使用 VAD 自动检测 - 检测到语音时发送 recording 事件
                def on_speech():
                    self._emit_ptt_event("recording")
                audio = self.assistant.record_with_vad(on_speech_detected=on_speech)
            else:
                # 按键录音模式 - 发送 recording 事件
                self._emit_ptt_event("recording")
                audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype="float32")
                sd.wait()
                audio = audio[:, 0]  # 转为 1D 数组

            if audio is None or len(audio) == 0:
                self._emit_ptt_event("idle")
                return {"success": False, "error": "No audio recorded"}

            self._log("🔄 识别中...")
            self._emit_ptt_event("processing")
            text, language = self.assistant.transcribe(audio)

            self._log(f"✅ 识别完成: '{text}' ({language})")
            self._emit_ptt_event("idle")

            return {"success": True, "text": text, "language": language}

        except Exception as e:
            self._log(f"❌ 录音失败: {e}")
            self._emit_ptt_event("idle")
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_record_start(self) -> dict:
        """Start PTT recording - called when hotkey is pressed"""
        try:
            if self.ptt_recording:
                return {"success": False, "error": "Already recording"}

            self._log("🎤 PTT: Starting recording...")

            # Clear previous audio frames
            self.ptt_audio_frames = []
            self.ptt_recording = True

            # Audio callback to collect frames
            def audio_callback(indata, frames, time_info, status):
                if self.ptt_recording:
                    self.ptt_audio_frames.append(indata.copy())

            # Start audio stream
            self.ptt_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                callback=audio_callback,
                blocksize=512
            )
            self.ptt_stream.start()

            self._log("🎤 PTT: Recording started")
            return {"success": True, "message": "Recording started"}

        except Exception as e:
            self._log(f"❌ PTT start failed: {e}")
            self.ptt_recording = False
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_record_stop(self, auto_chat: bool = True, use_tts: bool = True) -> dict:
        """Stop PTT recording and process - called when hotkey is released"""
        try:
            if not self.ptt_recording:
                return {"success": False, "error": "Not recording"}

            self._log("🎤 PTT: Stopping recording...")

            # Stop recording
            self.ptt_recording = False

            if self.ptt_stream:
                self.ptt_stream.stop()
                self.ptt_stream.close()
                self.ptt_stream = None

            # Combine audio frames
            if not self.ptt_audio_frames:
                return {"success": False, "error": "No audio recorded"}

            import numpy as np
            audio = np.concatenate(self.ptt_audio_frames, axis=0)
            audio = audio[:, 0]  # Convert to 1D array

            duration = len(audio) / 16000
            self._log(f"🎤 PTT: Recorded {duration:.2f}s of audio")

            if duration < 0.3:
                return {"success": False, "error": "Recording too short"}

            # ASR
            self._log("🔄 识别中...")
            text, language = self.assistant.transcribe(audio)
            self._log(f"✅ 识别完成: '{text}' ({language})")

            if not text or not text.strip():
                return {"success": True, "text": "", "language": language, "message": "No speech detected"}

            # Emit user message for frontend display
            self._emit_ptt_event("user_message", {"text": text})

            # Auto chat with TTS if enabled
            if auto_chat and text.strip():
                self._log(f"💬 PTT: Auto chat with TTS...")
                await self._handle_ptt_chat_tts(text, use_tts)

            return {"success": True, "text": text, "language": language}

        except Exception as e:
            self._log(f"❌ PTT stop failed: {e}")
            self.ptt_recording = False
            if self.ptt_stream:
                try:
                    self.ptt_stream.stop()
                    self.ptt_stream.close()
                except:
                    pass
                self.ptt_stream = None
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def _handle_ptt_chat_tts(self, text: str, use_tts: bool = True) -> None:
        """Handle LLM streaming chat + TTS for PTT mode (emits via stderr for Rust capture)"""
        try:
            self._log(f"💬🔊 PTT LLM+TTS: {text[:50]}...")

            backend = self.assistant.load_llm()
            full_response = ""

            # Check if streaming is supported
            if not hasattr(backend, "chat_stream"):
                # Fallback to non-streaming mode
                response = backend.chat(text)
                full_response = response
                self._emit_ptt_event("assistant_chunk", {"content": response})

                # Generate TTS
                if use_tts:
                    audio_path = await self.assistant.generate_audio(response)
                    if audio_path:
                        self._emit_ptt_event("audio_chunk", {"audio_path": audio_path, "text": response})
                        await self._play_audio(audio_path)
            else:
                # Stream LLM + TTS generation
                async for sentence in backend.chat_stream(text):
                    if sentence and sentence.strip():
                        full_response += sentence
                        self._log(f"📤 PTT streaming: {sentence[:30]}...")

                        # Send text chunk via stderr
                        self._emit_ptt_event("assistant_chunk", {"content": sentence})

                        # Generate TTS immediately
                        if use_tts:
                            try:
                                audio_path = await self.assistant.generate_audio(sentence)
                                if audio_path:
                                    self._log(f"🔊 TTS completed: {audio_path}")
                                    self._emit_ptt_event("audio_chunk", {"audio_path": audio_path, "text": sentence})
                                    await self._play_audio(audio_path)
                            except Exception as tts_error:
                                self._log(f"⚠️ TTS generation failed: {tts_error}")

            # Send completion marker
            self._emit_ptt_event("assistant_done", {"content": full_response})
            self._log("✅ PTT LLM+TTS completed")

        except Exception as e:
            self._log(f"❌ PTT LLM+TTS failed: {e}")
            traceback.print_exc(file=sys.stderr)
            self._emit_ptt_event("error", {"error": str(e)})

    async def handle_chat(self, text: str) -> dict:
        """处理 LLM 对话命令（非流式）"""
        try:
            self._log(f"💬 LLM 对话: {text[:50]}...")

            backend = self.assistant.load_llm()
            response = backend.chat(text)

            self._log(f"✅ LLM 响应: {response[:50]}...")

            return {"success": True, "content": response}

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
            if not hasattr(backend, "chat_stream"):
                # 不支持流式，返回完整响应
                response = backend.chat(text)
                print(json.dumps({"type": "chunk", "content": response}), flush=True)
                print(json.dumps({"type": "done"}), flush=True)
                return

            # 流式生成
            async for sentence in backend.chat_stream(text):
                if sentence:
                    self._log(f"📤 流式输出: {sentence[:30]}...")
                    print(json.dumps({"type": "chunk", "content": sentence}), flush=True)

            # 发送完成标记
            print(json.dumps({"type": "done"}), flush=True)
            self._log("✅ 流式对话完成")

        except Exception as e:
            self._log(f"❌ 流式对话失败: {e}")
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"type": "error", "error": str(e)}), flush=True)

    async def handle_chat_tts_stream(self, text: str, auto_play: bool = True) -> None:
        """Handle LLM streaming chat + TTS streaming generation

        Streaming response format:
        - Text chunk: {"type": "text_chunk", "content": "sentence content"}
        - Audio chunk: {"type": "audio_chunk", "audio_path": "/tmp/xxx.mp3", "text": "corresponding text"}
        - Done marker: {"type": "done"}
        - Error marker: {"type": "error", "error": "error message"}
        """
        import asyncio
        import platform

        try:
            self._log(f"💬🔊 LLM+TTS streaming: {text[:50]}...")

            backend = self.assistant.load_llm()

            # Check if streaming is supported
            if not hasattr(backend, "chat_stream"):
                # Fallback to non-streaming mode
                response = backend.chat(text)
                print(json.dumps({"type": "text_chunk", "content": response}), flush=True)

                # Generate TTS
                audio_path = await self.assistant.generate_audio(response)
                if audio_path and auto_play:
                    print(
                        json.dumps(
                            {"type": "audio_chunk", "audio_path": audio_path, "text": response}
                        ),
                        flush=True,
                    )
                    # Play audio immediately
                    await self._play_audio(audio_path)

                print(json.dumps({"type": "done"}), flush=True)
                return

            # Stream LLM + TTS generation
            async for sentence in backend.chat_stream(text):
                if sentence and sentence.strip():
                    self._log(f"📤 Streaming output: {sentence[:30]}...")

                    # Send text chunk
                    print(json.dumps({"type": "text_chunk", "content": sentence}), flush=True)

                    # Generate TTS immediately
                    try:
                        audio_path = await self.assistant.generate_audio(sentence)
                        if audio_path:
                            self._log(f"🔊 TTS completed: {audio_path}")
                            print(
                                json.dumps(
                                    {
                                        "type": "audio_chunk",
                                        "audio_path": audio_path,
                                        "text": sentence,
                                    }
                                ),
                                flush=True,
                            )
                            # Play audio immediately if auto_play is enabled
                            if auto_play:
                                await self._play_audio(audio_path)
                    except Exception as tts_error:
                        self._log(f"⚠️ TTS generation failed: {tts_error}")
                        # TTS failure should not interrupt streaming chat

            # Send completion marker
            print(json.dumps({"type": "done"}), flush=True)
            self._log("✅ Streaming chat+TTS completed")

        except Exception as e:
            self._log(f"❌ Streaming chat+TTS failed: {e}")
            traceback.print_exc(file=sys.stderr)
            print(json.dumps({"type": "error", "error": str(e)}), flush=True)

    async def _play_audio(self, audio_path: str) -> None:
        """Play audio file (cross-platform)"""
        import asyncio
        import os
        import platform
        import subprocess

        try:
            system = platform.system()

            if system == "Darwin":  # macOS
                # Use afplay (built-in macOS command)
                process = await asyncio.create_subprocess_exec(
                    "afplay", audio_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                self._log(f"🔊 Playing audio: {audio_path}")
                await process.wait()  # Wait for playback to complete

            elif system == "Linux":
                # Try mpg123 or ffplay
                try:
                    process = await asyncio.create_subprocess_exec(
                        "mpg123", "-q", audio_path,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    self._log(f"🔊 Playing audio: {audio_path}")
                    await process.wait()
                except FileNotFoundError:
                    # Fallback to ffplay if mpg123 is not available
                    process = await asyncio.create_subprocess_exec(
                        "ffplay", "-nodisp", "-autoexit", audio_path,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL
                    )
                    self._log(f"🔊 Playing audio: {audio_path}")
                    await process.wait()

            elif system == "Windows":
                # Use Windows Media Player with duration detection
                # Convert Unix path to Windows path if needed
                win_path = os.path.abspath(audio_path).replace('/', '\\')

                # PowerShell script to play audio and wait for completion
                ps_script = (
                    f"Add-Type -AssemblyName presentationCore; "
                    f"$mediaPlayer = New-Object System.Windows.Media.MediaPlayer; "
                    f"$mediaPlayer.Open([uri]::new('{win_path}')); "
                    f"$mediaPlayer.Play(); "
                    # Wait for NaturalDuration to be available
                    f"while ($mediaPlayer.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}; "
                    # Get duration in seconds and add 0.5s buffer
                    f"$duration = $mediaPlayer.NaturalDuration.TimeSpan.TotalSeconds + 0.5; "
                    f"Start-Sleep -Seconds $duration; "
                    f"$mediaPlayer.Close()"
                )

                process = await asyncio.create_subprocess_exec(
                    "powershell", "-c", ps_script,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                self._log(f"🔊 Playing audio: {audio_path}")
                await process.wait()

            else:
                self._log(f"⚠️ Unsupported operating system: {system}")

        except Exception as e:
            self._log(f"⚠️ Audio playback failed: {e}")

    async def handle_tts(self, text: str, language: str | None = None) -> dict:
        """处理 TTS 生成命令"""
        try:
            self._log(f"🔊 TTS 生成: {text[:50]}...")

            audio_path = await self.assistant.generate_audio(text, language)

            if audio_path:
                self._log(f"✅ TTS 完成: {audio_path}")
                return {"success": True, "audio_path": audio_path}
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

    async def handle_save_config(self, config: dict) -> dict:
        """保存配置"""
        try:
            from config_manager import ConfigManager

            ConfigManager.save(config)
            self._log("✅ 配置已保存")
            return {"success": True}
        except Exception as e:
            self._log(f"❌ 配置保存失败: {e}")
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
                "llm": self.assistant.llm_backend is not None,
            },
        }

    async def handle_command(self, command: str, args: dict) -> dict:
        """路由命令到对应的处理函数

        注意：chat_stream 是特殊命令，不返回 dict，而是直接输出流式数据
        """
        self.command_count += 1

        if command == "record":
            return await self.handle_record(**args)
        elif command == "record_start":
            return await self.handle_record_start()
        elif command == "record_stop":
            return await self.handle_record_stop(
                args.get("auto_chat", True),
                args.get("use_tts", True)
            )
        elif command == "chat":
            return await self.handle_chat(args.get("text", ""))
        elif command == "chat_stream":
            # 流式命令：直接输出到 stdout，不返回 dict
            await self.handle_chat_stream(args.get("text", ""))
            return None  # 表示已处理，但无返回值
        elif command == "chat_tts_stream":
            # 流式对话 + TTS：直接输出到 stdout，不返回 dict
            await self.handle_chat_tts_stream(args.get("text", ""), args.get("auto_play", True))
            return None
        elif command == "tts":
            return await self.handle_tts(args.get("text", ""), args.get("language"))
        elif command == "config":
            return await self.handle_config()
        elif command == "save_config":
            return await self.handle_save_config(args.get("config", {}))
        elif command == "health":
            return await self.handle_health()
        elif command == "exit":
            self._log("👋 收到退出命令")
            self.running = False
            return {"success": True, "message": "Daemon shutting down"}
        else:
            return {"success": False, "error": f"Unknown command: {command}"}

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
                    error_result = {"success": False, "error": f"Invalid JSON: {str(e)}"}
                    print(json.dumps(error_result), flush=True)

            except Exception as e:
                self._log(f"❌ 主循环错误: {e}")
                traceback.print_exc(file=sys.stderr)
                error_result = {"success": False, "error": f"Internal error: {str(e)}"}
                print(json.dumps(error_result), flush=True)

        self._log("👋 守护进程正常退出")


def main():
    """主入口"""
    # 检查是否以守护模式运行
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        daemon = SpeekiumDaemon()
        asyncio.run(daemon.run_daemon())
    else:
        logger.error("invalid_usage", usage="python3 worker_daemon.py daemon")
        sys.exit(1)


if __name__ == "__main__":
    main()
