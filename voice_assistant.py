#!/usr/bin/env python3
"""
语音助手 - 对接 Claude Code CLI
流程: [唤醒词/按键] → 录音 → Whisper识别 → Claude回复 → Edge TTS朗读
"""

import subprocess
import tempfile
import asyncio
import sys
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav

# 配置
SAMPLE_RATE = 16000
WHISPER_MODEL = "base"  # tiny/base/small/medium/large
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 小艺
TTS_RATE = "-15%"  # 语速
USE_WAKE_WORD = False  # 是否使用唤醒词（True=唤醒词，False=按回车）
WAKE_WORD = "hey_jarvis"
WAKE_THRESHOLD = 0.5


class VoiceAssistant:
    def __init__(self):
        self.whisper_model = None
        self.wake_model = None

    def load_whisper(self):
        if self.whisper_model is None:
            print("🔄 加载 Whisper 模型...", flush=True)
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel(WHISPER_MODEL, compute_type="int8")
            print("✅ Whisper 模型加载完成", flush=True)
        return self.whisper_model

    def load_wake_model(self):
        if self.wake_model is None:
            print("🔄 加载唤醒词模型...", flush=True)
            from openwakeword.model import Model
            self.wake_model = Model(
                wakeword_models=[WAKE_WORD],
                inference_framework='onnx'
            )
            print(f"✅ 唤醒词模型加载完成", flush=True)
        return self.wake_model

    def wait_for_wake_word(self):
        """等待唤醒词"""
        model = self.load_wake_model()
        print(f"\n👂 等待唤醒词 'Hey Jarvis'...", flush=True)

        chunk_size = 1280
        detected = False

        def callback(indata, frames, time_info, status):
            nonlocal detected
            if detected:
                return
            audio = indata[:, 0]
            prediction = model.predict(audio)
            score = prediction[WAKE_WORD]
            if score > WAKE_THRESHOLD:
                detected = True
                print(f"✨ 检测到唤醒词! (置信度: {score:.2f})", flush=True)

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype=np.float32,
            blocksize=chunk_size, callback=callback
        ):
            while not detected:
                sd.sleep(100)

        model.reset()
        return True

    def wait_for_key(self):
        """等待按键"""
        input("\n按回车开始录音...")
        return True

    def record_audio_manual(self):
        """录音 - 按回车停止"""
        print("🎤 开始录音... (按回车停止)", flush=True)

        frames = []
        recording = True

        def callback(indata, frame_count, time_info, status):
            if recording:
                frames.append(indata.copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype=np.float32, callback=callback
        )

        with stream:
            input()
            recording = False

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        print(f"✅ 录音完成 ({len(audio)/SAMPLE_RATE:.1f}秒)", flush=True)
        return audio

    def record_audio_auto(self, max_duration=10, silence_threshold=0.01, silence_duration=1.5):
        """录音 - 静音自动停止"""
        print("🎤 请说话... (静音自动停止)", flush=True)

        frames = []
        silent_chunks = 0
        chunk_duration = 0.1
        max_silent_chunks = int(silence_duration / chunk_duration)

        def callback(indata, frame_count, time_info, status):
            nonlocal silent_chunks
            frames.append(indata.copy())
            volume = np.abs(indata).mean()
            if volume < silence_threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0

        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype=np.float32,
            callback=callback, blocksize=int(SAMPLE_RATE * chunk_duration)
        ):
            while True:
                sd.sleep(100)
                if silent_chunks >= max_silent_chunks and len(frames) > 10:
                    print("🔇 检测到静音，停止录音", flush=True)
                    break
                if len(frames) * chunk_duration >= max_duration:
                    print("⏱️ 达到最大录音时长", flush=True)
                    break

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        print(f"✅ 录音完成 ({len(audio)/SAMPLE_RATE:.1f}秒)", flush=True)
        return audio

    def transcribe(self, audio):
        print("🔄 识别中...", flush=True)
        model = self.load_whisper()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(f.name, SAMPLE_RATE, audio_int16)
            segments, info = model.transcribe(f.name, language="zh")
            text = "".join([seg.text for seg in segments])

        print(f"📝 识别结果: {text}", flush=True)
        return text.strip()

    def ask_claude(self, question):
        print("🤖 Claude 思考中...", flush=True)
        try:
            result = subprocess.run(
                ["claude", "-p", question],
                capture_output=True, text=True, timeout=60
            )
            response = result.stdout.strip()
            print(f"💬 Claude: {response[:200]}{'...' if len(response) > 200 else ''}", flush=True)
            return response
        except subprocess.TimeoutExpired:
            return "抱歉，回复超时了"
        except Exception as e:
            return f"出错了: {e}"

    async def speak(self, text):
        import edge_tts
        print("🔊 朗读中...", flush=True)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
            await communicate.save(f.name)
            subprocess.run(["afplay", f.name])

    async def chat_once(self):
        # 录音
        if USE_WAKE_WORD:
            audio = self.record_audio_auto()
        else:
            audio = self.record_audio_manual()

        if audio is None or len(audio) < SAMPLE_RATE * 0.5:
            print("⚠️  录音太短，跳过", flush=True)
            return

        text = self.transcribe(audio)
        if not text:
            print("⚠️  未识别到内容", flush=True)
            return

        response = self.ask_claude(text)
        await self.speak(response)

    async def run(self):
        print("=" * 50, flush=True)
        print("🎙️  语音助手已启动", flush=True)
        if USE_WAKE_WORD:
            print(f"   唤醒词: 'Hey Jarvis'", flush=True)
        else:
            print("   按回车开始录音，再按回车停止", flush=True)
        print("   Ctrl+C 退出", flush=True)
        print("=" * 50, flush=True)

        # 预加载模型
        if USE_WAKE_WORD:
            self.load_wake_model()
        self.load_whisper()

        try:
            while True:
                if USE_WAKE_WORD:
                    self.wait_for_wake_word()
                    await self.speak("我在")
                else:
                    self.wait_for_key()

                await self.chat_once()

        except KeyboardInterrupt:
            print("\n👋 再见!", flush=True)


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
