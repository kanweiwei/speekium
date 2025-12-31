#!/usr/bin/env python3
"""
语音助手 - 对接 Claude Code CLI
流程: [唤醒词/按键] → 录音 → Whisper识别 → Claude流式回复 → 边生成边朗读
"""

import subprocess
import tempfile
import asyncio
import sys
import os
import json
import re
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write as write_wav

# 配置
SAMPLE_RATE = 16000
WHISPER_MODEL = "base"  # tiny/base/small/medium/large
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 小艺
TTS_RATE = "-15%"  # 语速
USE_WAKE_WORD = True  # 是否使用唤醒词（True=唤醒词，False=按回车）
WAKE_WORD = "hey_jarvis"
WAKE_THRESHOLD = 0.5
SILENCE_DURATION = 2.5  # 静音多少秒后停止录音
USE_STREAMING = True  # 是否使用流式输出（边生成边朗读）

# Claude 系统提示词（优化语音输出）
SYSTEM_PROMPT = """你是一个语音助手，请遵循以下规则：
1. 用口语化的中文回答，适合朗读
2. 不要使用 markdown 格式、代码块、列表符号
3. 不要使用特殊符号如 *、#、`、- 等
4. 数字用中文表达，如"三点五"而不是"3.5"
5. 语气自然友好，像朋友聊天一样"""


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
        model.reset()
        sd.sleep(500)

        print(f"\n👂 等待唤醒词 'Hey Jarvis'...", flush=True)

        chunk_size = 1280
        detected = False

        def callback(indata, frames, time_info, status):
            nonlocal detected
            if detected:
                return
            audio_float = indata[:, 0]
            audio_int16 = (audio_float * 32767).astype(np.int16)
            prediction = model.predict(audio_int16)
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

    def record_audio_auto(self, max_duration=10, silence_threshold=0.01, silence_duration=SILENCE_DURATION):
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
        tmp_file = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_file = f.name
                audio_int16 = (audio * 32767).astype(np.int16)
                write_wav(tmp_file, SAMPLE_RATE, audio_int16)
                segments, info = model.transcribe(tmp_file, language="zh")
                text = "".join([seg.text for seg in segments])
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

        print(f"📝 识别结果: {text}", flush=True)
        return text.strip()

    def ask_claude(self, question):
        """非流式调用 Claude"""
        print("🤖 Claude 思考中...", flush=True)
        try:
            result = subprocess.run(
                [
                    "claude", "-p", question,
                    "--dangerously-skip-permissions",
                    "--system-prompt", SYSTEM_PROMPT
                ],
                capture_output=True, text=True, timeout=120
            )
            response = result.stdout.strip()
            print(f"💬 Claude: {response}", flush=True)
            return response
        except subprocess.TimeoutExpired:
            return "抱歉，回复超时了"
        except Exception as e:
            return f"出错了: {e}"

    async def ask_claude_stream(self, question):
        """流式调用 Claude，返回句子生成器"""
        print("🤖 Claude 思考中...", flush=True)

        cmd = [
            "claude", "-p", question,
            "--dangerously-skip-permissions",
            "--system-prompt", SYSTEM_PROMPT,
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--verbose"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        buffer = ""
        full_response = ""
        sentence_endings = re.compile(r'([。！？\n])')

        async for line in process.stdout:
            try:
                data = json.loads(line.decode('utf-8'))

                # 提取流式文本片段
                if data.get("type") == "stream_event":
                    event = data.get("event", {})
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            buffer += text
                            full_response += text

                            # 检查是否有完整句子
                            while True:
                                match = sentence_endings.search(buffer)
                                if match:
                                    end_pos = match.end()
                                    sentence = buffer[:end_pos].strip()
                                    buffer = buffer[end_pos:]
                                    if sentence:
                                        print(f"🗣️  {sentence}", flush=True)
                                        yield sentence
                                else:
                                    break

            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"⚠️ 解析错误: {e}", flush=True)
                continue

        # 处理剩余内容
        if buffer.strip():
            print(f"🗣️  {buffer.strip()}", flush=True)
            yield buffer.strip()

        await process.wait()

    async def generate_audio(self, text):
        """生成 TTS 音频文件，返回文件路径"""
        import edge_tts
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_file = f.name
                communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
                await communicate.save(tmp_file)
                return tmp_file
        except Exception as e:
            print(f"⚠️ TTS 生成失败: {e}", flush=True)
            return None

    async def play_audio(self, tmp_file):
        """播放音频文件并清理（异步）"""
        if tmp_file and os.path.exists(tmp_file):
            try:
                process = await asyncio.create_subprocess_exec("afplay", tmp_file)
                await process.wait()
            finally:
                os.remove(tmp_file)

    async def speak(self, text):
        """TTS 朗读（单句）"""
        tmp_file = await self.generate_audio(text)
        await self.play_audio(tmp_file)

    async def chat_once(self):
        """单次对话 - 非流式"""
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

    async def chat_once_stream(self):
        """单次对话 - 流式（边生成边朗读，音频预生成）"""
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

        print("🔊 流式朗读中...", flush=True)

        # 使用队列实现流水线：TTS生成 -> 队列 -> 播放
        audio_queue = asyncio.Queue()

        async def generate_worker():
            """生成音频并放入队列"""
            async for sentence in self.ask_claude_stream(text):
                if sentence:
                    audio_file = await self.generate_audio(sentence)
                    if audio_file:
                        await audio_queue.put(audio_file)
            await audio_queue.put(None)  # 结束信号

        async def play_worker():
            """从队列取出音频播放"""
            while True:
                audio_file = await audio_queue.get()
                if audio_file is None:
                    break
                await self.play_audio(audio_file)

        # 并行运行生成和播放
        await asyncio.gather(generate_worker(), play_worker())

    async def run(self):
        print("=" * 50, flush=True)
        print("🎙️  语音助手已启动", flush=True)
        if USE_WAKE_WORD:
            print(f"   唤醒词: 'Hey Jarvis'", flush=True)
        else:
            print("   按回车开始录音，再按回车停止", flush=True)
        if USE_STREAMING:
            print("   模式: 流式输出（边生成边朗读）", flush=True)
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

                if USE_STREAMING:
                    await self.chat_once_stream()
                else:
                    await self.chat_once()

        except KeyboardInterrupt:
            print("\n👋 再见!", flush=True)


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
