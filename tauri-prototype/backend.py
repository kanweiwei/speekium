"""
Speekium Python Backend - PyTauri Version
Production-ready backend with real config management
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pytauri import Commands, AppHandle
import asyncio
import sys

# Add src-python to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src-python"))

from audio_recorder import AudioRecorder
from llm_backend import (
    LLMBackendManager,
    ChatMessageType,
)
from tts_engine import (
    TTSEngine,
    TTSRequest,
    TTSResult,
    get_tts_engine,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============ Config Models ============


class ConfigLoadRequest(BaseModel):
    """Request to load configuration"""

    pass


class ConfigSaveRequest(BaseModel):
    """Request to save configuration"""

    config: Dict[str, Any]


class ConfigGetRequest(BaseModel):
    """Request to get configuration value(s)"""

    key: Optional[str] = Field(
        default=None, description="Optional specific key to retrieve"
    )


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration"""

    key: str = Field(description="Key to update")
    value: Any = Field(description="Value to set")


class ConfigBulkUpdateRequest(BaseModel):
    """Request to bulk update configuration"""

    updates: Dict[str, Any] = Field(
        description="Dictionary of key-value pairs to update"
    )


class ConfigResult(BaseModel):
    """Standard config operation result"""

    success: bool
    config: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ============ Recording Models ============


class RecordingRequest(BaseModel):
    """Request to start voice recording"""

    mode: str = Field(
        default="push-to-talk",
        description="Recording mode: 'push-to-talk' or 'continuous'",
    )
    language: str = Field(default="auto", description="Language code or 'auto'")


class RecordingResult(BaseModel):
    """Result from voice recording"""

    success: bool
    text: Optional[str] = None
    language: Optional[str] = None
    error: Optional[str] = None


# ============ Chat Models ============


class ChatRequest(BaseModel):
    """Request for chat generation"""

    text: str
    language: str = Field(default="auto")
    history: Optional[List[Dict[str, Any]]] = None
    generate_audio: bool = Field(
        default=False, description="Whether to generate TTS audio for the response"
    )


class ChatChunk(BaseModel):
    """Chunk of streaming chat response"""

    type: str = Field(description="Chunk type: 'partial', 'complete', 'error'")
    content: Optional[str] = None
    audio: Optional[str] = Field(default=None, description="Base64 encoded audio data")
    error: Optional[str] = None


# ============ Config Constants ============

# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    "llm_backend": "ollama",
    "ollama_model": "qwen2.5:1.5b",
    "ollama_base_url": "http://localhost:11434",
    "tts_backend": "edge",
    "tts_rate": "+0%",
    "vad_threshold": 0.7,
    "max_history": 10,
}

# Config file path (will be resolved relative to app data dir)
CONFIG_FILENAME = "config.json"


# ============ Config Manager Implementation ============


class ConfigManager:
    """Configuration manager with JSON file persistence"""

    @staticmethod
    def _get_config_path(app_handle: AppHandle) -> Path:
        """Get the config file path from app data directory"""
        try:
            app_data_dir = app_handle.path().app_data_dir()
            config_path = app_data_dir.joinpath(CONFIG_FILENAME)

            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            return config_path
        except Exception as e:
            print(f"[ConfigManager] Error getting config path: {e}")
            # Fallback to local directory
            return Path(CONFIG_FILENAME)

    @staticmethod
    def load(app_handle: AppHandle) -> Dict[str, Any]:
        """Load configuration from file"""
        config_path = ConfigManager._get_config_path(app_handle)

        if not config_path.exists():
            print(
                f"[ConfigManager] Config file not found, creating default: {config_path}"
            )
            ConfigManager.save(DEFAULT_CONFIG.copy(), app_handle)
            return DEFAULT_CONFIG.copy()

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = {**DEFAULT_CONFIG, **config}
                print(f"[ConfigManager] Config loaded successfully from: {config_path}")
                return merged_config
        except json.JSONDecodeError as e:
            print(f"[ConfigManager] JSON decode error: {e}")
            # Backup corrupted config and return defaults
            backup_path = config_path.with_suffix(".json.backup")
            try:
                config_path.rename(backup_path)
                print(f"[ConfigManager] Corrupted config backed up to: {backup_path}")
            except Exception as backup_error:
                print(f"[ConfigManager] Failed to backup config: {backup_error}")
            ConfigManager.save(DEFAULT_CONFIG.copy(), app_handle)
            return DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"[ConfigManager] Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config: Dict[str, Any], app_handle: AppHandle) -> None:
        """Save configuration to file"""
        config_path = ConfigManager._get_config_path(app_handle)

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"[ConfigManager] Config saved successfully to: {config_path}")
        except Exception as e:
            print(f"[ConfigManager] Error saving config: {e}")
            raise RuntimeError(f"Failed to save configuration: {e}")


