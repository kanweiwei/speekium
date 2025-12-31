#!/usr/bin/env python3
"""
语音助手 - 对接 Claude Code CLI
流程: 录音 → Whisper识别 → Claude回复 → Edge TTS朗读
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
TTS_RATE = "-15%"  # 语速: -50%~+50%，负数慢，正数快


class VoiceAssistant:
    def __init__(self):
        self.whisper_model = None

    def load_whisper(self):
        """懒加载 Whisper 模型"""
        if self.whisper_model is None:
            print("🔄 加载 Whisper 模型...")
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel(WHISPER_MODEL, compute_type="int8")
            print("✅ 模型加载完成")
        return self.whisper_model

    def record_audio(self, duration=None):
        """录音 - 按回车停止"""
        print("\n🎤 开始录音... (按回车停止)")

        frames = []
        recording = True

        def callback(indata, frame_count, time_info, status):
            if recording:
                frames.append(indata.copy())

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype=np.float32,
            callback=callback
        )

        with stream:
            input()  # 等待回车
            recording = False

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        print(f"✅ 录音完成 ({len(audio)/SAMPLE_RATE:.1f}秒)")
        return audio

    def transcribe(self, audio):
        """语音识别"""
        print("🔄 识别中...")
        model = self.load_whisper()

        # 保存临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            audio_int16 = (audio * 32767).astype(np.int16)
            write_wav(f.name, SAMPLE_RATE, audio_int16)

            segments, info = model.transcribe(f.name, language="zh")
            text = "".join([seg.text for seg in segments])

        print(f"📝 识别结果: {text}")
        return text.strip()

    def ask_claude(self, question):
        """调用 Claude Code CLI"""
        print("🤖 Claude 思考中...")

        try:
            result = subprocess.run(
                ["claude", "-p", question],
                capture_output=True,
                text=True,
                timeout=60
            )
            response = result.stdout.strip()
            print(f"💬 Claude: {response[:200]}{'...' if len(response) > 200 else ''}")
            return response
        except subprocess.TimeoutExpired:
            return "抱歉，回复超时了"
        except Exception as e:
            return f"出错了: {e}"

    async def speak(self, text):
        """Edge TTS 朗读"""
        import edge_tts

        print("🔊 朗读中...")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
            await communicate.save(f.name)
            subprocess.run(["afplay", f.name])

    async def chat_once(self):
        """单次对话"""
        # 1. 录音
        audio = self.record_audio()
        if audio is None or len(audio) < SAMPLE_RATE * 0.5:
            print("⚠️  录音太短，跳过")
            return

        # 2. 识别
        text = self.transcribe(audio)
        if not text:
            print("⚠️  未识别到内容")
            return

        # 3. 问 Claude
        response = self.ask_claude(text)

        # 4. 朗读
        await self.speak(response)

    async def run(self):
        """主循环"""
        print("=" * 50)
        print("🎙️  语音助手已启动")
        print("   按回车开始录音，再按回车停止")
        print("   输入 'q' 退出")
        print("=" * 50)

        while True:
            cmd = input("\n按回车开始对话 (q退出): ").strip().lower()
            if cmd == 'q':
                print("👋 再见!")
                break

            await self.chat_once()


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
