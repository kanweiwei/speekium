"""
Speekium Audio Recorder Module for Tauri Backend
Non-blocking audio recording with VAD and ASR support
"""

import asyncio
import logging
import os
import re
import tempfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple, Dict, Any

import numpy as np
import sounddevice as sd
import torch
from scipy.io.wavfile import write as write_wav


# ===== Configuration Constants =====
SAMPLE_RATE = 16000
ASR_MODEL = "iic/SenseVoiceSmall"
DEFAULT_LANGUAGE = "zh"

# VAD Config
VAD_THRESHOLD = 0.7
VAD_CONSECUTIVE_THRESHOLD = 8
VAD_PRE_BUFFER = 0.3
MIN_SPEECH_DURATION = 0.4
SILENCE_AFTER_SPEECH = 0.8
MAX_RECORDING_DURATION = 30
INTERRUPT_CHECK_DURATION = 1.5


class AudioRecorder:
    """Non-blocking audio recorder with VAD and ASR support"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.asr_model = None
        self.vad_model = None
        self.logger = logger or logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=2)

    def load_asr(self):
        """Load ASR model (SenseVoice)"""
        if self.asr_model is None:
            self.logger.info("Loading SenseVoice model...")
            from funasr import AutoModel

            self.asr_model = AutoModel(model=ASR_MODEL, device="cpu")
            self.logger.info("SenseVoice model loaded")
        return self.asr_model

    def load_vad(self):
        """Load VAD model (Silero)"""
        if self.vad_model is None:
            self.logger.info("Loading VAD model...")
            self.vad_model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self.logger.info("VAD model loaded")
        return self.vad_model

    async def record_with_vad_async(
        self, speech_already_started: bool = False
    ) -> Optional[np.ndarray]:
        """Async wrapper for VAD-based recording"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            self.executor, self.record_with_vad, speech_already_started
        )
        return result

    def record_with_vad(
        self, speech_already_started: bool = False
    ) -> Optional[np.ndarray]:
        """Use VAD to detect speech, auto start and stop recording.

        Args:
            speech_already_started: If True, skip waiting for speech to begin

        Returns:
            numpy array of audio samples or None if no speech detected
        """
        model = self.load_vad()
        model.reset_states()

        self.logger.info("Listening for speech...")

        chunk_size = 512
        frames = []

        is_speaking = speech_already_started
        silence_chunks = 0
        speech_chunks = len(frames)
        consecutive_speech = VAD_CONSECUTIVE_THRESHOLD if speech_already_started else 0
        max_silence_chunks = int(SILENCE_AFTER_SPEECH * SAMPLE_RATE / chunk_size)
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / chunk_size)
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / chunk_size)

        pre_buffer_size = int(VAD_PRE_BUFFER * SAMPLE_RATE / chunk_size)
        pre_buffer = deque(maxlen=pre_buffer_size)

        recording_done = False

        def callback(indata, frame_count, time_info, status):
            nonlocal is_speaking
            nonlocal silence_chunks
            nonlocal speech_chunks
            nonlocal consecutive_speech
            nonlocal recording_done

            if recording_done:
                return

            try:
                audio_chunk = indata[:, 0].copy()

                audio_tensor = torch.from_numpy(audio_chunk).float()
                speech_prob = model(audio_tensor, SAMPLE_RATE).item()

                if speech_prob > VAD_THRESHOLD:
                    consecutive_speech += 1

                    if (
                        not is_speaking
                        and consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD
                    ):
                        is_speaking = True
                        frames.extend(pre_buffer)
                        pre_buffer.clear()
                        self.logger.info("Speech detected, recording...")

                    if is_speaking:
                        if consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                            silence_chunks = 0
                        speech_chunks += 1
                        frames.append(audio_chunk)
                    else:
                        pre_buffer.append(audio_chunk)
                else:
                    consecutive_speech = 0

                    if is_speaking:
                        frames.append(audio_chunk)
                        silence_chunks += 1

                        if (
                            silence_chunks >= max_silence_chunks
                            and speech_chunks >= min_speech_chunks
                        ):
                            recording_done = True
                            self.logger.info("Speech ended")
                    else:
                        pre_buffer.append(audio_chunk)

                if len(frames) >= max_chunks:
                    recording_done = True
                    self.logger.info("Max recording duration reached")

            except Exception as e:
                self.logger.error(f"VAD error: {e}")
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
        duration = len(audio) / SAMPLE_RATE
        self.logger.info(f"Recording complete: {duration:.1f}s")
        return audio

    def record_push_to_talk(
        self, is_recording_func, check_interval_ms: int = 50
    ) -> Optional[np.ndarray]:
        """Push-to-talk recording mode controlled by external signal.

        Args:
            is_recording_func: Callable that returns True while recording should continue
            check_interval_ms: Interval to check recording status

        Returns:
            numpy array of audio samples or None if no data recorded
        """
        self.logger.info("Push-to-talk mode waiting...")

        chunk_size = 512
        frames = []

        def callback(indata, frame_count, time_info, status):
            if is_recording_func():
                audio_chunk = indata[:, 0].copy()
                frames.append(audio_chunk)

        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            callback=callback,
        ):
            while not is_recording_func():
                sd.sleep(check_interval_ms)

            while is_recording_func():
                sd.sleep(check_interval_ms)

        if not frames:
            self.logger.warning("No audio data recorded")
            return None

        audio = np.concatenate(frames)
        duration = len(audio) / SAMPLE_RATE
        self.logger.info(f"Push-to-talk recording complete: {duration:.1f}s")
        return audio

    async def transcribe_async(
        self, audio: np.ndarray
    ) -> Tuple[Optional[str], Optional[str]]:
        """Async wrapper for transcription"""
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(self.executor, self.transcribe, audio)
        return result

    def transcribe(self, audio: np.ndarray) -> Tuple[Optional[str], Optional[str]]:
        """Transcribe audio and detect language.

        Args:
            audio: numpy array of audio samples

        Returns:
            Tuple of (text, language) or (None, None) on error
        """
        self.logger.info("Transcribing audio...")
        model = self.load_asr()
        tmp_file = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_file = f.name
                audio_int16 = (audio * 32767).astype(np.int16)
                write_wav(tmp_file, SAMPLE_RATE, audio_int16)
                result = model.generate(input=tmp_file)
                raw_text = result[0]["text"] if result else ""
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

        lang_match = re.search(r"<\|(zh|en|ja|ko|yue)\|>", raw_text)
        language = lang_match.group(1) if lang_match else DEFAULT_LANGUAGE

        text = re.sub(r"<\|[^|]+\|>", "", raw_text).strip()

        if text:
            self.logger.info(f"[{language}] {text}")
        else:
            self.logger.warning("No text recognized")

        return (text, language) if text else (None, None)

    def detect_speech_start(self, timeout: float = 1.5) -> bool:
        """Check if speech starts within timeout.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if speech detected within timeout
        """
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

    async def record_with_interruption_async(
        self, was_interrupted: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """Record with support for continuation (multi-segment speech).

        Args:
            was_interrupted: If True, starts recording immediately

        Returns:
            Tuple of (text, language) or (None, None) on error
        """
        all_segments = []

        speech_already_started = was_interrupted

        while True:
            segment = await self.record_with_vad_async(
                speech_already_started=speech_already_started
            )
            speech_already_started = False

            if segment is None:
                if not all_segments:
                    return None, None
                break

            all_segments.append(segment)

            combined_audio = np.concatenate(all_segments)
            asr_task = asyncio.create_task(self.transcribe_async(combined_audio))

            self.logger.info("Waiting for more input...")

            loop = asyncio.get_event_loop()
            has_more_speech = await loop.run_in_executor(
                self.executor, self.detect_speech_start, INTERRUPT_CHECK_DURATION
            )

            if has_more_speech:
                asr_task.cancel()
                try:
                    await asr_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("Continuing recording...")
                continue
            else:
                try:
                    text, language = await asr_task
                    return text, language
                except asyncio.CancelledError:
                    break

        if all_segments:
            combined_audio = np.concatenate(all_segments)
            return self.transcribe(combined_audio)

        return None, None

    def shutdown(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.logger.info("Audio recorder shut down")
