"""
Voice Pipeline for Speekium
Handles voice recording, VAD detection, ASR, TTS, and audio playback
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav

from logger import get_logger

# Initialize logger
logger = get_logger(__name__)

# Default constants
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_LANGUAGE = "zh"
DEFAULT_TTS_RATE = "+0%"
DEFAULT_VAD_THRESHOLD = 0.5
DEFAULT_VAD_CONSECUTIVE_THRESHOLD = 3
DEFAULT_VAD_SILENCE_DURATION = 0.8
DEFAULT_VAD_PRE_BUFFER = 0.3
DEFAULT_MIN_SPEECH_DURATION = 0.4
DEFAULT_MAX_RECORDING_DURATION = 30

# Edge TTS voices
EDGE_TTS_VOICES = {
    "zh": "zh-CN-XiaoyiNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "yue": "zh-HK-HiuGaaiNeural",
}


class VoicePipeline:
    """Handles all voice processing: recording, VAD, ASR, TTS, playback"""

    def __init__(
        self,
        asr_model=None,
        vad_model=None,
        llm_backend=None,
        config: Optional[dict] = None,
    ):
        self.asr_model = asr_model
        self.vad_model = vad_model
        self.llm_backend = llm_backend
        self.config = config or {}

        # Audio buffers
        self.audio_buffer: list[np.ndarray] = []
        self.sample_rate = DEFAULT_SAMPLE_RATE

    # ==================== Recording ====================

    def record_with_vad(
        self,
        vad_threshold: float = DEFAULT_VAD_THRESHOLD,
        vad_consecutive_threshold: int = DEFAULT_VAD_CONSECUTIVE_THRESHOLD,
        vad_silence_duration: float = DEFAULT_VAD_SILENCE_DURATION,
        vad_pre_buffer: float = DEFAULT_VAD_PRE_BUFFER,
        min_speech_duration: float = DEFAULT_MIN_SPEECH_DURATION,
        max_duration: float = DEFAULT_MAX_RECORDING_DURATION,
        speech_already_started: bool = False,
        on_speech_detected=None,
    ) -> Optional[np.ndarray]:
        """
        Record audio with VAD (Voice Activity Detection).

        Args:
            vad_threshold: VAD threshold (0-1)
            vad_consecutive_threshold: Consecutive detections to confirm speech
            vad_silence_duration: Silence duration to stop recording
            vad_pre_buffer: Pre-buffer duration to capture speech start
            min_speech_duration: Minimum speech duration
            max_duration: Maximum recording duration
            speech_already_started: If True, skip initial detection
            on_speech_detected: Callback when speech is detected

        Returns:
            Audio array or None if no speech detected
        """
        import librosa
        from scipy.signal import filtfilt, butter

        logger.info("recording_started", vad_threshold=vad_threshold)

        # Pre-buffer for capturing speech start
        pre_buffer_frames = int(vad_pre_buffer * self.sample_rate)
        pre_buffer = []
        is_speaking = speech_already_started
        consecutive_speech = 0
        consecutive_silence = 0
        speech_started = False

        # Audio callback
        def callback(indata, frame_count, time_info, status):
            nonlocal is_speaking, consecutive_speech, consecutive_silence, speech_started

            if status:
                logger.warning("audio_status", status=str(status))

            audio_data = indata[:, 0]  # Mono

            if not is_speaking:
                # Add to pre-buffer
                pre_buffer.append(audio_data.copy())

                # Check for speech
                if len(audio_data) > 0:
                    rms = np.sqrt(np.mean(audio_data**2))
                    if rms > vad_threshold:
                        consecutive_speech += 1
                        if consecutive_speech >= vad_consecutive_threshold:
                            is_speaking = True
                            speech_started = True
                            logger.info("speech_detected")

                            if on_speech_detected:
                                on_speech_detected()

                            # Keep pre-buffer audio
                            self.audio_buffer.extend(pre_buffer)
                            pre_buffer = []
                    else:
                        consecutive_speech = 0
            else:
                # Recording speech
                self.audio_buffer.append(audio_data.copy())

                # Check for silence
                rms = np.sqrt(np.mean(audio_data**2))
                if rms < vad_threshold:
                    consecutive_silence += 1
                else:
                    consecutive_silence = 0

                # Stop if silence for too long
                if consecutive_silence > vad_silence_duration * self.sample_rate / 1024:
                    logger.info("silence_detected", duration=vad_silence_duration)
                    raise sd.CallbackStop

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=1024,
                callback=callback,
            ):
                sd.sleep(int(max_duration * 1000))

        except sd.CallbackStop:
            pass

        except Exception as e:
            logger.error("recording_error", error=str(e))
            return None

        # Combine audio
        if self.audio_buffer:
            audio = np.concatenate(self.audio_buffer)
            self.audio_buffer = []

            # Check minimum duration
            if len(audio) / self.sample_rate < min_speech_duration:
                logger.info("speech_too_short", duration=len(audio) / self.sample_rate)
                return None

            logger.info("recording_completed", duration=len(audio) / self.sample_rate)
            return audio

        return None

    def record_push_to_talk(self, max_duration: float = DEFAULT_MAX_RECORDING_DURATION) -> Optional[np.ndarray]:
        """
        Simple push-to-talk recording (no VAD).

        Args:
            max_duration: Maximum recording duration in seconds

        Returns:
            Audio array or None
        """
        logger.info("ptt_recording_started")

        audio_buffer = []

        def callback(indata, frame_count, time_info, status):
            if status:
                logger.warning("audio_status", status=str(status))
            audio_buffer.append(indata[:, 0].copy())

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=1024,
                callback=callback,
            ):
                sd.sleep(int(max_duration * 1000))

        except Exception as e:
            logger.error("ptt_recording_error", error=str(e))
            return None

        if audio_buffer:
            audio = np.concatenate(audio_buffer)
            logger.info("ptt_recording_completed", duration=len(audio) / self.sample_rate)
            return audio

        return None

    # ==================== ASR (Speech Recognition) ====================

    def transcribe(self, audio: np.ndarray) -> Optional[str]:
        """
        Transcribe audio to text using ASR model.

        Args:
            audio: Audio array

        Returns:
            Transcribed text or None
        """
        if self.asr_model is None:
            logger.warning("asr_model_not_loaded")
            return None

        try:
            # Ensure audio is in correct format
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Normalize if needed
            if audio.max() > 1.0:
                audio = audio / 32768.0

            # Transcribe
            logger.info("transcribing", audio_duration=len(audio) / self.sample_rate)

            # SenseVoice input requirements
            if len(audio) < 1600:  # Minimum 100ms
                logger.warning("audio_too_short")
                return None

            input_features = self.asr_model.processor(
                audio, sampling_rate=self.sample_rate, return_tensors="pt"
            )

            with torch.no_grad():
                result = self.asr_model.model.generate(**input_features)

            text = self.asr_model.processor.batch_decode(result, decode_with_lm=False)[0]
            text = text.replace("<|zh|>", "").replace("<|en|>", "").replace("<|yue|>", "").replace("<|ja|>", "").replace("<|ko|>", "").replace("<|nospeech|>", "").strip()

            logger.info("transcription_completed", text=text[:100])
            return text if text else None

        except Exception as e:
            logger.error("transcription_error", error=str(e))
            return None

    async def transcribe_async(self, audio: np.ndarray) -> Optional[str]:
        """Async wrapper for transcribe."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe, audio)

    # ==================== VAD (Voice Activity Detection) ====================

    def detect_speech_start(self, timeout: float = 1.5) -> bool:
        """
        Detect when speech starts.

        Args:
            timeout: Maximum time to wait for speech

        Returns:
            True if speech detected
        """
        import torch

        logger.info("detecting_speech_start", timeout=timeout)

        audio_buffer = []
        speech_started = False

        def callback(indata, frame_count, time_info, status):
            nonlocal speech_started
            audio_data = indata[:, 0]

            if len(audio_data) > 0:
                rms = np.sqrt(np.mean(audio_data**2))
                if rms > vad_threshold:
                    speech_started = True
                    raise sd.CallbackStop

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=1024,
                callback=callback,
            ):
                sd.sleep(int(timeout * 1000))

        except sd.CallbackStop:
            pass

        except Exception as e:
            logger.warning("vad_detection_error", error=str(e))

        logger.info("speech_start_detected", result=speech_started)
        return speech_started

    # ==================== Language Detection ====================

    def detect_text_language(self, text: str) -> str:
        """
        Detect language from text.

        Args:
            text: Input text

        Returns:
            Language code (zh, en, ja, ko, yue)
        """
        if not text:
            return DEFAULT_LANGUAGE

        # Simple detection based on character ranges
        has_chinese = any("\u4e00" <= c <= "\u9fff" for c in text)
        has_japanese = any("\u3040" <= c <= "\u30ff" for c in text)
        has_korean = any("\uac00" <= c <= "\ud7af" for c in text)

        if has_japanese:
            return "ja"
        elif has_korean:
            return "ko"
        elif has_chinese:
            # Check for Cantonese (simplified heuristic)
            return "zh"

        return "en"

    # ==================== TTS (Text-to-Speech) ====================

    async def generate_audio(
        self, text: str, language: Optional[str] = None, tts_backend: str = "edge"
    ) -> Optional[str]:
        """
        Generate audio from text.

        Args:
            text: Text to synthesize
            language: Language code (auto-detected if None)
            tts_backend: TTS backend to use

        Returns:
            Path to generated audio file or None
        """
        if not text:
            return None

        # Detect language if not specified
        if language is None:
            language = self.detect_text_language(text)

        logger.info("generating_audio", language=language, text_len=len(text))

        if tts_backend == "edge":
            return await self._generate_audio_edge(text, language)

        logger.warning("unsupported_tts_backend", backend=tts_backend)
        return None

    async def _generate_audio_edge(self, text: str, language: str) -> Optional[str]:
        """Generate audio using Edge TTS."""
        try:
            import edge_tts

            # Get voice for language
            voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICES["zh"])

            # Create communicate object
            communicate = edge_tts.Communicate(text, voice, rate=DEFAULT_TTS_RATE)

            # Save to temp file
            fd, temp_file = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)

            await communicate.save(temp_file)

            logger.info("edge_tts_generated", path=temp_file)
            return temp_file

        except Exception as e:
            logger.error("edge_tts_error", error=str(e))
            return None

    # ==================== Audio Playback ====================

    async def play_audio(self, tmp_file: str, delete: bool = True) -> bool:
        """
        Play audio file.

        Args:
            tmp_file: Path to audio file
            delete: Delete file after playing

        Returns:
            True if successful
        """
        try:
            import platform

            if platform.system() == "Darwin":
                # macOS: use afplay
                proc = await asyncio.create_subprocess_exec(
                    "afplay", tmp_file, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
                )
                await proc.communicate()
            else:
                # Other platforms: simple playback
                import pygame

                pygame.mixer.init()
                pygame.mixer.music.load(tmp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)

            if delete and Path(tmp_file).exists():
                Path(tmp_file).unlink()

            logger.info("audio_played", file=tmp_file)
            return True

        except Exception as e:
            logger.error("audio_playback_error", error=str(e))
            return False

    async def play_audio_with_barge_in(self, tmp_file: str, delete: bool = True) -> bool:
        """
        Play audio with barge-in support (can be interrupted by voice).
        """
        # Simplified version - just play audio
        return await self.play_audio(tmp_file, delete)

    async def speak(self, text: str, language: Optional[str] = None) -> bool:
        """
        Complete TTS: generate + play audio.

        Args:
            text: Text to speak
            language: Language code

        Returns:
            True if successful
        """
        if not text:
            return False

        # Detect language
        if language is None:
            language = self.detect_text_language(text)

        # Generate audio
        audio_file = await self.generate_audio(text, language)
        if not audio_file:
            return False

        # Play audio
        return await self.play_audio(audio_file)

    # ==================== Utility ====================

    @staticmethod
    def save_audio_file(audio: np.ndarray, file_path: str) -> bool:
        """Save audio array to WAV file."""
        try:
            # Convert float32 to int16
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(file_path, DEFAULT_SAMPLE_RATE, audio_int16)
            logger.info("audio_saved", path=file_path)
            return True
        except Exception as e:
            logger.error("audio_save_error", error=str(e))
            return False


# VoicePipeline class is ready
