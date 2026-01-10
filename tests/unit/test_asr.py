"""
ASR (Automatic Speech Recognition) 单元测试

测试 FunASR 和 SenseVoice 模型集成及语音识别功能：
1. ASR 模型加载
2. 音频转录功能
3. 语言检测逻辑
4. 异步转录支持
5. 临时文件处理
6. 错误处理机制
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import speekium
from speekium import (
    ASR_MODEL,
    DEFAULT_LANGUAGE,
    SAMPLE_RATE,
    VoiceAssistant,
    create_secure_temp_file,
)


class TestASRConfiguration:
    """测试 ASR 配置常量"""

    def test_asr_model_valid(self):
        """测试 ASR 模型路径有效"""
        assert ASR_MODEL == "iic/SenseVoiceSmall"
        assert isinstance(ASR_MODEL, str)
        assert len(ASR_MODEL) > 0

    def test_default_language_valid(self):
        """测试默认语言配置"""
        assert DEFAULT_LANGUAGE in ["zh", "en", "ja", "ko", "yue"]

    def test_sample_rate_valid(self):
        """测试采样率配置"""
        assert SAMPLE_RATE == 16000
        assert isinstance(SAMPLE_RATE, int)


class TestASRModelLoading:
    """测试 ASR 模型加载功能"""

    @patch("funasr.AutoModel")
    def test_load_asr_first_time(self, mock_automodel):
        """测试首次加载 ASR 模型"""
        # Setup mock
        mock_model = MagicMock()
        mock_automodel.return_value = mock_model

        assistant = VoiceAssistant()
        model = assistant.load_asr()

        # Verify
        assert model is not None
        assert assistant.asr_model is mock_model
        mock_automodel.assert_called_once_with(model=ASR_MODEL, device="cpu")

    @patch("funasr.AutoModel")
    def test_load_asr_cached(self, mock_automodel):
        """测试 ASR 模型缓存机制"""
        mock_model = MagicMock()
        mock_automodel.return_value = mock_model

        assistant = VoiceAssistant()
        model1 = assistant.load_asr()
        model2 = assistant.load_asr()

        # Should only load once
        assert model1 is model2
        mock_automodel.assert_called_once()

    @patch("funasr.AutoModel")
    def test_load_asr_device_cpu(self, mock_automodel):
        """测试 ASR 模型使用 CPU 设备"""
        mock_model = MagicMock()
        mock_automodel.return_value = mock_model

        assistant = VoiceAssistant()
        assistant.load_asr()

        # Verify CPU device is used
        mock_automodel.assert_called_with(model=ASR_MODEL, device="cpu")


class TestAudioTranscription:
    """测试音频转录功能"""

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_transcribe_success(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试成功转录音频"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "<|zh|>你好世界</s>"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test_audio.wav"
        mock_exists.return_value = True

        # Create test audio
        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        text, language = assistant.transcribe(audio)

        # Verify
        assert "<|zh|>" in text or "你好世界" in text
        assert language == "zh"
        mock_model.generate.assert_called_once()
        mock_write_wav.assert_called_once()
        mock_remove.assert_called_once()

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_transcribe_empty_result(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试转录结果为空的情况"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.generate.return_value = []
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test_audio.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        text, language = assistant.transcribe(audio)

        # Should handle empty result gracefully
        assert text == ""
        assert language == DEFAULT_LANGUAGE

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_transcribe_cleans_up_temp_file(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试转录后清理临时文件"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "test"}]
        mock_automodel.return_value = mock_model
        tmp_file_path = "/tmp/test_audio.wav"
        mock_temp_file.return_value = tmp_file_path
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        assistant.transcribe(audio)

        # Verify temp file is removed
        mock_remove.assert_called_once_with(tmp_file_path)


class TestLanguageDetection:
    """测试语言检测功能"""

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_detect_chinese(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试检测中文"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "<|zh|>你好</s>"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)
        assistant = VoiceAssistant()
        _, language = assistant.transcribe(audio)

        assert language == "zh"

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_detect_english(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试检测英文"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "<|en|>hello world</s>"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)
        assistant = VoiceAssistant()
        _, language = assistant.transcribe(audio)

        assert language == "en"

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_detect_japanese(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试检测日语"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "<|ja|>こんにちは</s>"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)
        assistant = VoiceAssistant()
        _, language = assistant.transcribe(audio)

        assert language == "ja"

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_no_language_tag_uses_default(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试无语言标签时使用默认语言"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "no language tag"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)
        assistant = VoiceAssistant()
        _, language = assistant.transcribe(audio)

        assert language == DEFAULT_LANGUAGE


class TestAsyncTranscription:
    """测试异步转录功能"""

    @pytest.mark.asyncio
    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    async def test_transcribe_async_success(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试异步转录成功"""
        # Setup mocks
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "<|zh|>异步测试</s>"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/async_test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        text, language = await assistant.transcribe_async(audio)

        # Verify
        assert isinstance(text, str)
        assert language in ["zh", "en", "ja", "ko", "yue"]
        mock_model.generate.assert_called_once()

    @pytest.mark.asyncio
    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    async def test_transcribe_async_runs_in_executor(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试异步转录在执行器中运行"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "test"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        result = await assistant.transcribe_async(audio)

        # Should return a tuple
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestSecureTempFileHandling:
    """测试安全临时文件处理"""

    def test_create_secure_temp_file_returns_path(self):
        """测试创建安全临时文件返回路径"""
        tmp_file = create_secure_temp_file(suffix=".wav")
        try:
            assert tmp_file is not None
            assert isinstance(tmp_file, str)
            assert tmp_file.endswith(".wav")
            assert os.path.exists(tmp_file)
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_create_secure_temp_file_is_writable(self):
        """测试临时文件可写"""
        tmp_file = create_secure_temp_file(suffix=".wav")
        try:
            # Try to write to the file
            with open(tmp_file, "wb") as f:
                f.write(b"test data")

            # Verify data was written
            with open(tmp_file, "rb") as f:
                data = f.read()
                assert data == b"test data"
        finally:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_temp_file_cleanup_on_error(self):
        """测试错误时临时文件清理"""
        # This is tested implicitly in transcribe tests with mock_remove
        pass


class TestASRIntegration:
    """ASR 集成测试"""

    def test_asr_model_constant_valid(self):
        """测试 ASR 模型常量格式正确"""
        # SenseVoice model should follow format: org/model
        assert "/" in ASR_MODEL
        parts = ASR_MODEL.split("/")
        assert len(parts) == 2
        assert parts[0] == "iic"
        assert parts[1] == "SenseVoiceSmall"

    def test_supported_languages(self):
        """测试支持的语言列表"""
        supported_langs = ["zh", "en", "ja", "ko", "yue"]
        assert DEFAULT_LANGUAGE in supported_langs

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_audio_format_conversion(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试音频格式转换"""
        mock_model = MagicMock()
        mock_model.generate.return_value = [{"text": "test"}]
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        # Input is float32 in range [-1, 1]
        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        assistant.transcribe(audio)

        # Verify write_wav was called
        mock_write_wav.assert_called_once()
        call_args = mock_write_wav.call_args
        written_audio = call_args[0][2]

        # Audio should be converted to int16
        assert written_audio.dtype == np.int16


class TestASRErrorHandling:
    """测试 ASR 错误处理"""

    @patch("funasr.AutoModel")
    def test_asr_load_failure(self, mock_automodel):
        """测试 ASR 模型加载失败"""
        # Simulate model loading failure
        mock_automodel.side_effect = RuntimeError("Model load failed")

        assistant = VoiceAssistant()
        with pytest.raises(RuntimeError) as exc_info:
            assistant.load_asr()

        assert "Model load failed" in str(exc_info.value)

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    def test_transcribe_write_failure(self, mock_write_wav, mock_temp_file, mock_automodel):
        """测试写入临时文件失败"""
        mock_model = MagicMock()
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_write_wav.side_effect = OSError("Write failed")

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        with pytest.raises(OSError):
            assistant.transcribe(audio)

    @patch("funasr.AutoModel")
    @patch("speekium.create_secure_temp_file")
    @patch("speekium.write_wav")
    @patch("os.path.exists")
    @patch("os.remove")
    def test_transcribe_generation_failure(
        self, mock_remove, mock_exists, mock_write_wav, mock_temp_file, mock_automodel
    ):
        """测试 ASR 生成失败"""
        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("Generation failed")
        mock_automodel.return_value = mock_model
        mock_temp_file.return_value = "/tmp/test.wav"
        mock_exists.return_value = True

        audio = np.random.randn(16000).astype(np.float32)

        assistant = VoiceAssistant()
        with pytest.raises(RuntimeError):
            assistant.transcribe(audio)

        # Temp file should still be cleaned up
        mock_remove.assert_called_once()


# Mark tests for categorization
pytest.mark.unit
pytest.mark.asr
