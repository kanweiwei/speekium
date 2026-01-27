"""
VoiceAssistant - Main voice conversation orchestrator.

Integrates VAD, ASR, LLM, and TTS modules for natural voice interaction.
Flow: [VAD voice detection] → Record → SenseVoice ASR → LLM streaming → TTS playback
"""

import asyncio
import os
import platform
import sys
import threading
from typing import TYPE_CHECKING, Any

import edge_tts

from logger import get_logger
from mode_manager import ModeManager, RecordingMode
from speekium.models import (
    INITIAL_SPEECH_TIMEOUT,
    SAMPLE_RATE,
    check_asr_model_exists,
    check_vad_model_exists,
    create_llm_backend,
    get_asr_model_status,
    get_clear_history_message,
    get_vad_model_status,
    load_asr,
    load_llm_config,
    load_vad,
    load_vad_config,
)
from speekium.models.llm import CLEAR_HISTORY_KEYWORDS
from speekium.recording import detect_speech_start, record_push_to_talk, record_with_vad
from speekium.utils import create_secure_temp_file

if TYPE_CHECKING:
    import numpy as np

logger = get_logger(__name__)

# ===== TTS Config =====
TTS_BACKEND = "edge"  # Default fallback
TTS_RATE = "+0%"  # Speed for Edge TTS

# ===== Edge TTS Voices =====
EDGE_TTS_VOICES = {
    "zh": "zh-CN-XiaoyiNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "yue": "zh-HK-HiuGaaiNeural",
}

# ===== Streaming Config =====
USE_STREAMING = True


