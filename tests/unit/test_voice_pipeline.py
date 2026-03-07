"""
VoicePipeline 单元测试

测试语音处理模块：
1. 模块初始化
2. 配置加载
3. 音频参数验证
4. 工具函数
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from voice_pipeline import (
    VoicePipeline,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_LANGUAGE,
    DEFAULT_TTS_RATE,
    DEFAULT_VAD_THRESHOLD,
    DEFAULT_VAD_CONSECUTIVE_THRESHOLD,
    DEFAULT_VAD_SILENCE_DURATION,
    DEFAULT_VAD_PRE_BUFFER,
    DEFAULT_MIN_SPEECH_DURATION,
    DEFAULT_MAX_RECORDING_DURATION,
    EDGE_TTS_VOICES,
)


class TestVoicePipelineInit:
    """测试 VoicePipeline 初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        pipeline = VoicePipeline()
        assert pipeline.asr_model is None
        assert pipeline.vad_model is None
        assert pipeline.llm_backend is None
        assert pipeline.config == {}
        assert pipeline.sample_rate == DEFAULT_SAMPLE_RATE
        assert pipeline.audio_buffer == []

    def test_init_with_models(self):
        """测试带模型的初始化"""
        mock_asr = MagicMock()
        mock_vad = MagicMock()
        mock_llm = MagicMock()
        
        config = {"language": "en", "sample_rate": 16000}
        pipeline = VoicePipeline(
            asr_model=mock_asr,
            vad_model=mock_vad,
            llm_backend=mock_llm,
            config=config
        )
        
        assert pipeline.asr_model == mock_asr
        assert pipeline.vad_model == mock_vad
        assert pipeline.llm_backend == mock_llm
        assert pipeline.config == config


class TestVADConstants:
    """测试 VAD 常量"""

    def test_vad_threshold_range(self):
        """测试 VAD 阈值在有效范围 0-1"""
        assert 0.0 <= DEFAULT_VAD_THRESHOLD <= 1.0

    def test_vad_consecutive_threshold_positive(self):
        """测试连续检测阈值为正数"""
        assert DEFAULT_VAD_CONSECUTIVE_THRESHOLD > 0

    def test_vad_silence_duration_positive(self):
        """测试静音时长为正数"""
        assert DEFAULT_VAD_SILENCE_DURATION > 0

    def test_vad_pre_buffer_positive(self):
        """测试预缓冲为正数"""
        assert DEFAULT_VAD_PRE_BUFFER > 0

    def test_min_speech_duration_positive(self):
        """测试最小语音时长为正数"""
        assert DEFAULT_MIN_SPEECH_DURATION > 0

    def test_max_recording_duration_positive(self):
        """测试最大录音时长为正数"""
        assert DEFAULT_MAX_RECORDING_DURATION > 0


class TestTTSConstants:
    """测试 TTS 常量"""

    def test_sample_rate_valid(self):
        """测试采样率有效"""
        assert DEFAULT_SAMPLE_RATE > 0
        assert DEFAULT_SAMPLE_RATE in [8000, 16000, 22050, 44100]

    def test_default_language(self):
        """测试默认语言"""
        assert DEFAULT_LANGUAGE in ["zh", "en", "ja", "ko", "yue"]

    def test_tts_rate_format(self):
        """测试 TTS 语速格式"""
        assert isinstance(DEFAULT_TTS_RATE, str)
        assert DEFAULT_TTS_RATE.endswith("%")

    def test_edge_tts_voices(self):
        """测试 Edge TTS 语音列表"""
        assert isinstance(EDGE_TTS_VOICES, dict)
        assert "zh" in EDGE_TTS_VOICES
        assert "en" in EDGE_TTS_VOICES


class TestAudioBuffer:
    """测试音频缓冲区"""

    def test_audio_buffer_initially_empty(self):
        """测试初始音频缓冲区为空"""
        pipeline = VoicePipeline()
        assert pipeline.audio_buffer == []

    def test_audio_buffer_accepts_list(self):
        """测试音频缓冲区接受列表"""
        pipeline = VoicePipeline()
        test_audio = [np.array([1, 2, 3]), np.array([4, 5, 6])]
        pipeline.audio_buffer = test_audio
        assert len(pipeline.audio_buffer) == 2
