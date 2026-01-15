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

# Ensure immediate output flush
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
    """Speekium daemon core class"""

    def __init__(self):
        self.assistant = None
        self.running = True
        self.command_count = 0

        # PTT (Push-to-Talk) state
        self.ptt_recording = False
        self.ptt_audio_frames = []
        self.ptt_stream = None

        # Interrupt flag for LLM/TTS operations
        import threading

        self.interrupt_event = threading.Event()

        # Note: PTT hotkey is handled by Tauri/Rust side via ptt_press/ptt_release commands

        # Event loop reference (set during initialization)
        self.loop = None

        # Output startup log
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

    def _cleanup(self):
        """Clean up resources before exit"""
        self._log("🧹 正在清理资源...")

        # Stop PTT recording if active
        if self.ptt_recording:
            self._log("🧹 停止 PTT 录音...")
            self.ptt_recording = False

        # Close audio stream if open
        if self.ptt_stream:
            try:
                self._log("🧹 关闭音频流...")
                self.ptt_stream.stop()
                self.ptt_stream.close()
            except Exception as e:
                self._log(f"⚠️ 关闭音频流失败: {e}")
            finally:
                self.ptt_stream = None

        # Note: PTT hotkey is now handled by Tauri, no pynput cleanup needed

        self._log("✅ 资源清理完成")

    async def initialize(self):
        """Preload all models (only executed once at startup)"""
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

            # Note: PTT hotkey is now handled by Tauri global shortcuts (Rust side)
            # The pynput hotkey manager is no longer needed
            # PTT commands (ptt_press, ptt_release) are sent from Rust via stdin

            self._log("✅ 所有模型加载完成，进入待命状态")
            return True

        except Exception as e:
            self._log(f"❌ 初始化失败: {e}")
            traceback.print_exc(file=sys.stderr)
            return False

    async def handle_record(self, mode: str = "push-to-talk", duration: float = 3.0) -> dict:
        """Handle recording command"""
        try:
            self._log(f"🎤 开始录音 (mode={mode}, duration={duration}s)...")

            # 🔧 Fix: Clear interrupt flag before starting new recording
            self.assistant.recording_interrupt_event.clear()

            if mode == "continuous":
                # Send "listening" event when entering continuous mode
                self._emit_ptt_event("listening")
                self._log("🎤 正在监听...")

                # Use VAD auto-detection - send recording event when voice detected
                def on_speech():
                    # Send "detected" event when speech is first detected
                    self._emit_ptt_event("detected")
                    self._log("🎤 检测到声音，开始录音...")

                audio = self.assistant.record_with_vad(on_speech_detected=on_speech)
            else:
                # Push-to-talk recording mode - send recording event
                self._emit_ptt_event("recording")
                audio = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype="float32")
                sd.wait()
                audio = audio[:, 0]  # Convert to 1D array

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
                blocksize=512,
            )
            self.ptt_stream.start()

            self._log("🎤 PTT: Recording started")
            return {"success": True, "message": "Recording started"}

        except Exception as e:
            self._log(f"❌ PTT start failed: {e}")
            self.ptt_recording = False
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_ptt_audio(
        self,
        audio_path: str,
        sample_rate: int = 16000,
        duration: float = 0,
        auto_chat: bool = True,
        use_tts: bool = True,
    ) -> dict:
        """Handle PTT audio from Rust - receives WAV file path, performs ASR + chat"""
        import os
        import numpy as np
        from scipy.io import wavfile

        try:
            self._log(f"🎤 PTT Audio: Loading file ({duration:.2f}s): {audio_path}")

            # Check file exists
            if not os.path.exists(audio_path):
                return {"success": False, "error": f"Audio file not found: {audio_path}"}

            # Load WAV file using scipy (simple and reliable)
            wav_sample_rate, samples = wavfile.read(audio_path)

            # Convert to float32 if needed
            if samples.dtype == np.int16:
                samples = samples.astype(np.float32) / 32768.0
            elif samples.dtype == np.int32:
                samples = samples.astype(np.float32) / 2147483648.0
            elif samples.dtype != np.float32:
                samples = samples.astype(np.float32)

            # Convert to mono if stereo
            if len(samples.shape) > 1 and samples.shape[1] == 2:
                samples = samples.mean(axis=1)

            actual_duration = len(samples) / wav_sample_rate
            self._log(
                f"🎵 WAV info: {wav_sample_rate}Hz, {len(samples)} samples ({actual_duration:.2f}s)"
            )

            # Delete temp file after loading
            try:
                os.remove(audio_path)
                self._log(f"🗑️ Deleted temp file: {audio_path}")
            except Exception as e:
                self._log(f"⚠️ Failed to delete temp file: {e}")

            if actual_duration < 0.3:
                self._emit_ptt_event("idle")
                return {"success": False, "error": "Recording too short"}

            # ASR
            self._log("🔄 识别中...")
            text, language = self.assistant.transcribe(samples)
            self._log(f"✅ 识别完成: '{text}' ({language})")

            if not text or not text.strip():
                self._emit_ptt_event("idle")
                return {
                    "success": True,
                    "text": "",
                    "language": language,
                    "message": "No speech detected",
                }

            # Emit user message for frontend display
            self._emit_ptt_event("user_message", {"text": text})

            # Auto chat with TTS if enabled
            if auto_chat and text.strip():
                self._log(f"💬 PTT: Auto chat with TTS...")
                await self._handle_ptt_chat_tts(text, use_tts)

            self._emit_ptt_event("idle")
            return {"success": True, "text": text, "language": language}

        except Exception as e:
            self._log(f"❌ PTT Audio processing failed: {e}")
            self._emit_ptt_event("error", {"error": str(e)})
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
                return {
                    "success": True,
                    "text": "",
                    "language": language,
                    "message": "No speech detected",
                }

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
                except Exception:
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
                        self._emit_ptt_event(
                            "audio_chunk", {"audio_path": audio_path, "text": response}
                        )
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
                                    self._emit_ptt_event(
                                        "audio_chunk", {"audio_path": audio_path, "text": sentence}
                                    )
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
        """Handle LLM chat command (non-streaming)"""
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
        """Handle LLM streaming chat command

        流式响应格式：
        - 每个句子一行 JSON：{"type": "chunk", "content": "句子内容"}
        - 结束标记：{"type": "done"}
        - 错误标记：{"type": "error", "error": "错误信息"}
        """
        try:
            self._log(f"💬 LLM 流式对话: {text[:50]}...")

            backend = self.assistant.load_llm()

            # Check if streaming is supported
            if not hasattr(backend, "chat_stream"):
                # Streaming not supported, return complete response
                response = backend.chat(text)
                print(json.dumps({"type": "chunk", "content": response}), flush=True)
                print(json.dumps({"type": "done"}), flush=True)
                return

            # Stream generation
            async for sentence in backend.chat_stream(text):
                if sentence:
                    self._log(f"📤 流式输出: {sentence[:30]}...")
                    print(json.dumps({"type": "chunk", "content": sentence}), flush=True)

            # Send completion marker
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

            # Clear interrupt flag at start
            self.interrupt_event.clear()

            # Check if streaming is supported
            if not hasattr(backend, "chat_stream"):
                # Fallback to non-streaming mode
                response = backend.chat(text)

                # Check for interrupt before TTS generation
                if self.interrupt_event.is_set():
                    self._log("🚫 LLM response interrupted (before TTS)")
                    print(
                        json.dumps({"type": "interrupted", "reason": "Interrupted before TTS"}),
                        flush=True,
                    )
                    return

                print(json.dumps({"type": "text_chunk", "content": response}), flush=True)

                # Generate TTS
                audio_path = await self.assistant.generate_audio(response)

                # Check for interrupt before playback
                if self.interrupt_event.is_set():
                    self._log("🚫 TTS generation interrupted (before playback)")
                    print(
                        json.dumps(
                            {"type": "interrupted", "reason": "Interrupted before playback"}
                        ),
                        flush=True,
                    )
                    return

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
                # Check for interrupt in streaming loop
                if self.interrupt_event.is_set():
                    self._log("🚫 LLM streaming interrupted")
                    print(
                        json.dumps({"type": "interrupted", "reason": "LLM streaming interrupted"}),
                        flush=True,
                    )
                    break

                if sentence and sentence.strip():
                    self._log(f"📤 Streaming output: {sentence[:30]}...")

                    # Send text chunk
                    print(json.dumps({"type": "text_chunk", "content": sentence}), flush=True)

                    # Check for interrupt before TTS generation
                    if self.interrupt_event.is_set():
                        self._log("🚫 Interrupted before TTS generation")
                        break

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
                                # Check for interrupt before playback
                                if self.interrupt_event.is_set():
                                    self._log("🚫 Interrupted before audio playback")
                                    break
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
        """Play audio file (cross-platform) with interrupt support (P0-4)"""
        import asyncio
        import os
        import platform
        import subprocess

        try:
            system = platform.system()

            if system == "Darwin":  # macOS
                # Use afplay (built-in macOS command)
                process = await asyncio.create_subprocess_exec(
                    "afplay",
                    audio_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._log(f"🔊 Playing audio: {audio_path}")

                # Wait for playback with interrupt checking
                while True:
                    if self.interrupt_event.is_set():
                        self._log("🚫 Audio playback interrupted")
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            process.kill()
                        return
                    if process.poll() is not None:
                        break  # Process finished
                    await asyncio.sleep(0.1)  # Check every 100ms

            elif system == "Linux":
                # Try mpg123 or ffplay
                try:
                    process = await asyncio.create_subprocess_exec(
                        "mpg123",
                        "-q",
                        audio_path,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    self._log(f"🔊 Playing audio: {audio_path}")

                    # Wait for playback with interrupt checking
                    while True:
                        if self.interrupt_event.is_set():
                            self._log("🚫 Audio playback interrupted")
                            process.terminate()
                            try:
                                await asyncio.wait_for(process.wait(), timeout=1.0)
                            except asyncio.TimeoutError:
                                process.kill()
                            return
                        if process.poll() is not None:
                            break
                        await asyncio.sleep(0.1)

                except FileNotFoundError:
                    # Fallback to ffplay if mpg123 is not available
                    process = await asyncio.create_subprocess_exec(
                        "ffplay",
                        "-nodisp",
                        "-autoexit",
                        audio_path,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    self._log(f"🔊 Playing audio: {audio_path}")

                    # Wait for playback with interrupt checking
                    while True:
                        if self.interrupt_event.is_set():
                            self._log("🚫 Audio playback interrupted")
                            process.terminate()
                            try:
                                await asyncio.wait_for(process.wait(), timeout=1.0)
                            except asyncio.TimeoutError:
                                process.kill()
                            return
                        if process.poll() is not None:
                            break
                        await asyncio.sleep(0.1)

            elif system == "Windows":
                # Use Windows Media Player with duration detection
                # Convert Unix path to Windows path if needed
                win_path = os.path.abspath(audio_path).replace("/", "\\")

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
                    "powershell",
                    "-c",
                    ps_script,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                self._log(f"🔊 Playing audio: {audio_path}")

                # Wait for playback with interrupt checking (Windows)
                while True:
                    if self.interrupt_event.is_set():
                        self._log("🚫 Audio playback interrupted")
                        process.terminate()
                        try:
                            await asyncio.wait_for(process.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            process.kill()
                        return
                    if process.poll() is not None:
                        break
                    await asyncio.sleep(0.1)

            else:
                self._log(f"⚠️ Unsupported operating system: {system}")

        except Exception as e:
            self._log(f"⚠️ Audio playback failed: {e}")

    async def handle_tts(self, text: str, language: str | None = None) -> dict:
        """Handle TTS generation command"""
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
        """Handle get config command"""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
            return {"success": True, "config": config}
        except Exception as e:
            self._log(f"❌ 配置加载失败: {e}")
            return {"success": False, "error": str(e)}

    async def handle_save_config(self, config: dict) -> dict:
        """Save configuration"""
        try:
            from config_manager import ConfigManager

            self._log(f"📥 收到保存配置请求: work_mode = {config.get('work_mode', 'MISSING')}")
            ConfigManager.save(config)
            self._log("✅ 配置已保存")

            # Verify save
            saved_config = ConfigManager.load()

            return {"success": True}
        except Exception as e:
            self._log(f"❌ 配置保存失败: {e}")
            return {"success": False, "error": str(e)}

    async def handle_update_hotkey(self, hotkey_config: dict) -> dict:
        """Update hotkey configuration
        Note: Actual hotkey registration is handled by Tauri/Rust side.
        This just acknowledges the config update.
        """
        try:
            display_name = hotkey_config.get("displayName", "unknown")
            self._log(f"📥 收到热键更新请求: {display_name}")
            # Config is saved via set_config command from Rust
            # Tauri handles the actual hotkey re-registration
            self._log(f"✅ 热键配置已确认: {display_name}")
            return {"success": True}
        except Exception as e:
            self._log(f"❌ 热键更新失败: {e}")
            return {"success": False, "error": str(e)}

    async def handle_health(self) -> dict:
        """Health check"""
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

    async def handle_interrupt(self, priority: int = 1) -> dict:
        """P0-4: Handle interrupt request from Rust backend

        Args:
            priority: Interrupt priority (1=mode switch, 2=manual stop, 3=app exit)

        Returns:
            dict with success status and message
        """
        self._log(f"🚫 Interrupt request received (priority {priority})")

        # Set the interrupt flags
        self.interrupt_event.set()

        # 🔧 Fix: Also set VAD recording interrupt flag for continuous mode
        self.assistant.recording_interrupt_event.set()
        self._log("🛑 VAD recording interrupt flag set")

        return {
            "success": True,
            "message": f"Interrupt signal sent (priority {priority})",
        }

    async def handle_get_daemon_state(self) -> dict:
        """P2-10: Get current daemon state

        Returns comprehensive state information including:
        - Running status
        - PTT recording status
        - Model loading status
        - Command statistics
        - Interrupt flag status
        """
        try:
            # Get current state
            state = {
                "success": True,
                "running": self.running,
                "command_count": self.command_count,
                "ptt_recording": self.ptt_recording,
                "interrupt_flag_set": self.interrupt_event.is_set(),
                "models_loaded": {
                    "vad": self.assistant.vad_model is not None,
                    "asr": self.assistant.asr_model is not None,
                    "llm": self.assistant.llm_backend is not None,
                    "tts": self.assistant.tts_backend is not None,
                },
                "audio_frames_count": len(self.ptt_audio_frames) if self.ptt_audio_frames else 0,
                "ptt_stream_active": self.ptt_stream is not None,
            }

            self._log(
                f"📊 Daemon state requested: running={state['running']}, "
                f"ptt_recording={state['ptt_recording']}, "
                f"commands={state['command_count']}"
            )

            return state

        except Exception as e:
            self._log(f"❌ Failed to get daemon state: {e}")
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error": str(e)}

    async def handle_command(self, command: str, args: dict) -> dict:
        """Route commands to corresponding handler functions

        注意：chat_stream 是特殊命令，不返回 dict，而是直接输出流式数据
        """
        self.command_count += 1

        if command == "record":
            return await self.handle_record(**args)
        elif command == "record_start":
            return await self.handle_record_start()
        elif command == "record_stop":
            return await self.handle_record_stop(
                args.get("auto_chat", True), args.get("use_tts", True)
            )
        elif command == "ptt_press":
            # PTT key pressed - just emit event (Rust handles recording now)
            self._emit_ptt_event("recording")
            return {"success": True, "message": "PTT recording started (Rust side)"}
        elif command == "ptt_release":
            # PTT key released - emit event and stop recording (called from Rust, legacy mode)
            self._emit_ptt_event("processing")
            # Read config to determine auto_chat mode
            from config_manager import ConfigManager

            config = ConfigManager.load()
            work_mode = config.get("work_mode", "conversation")
            auto_chat = work_mode == "conversation"
            result = await self.handle_record_stop(auto_chat=auto_chat, use_tts=True)
            if result and result.get("success"):
                self._emit_ptt_event("idle", {"text": result.get("text", "")})
            else:
                self._emit_ptt_event(
                    "error",
                    {"error": result.get("error", "Unknown error") if result else "No result"},
                )
            return result
        elif command == "ptt_audio":
            # PTT audio file from Rust (Rust handles recording, Python handles ASR)
            from config_manager import ConfigManager

            config = ConfigManager.load()
            work_mode = config.get("work_mode", "conversation")
            auto_chat = work_mode == "conversation"
            return await self.handle_ptt_audio(
                audio_path=args.get("audio_path", ""),
                sample_rate=args.get("sample_rate", 16000),
                duration=args.get("duration", 0),
                auto_chat=auto_chat,
                use_tts=True,
            )
        elif command == "chat":
            return await self.handle_chat(args.get("text", ""))
        elif command == "chat_stream":
            # Streaming command: output directly to stdout, do not return dict
            await self.handle_chat_stream(args.get("text", ""))
            return None  # Indicates processed but no return value
        elif command == "chat_tts_stream":
            # Streaming chat + TTS: output directly to stdout, do not return dict
            await self.handle_chat_tts_stream(args.get("text", ""), args.get("auto_play", True))
            return None
        elif command == "tts":
            return await self.handle_tts(args.get("text", ""), args.get("language"))
        elif command == "config":
            return await self.handle_config()
        elif command == "save_config":
            # args is directly the config object (Rust side has processed it)
            return await self.handle_save_config(args)
        elif command == "update_hotkey":
            return await self.handle_update_hotkey(args)
        elif command == "health":
            return await self.handle_health()
        elif command == "interrupt":
            # Handle interrupt request
            priority = args.get("priority", 1)
            return await self.handle_interrupt(priority)
        elif command == "get_daemon_state":
            # Get current daemon state
            return await self.handle_get_daemon_state()
        elif command == "exit":
            self._log("👋 收到退出命令")
            self._cleanup()
            self.running = False
            return {"success": True, "message": "Daemon shutting down"}
        else:
            return {"success": False, "error": f"Unknown command: {command}"}

    async def run_daemon(self):
        """Daemon main loop"""
        # Initialize
        if not await self.initialize():
            self._log("❌ 初始化失败，退出")
            return

        self._log("✅ 守护进程就绪，等待命令...")

        # Main loop: listen for stdin commands
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                # Read one line from stdin (blocking operation, must run in executor)
                line = await loop.run_in_executor(None, sys.stdin.readline)

                if not line:
                    # stdin closed, exit
                    self._log("📪 stdin 关闭，退出守护进程")
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse JSON command
                try:
                    request = json.loads(line)
                    command = request.get("command")
                    args = request.get("args", {})

                    self._log(f"📥 收到命令: {command}")

                    # Handle command
                    result = await self.handle_command(command, args)

                    # Output result to stdout
                    # Note: streaming commands (chat_stream) return None because they already output directly
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

        # Clean up resources before exit
        self._cleanup()
        self._log("👋 守护进程正常退出")


def main():
    """Main entry point"""
    # Check if running in daemon mode
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        daemon = SpeekiumDaemon()
        asyncio.run(daemon.run_daemon())
    else:
        logger.error("invalid_usage", usage="python3 worker_daemon.py daemon")
        sys.exit(1)


if __name__ == "__main__":
    main()
