#!/usr/bin/env python3
"""
Speekium - Intelligent Voice Assistant
Natural voice conversation with large language models
Flow: [VAD voice detection] → Record → SenseVoice ASR → LLM streaming → TTS playback

Supported backends: Claude Code CLI, Ollama
"""

import tempfile
import asyncio
import os
import re
import platform
from collections import deque
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav
import edge_tts
import torch

from backends import create_backend

# ===== LLM Backend =====
LLM_BACKEND = "claude"  # Options: "claude", "ollama"

# Ollama config (only used when LLM_BACKEND="ollama")
OLLAMA_MODEL = "qwen2.5:1.5b"  # Ollama model (use qwen2.5:7b for smarter but slower)
OLLAMA_BASE_URL = "http://localhost:11434"  # Ollama server URL

# ===== Conversation Memory =====
MAX_HISTORY = 10  # Max conversation turns to keep (each turn = user + assistant)
CLEAR_HISTORY_KEYWORDS = ["clear history", "start over", "forget everything", "清空对话", "重新开始"]  # Keywords to trigger history clear

# ===== Basic Config =====
SAMPLE_RATE = 16000
ASR_MODEL = "iic/SenseVoiceSmall"  # SenseVoice model
TTS_RATE = "+0%"  # Speed: negative=slower, positive=faster, 0%=normal
USE_STREAMING = True  # Stream output (speak while generating)

# ===== TTS Voices (auto-selected based on detected language) =====
DEFAULT_LANGUAGE = "zh"
TTS_VOICES = {
    "zh": "zh-CN-XiaoyiNeural",    # Chinese female
    "en": "en-US-JennyNeural",     # English female
    "ja": "ja-JP-NanamiNeural",    # Japanese female
    "ko": "ko-KR-SunHiNeural",     # Korean female
    "yue": "zh-HK-HiuGaaiNeural",  # Cantonese female
}

# ===== VAD Config =====
VAD_THRESHOLD = 0.5  # Voice detection threshold
VAD_CONSECUTIVE_THRESHOLD = 3  # Consecutive detections to confirm speech start
VAD_PRE_BUFFER = 0.3  # Pre-buffer duration (seconds) to capture speech start
MIN_SPEECH_DURATION = 0.2  # Minimum speech duration (seconds)
SILENCE_AFTER_SPEECH = 0.8  # Silence duration to stop recording (seconds)
MAX_RECORDING_DURATION = 30  # Maximum recording duration (seconds)

# ===== System Prompt (optimized for voice output) =====
SYSTEM_PROMPT = """You are Speekium, an intelligent voice assistant. Follow these rules:
1. Detect the user's language and respond in the same language
2. ONLY answer the current question - do not repeat or re-answer previous topics
3. Keep responses concise - 1-2 sentences unless more detail is requested
4. Use natural conversational style suitable for speech output
5. Never use markdown formatting, code blocks, or list symbols
6. Avoid special symbols like *, #, `, - etc.
7. Express numbers naturally (e.g., "three point five" instead of "3.5")
8. Be friendly, like chatting with a friend"""