# ============ Command Registration ============

commands = Commands()


# ============ Config Commands ============


@commands.command()
async def config_load(body: ConfigLoadRequest, app_handle: AppHandle) -> ConfigResult:
    """
    Load application configuration from file

    Returns the complete configuration merged with defaults
    """
    try:
        config = ConfigManager.load(app_handle)
        print(f"[Config] Loaded config with {len(config)} keys")
        return ConfigResult(success=True, config=config)
    except Exception as e:
        print(f"[Config] Load error: {e}")
        return ConfigResult(success=False, error=str(e))


@commands.command()
async def config_save(body: ConfigSaveRequest, app_handle: AppHandle) -> ConfigResult:
    """
    Save application configuration to file

    Validates config structure and persists to disk
    """
    try:
        # Validate required keys exist
        merged_config = {**DEFAULT_CONFIG, **body.config}

        ConfigManager.save(merged_config, app_handle)
        print(f"[Config] Saved config with {len(merged_config)} keys")
        return ConfigResult(success=True, config=merged_config)
    except Exception as e:
        print(f"[Config] Save error: {e}")
        return ConfigResult(success=False, error=str(e))


@commands.command()
async def config_get(body: ConfigGetRequest, app_handle: AppHandle) -> ConfigResult:
    """
    Get configuration value(s)

    If key is provided, returns specific key-value pair
    Otherwise returns entire configuration
    """
    try:
        config = ConfigManager.load(app_handle)

        if body.key:
            value = config.get(body.key)
            print(f"[Config] Retrieved key: {body.key}")
            return ConfigResult(success=True, config={body.key: value})
        else:
            print(f"[Config] Retrieved entire config ({len(config)} keys)")
            return ConfigResult(success=True, config=config.copy())
    except Exception as e:
        print(f"[Config] Get error: {e}")
        return ConfigResult(success=False, error=str(e))


@commands.command()
async def config_update(
    body: ConfigUpdateRequest, app_handle: AppHandle
) -> ConfigResult:
    """
    Update a single configuration key

    Updates the specified key and saves to disk
    """
    try:
        config = ConfigManager.load(app_handle)
        config[body.key] = body.value
        ConfigManager.save(config, app_handle)
        print(f"[Config] Updated key: {body.key} = {body.value}")
        return ConfigResult(success=True, config=config.copy())
    except Exception as e:
        print(f"[Config] Update error: {e}")
        return ConfigResult(success=False, error=str(e))


@commands.command()
async def config_bulk_update(
    body: ConfigBulkUpdateRequest, app_handle: AppHandle
) -> ConfigResult:
    """
    Update multiple configuration keys at once

    Merges updates with existing config and saves to disk
    """
    try:
        config = ConfigManager.load(app_handle)
        config.update(body.updates)
        ConfigManager.save(config, app_handle)
        print(f"[Config] Bulk updated {len(body.updates)} keys")
        return ConfigResult(success=True, config=config.copy())
    except Exception as e:
        print(f"[Config] Bulk update error: {e}")
        return ConfigResult(success=False, error=str(e))


# ============ Audio Recorder Instance ============

_audio_recorder: Optional[AudioRecorder] = None


def get_audio_recorder() -> AudioRecorder:
    """Get or create audio recorder instance"""
    global _audio_recorder
    if _audio_recorder is None:
        _audio_recorder = AudioRecorder(logger=logger)
    return _audio_recorder


# ============ LLM Backend Instance ============

_llm_manager: Optional[LLMBackendManager] = None


def get_llm_manager(app_handle: AppHandle) -> LLMBackendManager:
    """Get or create LLM backend manager instance"""
    global _llm_manager
    if _llm_manager is None:
        config = ConfigManager.load(app_handle)
        _llm_manager = LLMBackendManager(config, logger=logger)
        _llm_manager.load_backend()
    return _llm_manager


# ============ TTS Engine Instance ============

_tts_engine: Optional[TTSEngine] = None


def get_tts_engine_instance() -> TTSEngine:
    """Get or create TTS engine instance"""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = get_tts_engine()
    return _tts_engine


# ============ Recording Commands ============


