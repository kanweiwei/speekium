"""
Voice Activity Detection (VAD) module.

Provides VAD model loading and configuration management.
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch

from logger import get_logger

if TYPE_CHECKING:
    import torch.nn

logger = get_logger(__name__)

# ===== VAD Config =====
VAD_THRESHOLD = 0.5  # Voice detection threshold (0.0-1.0, lower = more sensitive)  # noqa: E501
VAD_CONSECUTIVE_THRESHOLD = (
    3  # Consecutive detections to confirm speech start (lower = faster response)
)
VAD_PRE_BUFFER = 0.3  # Pre-buffer duration (seconds) to capture speech start
MIN_SPEECH_DURATION = 0.4  # Minimum speech duration (seconds) - increased
SILENCE_AFTER_SPEECH = 0.8  # Silence duration to stop recording (seconds)
MAX_RECORDING_DURATION = 30  # Maximum recording duration (seconds)
INTERRUPT_CHECK_DURATION = 1.5  # Duration to check for speech continuation after pause (seconds)
INITIAL_SPEECH_TIMEOUT = 60  # Maximum time to wait for initial speech to start (seconds)


def load_vad_config(config: dict | None = None) -> dict:
    """
    Load VAD configuration from config dict.

    Args:
        config: Configuration dictionary from ConfigManager

    Returns:
        Dictionary with VAD configuration values
    """
    if config is None:
        try:
            from config_manager import ConfigManager

            config = ConfigManager.load()
        except Exception as e:
            logger.warning("vad_config_load_failed", error=str(e), fallback="default")
            config = {}

    return {
        "threshold": config.get("vad_threshold", VAD_THRESHOLD),
        "consecutive_threshold": config.get("vad_consecutive_threshold", VAD_CONSECUTIVE_THRESHOLD),
        "silence_duration": config.get("vad_silence_duration", SILENCE_AFTER_SPEECH),
        "pre_buffer": config.get("vad_pre_buffer", VAD_PRE_BUFFER),
        "min_speech_duration": config.get("vad_min_speech_duration", MIN_SPEECH_DURATION),
        "max_recording_duration": config.get("vad_max_recording_duration", MAX_RECORDING_DURATION),
    }


def check_vad_model_exists() -> tuple[bool, str]:
    """
    Check if VAD model file exists in cache.

    Returns:
        Tuple of (exists, path) where exists is True if model is found,
        and path is the model directory path
    """
    # torch.hub stores models differently depending on version
    # Return the model root directory, not the file path

    # Option 1: Newer torch.hub uses checkpoints/ directory
    cache_dir = Path.home() / ".cache" / "torch" / "hub"
    checkpoints_dir = cache_dir / "checkpoints"
    if checkpoints_dir.exists():
        # Return the checkpoints directory as the model "root"
        return True, str(checkpoints_dir)

    # Option 2: Older torch.hub uses repo_model directory
    repo_dir = cache_dir / "snakers4_silero-vad_master"
    if repo_dir.exists():
        return True, str(repo_dir)

    return False, str(cache_dir / "checkpoints" / "silero_vad.onnx")


def load_vad(
    existing_vad_model=None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> torch.nn.Module:
    """
    Load the Silero VAD model.

    Args:
        existing_vad_model: Existing VAD model instance (will be returned if not None)
        on_progress: Optional callback for progress updates (model, current, total)

    Returns:
        Loaded VAD model
    """
    if existing_vad_model is not None:
        return existing_vad_model

    from logger import set_component

    set_component("VAD")

    # Check if model is already downloaded
    model_exists, model_path = check_vad_model_exists()

    if not model_exists:
        logger.info("download_started", model="Silero VAD", status="downloading", size="~60MB")

    logger.info("model_loading", model="VAD")

    # Load VAD model with retry logic for PyTorch Hub rate limit
    max_retries = 5
    vad_model: Any = None
    for attempt in range(max_retries):
        try:
            hub_result = torch.hub.load(  # nosec B614
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            # torch.hub.load may return tuple or single value
            if isinstance(hub_result, tuple):
                vad_model = hub_result[0]
            else:
                vad_model = hub_result
            logger.info("model_loaded", model="VAD", attempt=attempt + 1)
            break
        except Exception as e:
            error_str = str(e)
            logger.warning("vad_load_attempt_failed", attempt=attempt + 1, error=error_str[:100])

            # Check if it's a rate limit or authorization error
            is_rate_limit = (
                "rate limit" in error_str.lower()
                or "403" in error_str
                or "authorization" in error_str.lower()
            )
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = 15 * (attempt + 1)  # 15s, 30s, 45s, 60s, 75s
                logger.warning(
                    "vad_rate_limited",
                    retry_in=f"{wait_time}s",
                    message="PyTorch Hub is rate limited, waiting...",
                )
                time.sleep(wait_time)
                continue

            raise Exception(f"VAD model loading failed: {error_str}") from e

    logger.info("model_loaded", model="VAD")
    return vad_model  # type: ignore


def get_model_status(vad_model=None) -> dict:
    """
    Get status information for VAD model.

    Args:
        vad_model: Current VAD model instance

    Returns:
        Dictionary with model status
    """
    exists, path = check_vad_model_exists()

    status = {
        "loaded": vad_model is not None,
        "name": "Silero VAD",
        "exists": exists,
        "path": path,
    }

    if exists:
        status["size"] = _get_size_str(path)
    else:
        status["size"] = "0 B"

    return status


def _get_size_str(path: str) -> str:
    """Get human-readable size string for a file or directory."""
    from pathlib import Path

    path_obj = Path(path)
    if not path_obj.exists():
        return "0 B"

    if path_obj.is_file():
        size = path_obj.stat().st_size
    elif path_obj.is_dir():
        size = sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())
    else:
        return "0 B"

    # Convert to human-readable format
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
