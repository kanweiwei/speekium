#!/usr/bin/env python3
"""
Speekium - Intelligent Voice Assistant
Natural voice conversation with large language models
Flow: [VAD voice detection] → Record → SenseVoice ASR → LLM streaming → TTS playback

Supported backends: Claude Code CLI, Ollama
"""

import asyncio
import atexit
import os
import platform
import re
import stat
import tempfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import edge_tts
import numpy as np
import sounddevice as sd
import torch
from scipy.io.wavfile import write as write_wav

from backends import create_backend
from logger import get_logger, new_request, new_session, set_component
from mode_manager import ModeManager, RecordingMode

# Initialize logger
logger = get_logger(__name__)

# ===== Security: Temporary File Management =====
_temp_files: list[str] = []


def create_secure_temp_file(suffix: str = ".tmp") -> str:
    """
    Create a temporary file with secure permissions (0600 - owner read/write only)

    Args:
        suffix: File extension

    Returns:
        Path to the temporary file
    """
    # Create temp file with delete=False (we'll manage cleanup manually)
    fd, path = tempfile.mkstemp(suffix=suffix)

    # Set secure permissions: 0600 (owner read/write only)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    # Close the file descriptor
    os.close(fd)

    # Track for cleanup
    _temp_files.append(path)

    return path


def cleanup_temp_files():
    """Clean up all temporary files created by this session"""
    for path in _temp_files:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("temp_file_cleaned", file_path=path)
        except Exception as e:
            logger.warning("temp_file_cleanup_failed", file_path=path, error=str(e))

    _temp_files.clear()


# Register cleanup on exit
atexit.register(cleanup_temp_files)

# ===== LLM Backend =====
LLM_BACKEND = "ollama"  # Options: "claude", "ollama"

# Ollama config (only used when LLM_BACKEND="ollama")
OLLAMA_MODEL = "qwen2.5:1.5b"  # Ollama model (use qwen2.5:7b for smarter but slower)
OLLAMA_BASE_URL = "http://localhost:11434"  # Ollama server URL

# ===== Conversation Memory =====
MAX_HISTORY = 10  # Max conversation turns to keep (each turn = user + assistant)
CLEAR_HISTORY_KEYWORDS = [
    "clear history",
    "start over",
    "forget everything",
    "清空对话",
    "重新开始",
]  # Keywords to trigger history clear

# ===== Basic Config =====
SAMPLE_RATE = 16000
ASR_MODEL = "iic/SenseVoiceSmall"  # SenseVoice model
USE_STREAMING = True  # Stream output (speak while generating)

# ===== TTS Backend =====
TTS_BACKEND = "edge"  # Options: "edge" (online, high quality), "piper" (offline, fast)
TTS_RATE = "+0%"  # Speed for Edge TTS: negative=slower, positive=faster, 0%=normal

# ===== Edge TTS Voices (online, auto-selected based on detected language) =====
DEFAULT_LANGUAGE = "zh"
EDGE_TTS_VOICES = {
    "zh": "zh-CN-XiaoyiNeural",  # Chinese female
    "en": "en-US-JennyNeural",  # English female
    "ja": "ja-JP-NanamiNeural",  # Japanese female
    "ko": "ko-KR-SunHiNeural",  # Korean female
    "yue": "zh-HK-HiuGaaiNeural",  # Cantonese female
}

# ===== Piper TTS Config (offline) =====
# Models are stored in ~/.local/share/piper-voices/
# Download from: https://huggingface.co/rhasspy/piper-voices/tree/main
PIPER_VOICES = {
    "zh": "zh_CN-huayan-medium",  # Chinese female
    "en": "en_US-amy-medium",  # English female
}
PIPER_DATA_DIR = os.path.expanduser("~/.local/share/piper-voices")

# ===== VAD Config =====
VAD_THRESHOLD = 0.7  # Voice detection threshold - increased to avoid echo detection
VAD_CONSECUTIVE_THRESHOLD = (
    8  # Consecutive detections to confirm speech start - increased for robustness
)
VAD_PRE_BUFFER = 0.3  # Pre-buffer duration (seconds) to capture speech start
MIN_SPEECH_DURATION = 0.4  # Minimum speech duration (seconds) - increased
SILENCE_AFTER_SPEECH = 0.8  # Silence duration to stop recording (seconds)
MAX_RECORDING_DURATION = 30  # Maximum recording duration (seconds)
INTERRUPT_CHECK_DURATION = 1.5  # Duration to check for speech continuation after pause (seconds)

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