class VoiceAssistant:
    """Main voice assistant class that orchestrates all components."""

    def __init__(self):
        # Model instances
        self.asr_model = None
        self.vad_model = None
        self.llm_backend = None

        # State tracking
        self.was_interrupted = False
        self.is_generating_tts = False
        self.interrupt_audio_buffer: list = []

        # Mode management
        self.mode_manager = ModeManager(RecordingMode.CONTINUOUS)
        self.recording_interrupt_event = threading.Event()

        # Configuration
        self.tts_backend = None
        self._last_llm_config: dict = {}
        self._vad_config: dict = {}

        # Load configurations
        self._load_tts_config()
        self._load_vad_config()

    def _load_vad_config(self):
        """Load VAD configuration from config file."""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
            self._vad_config = load_vad_config(config)
            logger.info(
                "vad_config_loaded",
                threshold=self._vad_config["threshold"],
                consecutive=self._vad_config["consecutive_threshold"],
                silence=self._vad_config["silence_duration"],
            )
        except Exception as e:
            logger.warning("vad_config_load_failed", error=str(e), fallback="default")
            self._vad_config = load_vad_config()

    def _load_tts_config(self):
        """Load TTS backend and rate from config file."""
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
            self.tts_backend = config.get("tts_backend", "edge")
            global TTS_RATE
            TTS_RATE = config.get("tts_rate", "+0%")  # type: ignore
            logger.info("tts_config_loaded", backend=self.tts_backend, rate=TTS_RATE)
        except Exception as e:
            logger.warning("tts_config_load_failed", error=str(e), fallback="edge")
            self.tts_backend = "edge"

    def get_tts_backend(self):
        """Get current TTS backend from config (refreshes on each call)."""
        self._load_tts_config()
        return self.tts_backend

    def get_model_status(self) -> dict:
        """Get status information for all models."""
        asr_status = get_asr_model_status(self.asr_model)
        vad_status = get_vad_model_status(self.vad_model)

        return {
            "asr": asr_status,
            "vad": vad_status,
        }

    # ===== Model Loading =====

    def load_vad(self):
        """Load or return cached VAD model."""
        if self.vad_model is None:
            self.vad_model = load_vad(self.vad_model)
        return self.vad_model

    def load_asr(self):
        """Load or return cached ASR model."""
        if self.asr_model is None:
            self.asr_model = load_asr(self.asr_model)
        return self.asr_model

    def load_llm(self):
        """Load or create LLM backend."""
        # Always reload configuration to get latest settings
        config = load_llm_config()
        self.llm_backend, self._last_llm_config = create_llm_backend(
            self.llm_backend, self._last_llm_config, config
        )
        return self.llm_backend

    # ===== Recording =====

    def record_with_vad(
        self,
        speech_already_started: bool = False,
        on_speech_detected=None,
    ):
        """Use VAD to detect speech, auto start and stop recording.

        Args:
            speech_already_started: If True, skip waiting for speech
            on_speech_detected: Optional callback when speech is detected
        """
        vad_model = self.load_vad()

        # Show history count
        history_count = 0
        if self.llm_backend and hasattr(self.llm_backend, "history"):
            history_count = len(getattr(self.llm_backend, "history", [])) // 2

        if speech_already_started:
            logger.info("recording_started", mode="interrupted")
        elif history_count > 0:
            logger.info("listening", history_count=history_count)
        else:
            logger.info("listening")

        return record_with_vad(
            vad_model=vad_model,
            vad_threshold=self._vad_config["threshold"],
            vad_consecutive_threshold=self._vad_config["consecutive_threshold"],
            vad_silence_duration=self._vad_config["silence_duration"],
            vad_pre_buffer=self._vad_config["pre_buffer"],
            vad_min_speech_duration=self._vad_config["min_speech_duration"],
            vad_max_recording_duration=self._vad_config["max_recording_duration"],
            initial_speech_timeout=INITIAL_SPEECH_TIMEOUT,
            sample_rate=SAMPLE_RATE,
            recording_interrupt_event=self.recording_interrupt_event,
            is_generating_tts=self.is_generating_tts,
            speech_already_started=speech_already_started,
            on_speech_detected=on_speech_detected,
            interrupt_audio_buffer=self.interrupt_audio_buffer,
        )

    def record_push_to_talk(self):
        """Push-to-talk mode: manually control recording start and stop."""
        return record_push_to_talk(self.mode_manager, SAMPLE_RATE)

    def detect_speech_start(self, timeout: float = 1.5) -> bool:
        """Check if speech starts within timeout."""
        vad_model = self.load_vad()
        return detect_speech_start(
            vad_model,
            self._vad_config["threshold"],
            self._vad_config["consecutive_threshold"],
            SAMPLE_RATE,
            timeout,
        )

    # ===== Transcription =====

    def transcribe(self, audio: "np.ndarray"):
        """Transcribe audio and detect language. Returns (text, language)."""
        from speekium.models import transcribe

        asr_model = self.load_asr()
        return transcribe(asr_model, audio, SAMPLE_RATE)

    async def transcribe_async(self, audio: "np.ndarray"):
        """Async wrapper for transcribe."""
        from speekium.models import transcribe_async

        asr_model = self.load_asr()
        return await transcribe_async(asr_model, audio, SAMPLE_RATE)

    async def record_with_interruption(self):
        """Record with support for continuation detection."""
        all_segments = []

        # Check if we're coming from a barge-in interrupt
        speech_already_started = self.was_interrupted
        self.was_interrupted = False

        while True:
            # Record a segment
            segment = self.record_with_vad(speech_already_started=speech_already_started)
            speech_already_started = False

            if segment is None:
                if not all_segments:
                    return None, None
                break

            all_segments.append(segment)

            # Start ASR in background
            import numpy as np

            combined_audio = np.concatenate(all_segments)
            asr_task = asyncio.create_task(self.transcribe_async(combined_audio))

            # Check if user wants to continue speaking
            logger.info("waiting_for_input")

            has_more_speech = await asyncio.get_event_loop().run_in_executor(
                None, self.detect_speech_start, 1.5
            )

            if has_more_speech:
                asr_task.cancel()
                try:
                    await asr_task
                except asyncio.CancelledError:
                    pass
                logger.info("recording_continued")
                continue
            else:
                try:
                    text, language = await asr_task
                    return text, language
                except asyncio.CancelledError:
                    break

        if all_segments:
            import numpy as np

            combined_audio = np.concatenate(all_segments)
            return self.transcribe(combined_audio)

        return None, None

    # ===== TTS =====

    async def generate_audio(self, text: str, language: str | None = None):
        """Generate TTS audio file, returns file path."""
        from speekium.models import detect_text_language

        detected_lang = detect_text_language(text)
        return await self._generate_audio_edge(text, detected_lang)

    async def _generate_audio_edge(self, text: str, language: str):
        """Generate audio using Edge TTS (online)."""
        try:
            voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICES["zh"])
            tmp_file = create_secure_temp_file(suffix=".mp3")
            communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE)
            await communicate.save(tmp_file)
            return tmp_file
        except Exception as e:
            logger.error("edge_tts_error", error=str(e))
            return None

    async def play_audio(self, tmp_file: str, delete: bool = True):
        """Play audio file (async, cross-platform), optionally delete after."""
        if tmp_file and os.path.exists(tmp_file):
            try:
                system = platform.system()
                if system == "Darwin":  # macOS
                    cmd = ["afplay", tmp_file]
                elif system == "Linux":
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_file]
                elif system == "Windows":
                    player_cmd = f"(New-Object Media.SoundPlayer '{tmp_file}').PlaySync()"
                    cmd = ["powershell", "-c", player_cmd]
                else:
                    logger.warning("unsupported_platform", platform=system)
                    return

                process = await asyncio.create_subprocess_exec(*cmd)
                await process.wait()
            finally:
                if delete:
                    os.remove(tmp_file)

    async def play_audio_with_barge_in(self, tmp_file: str, delete: bool = True) -> bool:
        """Play audio with barge-in support (placeholder)."""
        if not tmp_file or not os.path.exists(tmp_file):
            return False

        await self.play_audio(tmp_file, delete)
        return False  # Never interrupted in current implementation

    async def speak(self, text: str, language: str | None = None):
        """TTS speak a single sentence."""
        tmp_file: str | None = await self.generate_audio(text, language)
        if tmp_file:
            await self.play_audio(tmp_file)

    # ===== Main Conversation Loop =====

    async def chat_once(self) -> bool:
        """Single conversation turn."""
        from resource_limiter import with_timeout

        # VAD recording with 30s timeout
        try:
            text, language = await with_timeout(
                self.record_with_interruption(), seconds=30, operation_name="VAD_recording"
            )
        except TimeoutError:
            logger.error("vad_timeout", timeout_seconds=30)
            return False

        if text is None:
            return False

        if not text:
            logger.warning("no_speech_recognized")
            return True

        backend = self.load_llm()

        # Check for clear history keywords
        for keyword in CLEAR_HISTORY_KEYWORDS:
            if keyword in text:
                clear_history_method = getattr(backend, "clear_history", None)
                if clear_history_method:
                    clear_history_method()
                msg = get_clear_history_message(language)
                await self.speak(msg, language)
                return True

        if USE_STREAMING:
            return await self._chat_streaming(backend, text, language)
        else:
            return await self._chat_non_streaming(backend, text, language)

    async def _chat_streaming(self, backend, text: str, language: str) -> bool:
        """Streaming chat with barge-in support."""
        from resource_limiter import with_timeout

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
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                    continue
                was_interrupted = await self.play_audio_with_barge_in(audio_file)
                if was_interrupted:
                    interrupted = True
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
            self.was_interrupted = True
            return True

        return True

    async def _chat_non_streaming(self, backend, text: str, language: str) -> bool:
        """Non-streaming chat."""
        from resource_limiter import with_timeout

        try:
            response = await with_timeout(
                asyncio.to_thread(backend.chat, text),
                seconds=120,
                operation_name="LLM_chat",
            )
        except TimeoutError:
            logger.error("llm_timeout", timeout_seconds=120)
            return False

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
        """Main run loop."""
        from speekium.models import LLM_BACKEND

        logger.info("speekium_banner", mode="continuous")
        logger.info("vad_enabled")
        logger.info("llm_backend_info", backend=LLM_BACKEND)

        tts_backend = self.get_tts_backend()
        tts_info = tts_backend if tts_backend == "piper" else "edge (online)"
        logger.info("tts_backend_info", backend=tts_info)

        if USE_STREAMING:
            logger.info("streaming_mode_enabled")
        logger.info("memory_config", max_history=10)
        logger.info("clear_history_hint")
        logger.info("exit_hint")

        # Show model status
        print(f"\n{'=' * 60}", file=sys.stderr)
        print("🔍 Checking model status...", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

        asr_exists, asr_path = check_asr_model_exists()
        vad_exists, vad_path = check_vad_model_exists()

        print(
            f"ASR model: {'✅ Downloaded' if asr_exists else '❌ Not downloaded'}",
            file=sys.stderr,
        )
        if asr_exists:
            print(f"  Path: {asr_path}", file=sys.stderr)

        print(
            f"VAD model: {'✅ Downloaded' if vad_exists else '❌ Not downloaded'}",
            file=sys.stderr,
        )
        if vad_exists:
            print(f"  Path: {vad_path}", file=sys.stderr)

        print(f"{'=' * 60}\n", file=sys.stderr)

        # Preload models
        self.load_vad()
        self.load_asr()
        self.load_llm()

        logger.info("ready_for_input")

        try:
            while True:
                await self.chat_once()
                if not self.was_interrupted:
                    await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("shutdown")


async def main():
    """Entry point for voice assistant."""
    assistant = VoiceAssistant()
    await assistant.run()