@commands.command()
async def start_recording(
    body: RecordingRequest, app_handle: AppHandle
) -> RecordingResult:
    """
    Start voice recording with VAD or push-to-talk mode

    Args:
        body.mode: 'push-to-talk' or 'continuous'
        body.language: Language code or 'auto' for auto-detection

    Returns:
        RecordingResult with transcribed text and detected language
    """
    try:
        logger.info(
            f"[Recording] Starting recording: mode={body.mode}, language={body.language}"
        )

        recorder = get_audio_recorder()

        if body.mode == "continuous":
            # Continuous mode with VAD and interruption support
            text, language = await recorder.record_with_interruption_async(
                was_interrupted=False
            )
        elif body.mode == "push-to-talk":
            # Push-to-talk mode - record with VAD
            audio = await recorder.record_with_vad_async(speech_already_started=False)
            if audio is None:
                logger.warning("[Recording] No speech detected")
                return RecordingResult(success=False, error="No speech detected")
            text, language = await recorder.transcribe_async(audio)
        else:
            logger.error(f"[Recording] Unknown mode: {body.mode}")
            return RecordingResult(
                success=False, error=f"Unknown recording mode: {body.mode}"
            )

        if text is None:
            logger.warning("[Recording] No text recognized")
            return RecordingResult(success=False, error="No speech recognized")

        # Use detected language if 'auto' was requested
        detected_language = language if body.language == "auto" else body.language

        result = RecordingResult(
            success=True,
            text=text,
            language=detected_language,
        )

        logger.info(f"[Recording] Result: [{result.language}] {result.text}")
        return result

    except Exception as e:
        logger.error(f"[Recording] Error: {e}", exc_info=True)
        return RecordingResult(success=False, error=str(e))


# ============ Chat Commands ============


class LoadLLMRequest(BaseModel):
    """Request to load or reload LLM backend"""

    backend_type: Optional[str] = Field(
        default=None,
        description="Backend type: 'claude' or 'ollama'. If None, uses current config",
    )