class VoiceAssistant:
    def __init__(self):
        self.asr_model = None
        self.vad_model = None
        self.llm_backend = None
        self.piper_voices = {}  # Cache for loaded Piper voices
        self.was_interrupted = False  # Track if last playback was interrupted
        self.mode_manager = ModeManager(RecordingMode.CONTINUOUS)  # 默认自由对话模式
        self.interrupt_audio_buffer = []  # Buffer for interrupt audio

    def load_asr(self):
        if self.asr_model is None:
            set_component("ASR"); logger.info("model_loading", model="SenseVoice")
            from funasr import AutoModel

            self.asr_model = AutoModel(model=ASR_MODEL, device="cpu")
            logger.info("model_loaded", model="SenseVoice")
        return self.asr_model

    def load_vad(self):
        if self.vad_model is None:
            set_component("VAD"); logger.info("model_loading", model="VAD")
            # Security note: trust_repo=True is required for official Silero VAD model
            # This is a verified, official PyTorch Hub repository
            self.vad_model, _ = torch.hub.load(  # nosec B614
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            logger.info("model_loaded", model="VAD")
        return self.vad_model

    def load_llm(self):
        if self.llm_backend is None:
            set_component("LLM"); logger.info("backend_initializing", backend=LLM_BACKEND)
            if LLM_BACKEND == "ollama":
                self.llm_backend = create_backend(
                    LLM_BACKEND,
                    SYSTEM_PROMPT,
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_BASE_URL,
                    max_history=MAX_HISTORY,
                )
            else:
                self.llm_backend = create_backend(
                    LLM_BACKEND, SYSTEM_PROMPT, max_history=MAX_HISTORY
                )
            logger.info("backend_initialized")
        return self.llm_backend

    def load_piper_voice(self, language):
        """Load Piper voice model for specified language."""
        if language in self.piper_voices:
            return self.piper_voices[language]

        voice_name = PIPER_VOICES.get(language, PIPER_VOICES.get("en"))
        model_path = os.path.join(PIPER_DATA_DIR, f"{voice_name}.onnx")

        if not os.path.exists(model_path):
            logger.warning(
                "piper_model_not_found",
                model_path=model_path,
                download_url="https://huggingface.co/rhasspy/piper-voices/tree/main"
            )
            return None

        try:
            from piper.voice import PiperVoice

            set_component("TTS"); logger.info("piper_voice_loading", voice=voice_name)
            voice = PiperVoice.load(model_path)
            self.piper_voices[language] = voice
            logger.info("piper_voice_loaded")
            return voice
        except ImportError:
            logger.warning("piper_not_installed", install_command="pip install piper-tts")
            return None
        except Exception as e:
            logger.error("piper_voice_load_failed", error=str(e))
            return None

    def record_with_vad(self, speech_already_started=False):
        """Use VAD to detect speech, auto start and stop recording.

        Args:
            speech_already_started: If True, skip waiting for speech to begin and start recording immediately.
                                   Used when user interrupts TTS (barge-in).
        """
        model = self.load_vad()
        model.reset_states()  # Reset VAD state

        # Show history count
        history_count = 0
        if self.llm_backend and hasattr(self.llm_backend, "history"):
            history_count = len(self.llm_backend.history) // 2

        if speech_already_started:
            logger.info("recording_started", mode="interrupted")
        elif history_count > 0:
            logger.info("listening", history_count=history_count)
        else:
            logger.info("listening")

        chunk_size = 512  # Silero VAD requires 512 samples @ 16kHz
        frames = []

        # Use captured audio from interrupt if available
        if speech_already_started and self.interrupt_audio_buffer:
            frames = self.interrupt_audio_buffer.copy()
            self.interrupt_audio_buffer = []  # Clear the buffer
            logger.debug("audio_buffer_used", chunks=len(frames))

        is_speaking = speech_already_started  # Start in speaking mode if interrupted
        silence_chunks = 0
        speech_chunks = len(frames)  # Count buffered frames as speech
        consecutive_speech = VAD_CONSECUTIVE_THRESHOLD if speech_already_started else 0
        max_silence_chunks = int(SILENCE_AFTER_SPEECH * SAMPLE_RATE / chunk_size)
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / chunk_size)
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / chunk_size)

        # Pre-buffer: keep audio before speech starts to avoid clipping
        pre_buffer_size = int(VAD_PRE_BUFFER * SAMPLE_RATE / chunk_size)
        pre_buffer = deque(maxlen=pre_buffer_size)

        recording_done = False

        def callback(indata, frame_count, time_info, status):
            nonlocal is_speaking, silence_chunks, speech_chunks, consecutive_speech, recording_done

            if recording_done:
                return

            try:
                audio_chunk = indata[:, 0].copy()

                # VAD detection
                audio_tensor = torch.from_numpy(audio_chunk).float()
                speech_prob = model(audio_tensor, SAMPLE_RATE).item()

                if speech_prob > VAD_THRESHOLD:
                    # Speech detected
                    consecutive_speech += 1

                    if not is_speaking and consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                        is_speaking = True
                        # Add pre-buffer to frames to avoid clipping speech start
                        frames.extend(pre_buffer)
                        pre_buffer.clear()
                        logger.info("speech_detected")

                    if is_speaking:
                        # Only reset silence count on consecutive speech
                        if consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                            silence_chunks = 0
                        speech_chunks += 1
                        frames.append(audio_chunk)
                    else:
                        # Not confirmed speaking yet, fill pre-buffer
                        pre_buffer.append(audio_chunk)
                else:
                    # Silence
                    consecutive_speech = 0  # Reset consecutive speech count

                    if is_speaking:
                        frames.append(audio_chunk)
                        silence_chunks += 1

                        # Stop recording after enough silence
                        if (
                            silence_chunks >= max_silence_chunks
                            and speech_chunks >= min_speech_chunks
                        ):
                            recording_done = True
                            logger.info("speech_ended")
                    else:
                        # Not speaking yet, fill pre-buffer
                        pre_buffer.append(audio_chunk)

                # Max duration reached
                if len(frames) >= max_chunks:
                    recording_done = True
                    logger.warning("max_recording_duration")

            except Exception as e:
                logger.error("vad_error", error=str(e))
                recording_done = True

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            blocksize=chunk_size,
            callback=callback,
        ):
            while not recording_done:
                sd.sleep(50)

        if not frames or speech_chunks < min_speech_chunks:
            return None

        audio = np.concatenate(frames)
        logger.info("recording_complete", duration=len(audio) / SAMPLE_RATE)
        return audio

    def record_push_to_talk(self):
        """
        按键录音模式：手动控制录音开始和结束
        通过 mode_manager.start_recording() 和 stop_recording() 控制
        """
        logger.info("ptt_mode_activated")

        chunk_size = 512
        frames = []

        def callback(indata, frame_count, time_info, status):
            # 只有在录音状态时才记录音频
            if self.mode_manager.is_recording:
                audio_chunk = indata[:, 0].copy()
                frames.append(audio_chunk)

        # 启动音频流
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            callback=callback,
        ):
            # 等待开始录音
            while not self.mode_manager.is_recording:
                sd.sleep(50)

            # 录音中
            while self.mode_manager.is_recording:
                sd.sleep(50)

        # 检查是否有录音数据
        if not frames:
            logger.warning("no_audio_data")
            return None

        audio = np.concatenate(frames)
        logger.info("ptt_recording_complete", duration=len(audio) / SAMPLE_RATE)
        return audio

    def transcribe(self, audio):
        """Transcribe audio and detect language. Returns (text, language)."""
        set_component("ASR"); logger.info("asr_processing")
        model = self.load_asr()

        # Security: Use secure temp file
        tmp_file = create_secure_temp_file(suffix=".wav")

        try:
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(tmp_file, SAMPLE_RATE, audio_int16)
            result = model.generate(input=tmp_file)
            raw_text = result[0]["text"] if result else ""
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

        # Extract language from SenseVoice tags like <|zh|>, <|en|>, <|yue|>
        lang_match = re.search(r"<\|(zh|en|ja|ko|yue)\|>", raw_text)
        language = lang_match.group(1) if lang_match else DEFAULT_LANGUAGE

        # Clean all tags from text
        text = re.sub(r"<\|[^|]+\|>", "", raw_text).strip()

        logger.info("asr_result", language=language, text=text)
        return text, language

    def detect_speech_start(self, timeout=1.5):
        """Check if speech starts within timeout. Returns True if speech detected."""
        model = self.load_vad()
        model.reset_states()

        chunk_size = 512
        speech_detected = False
        consecutive_speech = 0
        check_done = False

        def callback(indata, frame_count, time_info, status):
            nonlocal speech_detected, consecutive_speech, check_done

            if check_done:
                return

            try:
                audio_chunk = indata[:, 0].copy()
                audio_tensor = torch.from_numpy(audio_chunk).float()
                speech_prob = model(audio_tensor, SAMPLE_RATE).item()

                if speech_prob > VAD_THRESHOLD:
                    consecutive_speech += 1
                    if consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                        speech_detected = True
                        check_done = True
                else:
                    consecutive_speech = 0
            except Exception:
                pass

        timeout_ms = int(timeout * 1000)
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            blocksize=chunk_size,
            callback=callback,
        ):
            elapsed = 0
            while not check_done and elapsed < timeout_ms:
                sd.sleep(50)
                elapsed += 50

        return speech_detected

    async def transcribe_async(self, audio):
        """Async wrapper for transcribe using thread executor."""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(executor, self.transcribe, audio)
        return result

    async def record_with_interruption(self):
        """Record with support for interruption - if user continues speaking, keep recording."""
        all_segments = []

        # Check if we're coming from a barge-in interrupt
        speech_already_started = self.was_interrupted
        self.was_interrupted = False  # Reset the flag

        while True:
            # Record a segment
            segment = self.record_with_vad(speech_already_started=speech_already_started)
            speech_already_started = False  # Only applies to first segment

            if segment is None:
                # No speech detected
                if not all_segments:
                    return None, None
                break

            all_segments.append(segment)

            # Start ASR in background
            combined_audio = np.concatenate(all_segments)
            asr_task = asyncio.create_task(self.transcribe_async(combined_audio))

            # Check if user wants to continue speaking
            logger.info("waiting_for_input")

            # Run speech detection in executor (it's blocking)
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                has_more_speech = await loop.run_in_executor(
                    executor, self.detect_speech_start, INTERRUPT_CHECK_DURATION
                )

            if has_more_speech:
                # User is continuing, cancel ASR and keep recording
                asr_task.cancel()
                try:
                    await asr_task
                except asyncio.CancelledError:
                    pass
                logger.info("recording_continued")
                continue
            else:
                # No more speech, wait for ASR result
                try:
                    text, language = await asr_task
                    return text, language
                except asyncio.CancelledError:
                    break

        # Final transcription if we have segments but exited loop
        if all_segments:
            combined_audio = np.concatenate(all_segments)
            return self.transcribe(combined_audio)

        return None, None

    def detect_text_language(self, text):
        """Detect language from text content using character analysis."""
        # Count character types
        cjk_count = 0
        ja_specific = 0
        ko_specific = 0
        latin_count = 0

        for char in text:
            code = ord(char)
            # CJK Unified Ideographs (Chinese/Japanese/Korean shared)
            if 0x4E00 <= code <= 0x9FFF:
                cjk_count += 1
            # Hiragana/Katakana (Japanese specific)
            elif 0x3040 <= code <= 0x30FF:
                ja_specific += 1
            # Hangul (Korean specific)
            elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
                ko_specific += 1
            # Basic Latin letters
            elif 0x0041 <= code <= 0x007A:
                latin_count += 1

        total = len(text.replace(" ", ""))
        if total == 0:
            return DEFAULT_LANGUAGE

        # Japanese has hiragana/katakana
        if ja_specific > 0:
            return "ja"
        # Korean has hangul
        if ko_specific > 0:
            return "ko"
        # Chinese if mostly CJK
        if cjk_count > latin_count:
            return "zh"
        # Default to English for Latin text
        if latin_count > 0:
            return "en"

        return DEFAULT_LANGUAGE

    async def generate_audio(self, text, language=None):
        """Generate TTS audio file, returns file path."""
        # Auto-detect language from text content for better TTS matching
        detected_lang = self.detect_text_language(text)

        if TTS_BACKEND == "piper":
            return await self._generate_audio_piper(text, detected_lang)
        else:
            return await self._generate_audio_edge(text, detected_lang)

    async def _generate_audio_edge(self, text, language):
        """Generate audio using Edge TTS (online)."""
        try:
            voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICES[DEFAULT_LANGUAGE])
            # Security: Use secure temp file
            tmp_file = create_secure_temp_file(suffix=".mp3")
            communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE)
            await communicate.save(tmp_file)
            return tmp_file
        except Exception as e:
            logger.error("edge_tts_error", error=str(e))
            return None

    async def _generate_audio_piper(self, text, language):
        """Generate audio using Piper TTS (offline)."""
        try:
            voice = self.load_piper_voice(language)
            if voice is None:
                # Fallback to Edge TTS if Piper not available
                logger.info("fallback_to_edge_tts")
                return await self._generate_audio_edge(text, language)

            # Security: Use secure temp file
            tmp_file = create_secure_temp_file(suffix=".wav")

            # Run Piper synthesis in executor (it's blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._piper_synthesize, voice, text, tmp_file)
            return tmp_file
        except Exception as e:
            logger.error("piper_tts_error", error=str(e))
            # Fallback to Edge TTS
            return await self._generate_audio_edge(text, language)

    def _piper_synthesize(self, voice, text, output_path):
        """Synchronous Piper synthesis."""
        import wave

        with wave.open(output_path, "w") as wav_file:
            voice.synthesize(text, wav_file)

    async def play_audio(self, tmp_file, delete=True):
        """Play audio file (async, cross-platform), optionally delete after."""
        if tmp_file and os.path.exists(tmp_file):
            try:
                system = platform.system()
                if system == "Darwin":  # macOS
                    cmd = ["afplay", tmp_file]
                elif system == "Linux":
                    cmd = [
                        "ffplay",
                        "-nodisp",
                        "-autoexit",
                        "-loglevel",
                        "quiet",
                        tmp_file,
                    ]
                elif system == "Windows":
                    cmd = [
                        "powershell",
                        "-c",
                        f"(New-Object Media.SoundPlayer '{tmp_file}').PlaySync()",
                    ]
                else:
                    logger.warning("unsupported_platform", platform=system)
                    return

                process = await asyncio.create_subprocess_exec(*cmd)
                await process.wait()
            finally:
                if delete:
                    os.remove(tmp_file)

    def load_audio_file(self, file_path):
        """Load audio file and return numpy array at SAMPLE_RATE.
        Supports WAV and MP3 formats.
        """
        import subprocess

        from scipy.io.wavfile import read as read_wav

        if file_path.endswith(".wav"):
            sr, audio = read_wav(file_path)
            # Convert to float32
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype == np.int32:
                audio = audio.astype(np.float32) / 2147483648.0
        else:
            # Use ffmpeg to convert MP3 to WAV
            # Security: Use secure temp file
            tmp_wav = create_secure_temp_file(suffix=".wav")
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        file_path,
                        "-ar",
                        str(SAMPLE_RATE),
                        "-ac",
                        "1",
                        "-f",
                        "wav",
                        tmp_wav,
                    ],
                    capture_output=True,
                    check=True,
                )
                sr, audio = read_wav(tmp_wav)
                if audio.dtype == np.int16:
                    audio = audio.astype(np.float32) / 32768.0
            finally:
                if os.path.exists(tmp_wav):
                    os.remove(tmp_wav)

        # Resample if needed
        if sr != SAMPLE_RATE:
            from scipy import signal

            audio = signal.resample(audio, int(len(audio) * SAMPLE_RATE / sr))

        return audio.astype(np.float32)

    async def play_audio_with_barge_in(self, tmp_file, delete=True):
        """Play audio with barge-in support (placeholder for future implementation).

        TODO: Implement key-based interruption (e.g., SPACE key)
        Currently plays audio without interruption support.
        """
        if not tmp_file or not os.path.exists(tmp_file):
            return False

        # Simple playback without interruption for now
        # TODO: Add async interruption via keyboard listener
        await self.play_audio(tmp_file, delete)

        return False  # Never interrupted in current implementation

    async def speak(self, text, language=None):
        """TTS speak a single sentence."""
        tmp_file = await self.generate_audio(text, language)
        await self.play_audio(tmp_file)

    async def chat_once(self):
        """Single conversation turn"""
        from resource_limiter import with_timeout

        # VAD 录音操作添加 30 秒超时保护
        try:
            text, language = await with_timeout(
                self.record_with_interruption(), seconds=30, operation_name="VAD_recording"
            )
        except TimeoutError:
            logger.error("vad_timeout", timeout_seconds=30)
            return False

        if text is None:
            return False  # No valid speech detected

        if not text:
            logger.warning("no_speech_recognized")
            return True

        backend = self.load_llm()

        # Check if user wants to clear history
        for keyword in CLEAR_HISTORY_KEYWORDS:
            if keyword in text:
                backend.clear_history()
                # Respond in detected language
                clear_messages = {
                    "zh": "好的，已清空对话记录，重新开始。",
                    "en": "OK, conversation cleared. Let's start fresh.",
                    "ja": "会話履歴をクリアしました。",
                    "ko": "대화 기록을 지웠습니다.",
                    "yue": "好，已清空對話記錄。",
                }
                msg = clear_messages.get(language, clear_messages["en"])
                await self.speak(msg, language)
                return True

        if USE_STREAMING:
            # Streaming output with barge-in support
            logger.info("streaming_started")
            audio_queue = asyncio.Queue()
            interrupted = False
            generation_done = False

            async def generate_worker():
                nonlocal generation_done
                try:
                    async for sentence in backend.chat_stream(text):
                        if interrupted:
                            break
                        if sentence:
                            # TTS 生成添加 30 秒超时保护
                            try:
                                audio_file = await with_timeout(
                                    self.generate_audio(sentence, language),
                                    seconds=30,
                                    operation_name="TTS_streaming",
                                )
                                if audio_file:
                                    await audio_queue.put(audio_file)
                            except TimeoutError:
                                logger.error("tts_streaming_timeout", timeout_seconds=30)
                                # 继续处理下一句，不中断整个流
                                continue
                finally:
                    generation_done = True
                    await audio_queue.put(None)

            async def play_worker():
                nonlocal interrupted
                while True:
                    audio_file = await audio_queue.get()
                    if audio_file is None:
                        break
                    if interrupted:
                        # Clean up remaining audio files
                        if os.path.exists(audio_file):
                            os.remove(audio_file)
                        continue
                    # Play audio without interruption
                    was_interrupted = await self.play_audio_with_barge_in(audio_file)
                    if was_interrupted:
                        interrupted = True
                        # Drain remaining queue
                        while not audio_queue.empty():
                            try:
                                remaining = audio_queue.get_nowait()
                                if remaining and os.path.exists(remaining):
                                    os.remove(remaining)
                            except asyncio.QueueEmpty:
                                break
                        break

            await asyncio.gather(generate_worker(), play_worker())

            if interrupted:
                # User interrupted, set flag for immediate recording
                self.was_interrupted = True
                return True
        else:
            # Non-streaming output (without barge-in)
            # LLM 对话添加 120 秒超时保护
            try:
                response = await with_timeout(
                    asyncio.to_thread(backend.chat, text),
                    seconds=120,
                    operation_name="LLM_chat",
                )
            except TimeoutError:
                logger.error("llm_timeout", timeout_seconds=120)
                return False

            # TTS 生成添加 30 秒超时保护
            try:
                tmp_file = await with_timeout(
                    self.generate_audio(response, language),
                    seconds=30,
                    operation_name="TTS_generation",
                )
            except TimeoutError:
                logger.error("tts_timeout", timeout_seconds=30)
                return False

            if tmp_file:
                was_interrupted = await self.play_audio_with_barge_in(tmp_file)
                if was_interrupted:
                    self.was_interrupted = True
                    return True

        return True

    async def run(self):
        logger.info("speekium_banner", mode="continuous")
        logger.info("vad_enabled")
        llm_info = LLM_BACKEND
        if LLM_BACKEND == "ollama":
            llm_info = f"ollama ({OLLAMA_MODEL})"
        logger.info("llm_backend_info", backend=llm_info)
        tts_info = TTS_BACKEND
        if TTS_BACKEND == "piper":
            tts_info = "piper (offline)"
        else:
            tts_info = "edge (online)"
        logger.info("tts_backend_info", backend=tts_info)
        if USE_STREAMING:
            logger.info("streaming_mode_enabled")
        logger.info("memory_config", max_history=MAX_HISTORY)
        logger.info("clear_history_hint")
        logger.info("exit_hint")
        
        # Preload models
        self.load_vad()
        self.load_asr()
        self.load_llm()

        logger.info("ready_for_input")

        try:
            while True:
                await self.chat_once()
                # Brief delay before next round (skip if interrupted for faster response)
                if not self.was_interrupted:
                    await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            logger.info("shutdown")


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    # 设置资源限制（防止资源耗尽攻击）
    from resource_limiter import initialize_resource_limits

    initialize_resource_limits()

    # 运行主程序
    asyncio.run(main())
