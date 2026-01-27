"""
Audio recording module with VAD (Voice Activity Detection).

Provides continuous VAD-based recording and push-to-talk modes.
"""

import time
from collections import deque
from collections.abc import Callable

import numpy as np
import sounddevice as sd
import torch

from logger import get_logger

logger = get_logger(__name__)


def record_with_vad(
    vad_model,
    vad_threshold: float,
    vad_consecutive_threshold: int,
    vad_silence_duration: float,
    vad_pre_buffer: float,
    vad_min_speech_duration: float,
    vad_max_recording_duration: float,
    initial_speech_timeout: float,
    sample_rate: int,
    recording_interrupt_event,
    is_generating_tts: bool,
    speech_already_started: bool = False,
    on_speech_detected: Callable[[], None] | None = None,
    interrupt_audio_buffer: list | None = None,
) -> np.ndarray | None:
    """
    Use VAD to detect speech, auto start and stop recording.

    Args:
        vad_model: Loaded VAD model
        vad_threshold: Speech detection threshold (0.0-1.0)
        vad_consecutive_threshold: Consecutive detections to confirm speech
        vad_silence_duration: Silence duration to stop recording (seconds)
        vad_pre_buffer: Pre-buffer duration to capture speech start (seconds)
        vad_min_speech_duration: Minimum speech duration (seconds)
        vad_max_recording_duration: Maximum recording duration (seconds)
        initial_speech_timeout: Max time to wait for initial speech (seconds)
        sample_rate: Audio sample rate
        recording_interrupt_event: Threading event to signal interruption
        is_generating_tts: Whether TTS is in progress
        speech_already_started: If True, skip waiting for speech to begin
        on_speech_detected: Optional callback called when speech is detected
        interrupt_audio_buffer: Optional buffer with pre-captured audio

    Returns:
        Audio numpy array or None if no valid speech
    """
    vad_model.reset_states()  # Reset VAD state

    if speech_already_started:
        logger.info("recording_started", mode="interrupted")
    else:
        logger.info("listening")

    # Check if TTS is being generated/played - pause VAD during TTS
    if is_generating_tts:
        logger.info("tts_in_progress", status="vad_paused")
        return None

    chunk_size = 512  # Silero VAD requires 512 samples @ 16kHz
    frames = []

    # Use captured audio from interrupt if available
    if speech_already_started and interrupt_audio_buffer:
        frames = interrupt_audio_buffer.copy()
        interrupt_audio_buffer.clear()
        logger.debug("audio_buffer_used", chunks=len(frames))

    is_speaking = speech_already_started
    silence_chunks = 0
    speech_chunks = len(frames)
    consecutive_speech = vad_consecutive_threshold if speech_already_started else 0
    max_silence_chunks = int(vad_silence_duration * sample_rate / chunk_size)
    min_speech_chunks = int(vad_min_speech_duration * sample_rate / chunk_size)
    max_chunks = int(vad_max_recording_duration * sample_rate / chunk_size)

    # Pre-buffer: keep audio before speech starts to avoid clipping
    pre_buffer_size = int(vad_pre_buffer * sample_rate / chunk_size)
    pre_buffer = deque(maxlen=pre_buffer_size)

    recording_done = False
    start_time = time.time()

    def callback(indata, frame_count, time_info, status):
        nonlocal is_speaking, silence_chunks, speech_chunks
        nonlocal consecutive_speech, recording_done

        if recording_done:
            return

        try:
            audio_chunk = indata[:, 0].copy()

            # VAD detection
            audio_tensor = torch.from_numpy(audio_chunk).float()
            speech_prob = vad_model(audio_tensor, sample_rate).item()

            if speech_prob > vad_threshold:
                # Speech detected
                consecutive_speech += 1

                if not is_speaking and consecutive_speech >= vad_consecutive_threshold:
                    is_speaking = True
                    # Add pre-buffer to frames to avoid clipping speech start
                    frames.extend(pre_buffer)
                    pre_buffer.clear()
                    logger.info("speech_detected")
                    # Call callback if provided
                    if on_speech_detected:
                        on_speech_detected()

                if is_speaking:
                    # Only reset silence count on consecutive speech
                    if consecutive_speech >= vad_consecutive_threshold:
                        silence_chunks = 0
                    speech_chunks += 1
                    frames.append(audio_chunk)
                else:
                    # Not confirmed speaking yet, fill pre-buffer
                    pre_buffer.append(audio_chunk)
            else:
                # Silence
                consecutive_speech = 0

                if is_speaking:
                    frames.append(audio_chunk)
                    silence_chunks += 1

                    # Stop recording after enough silence
                    if silence_chunks >= max_silence_chunks and speech_chunks >= min_speech_chunks:
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
        samplerate=sample_rate,
        channels=1,
        dtype=np.float32,
        blocksize=chunk_size,
        callback=callback,
    ):
        config_check_counter = 0
        while not recording_done:
            # Check for interrupt signal
            if recording_interrupt_event.is_set():
                logger.info("recording_interrupted")
                recording_done = True
                break

            # Check initial speech timeout (only before speech starts)
            if not is_speaking:
                elapsed = time.time() - start_time
                if elapsed > initial_speech_timeout:
                    logger.info("initial_speech_timeout", elapsed=elapsed)
                    recording_done = True
                    break

            # Also check config file for recording mode changes
            config_check_counter += 1
            if config_check_counter % 5 == 0:
                try:
                    from config_manager import ConfigManager

                    config = ConfigManager.load(silent=True)
                    config_mode = config.get("recording_mode", "continuous")
                    # If mode is not continuous, abort recording
                    if config_mode != "continuous":
                        logger.info(f"recording_mode_changed_to_{config_mode}, aborting")
                        recording_done = True
                        break
                except Exception:
                    pass  # Ignore config read errors

            sd.sleep(50)  # Sleep for 50ms

    if not frames or speech_chunks < min_speech_chunks:
        return None

    audio = np.concatenate(frames)
    logger.info("recording_complete", duration=len(audio) / sample_rate)
    return audio


