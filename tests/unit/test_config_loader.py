"""
ConfigLoader 单元测试

测试配置加载模块：
1. 模块初始化
2. VAD 配置加载
3. TTS 配置加载
4. LLM 配置加载
5. 完整配置加载
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config_loader import (
    ConfigLoader,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_ASR_MODEL,
    DEFAULT_VAD_THRESHOLD,
    DEFAULT_VAD_CONSECUTIVE_THRESHOLD,
    DEFAULT_VAD_SILENCE_DURATION,
    DEFAULT_VAD_PRE_BUFFER,
    DEFAULT_MIN_SPEECH_DURATION,
    DEFAULT_MAX_RECORDING_DURATION,
    DEFAULT_TTS_RATE,
)


class TestConfigLoaderInit:
    """测试 ConfigLoader 初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        loader = ConfigLoader()
        assert loader._tts_backend == "edge"


class TestVADConfig:
    """测试 VAD 配置加载"""

    def test_load_vad_config_defaults(self):
        """测试默认 VAD 配置"""
        loader = ConfigLoader()
        config = {}
        
        vad_config = loader._load_vad_config(config)
        
        assert vad_config["vad_threshold"] == DEFAULT_VAD_THRESHOLD
        assert vad_config["vad_consecutive_threshold"] == DEFAULT_VAD_CONSECUTIVE_THRESHOLD
        assert vad_config["vad_silence_duration"] == DEFAULT_VAD_SILENCE_DURATION
        assert vad_config["vad_pre_buffer"] == DEFAULT_VAD_PRE_BUFFER
        assert vad_config["vad_min_speech_duration"] == DEFAULT_MIN_SPEECH_DURATION
        assert vad_config["vad_max_recording_duration"] == DEFAULT_MAX_RECORDING_DURATION

    def test_load_vad_config_custom(self):
        """测试自定义 VAD 配置"""
        loader = ConfigLoader()
        config = {
            "vad_threshold": 0.6,
            "vad_consecutive_threshold": 5,
            "vad_silence_duration": 1.0,
            "vad_pre_buffer": 0.5,
            "vad_min_speech_duration": 0.6,
            "vad_max_recording_duration": 60,
        }
        
        vad_config = loader._load_vad_config(config)
        
        assert vad_config["vad_threshold"] == 0.6
        assert vad_config["vad_consecutive_threshold"] == 5
        assert vad_config["vad_silence_duration"] == 1.0
        assert vad_config["vad_pre_buffer"] == 0.5
        assert vad_config["vad_min_speech_duration"] == 0.6
        assert vad_config["vad_max_recording_duration"] == 60


class TestTTSConfig:
    """测试 TTS 配置加载"""

    def test_load_tts_config_defaults(self):
        """测试默认 TTS 配置"""
        loader = ConfigLoader()
        config = {}
        
        tts_config = loader._load_tts_config(config)
        
        assert tts_config["tts_backend"] == "edge"
        assert tts_config["tts_rate"] == DEFAULT_TTS_RATE

    def test_load_tts_config_custom(self):
        """测试自定义 TTS 配置"""
        loader = ConfigLoader()
        config = {
            "tts_backend": "openai",
            "tts_rate": "+50%",
        }
        
        tts_config = loader._load_tts_config(config)
        
        assert tts_config["tts_backend"] == "openai"
        assert tts_config["tts_rate"] == "+50%"


class TestLLMConfig:
    """测试 LLM 配置加载"""

    def test_load_llm_config_defaults(self):
        """测试默认 LLM 配置"""
        loader = ConfigLoader()
        config = {}
        
        llm_config = loader._load_llm_config(config)
        
        assert llm_config["llm_provider"] == "ollama"
        assert llm_config["llm_backend"] == "ollama"
        assert llm_config["llm_providers"] == []
        assert llm_config["current_provider_config"] == {}

    def test_load_llm_config_custom_provider(self):
        """测试自定义 LLM provider"""
        loader = ConfigLoader()
        config = {
            "llm_provider": "openai",
            "llm_providers": [
                {"name": "openai", "model": "gpt-4", "api_key": "test"}
            ]
        }
        
        llm_config = loader._load_llm_config(config)
        
        assert llm_config["llm_provider"] == "openai"
        assert llm_config["llm_backend"] == "openai"
        assert len(llm_config["llm_providers"]) == 1
        assert llm_config["current_provider_config"]["name"] == "openai"

    def test_load_llm_config_no_matching_provider(self):
        """测试无匹配的 provider"""
        loader = ConfigLoader()
        config = {
            "llm_provider": "anthropic",
            "llm_providers": [
                {"name": "openai", "model": "gpt-4"}
            ]
        }
        
        llm_config = loader._load_llm_config(config)
        
        assert llm_config["llm_provider"] == "anthropic"
        assert llm_config["current_provider_config"] == {}


class TestConstants:
    """测试常量定义"""

    def test_sample_rate_valid(self):
        """测试采样率有效"""
        assert DEFAULT_SAMPLE_RATE > 0

    def test_asr_model_default(self):
        """测试默认 ASR 模型"""
        assert isinstance(DEFAULT_ASR_MODEL, str)
        assert len(DEFAULT_ASR_MODEL) > 0

    def test_vad_threshold_range(self):
        """测试 VAD 阈值范围"""
        assert 0.0 <= DEFAULT_VAD_THRESHOLD <= 1.0

    def test_vad_config_positive_values(self):
        """测试 VAD 配置为正数"""
        assert DEFAULT_VAD_CONSECUTIVE_THRESHOLD > 0
        assert DEFAULT_VAD_SILENCE_DURATION > 0
        assert DEFAULT_VAD_PRE_BUFFER > 0
        assert DEFAULT_MIN_SPEECH_DURATION > 0
        assert DEFAULT_MAX_RECORDING_DURATION > 0

    def test_tts_rate_format(self):
        """测试 TTS 语速格式"""
        assert isinstance(DEFAULT_TTS_RATE, str)
        assert DEFAULT_TTS_RATE.endswith("%")
