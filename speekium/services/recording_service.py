"""
Recording Service

Manages audio recording state and coordinates recording operations.

Note: This service provides state management and progress reporting for
recording operations. The actual recording is handled by the recording
module (speekium.recording) which has its own API optimized for the
voice assistant workflow.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from logger import get_logger

from .base import BaseService, ProgressEvent, ServiceConfig

logger = get_logger(__name__)


class RecordingState(Enum):
    """Recording state."""

    IDLE = "idle"
    STARTING = "starting"
    RECORDING = "recording"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RecordingServiceConfig(ServiceConfig):
    """Recording service config."""

    name: str = "recording"
    enabled: bool = True
    sample_rate: int = 16000
    channels: int = 1
    max_duration: float = 300.0  # 5 minutes max


@dataclass
class RecordingResult:
    """Result of a recording operation."""

    success: bool
    duration: float = 0.0
    error: Optional[str] = None


class RecordingService(BaseService):
    """
    Audio recording service.

    Manages:
    - Recording state tracking
    - Progress reporting for recording operations
    - Recording lifecycle coordination

    Note: Actual audio recording is performed by the recording module.
    This service coordinates and tracks the recording state.
    """

    def __init__(
        self,
        config: RecordingServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        super().__init__(config, progress_callback)
        self.sample_rate = config.sample_rate
        self.channels = config.channels
        self.max_duration = config.max_duration

        # State
        self._state = RecordingState.IDLE
        self._recording_start_time: Optional[float] = None
        self._recording_stop_event: Optional[asyncio.Event] = None

    @property
    def state(self) -> RecordingState:
        """Get current recording state."""
        return self._state

    async def _on_initialize(self) -> None:
        """Initialize recording service."""
        self._emit_progress("initializing", 0.0, "Initializing recording service")
        # The recording module handles its own initialization
        self._emit_progress("initialized", 1.0, "Recording service ready")

    async def _on_start(self) -> None:
        """Start recording service."""
        self._state = RecordingState.IDLE

    async def _on_stop(self) -> None:
        """Stop recording service."""
        # Signal any ongoing recording to stop
        if self._recording_stop_event:
            self._recording_stop_event.set()

    async def _on_shutdown(self) -> None:
        """Release recording resources."""
        await self._on_stop()

    def set_state(self, state: RecordingState) -> None:
        """
        Set recording state (used by recording module).

        Args:
            state: New recording state
        """
        old_state = self._state
        self._state = state

        if state == RecordingState.RECORDING and old_state != RecordingState.RECORDING:
            self._recording_start_time = asyncio.get_event_loop().time()
            self._emit_progress("recording_started", 0.0, "Recording started")

        elif state == RecordingState.STOPPED and old_state == RecordingState.RECORDING:
            if self._recording_start_time:
                duration = asyncio.get_event_loop().time() - self._recording_start_time
                self._emit_progress("recording_stopped", 1.0, f"Recording stopped: {duration:.1f}s")

        logger.info("recording_state_changed", from_state=old_state.value, to_state=state.value)

    def create_stop_event(self) -> asyncio.Event:
        """
        Create a new stop event for recording.

        Returns:
            New asyncio.Event for signaling recording stop
        """
        self._recording_stop_event = asyncio.Event()
        return self._recording_stop_event

    async def wait_for_stop(self, timeout: float = 10.0) -> bool:
        """
        Wait for recording to stop.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if recording stopped, False if timeout
        """
        if not self._recording_stop_event:
            return False

        try:
            await asyncio.wait_for(self._recording_stop_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("recording_stop_timeout")
            return False

    def signal_stop(self) -> None:
        """Signal recording to stop."""
        if self._recording_stop_event:
            self._recording_stop_event.set()

    def emit_recording_progress(self, audio_level: float, duration: float) -> None:
        """
        Emit recording progress event.

        Args:
            audio_level: Current audio level in dB
            duration: Recording duration in seconds
        """
        progress = min(duration / self.max_duration, 1.0)
        self._emit_progress("recording", progress, f"{audio_level:.1f} dB")

    async def health_check(self) -> bool:
        """Check if recording service is healthy."""
        try:
            return self._is_initialized and self._state in (
                RecordingState.IDLE,
                RecordingState.STOPPED,
            )
        except Exception:
            return False