class VoiceAssistant:
    def __init__(self):
        self.asr_model = None
        self.vad_model = None
        self.llm_backend = None

    def load_asr(self):
        if self.asr_model is None:
            print("🔄 Loading SenseVoice model...", flush=True)
            from funasr import AutoModel
            self.asr_model = AutoModel(model=ASR_MODEL, device="cpu")
            print("✅ SenseVoice model loaded", flush=True)
        return self.asr_model

    def load_vad(self):
        if self.vad_model is None:
            print("🔄 Loading VAD model...", flush=True)
            self.vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            print("✅ VAD model loaded", flush=True)
        return self.vad_model

    def load_llm(self):
        if self.llm_backend is None:
            print(f"🔄 Initializing LLM backend ({LLM_BACKEND})...", flush=True)
            if LLM_BACKEND == "ollama":
                self.llm_backend = create_backend(
                    LLM_BACKEND,
                    SYSTEM_PROMPT,
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_BASE_URL,
                    max_history=MAX_HISTORY
                )
            else:
                self.llm_backend = create_backend(
                    LLM_BACKEND,
                    SYSTEM_PROMPT,
                    max_history=MAX_HISTORY
                )
            print(f"✅ LLM backend initialized", flush=True)
        return self.llm_backend

    def record_with_vad(self):
        """Use VAD to detect speech, auto start and stop recording"""
        model = self.load_vad()
        model.reset_states()  # Reset VAD state

        # Show history count
        history_count = 0
        if self.llm_backend and hasattr(self.llm_backend, 'history'):
            history_count = len(self.llm_backend.history) // 2
        if history_count > 0:
            print(f"\n👂 Listening... ({history_count} turns in memory)", flush=True)
        else:
            print("\n👂 Listening...", flush=True)

        chunk_size = 512  # Silero VAD requires 512 samples @ 16kHz
        frames = []
        is_speaking = False
        silence_chunks = 0
        speech_chunks = 0
        consecutive_speech = 0  # Consecutive speech detections
        max_silence_chunks = int(SILENCE_AFTER_SPEECH * SAMPLE_RATE / chunk_size)
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / chunk_size)
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / chunk_size)

        # Pre-buffer: keep audio before speech starts to avoid clipping
        pre_buffer_size = int(VAD_PRE_BUFFER * SAMPLE_RATE / chunk_size)
        pre_buffer = deque(maxlen=pre_buffer_size)

        recording_done = False

        def callback(indata, frame_count, time_info, status):
            nonlocal is_speaking, silence_chunks, speech_chunks, consecutive_speech, recording_done

            if recording_done:
                return

            try:
                audio_chunk = indata[:, 0].copy()

                # VAD detection
                audio_tensor = torch.from_numpy(audio_chunk).float()
                speech_prob = model(audio_tensor, SAMPLE_RATE).item()

                if speech_prob > VAD_THRESHOLD:
                    # Speech detected
                    consecutive_speech += 1

                    if not is_speaking and consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                        is_speaking = True
                        # Add pre-buffer to frames to avoid clipping speech start
                        frames.extend(pre_buffer)
                        pre_buffer.clear()
                        print(f"🎤 Speech detected, recording...", flush=True)

                    if is_speaking:
                        # Only reset silence count on consecutive speech
                        if consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                            silence_chunks = 0
                        speech_chunks += 1
                        frames.append(audio_chunk)
                    else:
                        # Not confirmed speaking yet, fill pre-buffer
                        pre_buffer.append(audio_chunk)
                else:
                    # Silence
                    consecutive_speech = 0  # Reset consecutive speech count

                    if is_speaking:
                        frames.append(audio_chunk)
                        silence_chunks += 1

                        # Stop recording after enough silence
                        if silence_chunks >= max_silence_chunks and speech_chunks >= min_speech_chunks:
                            recording_done = True
                            print("🔇 Speech ended", flush=True)
                    else:
                        # Not speaking yet, fill pre-buffer
                        pre_buffer.append(audio_chunk)

                # Max duration reached
                if len(frames) >= max_chunks:
                    recording_done = True
                    print("⏱️ Max recording duration reached", flush=True)

            except Exception as e:
                print(f"⚠️ VAD error: {e}", flush=True)
                recording_done = True

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype=np.float32,
            blocksize=chunk_size, callback=callback
        ):
            while not recording_done:
                sd.sleep(50)

        if not frames or speech_chunks < min_speech_chunks:
            return None

        audio = np.concatenate(frames)
        print(f"✅ Recording complete ({len(audio)/SAMPLE_RATE:.1f}s)", flush=True)
        return audio

    def transcribe(self, audio):
        """Transcribe audio and detect language. Returns (text, language)."""
        print("🔄 Recognizing...", flush=True)
        model = self.load_asr()
        tmp_file = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_file = f.name
                audio_int16 = (audio * 32767).astype(np.int16)
                write_wav(tmp_file, SAMPLE_RATE, audio_int16)
                result = model.generate(input=tmp_file)
                raw_text = result[0]["text"] if result else ""
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

        # Extract language from SenseVoice tags like <|zh|>, <|en|>, <|yue|>
        lang_match = re.search(r'<\|(zh|en|ja|ko|yue)\|>', raw_text)
        language = lang_match.group(1) if lang_match else DEFAULT_LANGUAGE

        # Clean all tags from text
        text = re.sub(r'<\|[^|]+\|>', '', raw_text).strip()

        voice = TTS_VOICES.get(language, TTS_VOICES[DEFAULT_LANGUAGE])
        print(f"📝 [{language}] {text}", flush=True)
        return text, language

    def detect_text_language(self, text):
        """Detect language from text content using character analysis."""
        # Count character types
        cjk_count = 0
        ja_specific = 0
        ko_specific = 0
        latin_count = 0

        for char in text:
            code = ord(char)
            # CJK Unified Ideographs (Chinese/Japanese/Korean shared)
            if 0x4E00 <= code <= 0x9FFF:
                cjk_count += 1
            # Hiragana/Katakana (Japanese specific)
            elif 0x3040 <= code <= 0x30FF:
                ja_specific += 1
            # Hangul (Korean specific)
            elif 0xAC00 <= code <= 0xD7AF or 0x1100 <= code <= 0x11FF:
                ko_specific += 1
            # Basic Latin letters
            elif 0x0041 <= code <= 0x007A:
                latin_count += 1

        total = len(text.replace(" ", ""))
        if total == 0:
            return DEFAULT_LANGUAGE

        # Japanese has hiragana/katakana
        if ja_specific > 0:
            return "ja"
        # Korean has hangul
        if ko_specific > 0:
            return "ko"
        # Chinese if mostly CJK
        if cjk_count > latin_count:
            return "zh"
        # Default to English for Latin text
        if latin_count > 0:
            return "en"

        return DEFAULT_LANGUAGE

    async def generate_audio(self, text, language=None):
        """Generate TTS audio file, returns file path."""
        try:
            # Auto-detect language from text content for better TTS matching
            detected_lang = self.detect_text_language(text)
            voice = TTS_VOICES.get(detected_lang, TTS_VOICES[DEFAULT_LANGUAGE])
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_file = f.name
                communicate = edge_tts.Communicate(text, voice, rate=TTS_RATE)
                await communicate.save(tmp_file)
                return tmp_file
        except Exception as e:
            print(f"⚠️ TTS error: {e}", flush=True)
            return None

    async def play_audio(self, tmp_file, delete=True):
        """Play audio file (async, cross-platform), optionally delete after."""
        if tmp_file and os.path.exists(tmp_file):
            try:
                system = platform.system()
                if system == "Darwin":  # macOS
                    cmd = ["afplay", tmp_file]
                elif system == "Linux":
                    cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_file]
                elif system == "Windows":
                    cmd = ["powershell", "-c", f"(New-Object Media.SoundPlayer '{tmp_file}').PlaySync()"]
                else:
                    print(f"⚠️ Unsupported platform: {system}", flush=True)
                    return

                process = await asyncio.create_subprocess_exec(*cmd)
                await process.wait()
            finally:
                if delete:
                    os.remove(tmp_file)

    async def speak(self, text, language=None):
        """TTS speak a single sentence."""
        tmp_file = await self.generate_audio(text, language)
        await self.play_audio(tmp_file)

    async def chat_once(self):
        """Single conversation turn"""
        audio = self.record_with_vad()

        if audio is None:
            return False  # No valid speech detected

        text, language = self.transcribe(audio)
        if not text:
            print("⚠️ No speech recognized", flush=True)
            return True

        backend = self.load_llm()

        # Check if user wants to clear history
        for keyword in CLEAR_HISTORY_KEYWORDS:
            if keyword in text:
                backend.clear_history()
                # Respond in detected language
                clear_messages = {
                    "zh": "好的，已清空对话记录，重新开始。",
                    "en": "OK, conversation cleared. Let's start fresh.",
                    "ja": "会話履歴をクリアしました。",
                    "ko": "대화 기록을 지웠습니다.",
                    "yue": "好，已清空對話記錄。",
                }
                msg = clear_messages.get(language, clear_messages["en"])
                await self.speak(msg, language)
                return True

        if USE_STREAMING:
            # Streaming output
            print("🔊 Streaming...", flush=True)
            audio_queue = asyncio.Queue()

            async def generate_worker():
                async for sentence in backend.chat_stream(text):
                    if sentence:
                        audio_file = await self.generate_audio(sentence, language)
                        if audio_file:
                            await audio_queue.put(audio_file)
                await audio_queue.put(None)

            async def play_worker():
                while True:
                    audio_file = await audio_queue.get()
                    if audio_file is None:
                        break
                    await self.play_audio(audio_file)

            await asyncio.gather(generate_worker(), play_worker())
        else:
            # Non-streaming output
            response = backend.chat(text)
            await self.speak(response, language)

        return True

    async def run(self):
        print("=" * 50, flush=True)
        print("🎙️  Speekium started (continuous conversation mode)", flush=True)
        print("   VAD auto voice detection enabled", flush=True)
        backend_info = LLM_BACKEND
        if LLM_BACKEND == "ollama":
            backend_info = f"ollama ({OLLAMA_MODEL})"
        print(f"   LLM backend: {backend_info}", flush=True)
        if USE_STREAMING:
            print("   Mode: streaming (speak while generating)", flush=True)
        print(f"   Memory: last {MAX_HISTORY} turns", flush=True)
        print("   Say 'clear history' to reset memory", flush=True)
        print("   Ctrl+C to exit", flush=True)
        print("=" * 50, flush=True)

        # Preload models
        self.load_vad()
        self.load_asr()
        self.load_llm()

        print("\n🎧 Ready, start speaking...\n", flush=True)

        try:
            while True:
                await self.chat_once()
                # Brief delay before next round
                await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            print("\n👋 Goodbye!", flush=True)


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