def detect_speech_start(
    vad_model,
    vad_threshold: float,
    vad_consecutive_threshold: int,
    sample_rate: int,
    timeout: float = 1.5,
) -> bool:
    """
    Check if speech starts within timeout.

    Args:
        vad_model: Loaded VAD model
        vad_threshold: Speech detection threshold
        vad_consecutive_threshold: Consecutive detections to confirm speech
        sample_rate: Audio sample rate
        timeout: Maximum time to wait for speech (seconds)

    Returns:
        True if speech detected, False otherwise
    """
    vad_model.reset_states()

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
            speech_prob = vad_model(audio_tensor, sample_rate).item()

            if speech_prob > vad_threshold:
                consecutive_speech += 1
                if consecutive_speech >= vad_consecutive_threshold:
                    speech_detected = True
                    check_done = True
            else:
                consecutive_speech = 0
        except Exception:
            pass

    timeout_ms = int(timeout * 1000)
    with sd.InputStream(
        samplerate=sample_rate,
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


def record_push_to_talk(
    mode_manager,
    sample_rate: int,
) -> np.ndarray | None:
    """
    Push-to-talk mode: manually control recording start and stop.

    Args:
        mode_manager: ModeManager instance with is_recording flag
        sample_rate: Audio sample rate

    Returns:
        Audio numpy array or None if no data recorded
    """
    logger.info("ptt_mode_activated")

    chunk_size = 512
    frames = []

    def callback(indata, frame_count, time_info, status):
        # Only record when in recording state
        if mode_manager.is_recording:
            audio_chunk = indata[:, 0].copy()
            frames.append(audio_chunk)

    # Start audio stream
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=chunk_size,
        callback=callback,
    ):
        # Wait for recording to start
        while not mode_manager.is_recording:
            sd.sleep(50)

        # Recording in progress
        while mode_manager.is_recording:
            sd.sleep(50)

    # Check if we have recording data
    if not frames:
        logger.warning("no_audio_data")
        return None

    audio = np.concatenate(frames)
    logger.info("ptt_recording_complete", duration=len(audio) / sample_rate)
    return audio
