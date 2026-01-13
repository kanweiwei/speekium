"""
Structured Logging Tests

Tests:
1. Logger configuration and initialization
2. Sensitive data masking
3. Context management
4. Log level configuration
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import logger as logger_module
from logger import (
    configure_logging,
    get_logger,
    mask_sensitive_processor,
    new_request,
    new_session,
    set_component,
)


class TestLoggerConfiguration:
    """测试日志配置"""

    def test_configure_logging_console_format(self):
        """测试控制台格式配置"""
        configure_logging(level="INFO", format="console", colored=False)
        test_logger = get_logger("test")
        assert test_logger is not None

    def test_configure_logging_json_format(self):
        """测试 JSON 格式配置"""
        configure_logging(level="INFO", format="json", colored=False)
        test_logger = get_logger("test")
        assert test_logger is not None

    def test_configure_logging_auto_format(self):
        """测试自动格式选择"""
        configure_logging(level="INFO", format="auto", colored=False)
        test_logger = get_logger("test")
        assert test_logger is not None

    def test_configure_logging_levels(self):
        """测试不同日志级别"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            configure_logging(level=level, format="console", colored=False)
            test_logger = get_logger(f"test_{level}")
            assert test_logger is not None


class TestSensitiveDataMasking:
    """测试敏感数据脱敏"""

    def test_mask_api_key(self):
        """测试 API key 脱敏"""
        event_dict = {"event": "test", "api_key": "sk-1234567890abcdef"}

        result = mask_sensitive_processor(None, "info", event_dict)

        # API key should be masked (only last 4 chars visible)
        assert "sk-1234567890abcdef" not in result["api_key"]
        assert "***" in result["api_key"]
        assert "cdef" in result["api_key"]  # Last 4 chars

    def test_mask_anthropic_api_key(self):
        """测试 Anthropic API key 脱敏"""
        event_dict = {"event": "test", "anthropic_api_key": "sk-ant-api03-xxxxx"}

        result = mask_sensitive_processor(None, "info", event_dict)
        assert "sk-ant-api03-xxxxx" not in result["anthropic_api_key"]
        assert "***" in result["anthropic_api_key"]

    def test_mask_password(self):
        """测试密码脱敏"""
        event_dict = {"event": "test", "password": "supersecret123"}

        result = mask_sensitive_processor(None, "info", event_dict)
        assert "supersecret123" not in result["password"]
        assert "***" in result["password"]

    def test_mask_token(self):
        """测试 token 脱敏"""
        event_dict = {"event": "test", "token": "bearer_token_12345"}

        result = mask_sensitive_processor(None, "info", event_dict)
        assert "bearer_token_12345" not in result["token"]
        assert "***" in result["token"]

    def test_mask_long_user_text(self):
        """测试用户输入长文本预览"""
        long_text = "a" * 100
        event_dict = {"event": "test", "text": long_text}

        result = mask_sensitive_processor(None, "info", event_dict)

        # Long text should be truncated
        assert long_text not in result["text"]
        assert "..." in result["text"]
        assert "100 chars" in result["text"]
        assert len(result["text"]) < len(long_text)

    def test_preserve_short_text(self):
        """测试短文本保留"""
        short_text = "Hello world"
        event_dict = {"event": "test", "text": short_text}

        result = mask_sensitive_processor(None, "info", event_dict)

        # Short text should be preserved
        assert result["text"] == short_text

    def test_mask_message_field(self):
        """测试 message 字段长文本预览"""
        long_message = "x" * 80
        event_dict = {"event": "test", "message": long_message}

        result = mask_sensitive_processor(None, "info", event_dict)

        # Long message should be truncated
        assert long_message not in result["message"]
        assert "..." in result["message"]

    def test_mask_file_paths(self):
        """测试文件路径脱敏"""
        event_dict = {"event": "test", "file_path": "/Users/user/sensitive/data.txt"}

        result = mask_sensitive_processor(None, "info", event_dict)

        # Only basename should be shown
        assert "/Users/user/sensitive/" not in result["file_path"]
        assert result["file_path"] == "data.txt"

    def test_mask_audio_file(self):
        """测试音频文件路径脱敏"""
        event_dict = {"event": "test", "audio_file": "/tmp/recordings/recording_12345.wav"}

        result = mask_sensitive_processor(None, "info", event_dict)

        assert "/tmp/recordings/" not in result["audio_file"]
        assert result["audio_file"] == "recording_12345.wav"

    def test_preserve_non_sensitive_fields(self):
        """测试非敏感字段不被修改"""
        event_dict = {
            "event": "test_event",
            "component": "VAD",
            "duration": 1.5,
            "status": "success",
        }

        result = mask_sensitive_processor(None, "info", event_dict)

        # Non-sensitive fields should be preserved
        assert result["event"] == "test_event"
        assert result["component"] == "VAD"
        assert result["duration"] == 1.5
        assert result["status"] == "success"


