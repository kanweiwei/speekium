"""Tests for speekium.utils module"""

import os
import stat
import tempfile
from pathlib import Path

import pytest

from speekium.utils import create_secure_temp_file, cleanup_temp_files
from speekium import utils


class TestSecureTempFile:
    """Test secure temporary file creation and cleanup."""

    def test_create_temp_file(self):
        """Test creating a temporary file."""
        path = create_secure_temp_file(suffix=".test")

        # File should exist
        assert os.path.exists(path)

        # Should end with specified suffix
        assert path.endswith(".test")

        # Should be tracked
        assert path in utils._temp_files

        # Clean up
        os.remove(path)
        utils._temp_files.remove(path)

    def test_temp_file_has_secure_permissions(self):
        """Test that temp files have 0600 permissions (owner only)."""
        path = create_secure_temp_file()

        try:
            # Check file permissions
            file_stat = os.stat(path)
            mode = file_stat.st_mode

            # On Unix, 0600 means owner read/write only
            # Check that group and others have no permissions
            group_perms = stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP
            other_perms = stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH

            assert not (mode & group_perms), "Group should have no permissions"
            assert not (mode & other_perms), "Others should have no permissions"

            # Owner should have read and write
            owner_read = stat.S_IRUSR & mode
            owner_write = stat.S_IWUSR & mode
            assert owner_read, "Owner should have read permission"
            assert owner_write, "Owner should have write permission"
        finally:
            os.remove(path)
            utils._temp_files.remove(path)

    def test_cleanup_temp_files(self):
        """Test cleanup of all tracked temporary files."""
        # Create multiple temp files
        files = []
        for i in range(3):
            path = create_secure_temp_file(suffix=f".test{i}")
            files.append(path)

        # All should exist
        for path in files:
            assert os.path.exists(path)

        # Cleanup
        cleanup_temp_files()

        # All should be removed
        for path in files:
            assert not os.path.exists(path)

        # Tracking list should be empty
        assert len(utils._temp_files) == 0

    def test_cleanup_nonexistent_file(self):
        """Test cleanup handles already deleted files gracefully."""
        path = create_secure_temp_file()

        # Delete file manually before cleanup
        os.remove(path)

        # Should not raise error
        cleanup_temp_files()

        assert len(utils._temp_files) == 0

    def test_cleanup_with_invalid_path(self):
        """Test cleanup handles various error conditions."""
        path = create_secure_temp_file()

        # Make path invalid (e.g., delete and create directory with same name)
        os.remove(path)
        os.mkdir(path)

        # Should log warning but not crash
        cleanup_temp_files()

        # Clean up directory
        os.rmdir(path)

        assert len(utils._temp_files) == 0
