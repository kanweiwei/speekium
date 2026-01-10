"""
Speekium TTS Engine Module for Tauri Backend
Async-ready TTS with Edge and Piper backends
"""

import asyncio
import base64
import io
import logging
import os
import wave
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

from pydantic import BaseModel, Field


# ============ Configuration Constants ============

DEFAULT_LANGUAGE = "zh"

# Edge TTS Voices (online)
EDGE_TTS_VOICES = {
    "zh": "zh-CN-XiaoyiNeural",  # Chinese female
    "en": "en-US-JennyNeural",  # English female
    "ja": "ja-JP-NanamiNeural",  # Japanese female
    "ko": "ko-KR-SunHiNeural",  # Korean female
    "yue": "zh-HK-HiuGaaiNeural",  # Cantonese female
}

# Piper TTS Config (offline)
PIPER_VOICES = {
    "zh": "zh_CN-huayan-medium",  # Chinese female
    "en": "en_US-amy-medium",  # English female
}
PIPER_DATA_DIR = os.path.expanduser("~/.local/share/piper-voices")


# ============ Pydantic Models ============


class TTSRequest(BaseModel):
    """Request for TTS generation"""

    text: str = Field(description="Text to convert to speech")
    language: str = Field(default="zh", description="Language code")
    backend: str = Field(
        default="edge",
        description="Backend: 'edge' (online) or 'piper' (offline)",
    )
    voice: Optional[str] = Field(
        default=None, description="Override voice selection (optional)"
    )
    rate: str = Field(default="+0%", description="Speech rate for Edge TTS")


class TTSResult(BaseModel):
    """Result from TTS generation"""

    success: bool
    audio_base64: Optional[str] = None
    format: Optional[str] = None
    error: Optional[str] = None


# ============ TTS Engine Class ============


