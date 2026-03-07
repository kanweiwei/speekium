"""
Error Tracker for Speekium
Collects and stores runtime errors for analysis
"""

import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# Error severity levels
ERROR_LEVELS = {
    "error": "Error",
    "warning": "Warning", 
    "info": "Info"
}


class ErrorRecord:
    """Single error record"""
    
    def __init__(
        self,
        level: str,
        message: str,
        error_type: str,
        context: dict | None = None,
        stack_trace: str | None = None
    ):
        self.timestamp = datetime.now().isoformat()
        self.level = level
        self.message = message
        self.error_type = error_type
        self.context = context or {}
        self.stack_trace = stack_trace
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "error_type": self.error_type,
            "context": self.context,
            "stack_trace": self.stack_trace
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ErrorTracker:
    """
    Error tracker for collecting runtime errors.
    
    Features:
    - Local storage of errors
    - Context preservation
    - Privacy filtering
    """
    
    def __init__(self, storage_path: str | None = None):
        """
        Initialize error tracker.
        
        Args:
            storage_path: Path to store error logs. Defaults to ~/.speekium/errors/
        """
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            self.storage_path = Path.home() / ".speekium" / "errors"
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._errors_file = self.storage_path / "errors.jsonl"
        
        # Privacy-sensitive keys to filter
        self._sensitive_keys = {
            "api_key", "api_key", "password", "token", "secret",
            "Authorization", "content", "history", "messages"
        }
    
    def _filter_sensitive(self, data: dict) -> dict:
        """Remove sensitive information from context."""
        filtered = {}
        for key, value in data.items():
            # Skip sensitive keys
            if any(s in key.lower() for s in self._sensitive_keys):
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive(value)
            else:
                filtered[key] = value
        return filtered
    
    def capture(
        self,
        error: Exception | str,
        level: str = "error",
        context: dict | None = None
    ) -> ErrorRecord:
        """
        Capture an error.
        
        Args:
            error: Exception object or error message string
            level: Error level (error/warning/info)
            context: Additional context about the error
            
        Returns:
            ErrorRecord object
        """
        # Extract error info
        if isinstance(error, Exception):
            error_type = type(error).__name__
            message = str(error)
            stack_trace = traceback.format_exc()
        else:
            error_type = "RuntimeError"
            message = str(error)
            stack_trace = None
        
        # Filter sensitive data from context
        filtered_context = self._filter_sensitive(context or {})
        
        # Create record
        record = ErrorRecord(
            level=level,
            message=message,
            error_type=error_type,
            context=filtered_context,
            stack_trace=stack_trace
        )
        
        # Save to storage
        self._save_record(record)
        
        return record
    
    def _save_record(self, record: ErrorRecord):
        """Save error record to file."""
        try:
            with open(self._errors_file, "a", encoding="utf-8") as f:
                f.write(record.to_json() + "\n")
        except Exception as e:
            print(f"Failed to save error record: {e}")
    
    def get_errors(self, limit: int = 100) -> list[ErrorRecord]:
        """
        Get recent errors.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of ErrorRecord objects
        """
        errors = []
        
        if not self._errors_file.exists():
            return errors
        
        try:
            with open(self._errors_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for line in reversed(lines):
                if len(errors) >= limit:
                    break
                try:
                    data = json.loads(line)
                    errors.append(ErrorRecord(
                        level=data.get("level", "error"),
                        message=data.get("message", ""),
                        error_type=data.get("error_type", "Unknown"),
                        context=data.get("context", {}),
                        stack_trace=data.get("stack_trace")
                    ))
                except json.JSONDecodeError:
                    continue
                    
        except Exception as e:
            print(f"Failed to read errors: {e}")
        
        return errors
    
    def clear_errors(self):
        """Clear all stored errors."""
        try:
            if self._errors_file.exists():
                self._errors_file.unlink()
        except Exception as e:
            print(f"Failed to clear errors: {e}")


# Global instance
_error_tracker: ErrorTracker | None = None


def get_error_tracker() -> ErrorTracker:
    """Get global error tracker instance."""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker
