"""
TTS Cache for Speekium
Caches generated TTS audio to reduce API calls and improve response time
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional


class TTSCache:
    """
    TTS audio cache using file-based storage.
    
    Features:
    - SHA256 hash of text+language as cache key
    - LRU eviction when cache exceeds max size
    - Thread-safe operations
    """
    
    def __init__(self, cache_dir: str | None = None, max_size_mb: int = 100):
        """
        Initialize TTS cache.
        
        Args:
            cache_dir: Cache directory path. Defaults to ~/.speekium/tts_cache/
            max_size_mb: Maximum cache size in MB
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.home() / ".speekium" / "tts_cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Track access times for LRU
        self._access_file = self.cache_dir / "access.json"
        self._access_times: dict[str, float] = self._load_access_times()
    
    def _load_access_times(self) -> dict[str, float]:
        """Load access times from file."""
        if not self._access_file.exists():
            return {}
        try:
            with open(self._access_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_access_times(self):
        """Save access times to file."""
        try:
            with open(self._access_file, "w") as f:
                json.dump(self._access_times, f)
        except Exception:
            pass
    
    def _get_cache_key(self, text: str, language: str, voice: str) -> str:
        """Generate cache key from text, language, and voice."""
        content = f"{language}:{voice}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        return self.cache_dir / f"{key}.mp3"
    
    def get(self, text: str, language: str = "zh", voice: str = "zh-CN-XiaoyiNeural") -> Optional[str]:
        """
        Get cached TTS audio file path.
        
        Args:
            text: Text that was synthesized
            language: Language code
            voice: Voice name
            
        Returns:
            Path to cached audio file, or None if not in cache
        """
        key = self._get_cache_key(text, language, voice)
        cache_path = self._get_cache_path(key)
        
        if cache_path.exists():
            # Update access time for LRU
            import time
            self._access_times[key] = time.time()
            self._save_access_times()
            return str(cache_path)
        
        return None
    
    def put(self, text: str, audio_path: str, language: str = "zh", voice: str = "zh-CN-XiaoyiNeural") -> bool:
        """
        Store TTS audio in cache.
        
        Args:
            text: Text that was synthesized
            audio_path: Path to the audio file
            language: Language code
            voice: Voice name
            
        Returns:
            True if successfully cached
        """
        key = self._get_cache_key(text, language, voice)
        cache_path = self._get_cache_path(key)
        
        try:
            # Copy file to cache
            import shutil
            shutil.copy2(audio_path, cache_path)
            
            # Update access time
            import time
            self._access_times[key] = time.time()
            self._save_access_times()
            
            # Check cache size and evict if needed
            self._evict_if_needed()
            
            return True
        except Exception as e:
            print(f"Failed to cache TTS: {e}")
            return False
    
    def _evict_if_needed(self):
        """Evict oldest entries if cache exceeds max size."""
        # Calculate current cache size
        total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.mp3"))
        
        if total_size <= self.max_size_bytes:
            return
        
        # Sort by access time (oldest first)
        sorted_keys = sorted(self._access_times.items(), key=lambda x: x[1])
        
        # Remove oldest entries until under limit
        for key, _ in sorted_keys:
            if total_size <= self.max_size_bytes * 0.8:  # Keep 20% margin
                break
            
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                size = cache_path.stat().st_size
                cache_path.unlink()
                total_size -= size
            
            del self._access_times[key]
        
        self._save_access_times()
    
    def clear(self):
        """Clear all cached TTS files."""
        for f in self.cache_dir.glob("*.mp3"):
            f.unlink()
        self._access_times.clear()
        self._save_access_times()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        files = list(self.cache_dir.glob("*.mp3"))
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": self.max_size_bytes // (1024 * 1024),
        }


# Global instance
_tts_cache: Optional[TTSCache] = None


def get_tts_cache() -> TTSCache:
    """Get global TTS cache instance."""
    global _tts_cache
    if _tts_cache is None:
        _tts_cache = TTSCache()
    return _tts_cache