@commands.command()
async def load_llm(body: LoadLLMRequest, app_handle: AppHandle) -> Dict[str, Any]:
    """
    Load or reload LLM backend

    Args:
        backend_type: Optional backend type to load. If None, uses config value.

    Returns:
        Success status and loaded backend info
    """
    try:
        manager = get_llm_manager(app_handle)
        backend = manager.load_backend(body.backend_type)

        logger.info(f"[LLM] Loaded backend: {manager.backend_type}")

        return {
            "success": True,
            "backend_type": manager.backend_type,
            "model": (
                backend.model if hasattr(backend, "model") else "default"
            ),  # For Ollama
        }
    except Exception as e:
        logger.error(f"[LLM] Error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@commands.command()
async def chat_generator(body: ChatRequest, app_handle: AppHandle) -> List[ChatChunk]:
    """
    Generate chat response using LLM backend with streaming

    Yields ChatChunk objects as text is generated

    Args:
        body.generate_audio: If True, generates TTS audio for complete response
    """
    try:
        logger.info(
            f"[Chat] Request: text={body.text[:50]}..., language={body.language}, "
            f"generate_audio={body.generate_audio}"
        )

        manager = get_llm_manager(app_handle)
        backend = manager.get_backend()

        chunks = []
        full_response = ""
        last_msg_type = None

        async for text, msg_type in backend.chat_stream_async(body.text):
            last_msg_type = msg_type

            if msg_type == ChatMessageType.ERROR:
                chunks.append(ChatChunk(type="error", error=text))
                break
            elif msg_type == ChatMessageType.COMPLETE:
                full_response = text
                chunks.append(
                    ChatChunk(
                        type="complete",
                        content=text,
                        audio=None,
                    )
                )
                break
            else:
                full_response += text
                chunks.append(
                    ChatChunk(
                        type="partial",
                        content=text,
                    )
                )

        # Generate TTS audio if requested and response is complete
        if (
            body.generate_audio
            and full_response
            and last_msg_type != ChatMessageType.ERROR
        ):
            logger.info("[Chat] Generating TTS audio for response...")
            try:
                config = ConfigManager.load(app_handle)
                tts_backend = config.get("tts_backend", "edge")

                tts_request = TTSRequest(
                    text=full_response,
                    language=body.language,
                    backend=tts_backend,
                    rate=config.get("tts_rate", "+0%"),
                )

                engine = get_tts_engine_instance()
                tts_result = await engine.generate_async(tts_request)

                if tts_result.success and tts_result.audio_base64:
                    # Update the complete chunk with audio
                    complete_chunk = chunks[-1]
                    complete_chunk.audio = tts_result.audio_base64
                    logger.info("[Chat] TTS audio generated successfully")
                else:
                    logger.warning(f"[Chat] TTS generation failed: {tts_result.error}")

            except Exception as e:
                logger.error(f"[Chat] TTS generation error: {e}", exc_info=True)

        logger.info(f"[Chat] Generated {len(chunks)} chunks")
        return chunks

    except Exception as e:
        logger.error(f"[Chat] Error: {e}", exc_info=True)
        return [ChatChunk(type="error", error=str(e))]


# ============ TTS Commands ============


@commands.command()
async def generate_tts(body: TTSRequest, app_handle: AppHandle) -> TTSResult:
    """
    Generate TTS audio using specified backend

    Args:
        body.text: Text to convert to speech
        body.language: Language code (e.g., 'zh', 'en', 'auto')
        body.backend: 'edge' (online, MP3) or 'piper' (offline, WAV)
        body.voice: Optional voice override
        body.rate: Speech rate for Edge TTS (e.g., '+0%', '+10%', '-10%')

    Returns:
        TTSResult with base64 encoded audio
    """
    try:
        logger.info(
            f"[TTS] Generating: backend={body.backend}, "
            f"text={body.text[:50]}..., language={body.language}"
        )

        # Load config for default settings
        config = ConfigManager.load(app_handle)

        # Override with config if not specified
        if body.backend == "auto" or body.backend is None:
            body.backend = config.get("tts_backend", "edge")

        # Get TTS engine
        engine = get_tts_engine_instance()

        # Generate audio
        result = await engine.generate_async(body)

        if result.success:
            logger.info(f"[TTS] Generated audio: {result.format}")

        return result

    except Exception as e:
        logger.error(f"[TTS] Error: {e}", exc_info=True)
        return TTSResult(success=False, error=str(e))


@commands.command()
async def play_tts(
    audio_base64: str, audio_format: str, app_handle: AppHandle
) -> Dict[str, Any]:
    """
    Play audio from base64 encoded data

    Args:
        audio_base64: Base64 encoded audio data
        audio_format: Audio MIME type (e.g., 'audio/mp3', 'audio/wav')

    Returns:
        Success status
    """
    try:
        logger.info("[TTS] Playing audio")

        # Get TTS engine
        engine = get_tts_engine_instance()

        # Play audio
        await engine.play_audio_async(audio_base64, audio_format)

        logger.info("[TTS] Playback completed")

        return {"success": True}
    except Exception as e:
        logger.error(f"[TTS] Playback error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


# ============ History Commands ============


@commands.command()
async def clear_history(app_handle: AppHandle) -> Dict[str, Any]:
    """
    Clear chat history
    """
    try:
        manager = get_llm_manager(app_handle)
        await manager.clear_history()
        logger.info("[History] Cleared chat history")
        return {"success": True}
    except Exception as e:
        logger.error(f"[History] Error: {e}")
        return {"success": False, "error": str(e)}


# ============ Legacy Commands (Backward Compatibility) ============


@commands.command()
async def get_config(app_handle: AppHandle) -> Dict[str, Any]:
    """
    Legacy get_config command for backward compatibility

    Use config_load or config_get for new code
    """
    result = await config_load(ConfigLoadRequest(), app_handle)
    return result.config if result.success and result.config is not None else {}


@commands.command()
async def save_config(
    key: Optional[str] = None, value: Optional[Any] = None, app_handle: AppHandle = None
) -> Dict[str, Any]:
    """
    Legacy save_config command for backward compatibility

    Use config_update or config_bulk_update for new code
    """
    try:
        if key and value is not None:
            request = ConfigUpdateRequest(key=key, value=value)
            result = await config_update(request, app_handle)
        elif isinstance(value, dict):
            request = ConfigBulkUpdateRequest(updates=value)
            result = await config_bulk_update(request, app_handle)
        else:
            return {"success": False, "error": "Invalid parameters"}

        return {
            "success": result.success,
            "config": result.config,
            "error": result.error,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============ Main Entry Point ============


def main():
    """Main entry point for PyTauri backend"""
    print("[Speekium] ================================================")
    print("[Speekium] PyTauri Backend Starting...")
    print("[Speekium] ================================================")
    print(f"[Speekium] Default Config: {list(DEFAULT_CONFIG.keys())}")
    print("[Speekium] Config File: config.json")
    print("[Speekium] Audio Recording: VAD + SenseVoice ASR")
    print("[Speekium] Recording Modes: continuous, push-to-talk")
    print("[Speekium] LLM Backends: Claude, Ollama")
    print("[Speekium] TTS Backends: Edge (online, MP3), Piper (offline, WAV)")
    print("[Speekium] ================================================")
    print("[Speekium] Registered Commands:")
    print("  Config Commands:")
    print("    - config_load")
    print("    - config_save")
    print("    - config_get")
    print("    - config_update")
    print("    - config_bulk_update")
    print("  Legacy Config Commands:")
    print("    - get_config (use config_load/config_get instead)")
    print("    - save_config (use config_update instead)")
    print("  Recording Commands:")
    print("    - start_recording (VAD-based with ASR)")
    print("  LLM Commands:")
    print("    - load_llm (load/reload LLM backend)")
    print("    - chat_generator (streaming chat)")
    print("  TTS Commands:")
    print("    - generate_tts (generate audio from text)")
    print("    - play_tts (play base64 encoded audio)")
    print("  History Commands:")
    print("    - clear_history")
    print("[Speekium] ================================================")


if __name__ == "__main__":
    main()
