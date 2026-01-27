"""
Utility functions for Speekium voice assistant.

Provides secure temporary file management.
"""

import atexit
import os
import stat
import tempfile

from logger import get_logger

logger = get_logger(__name__)

# ===== Security: Temporary File Management =====
_temp_files: list[str] = []


def create_secure_temp_file(suffix: str = ".tmp") -> str:
    """
    Create a temporary file with secure permissions (0600 - owner read/write only)

    Args:
        suffix: File extension

    Returns:
        Path to the temporary file
    """
    # Create temp file with delete=False (we'll manage cleanup manually)
    fd, path = tempfile.mkstemp(suffix=suffix)

    # Set secure permissions: 0600 (owner read/write only)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    # Close the file descriptor
    os.close(fd)

    # Track for cleanup
    _temp_files.append(path)

    return path


def cleanup_temp_files():
    """Clean up all temporary files created by this session"""
    for path in _temp_files:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.info("temp_file_cleaned", file_path=path)
        except Exception as e:
            logger.warning("temp_file_cleanup_failed", file_path=path, error=str(e))

    _temp_files.clear()


# Register cleanup on exit
atexit.register(cleanup_temp_files)
