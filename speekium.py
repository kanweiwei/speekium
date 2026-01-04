#!/usr/bin/env python3
"""
Speekium - 智能语音助手
通过自然语音与大语言模型进行对话交互
流程: [VAD检测人声] → 录音 → SenseVoice识别 → LLM流式回复 → 边生成边朗读

支持后端: Claude Code CLI, Ollama
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

# ===== LLM 后端配置 =====
LLM_BACKEND = "claude"  # 可选: "claude", "ollama"

# Ollama 配置 (仅当 LLM_BACKEND="ollama" 时生效)
OLLAMA_MODEL = "qwen2.5:1.5b"  # Ollama 模型名称 (可选: qwen2.5:7b 更智能但更慢)
OLLAMA_BASE_URL = "http://localhost:11434"  # Ollama 服务地址

# ===== 基础配置 =====
SAMPLE_RATE = 16000
ASR_MODEL = "iic/SenseVoiceSmall"  # SenseVoice 模型
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 小艺
TTS_RATE = "+0%"  # 语速 (负值减慢，正值加快，0%为正常)
USE_STREAMING = True  # 是否使用流式输出（边生成边朗读）

# ===== VAD 配置 =====
VAD_THRESHOLD = 0.5  # 语音检测阈值
VAD_CONSECUTIVE_THRESHOLD = 3  # 连续检测到语音的次数才确认开始说话
VAD_PRE_BUFFER = 0.3  # 预缓冲时长（秒），保留语音开始前的音频
MIN_SPEECH_DURATION = 0.5  # 最短语音时长（秒）
SILENCE_AFTER_SPEECH = 1.5  # 说完后静音多久停止录音（秒）
MAX_RECORDING_DURATION = 30  # 最大录音时长（秒）

# ===== 系统提示词（优化语音输出）=====
SYSTEM_PROMPT = """你是 Speekium 智能语音助手，请遵循以下规则：
1. 用口语化的中文回答，适合朗读
2. 不要使用 markdown 格式、代码块、列表符号
3. 不要使用特殊符号如 *、#、`、- 等
4. 数字用中文表达，如"三点五"而不是"3.5"
5. 语气自然友好，像朋友聊天一样"""


class VoiceAssistant:
    def __init__(self):
        self.asr_model = None
        self.vad_model = None
        self.llm_backend = None

    def load_asr(self):
        if self.asr_model is None:
            print("🔄 加载 SenseVoice 模型...", flush=True)
            from funasr import AutoModel
            self.asr_model = AutoModel(model=ASR_MODEL, device="cpu")
            print("✅ SenseVoice 模型加载完成", flush=True)
        return self.asr_model

    def load_vad(self):
        if self.vad_model is None:
            print("🔄 加载 VAD 模型...", flush=True)
            self.vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            print("✅ VAD 模型加载完成", flush=True)
        return self.vad_model

    def load_llm(self):
        if self.llm_backend is None:
            print(f"🔄 初始化 LLM 后端 ({LLM_BACKEND})...", flush=True)
            if LLM_BACKEND == "ollama":
                self.llm_backend = create_backend(
                    LLM_BACKEND,
                    SYSTEM_PROMPT,
                    model=OLLAMA_MODEL,
                    base_url=OLLAMA_BASE_URL
                )
            else:
                self.llm_backend = create_backend(LLM_BACKEND, SYSTEM_PROMPT)
            print(f"✅ LLM 后端初始化完成", flush=True)
        return self.llm_backend

    def record_with_vad(self):
        """使用 VAD 检测语音，自动开始和停止录音"""
        model = self.load_vad()
        model.reset_states()  # 重置 VAD 状态

        print("\n👂 正在聆听...", flush=True)

        chunk_size = 512  # Silero VAD 需要 512 samples @ 16kHz
        frames = []
        is_speaking = False
        silence_chunks = 0
        speech_chunks = 0
        consecutive_speech = 0  # 连续检测到语音的次数
        max_silence_chunks = int(SILENCE_AFTER_SPEECH * SAMPLE_RATE / chunk_size)
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / chunk_size)
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / chunk_size)

        # 预缓冲：保留语音开始前的音频，避免丢失开头
        pre_buffer_size = int(VAD_PRE_BUFFER * SAMPLE_RATE / chunk_size)
        pre_buffer = deque(maxlen=pre_buffer_size)

        recording_done = False

        def callback(indata, frame_count, time_info, status):
            nonlocal is_speaking, silence_chunks, speech_chunks, consecutive_speech, recording_done

            if recording_done:
                return

            try:
                audio_chunk = indata[:, 0].copy()

                # VAD 检测
                audio_tensor = torch.from_numpy(audio_chunk).float()
                speech_prob = model(audio_tensor, SAMPLE_RATE).item()

                if speech_prob > VAD_THRESHOLD:
                    # 检测到语音
                    consecutive_speech += 1

                    if not is_speaking and consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                        is_speaking = True
                        # 将预缓冲的音频添加到 frames，避免丢失语音开头
                        frames.extend(pre_buffer)
                        pre_buffer.clear()
                        print(f"🎤 检测到语音，开始录音...", flush=True)

                    if is_speaking:
                        # 只有连续检测到语音才重置静音计数
                        if consecutive_speech >= VAD_CONSECUTIVE_THRESHOLD:
                            silence_chunks = 0
                        speech_chunks += 1
                        frames.append(audio_chunk)
                    else:
                        # 还未确认开始说话，继续填充预缓冲
                        pre_buffer.append(audio_chunk)
                else:
                    # 静音
                    consecutive_speech = 0  # 重置连续语音计数

                    if is_speaking:
                        frames.append(audio_chunk)
                        silence_chunks += 1

                        # 说完后静音足够长，停止录音
                        if silence_chunks >= max_silence_chunks and speech_chunks >= min_speech_chunks:
                            recording_done = True
                            print("🔇 语音结束", flush=True)
                    else:
                        # 还未开始说话，继续填充预缓冲
                        pre_buffer.append(audio_chunk)

                # 超过最大时长
                if len(frames) >= max_chunks:
                    recording_done = True
                    print("⏱️ 达到最大录音时长", flush=True)

            except Exception as e:
                print(f"⚠️ VAD 处理错误: {e}", flush=True)
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
        print(f"✅ 录音完成 ({len(audio)/SAMPLE_RATE:.1f}秒)", flush=True)
        return audio

    def transcribe(self, audio):
        print("🔄 识别中...", flush=True)
        model = self.load_asr()
        tmp_file = None

        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_file = f.name
                audio_int16 = (audio * 32767).astype(np.int16)
                write_wav(tmp_file, SAMPLE_RATE, audio_int16)
                result = model.generate(input=tmp_file)
                text = result[0]["text"] if result else ""
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

        # 清理 SenseVoice 输出的标签，如 <|yue|><|EMO_UNKNOWN|><|Speech|>
        text = re.sub(r'<\|[^|]+\|>', '', text).strip()

        print(f"📝 识别结果: {text}", flush=True)
        return text

    async def generate_audio(self, text):
        """生成 TTS 音频文件，返回文件路径"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_file = f.name
                communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
                await communicate.save(tmp_file)
                return tmp_file
        except Exception as e:
            print(f"⚠️ TTS 生成失败: {e}", flush=True)
            return None

    async def play_audio(self, tmp_file, delete=True):
        """播放音频文件（异步，跨平台），可选是否删除"""
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
                    print(f"⚠️ 不支持的平台: {system}", flush=True)
                    return

                process = await asyncio.create_subprocess_exec(*cmd)
                await process.wait()
            finally:
                if delete:
                    os.remove(tmp_file)

    async def speak(self, text):
        """TTS 朗读（单句）"""
        tmp_file = await self.generate_audio(text)
        await self.play_audio(tmp_file)

    async def chat_once(self):
        """单次对话"""
        audio = self.record_with_vad()

        if audio is None:
            return False  # 没有检测到有效语音

        text = self.transcribe(audio)
        if not text:
            print("⚠️  未识别到内容", flush=True)
            return True

        backend = self.load_llm()

        if USE_STREAMING:
            # 流式输出
            print("🔊 流式朗读中...", flush=True)
            audio_queue = asyncio.Queue()

            async def generate_worker():
                async for sentence in backend.chat_stream(text):
                    if sentence:
                        audio_file = await self.generate_audio(sentence)
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
            # 非流式输出
            response = backend.chat(text)
            await self.speak(response)

        return True

    async def run(self):
        print("=" * 50, flush=True)
        print("🎙️  Speekium 已启动 (持续对话模式)", flush=True)
        print("   使用 VAD 自动检测语音", flush=True)
        backend_info = LLM_BACKEND
        if LLM_BACKEND == "ollama":
            backend_info = f"ollama ({OLLAMA_MODEL})"
        print(f"   LLM 后端: {backend_info}", flush=True)
        if USE_STREAMING:
            print("   模式: 流式输出（边生成边朗读）", flush=True)
        print("   Ctrl+C 退出", flush=True)
        print("=" * 50, flush=True)

        # 预加载模型
        self.load_vad()
        self.load_asr()
        self.load_llm()

        print("\n🎧 准备就绪，请开始说话...\n", flush=True)

        try:
            while True:
                await self.chat_once()
                # 短暂延迟，避免立即开始下一轮
                await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            print("\n👋 再见!", flush=True)


async def main():
    assistant = VoiceAssistant()
    await assistant.run()


if __name__ == "__main__":
    asyncio.run(main())
