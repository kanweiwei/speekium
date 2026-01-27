"""
Download progress tracking for model downloads.

Provides classes to track and log model download progress from
HuggingFace and ModelScope.
"""

import time
from typing import TYPE_CHECKING

from logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    import huggingface_hub.utils


class DownloadProgressTracker:
    """Track and emit HuggingFace model download progress"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.last_emit_time = 0
        self.start_time = 0
        self.file_count = 0
        self.total_files = 0

    def start(self):
        """Initialize download tracking"""
        self.start_time = time.time()
        self.last_emit_time = 0
        logger.info("download_started", model=self.model_name, status="downloading")

    def on_progress(self, progress: "huggingface_hub.utils.Progress"):
        """Called by huggingface_hub during download"""
        current_time = time.time()
        # Emit update every 0.5 seconds (not every byte)
        if current_time - self.last_emit_time < 0.5:
            return

        self.last_emit_time = current_time
        downloaded = progress.downloaded if hasattr(progress, "downloaded") else 0
        total = progress.total if hasattr(progress, "total") else 0

        if total > 0:
            percent = int(downloaded / total * 100)
            # Calculate speed (bytes/second)
            elapsed = current_time - self.start_time
            speed = downloaded / elapsed if elapsed > 0 else 0

            # Format speed
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"

            # Format size
            if total > 1024 * 1024:
                total_str = f"{total / (1024 * 1024):.1f} MB"
            elif total > 1024:
                total_str = f"{total / 1024:.1f} KB"
            else:
                total_str = f"{total} B"

            logger.info(
                "download_progress",
                model=self.model_name,
                percent=percent,
                downloaded=downloaded,
                total=total,
                speed=speed_str,
                total_size=total_str,
            )

    def complete(self):
        """Mark download as complete"""
        elapsed = 0
        if self.start_time:
            elapsed = time.time() - self.start_time

        logger.info(
            "download_completed",
            model=self.model_name,
            elapsed_seconds=int(elapsed),
            status="completed",
        )


class ModelScopeProgressCallback:
    """Custom ModelScope progress callback that emits JSON logs for frontend"""

    def __init__(self, filename: str, file_size: int, model_name: str = "SenseVoice ASR"):
        self.filename = filename
        self.file_size = file_size
        self.model_name = model_name
        self.downloaded = 0
        self.start_time = time.time()
        self.last_emit_time = 0

    def update(self, size: int):
        """Called by ModelScope during download"""
        self.downloaded += size
        current_time = time.time()

        # Emit update every 0.5 seconds
        if current_time - self.last_emit_time < 0.5:
            return

        self.last_emit_time = current_time

        if self.file_size > 0:
            percent = int(self.downloaded / self.file_size * 100)
            # Calculate speed
            elapsed = current_time - self.start_time
            speed = self.downloaded / elapsed if elapsed > 0 else 0

            # Format speed
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed:.0f} B/s"

            # Format size
            if self.file_size > 1024 * 1024:
                total_str = f"{self.file_size / (1024 * 1024):.1f} MB"
            elif self.file_size > 1024:
                total_str = f"{self.file_size / 1024:.1f} KB"
            else:
                total_str = f"{self.file_size} B"

            logger.info(
                "download_progress",
                model=self.model_name,
                percent=percent,
                downloaded=self.downloaded,
                total=self.file_size,
                speed=speed_str,
                total_size=total_str,
            )

    def end(self):
        """Called when download completes"""
        elapsed = 0
        if self.start_time:
            elapsed = time.time() - self.start_time

        logger.info(
            "download_completed",
            model=self.model_name,
            elapsed_seconds=int(elapsed),
            status="completed",
        )