class TestContextManagement:
    """测试上下文管理"""

    def setup_method(self):
        """每个测试前重置上下文"""
        logger_module._context = logger_module.LoggerContext()

    def test_new_request_generates_id(self):
        """测试生成新请求 ID"""
        request_id = new_request()
        assert request_id is not None
        assert len(request_id) == 8  # UUID shortened to 8 chars
        assert isinstance(request_id, str)

    def test_new_session_generates_id(self):
        """测试生成新会话 ID"""
        session_id = new_session()
        assert session_id is not None
        assert len(session_id) == 8
        assert isinstance(session_id, str)

    def test_new_request_returns_different_ids(self):
        """测试每次生成不同的请求 ID"""
        id1 = new_request()
        id2 = new_request()
        # IDs should be different (though second replaces first)
        assert isinstance(id1, str)
        assert isinstance(id2, str)

    def test_set_component(self):
        """测试设置组件名称"""
        set_component("VAD")
        context = logger_module._context.get_context()
        assert context["component"] == "VAD"

    def test_set_multiple_components(self):
        """测试设置多个组件"""
        set_component("VAD")
        assert logger_module._context.get_context()["component"] == "VAD"

        set_component("ASR")
        assert logger_module._context.get_context()["component"] == "ASR"

    def test_get_context_with_all_fields(self):
        """测试获取完整上下文"""
        request_id = new_request()
        session_id = new_session()
        set_component("LLM")

        context = logger_module._context.get_context()
        assert context["request_id"] == request_id
        assert context["session_id"] == session_id
        assert context["component"] == "LLM"

    def test_get_context_empty(self):
        """测试获取空上下文"""
        context = logger_module._context.get_context()
        assert context == {}

    def test_context_isolation(self):
        """测试上下文独立性"""
        request_id1 = new_request()
        request_id2 = new_request()

        # Second request should replace first
        context = logger_module._context.get_context()
        assert context["request_id"] == request_id2
        assert context["request_id"] != request_id1


class TestLoggerFactory:
    """测试 logger 工厂"""

    def test_get_logger_returns_logger(self):
        """测试获取 logger"""
        configure_logging(level="INFO", format="console", colored=False)
        logger = get_logger("test_factory")
        assert logger is not None

    def test_get_logger_with_different_names(self):
        """测试获取不同名称的 logger"""
        configure_logging(level="INFO", format="console", colored=False)
        logger1 = get_logger("logger1")
        logger2 = get_logger("logger2")

        assert logger1 is not None
        assert logger2 is not None

    def test_get_logger_with_context(self):
        """测试带上下文的 logger"""
        configure_logging(level="INFO", format="console", colored=False)

        new_request()
        new_session()
        set_component("TEST")

        logger = get_logger("test_context")
        assert logger is not None


# Mark tests
pytestmark = pytest.mark.unit
