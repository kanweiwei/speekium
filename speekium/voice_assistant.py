"""
VoiceAssistant - Main voice conversation orchestrator.

Refactored to use the service layer for clean separation of concerns.
Flow: [VAD voice detection] → Record → ASR → LLM streaming → TTS playback
"""

import asyncio
import os
import platform
import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

import edge_tts

from logger import get_logger
from mode_manager import ModeManager, RecordingMode
from speekium.models import INITIAL_SPEECH_TIMEOUT, SAMPLE_RATE
from speekium.recording import detect_speech_start, record_push_to_talk, record_with_vad
from speekium.services import ServiceContainer
from speekium.services.base import ProgressEvent
from speekium.utils import create_secure_temp_file

if TYPE_CHECKING:
    import numpy as np

logger = get_logger(__name__)

# ===== TTS Config =====
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
    """
    Main voice assistant class that orchestrates all components.

    Refactored to use the service layer for:
    - Model management (ASR, LLM, VAD, TTS)
    - Configuration management
    - Progress reporting
    """

    def __init__(
        self,
        container: Optional[ServiceContainer] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        """
        Initialize the voice assistant.

        Args:
            container: Optional service container (creates new one if None)
            progress_callback: Optional callback for progress events
        """
        self.container = container
        self._own_container = container is None

        # State tracking
        self.was_interrupted = False
        self.is_generating_tts = False
        self.interrupt_audio_buffer: list = []

        # Mode management
        self.mode_manager = ModeManager(RecordingMode.CONTINUOUS)
        self.recording_interrupt_event = asyncio.Event()

        # TTS configuration (cached for performance)
        self._tts_rate = "+0%"

        # Progress callback for model downloads
        self._progress_callback = progress_callback

    async def _ensure_container(self) -> ServiceContainer:
        """Ensure service container is initialized."""
        if self.container is None:
            self.container = ServiceContainer(
                progress_callback=self._progress_callback,
            )
            self._own_container = True

        if not self.container.config.is_initialized:
            await self.container.initialize()

        return self.container

    async def start(self) -> None:
        """Start the voice assistant and all services."""
        container = await self._ensure_container()
        await container.start()

        # Preload models
        await container.vad.load_model()
        await container.asr.load_model()
        await container.llm._ensure_backend()

        logger.info("voice_assistant_started")

    async def stop(self) -> None:
        """Stop the voice assistant and all services."""
        if self.container:
            await self.container.stop()

        if self._own_container and self.container:
            await self.container.shutdown()
            self.container = None

        logger.info("voice_assistant_stopped")

    def get_model_status(self) -> dict:
        """Get status information for all models."""
        if not self.container:
            return {"asr": {"loaded": False}, "vad": {"loaded": False}}

        return {
            "asr": self._asr_status(),
            "vad": self._vad_status(),
        }

    async def _asr_status(self) -> dict:
        """Get ASR model status."""
        if self.container is None:
            return {"loaded": False}
        try:
            return await self.container.asr.get_model_status()
        except Exception:
            return {"loaded": False}

    async def _vad_status(self) -> dict:
        """Get VAD model status."""
        if self.container is None:
            return {"loaded": False}
        try:
            return await self.container.vad.get_model_status()
        except Exception:
            return {"loaded": False}

    # ===== Recording =====

    async def record_with_vad(
        self,
        speech_already_started: bool = False,
        on_speech_detected: Optional[Callable[[], None]] = None,
    ):
        """Use VAD to detect speech, auto start and stop recording.

        Args:
            speech_already_started: If True, skip waiting for speech
            on_speech_detected: Optional callback when speech is detected
        """
        container = await self._ensure_container()

        # Load VAD model
        vad_model = await container.vad.load_model()
        vad_config = await container.vad.get_config()

        # Show history count
        history_count = 0
        if container.llm.is_backend_loaded:
            history_count = len(container.llm.get_history()) // 2

        if speech_already_started:
            logger.info("recording_started", mode="interrupted")
        elif history_count > 0:
            logger.info("listening", history_count=history_count)
        else:
            logger.info("listening")

        return record_with_vad(
            vad_model=vad_model,
            vad_threshold=vad_config["threshold"],
            vad_consecutive_threshold=vad_config["consecutive_threshold"],
            vad_silence_duration=vad_config["silence_duration"],
            vad_pre_buffer=vad_config["pre_buffer"],
            vad_min_speech_duration=vad_config["min_speech_duration"],
            vad_max_recording_duration=vad_config["max_recording_duration"],
            initial_speech_timeout=INITIAL_SPEECH_TIMEOUT,
            sample_rate=SAMPLE_RATE,
            recording_interrupt_event=self.recording_interrupt_event,
            is_generating_tts=self.is_generating_tts,
            speech_already_started=speech_already_started,
            on_speech_detected=on_speech_detected,
            interrupt_audio_buffer=self.interrupt_audio_buffer,
        )

    async def record_push_to_talk(self) -> Optional["np.ndarray"]:
        """Push-to-talk mode: manually control recording start and stop."""
        return await asyncio.to_thread(record_push_to_talk, self.mode_manager, SAMPLE_RATE)

    async def detect_speech_start(self, timeout: float = 1.5) -> bool:
        """Check if speech starts within timeout."""
        container = await self._ensure_container()
        vad_model = await container.vad.load_model()
        vad_config = await container.vad.get_config()

        return await asyncio.to_thread(
            detect_speech_start,
            vad_model,
            vad_config["threshold"],
            vad_config["consecutive_threshold"],
            SAMPLE_RATE,
            timeout,
        )

    # ===== Transcription =====

    async def transcribe_async(self, audio: "np.ndarray") -> tuple[str, str]:
        """Transcribe audio and detect language. Returns (text, language)."""
        container = await self._ensure_container()
        result = await container.asr.transcribe(audio)

        if result.success:
            return result.text, result.language
        else:
            logger.error("transcription_failed", error=result.error)
            return "", "zh"

    # ===== Conversation Loop =====

    async def record_with_interruption(self) -> tuple[Optional[str], Optional[str]]:
        """Record with support for continuation detection."""
        all_segments = []

        # Check if we're coming from a barge-in interrupt
        speech_already_started = self.was_interrupted
        self.was_interrupted = False

        while True:
            # Record a segment
            segment = await self.record_with_vad(speech_already_started=speech_already_started)
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

            has_more_speech = await self.detect_speech_start(1.5)

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
            return await self.transcribe_async(combined_audio)

        return None, None

    # ===== TTS =====

    async def generate_audio(self, text: str, language: Optional[str] = None) -> Optional[str]:
        """Generate TTS audio file, returns file path."""
        container = await self._ensure_container()

        # Detect language if not provided
        if language is None:
            result = await container.asr.detect_language(text)
            language = result if isinstance(result, str) else "zh"

        # Check if we should use Piper or Edge TTS
        backend_type, model_id = await container.tts.get_backend_for_language(language)

        if backend_type == "piper" and model_id:
            result = await container.tts.synthesize(text, language)
            if result.success and result.audio_path:
                return str(result.audio_path)

        # Fallback to Edge TTS
        return await self._generate_audio_edge(text, language)

    async def _generate_audio_edge(self, text: str, language: str) -> Optional[str]:
        """Generate audio using Edge TTS (online)."""
        try:
            voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICES["zh"])
            tmp_file = create_secure_temp_file(suffix=".mp3")
            communicate = edge_tts.Communicate(text, voice, rate=self._tts_rate)
            await communicate.save(tmp_file)
            return tmp_file
        except Exception as e:
            logger.error("edge_tts_error", error=str(e))
            return None

    async def play_audio(self, tmp_file: str, delete: bool = True) -> None:
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

    async def speak(self, text: str, language: Optional[str] = None) -> None:
        """TTS speak a single sentence."""
        tmp_file = await self.generate_audio(text, language)
        if tmp_file:
            await self.play_audio(tmp_file)

    # ===== Main Conversation Loop =====

    async def chat_once(self) -> bool:
        """Single conversation turn."""
        from resource_limiter import with_timeout
        from speekium.models.llm import CLEAR_HISTORY_KEYWORDS, get_clear_history_message

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

        container = await self._ensure_container()
        llm_service = container.llm

        # Check for clear history keywords
        for keyword in CLEAR_HISTORY_KEYWORDS:
            if keyword in text:
                llm_service.clear_history()
                msg = get_clear_history_message(language)
                await self.speak(msg, language)
                return True

        if USE_STREAMING:
            return await self._chat_streaming(llm_service, text, language)
        else:
            return await self._chat_non_streaming(llm_service, text, language)

    async def _chat_streaming(self, llm_service, text: str, language: str) -> bool:
        """Streaming chat with barge-in support."""
        from resource_limiter import with_timeout

        logger.info("streaming_started")
        audio_queue = asyncio.Queue()
        interrupted = False
        generation_done = False

        async def generate_worker():
            nonlocal generation_done
            try:
                async for sentence in llm_service.chat_stream(text):
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

    async def _chat_non_streaming(self, llm_service, text: str, language: str) -> bool:
        """Non-streaming chat."""
        from resource_limiter import with_timeout

        try:
            response = await with_timeout(
                asyncio.to_thread(llm_service.chat, text),
                seconds=120,
                operation_name="LLM_chat",
            )
        except TimeoutError:
            logger.error("llm_timeout", timeout_seconds=120)
            return False

        if not response.success:
            logger.error("llm_chat_failed", error=response.error)
            return False

        try:
            tmp_file = await with_timeout(
                self.generate_audio(response.response, language),
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

    async def run(self) -> None:
        """Main run loop."""

        logger.info("speekium_banner", mode="continuous")
        logger.info("vad_enabled")

        container = await self._ensure_container()
        llm_config = await container.llm.get_config()
        logger.info("llm_backend_info", backend=llm_config["provider"])

        tts_config = await container.tts.get_backend_config()
        tts_backend = tts_config["default"]
        tts_info = tts_backend if tts_backend == "piper" else "edge (online)"
        logger.info("tts_backend_info", backend=tts_info)

        if USE_STREAMING:
            logger.info("streaming_mode_enabled")

        logger.info("memory_config", max_history=llm_config["max_history"])
        logger.info("clear_history_hint")
        logger.info("exit_hint")

        # Show model status
        await self._show_model_status()

        # Start services
        await self.start()

        logger.info("ready_for_input")

        try:
            while True:
                await self.chat_once()
                if not self.was_interrupted:
                    await asyncio.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("shutdown")
        finally:
            await self.stop()

    async def _show_model_status(self) -> None:
        """Show model status information."""
        container = await self._ensure_container()

        print(f"\n{'=' * 60}", file=sys.stderr)
        print("🔍 Checking model status...", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

        asr_status = await container.asr.check_model_exists()
        vad_status = await container.vad.check_model_exists()

        print(
            f"ASR model: {'✅ Downloaded' if asr_status[0] else '❌ Not downloaded'}",
            file=sys.stderr,
        )
        if asr_status[0]:
            print(f"  Path: {asr_status[1]}", file=sys.stderr)

        print(
            f"VAD model: {'✅ Downloaded' if vad_status[0] else '❌ Not downloaded'}",
            file=sys.stderr,
        )
        if vad_status[0]:
            print(f"  Path: {vad_status[1]}", file=sys.stderr)

        print(f"{'=' * 60}\n", file=sys.stderr)


# Backward compatibility: default factory function
async def create_assistant(
    progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
) -> VoiceAssistant:
    """
    Create a new VoiceAssistant with service container.

    Args:
        progress_callback: Optional callback for progress events

    Returns:
        Initialized VoiceAssistant ready to use
    """
    assistant = VoiceAssistant(progress_callback=progress_callback)
    await assistant._ensure_container()
    return assistant


# Legacy main entry point
async def main():
    """Entry point for voice assistant (backward compatible)."""
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
