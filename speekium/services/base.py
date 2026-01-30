"""
Base service class for all Speekium services.

Provides common functionality like:
- Service lifecycle (initialize, start, stop, shutdown)
- Progress reporting
- Error handling
- Logging
"""

import abc
import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional

from logger import get_logger

logger = get_logger(__name__)


@dataclass
class ServiceConfig:
    """Base configuration for all services."""

    name: str
    enabled: bool = True


@dataclass
class ProgressEvent:
    """Progress event for service operations."""

    service: str
    stage: str
    progress: float  # 0.0 to 1.0
    message: str


class ServiceError(Exception):
    """Base exception for service errors."""

    def __init__(self, service: str, message: str, details: Optional[dict] = None):
        self.service = service
        self.message = message
        self.details = details or {}
        super().__init__(f"[{service}] {message}")


class ServiceInitializationError(ServiceError):
    """Raised when a service fails to initialize."""

    def __init__(self, service: str, message: str, details: Optional[dict] = None):
        super().__init__(service, f"Initialization failed: {message}", details)


class BaseService(abc.ABC):
    """
    Abstract base class for all services.

    All services must implement these lifecycle methods:
    - initialize(): Set up resources and configurations
    - start(): Begin service operation
    - stop(): Pause service operation
    - shutdown(): Release all resources
    """

    def __init__(
        self,
        config: ServiceConfig,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ):
        """
        Initialize the service.

        Args:
            config: Service configuration
            progress_callback: Optional callback for progress events
        """
        self.config = config
        self._progress_callback = progress_callback
        self._is_initialized = False
        self._is_running = False
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Get service name."""
        return self.config.name

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized."""
        return self._is_initialized

    @property
    def is_running(self) -> bool:
        """Check if service is running."""
        return self._is_running

    async def initialize(self) -> None:
        """
        Initialize the service.

        This method should be called once before using the service.
        It loads configurations, initializes resources, and validates the service state.

        Raises:
            ServiceInitializationError: If initialization fails
        """
        if self._is_initialized:
            logger.debug("service_already_initialized", service=self.name)
            return

        logger.info("service_initializing", service=self.name)

        try:
            await self._on_initialize()
            self._is_initialized = True
            logger.info("service_initialized", service=self.name)
        except Exception as e:
            logger.error(
                "service_init_failed",
                service=self.name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ServiceInitializationError(self.name, str(e)) from e

    async def start(self) -> None:
        """
        Start the service.

        Raises:
            ServiceError: If service is not initialized or start fails
        """
        if not self._is_initialized:
            raise ServiceError(self.name, "Cannot start: service not initialized")

        if self._is_running:
            logger.debug("service_already_running", service=self.name)
            return

        logger.info("service_starting", service=self.name)

        try:
            await self._on_start()
            self._is_running = True
            logger.info("service_started", service=self.name)
        except Exception as e:
            logger.error(
                "service_start_failed",
                service=self.name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ServiceError(self.name, f"Failed to start: {e}") from e

    async def stop(self) -> None:
        """Stop the service."""
        if not self._is_running:
            logger.debug("service_not_running", service=self.name)
            return

        logger.info("service_stopping", service=self.name)

        try:
            await self._on_stop()
            self._is_running = False
            logger.info("service_stopped", service=self.name)
        except Exception as e:
            logger.error(
                "service_stop_failed",
                service=self.name,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise ServiceError(self.name, f"Failed to stop: {e}") from e

    async def shutdown(self) -> None:
        """
        Shutdown the service and release all resources.

        This should be called when the service is no longer needed.
        """
        if not self._is_initialized:
            return

        logger.info("service_shutting_down", service=self.name)

        # Stop if running
        if self._is_running:
            await self.stop()

        try:
            await self._on_shutdown()
        finally:
            self._is_initialized = False
            logger.info("service_shutdown", service=self.name)

    def _emit_progress(self, stage: str, progress: float, message: str) -> None:
        """Emit a progress event if callback is configured."""
        if self._progress_callback:
            try:
                event = ProgressEvent(
                    service=self.name,
                    stage=stage,
                    progress=progress,
                    message=message,
                )
                self._progress_callback(event)
            except Exception as e:
                logger.warning(
                    "progress_callback_failed",
                    service=self.name,
                    error=str(e),
                )

    # Abstract methods to be implemented by subclasses
    @abc.abstractmethod
    async def _on_initialize(self) -> None:
        """Initialize service-specific resources."""

    @abc.abstractmethod
    async def _on_start(self) -> None:
        """Start service-specific operation."""

    @abc.abstractmethod
    async def _on_stop(self) -> None:
        """Stop service-specific operation."""

    @abc.abstractmethod
    async def _on_shutdown(self) -> None:
        """Release service-specific resources."""

    async def health_check(self) -> bool:
        """
        Check if the service is healthy.

        Returns:
            True if the service is operational, False otherwise
        """
        return self._is_initialized and self._is_running

    def get_status(self) -> dict[str, Any]:
        """
        Get service status information.

        Returns:
            Dictionary with service status details
        """
        return {
            "name": self.name,
            "enabled": self.config.enabled,
            "initialized": self._is_initialized,
            "running": self._is_running,
        }