class TTSEngine:
    """TTS engine with Edge and Piper backends"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.piper_voices = {}  # Cache for loaded Piper voices

    def detect_text_language(self, text: str) -> str:
        """Detect language from text content (simple character-based detection)."""
        if not text:
            return DEFAULT_LANGUAGE

        # Count Chinese characters
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        total_chars = len(text.strip())

        if total_chars == 0:
            return DEFAULT_LANGUAGE

        # If more than 30% Chinese, treat as Chinese
        if chinese_chars / total_chars > 0.3:
            return "zh"
        elif any(c in text for c in "ぁァー"):  # Japanese hiragana/katakana
            return "ja"
        elif any(c in text for c in "가-힣"):  # Korean
            return "ko"
        else:
            return "en"

    def load_piper_voice(self, language: str) -> Optional[object]:
        """Load Piper voice model for specified language."""
        if language in self.piper_voices:
            return self.piper_voices[language]

        voice_name = PIPER_VOICES.get(language, PIPER_VOICES.get("en"))
        model_path = os.path.join(PIPER_DATA_DIR, f"{voice_name}.onnx")

        if not os.path.exists(model_path):
            self.logger.warning(f"Piper model not found: {model_path}")
            self.logger.info(
                "Download from: https://huggingface.co/rhasspy/piper-voices/tree/main"
            )
            return None

        try:
            from piper.voice import PiperVoice

            self.logger.info(f"Loading Piper voice: {voice_name}...")
            voice = PiperVoice.load(model_path)
            self.piper_voices[language] = voice
            self.logger.info("Piper voice loaded")
            return voice
        except ImportError:
            self.logger.warning("piper-tts not installed. Run: pip install piper-tts")
            return None
        except Exception as e:
            self.logger.error(f"Failed to load Piper voice: {e}")
            return None

    async def generate_async(self, request: TTSRequest) -> TTSResult:
        """Generate TTS audio asynchronously.

        Args:
            request: TTS request with text, language, backend, etc.

        Returns:
            TTSResult with base64 encoded audio
        """
        try:
            # Auto-detect language if needed
            detected_lang = (
                request.language
                if request.language != "auto"
                else self.detect_text_language(request.text)
            )

            self.logger.info(
                f"[TTS] Generating: backend={request.backend}, "
                f"language={detected_lang}, text={request.text[:50]}..."
            )

            # Route to appropriate backend
            if request.backend == "piper":
                return await self._generate_piper(request, detected_lang)
            else:  # Default to edge
                return await self._generate_edge(request, detected_lang)

        except Exception as e:
            self.logger.error(f"[TTS] Generation error: {e}", exc_info=True)
            return TTSResult(success=False, error=str(e))

    async def _generate_edge(self, request: TTSRequest, language: str) -> TTSResult:
        """Generate audio using Edge TTS (online, async native).

        Args:
            request: TTS request
            language: Detected language code

        Returns:
            TTSResult with MP3 audio (base64)
        """
        try:
            import edge_tts

            # Select voice
            voice = request.voice or EDGE_TTS_VOICES.get(
                language, EDGE_TTS_VOICES[DEFAULT_LANGUAGE]
            )

            # Generate audio
            communicate = edge_tts.Communicate(request.text, voice, rate=request.rate)
            audio_bytes = b""

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes += chunk["data"]

            # Convert to base64
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

            self.logger.info(f"[TTS] Edge TTS generated: {len(audio_bytes)} bytes")

            return TTSResult(
                success=True, audio_base64=base64_audio, format="audio/mp3"
            )

        except Exception as e:
            self.logger.error(f"[TTS] Edge TTS error: {e}")
            # Try fallback to Piper if available
            self.logger.info("[TTS] Attempting fallback to Piper TTS...")
            return await self._generate_piper(request, language)

    async def _generate_piper(self, request: TTSRequest, language: str) -> TTSResult:
        """Generate audio using Piper TTS (offline, blocking).

        Args:
            request: TTS request
            language: Detected language code

        Returns:
            TTSResult with WAV audio (base64)
        """
        try:
            voice = self.load_piper_voice(language)

            if voice is None:
                # Piper not available, try fallback to Edge TTS
                self.logger.warning(
                    "[TTS] Piper not available, falling back to Edge TTS"
                )
                if request.backend == "piper":
                    # Original request was for Piper, now try Edge
                    fallback_request = request.model_copy(update={"backend": "edge"})
                    return await self._generate_edge(fallback_request, language)
                else:
                    raise RuntimeError("Piper voice not loaded")

            # Run blocking Piper synthesis in executor
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(
                self.executor, self._synthesize_piper, voice, request.text
            )

            # Convert to base64
            base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

            self.logger.info(f"[TTS] Piper TTS generated: {len(audio_bytes)} bytes")

            return TTSResult(
                success=True, audio_base64=base64_audio, format="audio/wav"
            )

        except Exception as e:
            self.logger.error(f"[TTS] Piper TTS error: {e}")
            # If Piper fails and request was for Piper, try Edge fallback
            if request.backend == "piper":
                self.logger.info("[TTS] Piper failed, trying Edge TTS fallback...")
                fallback_request = request.model_copy(update={"backend": "edge"})
                return await self._generate_edge(fallback_request, language)
            else:
                return TTSResult(success=False, error=str(e))

    def _synthesize_piper(self, voice, text: str) -> bytes:
        """Synchronous Piper synthesis.

        Args:
            voice: Loaded PiperVoice object
            text: Text to synthesize

        Returns:
            WAV audio as bytes
        """
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wav_file:
                voice.synthesize(text, wav_file)
            buffer.seek(0)
            return buffer.read()

    async def play_audio_async(self, audio_base64: str, audio_format: str) -> None:
        """Play audio from base64 encoded data.

        Args:
            audio_base64: Base64 encoded audio data
            audio_format: Audio MIME type (e.g., "audio/mp3", "audio/wav")
        """
        tmp_file = None
        try:
            # Decode base64
            audio_bytes = base64.b64decode(audio_base64)

            # Write to temporary file
            import tempfile

            ext = "mp3" if audio_format == "audio/mp3" else "wav"
            with tempfile.NamedTemporaryFile(
                suffix=f".{ext}", delete=False, mode="wb"
            ) as f:
                f.write(audio_bytes)
                tmp_file = f.name

            # Play using platform-specific command
            import platform

            system = platform.system()
            if system == "Darwin":  # macOS
                cmd = ["afplay", tmp_file]
            elif system == "Linux":
                cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_file]
            elif system == "Windows":
                cmd = [
                    "powershell",
                    "-c",
                    f"(New-Object Media.SoundPlayer '{tmp_file}').PlaySync()",
                ]
            else:
                self.logger.warning(f"Unsupported platform: {system}")
                return

            # Run playback
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.wait()

        except Exception as e:
            self.logger.error(f"[TTS] Playback error: {e}", exc_info=True)
        finally:
            # Clean up temp file
            if tmp_file is not None and os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

    async def shutdown(self):
        """Cleanup resources."""
        self.executor.shutdown(wait=True)
        self.piper_voices.clear()
        self.logger.info("TTS engine shut down")


# ============ Global Instance ============

_tts_engine: Optional[TTSEngine] = None


def get_tts_engine() -> TTSEngine:
    """Get or create TTS engine instance."""
    global _tts_engine
    if _tts_engine is None:
        _tts_engine = TTSEngine()
    return _tts_engine


# ============ Test Code ============


async def test_edge_tts():
    """Test Edge TTS generation."""
    print("[Test] Testing Edge TTS...")
    engine = get_tts_engine()

    request = TTSRequest(
        text="你好，这是一个测试。Hello, this is a test.", language="auto"
    )
    result = await engine.generate_async(request)

    if result.success:
        print(f"[Test] Success! Format: {result.format}")
        print(f"[Test] Audio length: {len(result.audio_base64 or '')} chars")
    else:
        print(f"[Test] Failed: {result.error}")


async def test_piper_tts():
    """Test Piper TTS generation."""
    print("[Test] Testing Piper TTS...")
    engine = get_tts_engine()

    request = TTSRequest(
        text="你好，这是一个测试。Hello, this is a test.",
        language="auto",
        backend="piper",
    )
    result = await engine.generate_async(request)

    if result.success:
        print(f"[Test] Success! Format: {result.format}")
        print(f"[Test] Audio length: {len(result.audio_base64 or '')} chars")
    else:
        print(f"[Test] Failed: {result.error}")


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_edge_tts())
    asyncio.run(test_piper_tts())
