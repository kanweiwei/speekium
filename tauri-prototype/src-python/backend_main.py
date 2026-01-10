#!/usr/bin/env python3
"""
Speerium Backend - Main Entry Point for Tauri Sidecar
Provides PyTauri commands for audio recording, LLM, and TTS
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Import PyTauri
try:
    from pytauri import Commands, AppHandle, Event
    from pydantic import BaseModel, Field
except ImportError as e:
    logger.error(f"Failed to import PyTauri: {e}")
    logger.error("Please install: pip install pytauri pydantic")
    sys.exit(1)

# Import backend modules
try:
    from src_python.audio_recorder import AudioRecorder
    from src_python.llm_backend import LLMBackendManager
    from src_python.tts_engine import get_tts_engine, TTSRequest
except ImportError as e:
    logger.error(f"Failed to import backend modules: {e}")
    sys.exit(1)

# ===== PyTauri Commands =====

commands = Commands()

# Global instances
audio_recorder: AudioRecorder = None
llm_manager: LLMBackendManager = None
tts_engine = get_tts_engine()

# ===== Request/Response Models =====


class StartRecordingRequest(BaseModel):
    """Request to start recording"""

    mode: str = Field(default="vad", description="Recording mode: vad, push_to_talk")


class RecordingResult(BaseModel):
    """Result from recording"""

    text: str = Field(description="Transcribed text")
    language: str = Field(description="Detected language")


class ChatRequest(BaseModel):
    """Request for LLM chat"""

    message: str = Field(description="User message")
    stream: bool = Field(default=True, description="Use streaming response")


class TTSRequestWrapper(BaseModel):
    """Wrapper for TTS request"""

    text: str
    language: str = "auto"
    backend: str = "edge"


class ConfigResult(BaseModel):
    """Configuration result"""

    success: bool
    config: dict = Field(default_factory=dict)


# ===== Audio Recording Commands =====


@commands.command()
async def start_recording(
    body: StartRecordingRequest, app_handle: AppHandle
) -> RecordingResult:
    """Start audio recording with VAD or push-to-talk"""
    global audio_recorder

    if audio_recorder is None:
        audio_recorder = AudioRecorder(logger=logger)

    try:
        if body.mode == "vad":
            text, language = await audio_recorder.record_with_vad_async()
        elif body.mode == "push_to_talk":
            text, language = await audio_recorder.record_push_to_talk_async()
        else:
            raise ValueError(f"Unknown recording mode: {body.mode}")

        if text is None:
            return RecordingResult(text="", language="")

        logger.info(f"Recording complete: [{language}] {text[:50]}...")
        return RecordingResult(text=text, language=language or "unknown")
    except Exception as e:
        logger.error(f"Recording error: {e}", exc_info=True)
        raise


# ===== LLM Commands =====


@commands.command()
async def chat(body: ChatRequest, app_handle: AppHandle) -> str:
    """Send message to LLM (non-streaming)"""
    global llm_manager

    if llm_manager is None:
        llm_manager = LLMBackendManager(config={}, logger=logger)

    try:
        backend = llm_manager.get_backend()
        result = await backend.chat_async(body.message)
        return result
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        raise


@commands.command()
async def chat_stream(body: ChatRequest, app_handle: AppHandle) -> str:
    """Send message to LLM (streaming) - simplified for now"""
    # TODO: Implement proper streaming with events
    global llm_manager

    if llm_manager is None:
        llm_manager = LLMBackendManager(config={}, logger=logger)

    try:
        backend = llm_manager.get_backend()
        # For now, return full response (streaming to be implemented)
        result = await backend.chat_async(body.message)
        return result
    except Exception as e:
        logger.error(f"LLM chat error: {e}", exc_info=True)
        raise


# ===== TTS Commands =====


@commands.command()
async def generate_tts(body: TTSRequestWrapper, app_handle: AppHandle) -> dict:
    """Generate text-to-speech audio"""
    global tts_engine

    try:
        request = TTSRequest(
            text=body.text, language=body.language, backend=body.backend
        )
        result = await tts_engine.generate_async(request)

        return {
            "success": result.success,
            "audio_base64": result.audio_base64,
            "format": result.format,
            "error": result.error,
        }
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise


@commands.command()
async def play_tts(audio_base64: str, audio_format: str, app_handle: AppHandle) -> None:
    """Play TTS audio"""
    global tts_engine

    try:
        await tts_engine.play_audio_async(audio_base64, audio_format)
    except Exception as e:
        logger.error(f"TTS playback error: {e}", exc_info=True)
        raise


# ===== Configuration Commands =====


@commands.command()
async def get_config(app_handle: AppHandle) -> dict:
    """Get current configuration"""
    # TODO: Load from config file
    return {"llm_backend": "ollama", "tts_backend": "edge", "vad_threshold": 0.7}


@commands.command()
async def save_config(config: dict, app_handle: AppHandle) -> ConfigResult:
    """Save configuration"""
    # TODO: Save to config file
    logger.info(f"Saving config: {config}")
    return ConfigResult(success=True, config=config)


# ===== Utility Commands =====


@commands.command()
async def clear_history(app_handle: AppHandle) -> None:
    """Clear conversation history"""
    global llm_manager

    if llm_manager:
        await llm_manager.clear_history()


# ===== Main Entry Point =====


async def main():
    """Main entry point for PyTauri backend"""
    logger.info("Starting Speekium Backend...")

    # Initialize components
    global audio_recorder, llm_manager
    audio_recorder = AudioRecorder(logger=logger)
    llm_manager = LLMBackendManager(config={}, logger=logger)

    # Start PyTauri event loop
    logger.info("Speerium Backend ready")
    await commands.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
