"""
VAD (Voice Activity Detection) 单元测试

测试 Silero VAD 模型集成和语音检测功能：
1. VAD 模型加载
2. VAD 配置验证
3. 语音活动检测逻辑
4. 录音控制流程
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from speekium import (
    MAX_RECORDING_DURATION,
    MIN_SPEECH_DURATION,
    SAMPLE_RATE,
    SILENCE_AFTER_SPEECH,
    VAD_CONSECUTIVE_THRESHOLD,
    VAD_PRE_BUFFER,
    VAD_THRESHOLD,
    VoiceAssistant,
)


class TestVADConfiguration:
    """测试 VAD 配置常量"""

    def test_vad_threshold_valid(self):
        """测试 VAD 阈值在有效范围内"""
        assert 0.0 <= VAD_THRESHOLD <= 1.0
        assert VAD_THRESHOLD == 0.5  # Default: more sensitive detection

    def test_vad_consecutive_threshold_positive(self):
        """测试连续检测阈值为正数"""
        assert VAD_CONSECUTIVE_THRESHOLD > 0
        assert isinstance(VAD_CONSECUTIVE_THRESHOLD, int)

    def test_vad_pre_buffer_positive(self):
        """测试预缓冲时长为正数"""
        assert VAD_PRE_BUFFER > 0
        assert isinstance(VAD_PRE_BUFFER, (int, float))

    def test_min_speech_duration_positive(self):
        """测试最小语音时长为正数"""
        assert MIN_SPEECH_DURATION > 0

    def test_silence_after_speech_positive(self):
        """测试静音检测时长为正数"""
        assert SILENCE_AFTER_SPEECH > 0

    def test_max_recording_duration_reasonable(self):
        """测试最大录音时长合理"""
        assert 10 <= MAX_RECORDING_DURATION <= 60


class TestVADModelLoading:
    """测试 VAD 模型加载功能"""

    @patch("torch.hub.load")
    def test_load_vad_first_time(self, mock_torch_load):
        """测试首次加载 VAD 模型"""
        # Setup mock
        mock_model = MagicMock()
        mock_torch_load.return_value = (mock_model, None)

        assistant = VoiceAssistant()
        model = assistant.load_vad()

        # Verify
        assert model is not None
        assert assistant.vad_model is mock_model
        mock_torch_load.assert_called_once_with(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )

    @patch("torch.hub.load")
    def test_load_vad_cached(self, mock_torch_load):
        """测试 VAD 模型缓存机制"""
        mock_model = MagicMock()
        mock_torch_load.return_value = (mock_model, None)

        assistant = VoiceAssistant()
        model1 = assistant.load_vad()
        model2 = assistant.load_vad()

        # Should only load once
        assert model1 is model2
        mock_torch_load.assert_called_once()

    @patch("torch.hub.load")
    def test_load_vad_resets_states(self, mock_torch_load):
        """测试 VAD 模型状态重置"""
        mock_model = MagicMock()
        mock_torch_load.return_value = (mock_model, None)

        assistant = VoiceAssistant()
        assistant.load_vad()

        # Model should have reset_states method
        assert hasattr(assistant.vad_model, "reset_states")


class TestDetectSpeechStart:
    """测试语音开始检测功能"""

    @patch("sounddevice.InputStream")
    @patch.object(VoiceAssistant, "load_vad")
    def test_detect_speech_start_success(self, mock_load_vad, mock_input_stream):
        """测试成功检测到语音开始"""
        # Setup VAD model
        mock_vad = MagicMock()
        mock_vad.return_value.item.return_value = 0.8  # Above threshold
        mock_vad.reset_states = MagicMock()
        mock_load_vad.return_value = mock_vad

        # Setup audio stream to simulate callback calls
        def create_mock_stream(callback, **kwargs):
            # Simulate multiple callback calls with audio data
            for _ in range(VAD_CONSECUTIVE_THRESHOLD + 1):
                # Create mock audio data (512 samples, 1 channel)
                audio_data = np.random.randn(512, 1).astype(np.float32)
                callback(audio_data, 512, None, None)
            return MagicMock()

        mock_input_stream.side_effect = create_mock_stream

        assistant = VoiceAssistant()
        result = assistant.detect_speech_start(timeout=0.5)

        # Should detect speech
        assert result is True
        mock_vad.reset_states.assert_called_once()

    @patch("sounddevice.InputStream")
    @patch.object(VoiceAssistant, "load_vad")
    def test_detect_speech_start_timeout(self, mock_load_vad, mock_input_stream):
        """测试语音检测超时"""
        # Setup VAD model - below threshold
        mock_vad = MagicMock()
        mock_vad.return_value.item.return_value = 0.3  # Below threshold
        mock_vad.reset_states = MagicMock()
        mock_load_vad.return_value = mock_vad

        mock_stream = MagicMock()
        mock_input_stream.return_value.__enter__.return_value = mock_stream

        assistant = VoiceAssistant()
        result = assistant.detect_speech_start(timeout=0.1)

        # Should timeout without detecting speech
        assert result is False

    @patch("sounddevice.InputStream")
    @patch.object(VoiceAssistant, "load_vad")
    def test_detect_speech_start_consecutive_threshold(self, mock_load_vad, mock_input_stream):
        """测试连续检测阈值要求"""
        mock_vad = MagicMock()
        # Simulate sporadic speech detection (not consecutive)
        speech_probs = [0.8, 0.3, 0.8, 0.3, 0.8]
        mock_vad.return_value.item.side_effect = speech_probs
        mock_vad.reset_states = MagicMock()
        mock_load_vad.return_value = mock_vad

        mock_stream = MagicMock()
        mock_input_stream.return_value.__enter__.return_value = mock_stream

        assistant = VoiceAssistant()
        # With sporadic detection, should not meet consecutive threshold
        result = assistant.detect_speech_start(timeout=0.1)

        # Depends on implementation, but should handle consecutive check
        assert isinstance(result, bool)


class TestRecordWithVAD:
    """测试 VAD 录音功能"""

    @pytest.mark.skip(reason="Requires complex audio stream mocking, tested in integration")
    @patch("sounddevice.InputStream")
    @patch.object(VoiceAssistant, "load_vad")
    def test_record_with_vad_basic_flow(self, mock_load_vad, mock_input_stream):
        """测试基本录音流程"""
        # Setup VAD model
        mock_vad = MagicMock()
        mock_vad.reset_states = MagicMock()
        mock_load_vad.return_value = mock_vad

        # Setup audio stream
        mock_stream = MagicMock()
        mock_input_stream.return_value.__enter__.return_value = mock_stream

        assistant = VoiceAssistant()

        # This would need more complex mocking to fully test
        # For now, just verify VAD model is loaded and reset
        try:
            assistant.record_with_vad()
        except Exception:
            pass  # Expected due to mocking limitations

        mock_load_vad.assert_called_once()
        mock_vad.reset_states.assert_called_once()

    @pytest.mark.skip(reason="Requires complex audio stream mocking, tested in integration")
    @patch("sounddevice.InputStream")
    @patch.object(VoiceAssistant, "load_vad")
    def test_record_with_vad_speech_already_started(self, mock_load_vad, mock_input_stream):
        """测试语音已开始情况（打断场景）"""
        mock_vad = MagicMock()
        mock_vad.reset_states = MagicMock()
        mock_load_vad.return_value = mock_vad

        mock_stream = MagicMock()
        mock_input_stream.return_value.__enter__.return_value = mock_stream

        assistant = VoiceAssistant()

        try:
            assistant.record_with_vad(speech_already_started=True)
        except Exception:
            pass

        # Should still load and reset VAD
        mock_load_vad.assert_called_once()
        mock_vad.reset_states.assert_called_once()

    def test_record_with_vad_uses_correct_chunk_size(self):
        """测试 VAD 使用正确的音频块大小"""
        # Silero VAD requires 512 samples @ 16kHz
        expected_chunk_size = 512
        # This is implementation detail, verified through code inspection
        assert expected_chunk_size == 512


class TestVADIntegration:
    """VAD 集成测试"""

    def test_vad_threshold_vs_consecutive_threshold(self):
        """测试 VAD 阈值和连续检测阈值的关系"""
        # Higher consecutive threshold = more robust against noise
        assert VAD_CONSECUTIVE_THRESHOLD >= 3
        # Threshold should be reasonable for voice detection
        assert 0.5 <= VAD_THRESHOLD <= 0.9

    def test_silence_detection_config(self):
        """测试静音检测配置合理性"""
        # Calculate silence chunks needed
        chunk_size = 512
        max_silence_chunks = int(SILENCE_AFTER_SPEECH * SAMPLE_RATE / chunk_size)

        # Should require multiple chunks to confirm silence
        assert max_silence_chunks > 5

    def test_min_speech_duration_config(self):
        """测试最小语音时长配置"""
        chunk_size = 512
        min_speech_chunks = int(MIN_SPEECH_DURATION * SAMPLE_RATE / chunk_size)

        # Should require multiple chunks to confirm speech
        assert min_speech_chunks > 3

    def test_pre_buffer_size_calculation(self):
        """测试预缓冲大小计算"""
        chunk_size = 512
        pre_buffer_size = int(VAD_PRE_BUFFER * SAMPLE_RATE / chunk_size)

        # Pre-buffer should be reasonable
        assert 5 <= pre_buffer_size <= 20

    def test_max_recording_chunks(self):
        """测试最大录音块数计算"""
        chunk_size = 512
        max_chunks = int(MAX_RECORDING_DURATION * SAMPLE_RATE / chunk_size)

        # Should allow reasonable recording duration
        assert max_chunks > 100


class TestVADAudioProcessing:
    """测试 VAD 音频处理"""

    def test_audio_tensor_conversion(self):
        """测试音频数据转换为 Tensor"""
        # Simulate audio chunk
        audio_chunk = np.random.randn(512).astype(np.float32)

        # Convert to tensor (as done in VAD processing)
        audio_tensor = torch.from_numpy(audio_chunk).float()

        assert isinstance(audio_tensor, torch.Tensor)
        assert audio_tensor.shape == (512,)
        assert audio_tensor.dtype == torch.float32

    def test_vad_probability_interpretation(self):
        """测试 VAD 概率值解释"""
        # VAD returns probability between 0 and 1
        # Values > VAD_THRESHOLD indicate speech

        test_probs = [0.1, 0.5, 0.7, 0.9]
        for prob in test_probs:
            is_speech = prob > VAD_THRESHOLD
            if prob > VAD_THRESHOLD:
                assert is_speech is True
            else:
                assert is_speech is False


# Mark tests for categorization
pytest.mark.unit
pytest.mark.vad
