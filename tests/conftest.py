"""
Pytest 配置文件和共享 fixtures

提供测试所需的共享资源和配置
"""

import os
import tempfile
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def sample_audio_16k():
    """生成 16kHz 采样率的测试音频数据（1秒静音）"""
    return np.zeros(16000, dtype=np.float32)


@pytest.fixture
def sample_audio_with_speech():
    """生成包含模拟语音的测试音频数据"""
    # 生成简单的正弦波模拟语音
    duration = 2.0  # 2秒
    sample_rate = 16000
    frequency = 440  # A4音高

    t = np.linspace(0, duration, int(sample_rate * duration))
    audio = 0.3 * np.sin(2 * np.pi * frequency * t).astype(np.float32)

    return audio


@pytest.fixture
def temp_wav_file(sample_audio_16k):
    """创建临时 WAV 文件用于测试"""
    from scipy.io.wavfile import write as write_wav

    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    # 写入音频数据
    audio_int16 = (sample_audio_16k * 32767).astype(np.int16)
    write_wav(path, 16000, audio_int16)

    yield path

    # 清理
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def mock_llm_response():
    """模拟 LLM 响应数据"""
    return "这是一个测试响应。"


@pytest.fixture
def mock_conversation_history():
    """模拟对话历史"""
    return [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！有什么我可以帮助你的吗？"},
    ]


@pytest.fixture
def project_root():
    """获取项目根目录路径"""
    return Path(__file__).parent.parent
