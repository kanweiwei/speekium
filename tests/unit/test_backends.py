"""
LLM Backend 单元测试

重点测试：
1. P0 安全修复 - validate_input() 函数
2. 后端创建和配置
3. 对话历史管理
"""

from unittest.mock import MagicMock, patch

import pytest

from backends import (
    MAX_INPUT_LENGTH,
    ClaudeBackend,
    OllamaBackend,
    create_backend,
    validate_input,
)


class TestInputValidation:
    """测试输入验证功能（P0 安全修复）"""

    def test_validate_normal_input(self):
        """测试正常输入通过验证"""
        text = "Hello, how are you?"
        result = validate_input(text)
        assert result == text

    def test_validate_chinese_input(self):
        """测试中文输入"""
        text = "你好，今天天气怎么样？"
        result = validate_input(text)
        assert result == text

    def test_validate_multiline_input(self):
        """测试多行输入（保留换行符）"""
        text = "Line 1\nLine 2\nLine 3"
        result = validate_input(text)
        assert "\n" in result
        assert "Line 1" in result

    def test_reject_too_long_input(self):
        """测试拒绝过长输入"""
        text = "a" * (MAX_INPUT_LENGTH + 1)
        with pytest.raises(ValueError, match="too long"):
            validate_input(text)

    def test_reject_empty_input(self):
        """测试拒绝空输入"""
        with pytest.raises(ValueError, match="empty"):
            validate_input("   ")

    def test_reject_empty_string(self):
        """测试拒绝空字符串"""
        with pytest.raises(ValueError, match="empty"):
            validate_input("")

    def test_reject_xss_script_tag(self):
        """测试拒绝 XSS 攻击（script 标签）"""
        text = '<script>alert("XSS")</script>'
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input(text)

    def test_reject_xss_script_tag_uppercase(self):
        """测试拒绝大写 script 标签"""
        text = '<SCRIPT>alert("XSS")</SCRIPT>'
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input(text)

    def test_reject_javascript_url(self):
        """测试拒绝 JavaScript URL"""
        text = "javascript:alert(1)"
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input(text)

    def test_reject_javascript_url_uppercase(self):
        """测试拒绝大写 JavaScript URL"""
        text = "JAVASCRIPT:alert(1)"
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input(text)

    def test_reject_null_byte(self):
        """测试拒绝空字节注入"""
        text = "test\x00injection"
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input(text)

    def test_filter_control_characters(self):
        """测试过滤控制字符"""
        text = "hello\x01\x02\x03world"
        result = validate_input(text)
        # 控制字符应该被移除
        assert "\x01" not in result
        assert "\x02" not in result
        assert "\x03" not in result
        assert result == "helloworld"

    def test_preserve_allowed_control_characters(self):
        """测试保留允许的控制字符（换行、制表符）"""
        text = "line1\nline2\ttab"
        result = validate_input(text)
        assert "\n" in result
        assert "\t" in result

    def test_reject_non_string_input(self):
        """测试拒绝非字符串输入"""
        with pytest.raises(ValueError, match="must be a string"):
            validate_input(123)

    def test_reject_none_input(self):
        """测试拒绝 None 输入"""
        with pytest.raises(ValueError, match="must be a string"):
            validate_input(None)

    def test_custom_max_length(self):
        """测试自定义最大长度"""
        text = "a" * 100
        # 应该通过默认长度验证
        validate_input(text)
        # 应该拒绝自定义长度验证
        with pytest.raises(ValueError, match="too long"):
            validate_input(text, max_length=50)


class TestBackendCreation:
    """测试后端创建逻辑"""

    def test_create_claude_backend(self):
        """测试创建 Claude 后端"""
        backend = create_backend("claude", "You are a helpful assistant")
        assert isinstance(backend, ClaudeBackend)

    def test_create_ollama_backend(self):
        """测试创建 Ollama 后端"""
        backend = create_backend("ollama", "You are a helpful assistant")
        assert isinstance(backend, OllamaBackend)

    def test_create_ollama_with_model(self):
        """测试创建指定模型的 Ollama 后端"""
        backend = create_backend("ollama", "You are a helpful assistant", model="llama2")
        assert isinstance(backend, OllamaBackend)
        assert backend.model == "llama2"

    def test_create_ollama_default_model(self):
        """测试 Ollama 默认模型"""
        backend = create_backend("ollama", "You are a helpful assistant")
        # 应该有默认模型
        assert backend.model is not None
        assert len(backend.model) > 0

    def test_invalid_backend_type(self):
        """测试无效的后端类型"""
        with pytest.raises(ValueError, match="Unknown backend"):
            create_backend("invalid_backend", "test prompt")


class TestClaudeBackend:
    """测试 Claude 后端"""

    def test_claude_initialization(self):
        """测试 Claude 后端初始化"""
        backend = ClaudeBackend("You are a helpful assistant")
        assert backend.history == []
        assert backend.system_prompt is not None

    def test_claude_custom_system_prompt(self):
        """测试自定义系统提示词"""
        custom_prompt = "You are a helpful assistant."
        backend = ClaudeBackend(system_prompt=custom_prompt)
        assert backend.system_prompt == custom_prompt

    @patch("subprocess.run")
    def test_claude_chat_validates_input(self, mock_run):
        """测试 Claude chat 方法调用输入验证"""
        backend = ClaudeBackend("You are a helpful assistant")

        # 模拟成功的 subprocess 调用
        mock_run.return_value = MagicMock(stdout="Test response", returncode=0)

        # 测试正常输入
        result = backend.chat("Hello")
        assert result == "Test response"

        # 测试输入验证被调用（通过尝试无效输入）
        result = backend.chat("   ")
        assert "Error" in result or "validation" in result.lower()

    @patch("subprocess.run")
    def test_claude_chat_handles_xss(self, mock_run):
        """测试 Claude chat 拒绝 XSS 输入"""
        backend = ClaudeBackend("You are a helpful assistant")

        # 尝试 XSS 攻击
        result = backend.chat('<script>alert("XSS")</script>')
        assert "Error" in result
        # subprocess 不应该被调用
        assert not mock_run.called

    def test_claude_conversation_history(self):
        """测试对话历史管理"""
        backend = ClaudeBackend("You are a helpful assistant")
        assert len(backend.history) == 0

        # 添加消息后应该记录历史
        backend.add_message("user", "test")
        assert len(backend.history) == 1


class TestOllamaBackend:
    """测试 Ollama 后端"""

    def test_ollama_initialization(self):
        """测试 Ollama 后端初始化"""
        backend = OllamaBackend("You are a helpful assistant")
        assert backend.history == []
        assert backend.model is not None

    def test_ollama_custom_model(self):
        """测试自定义模型"""
        backend = OllamaBackend("You are a helpful assistant", model="custom-model")
        assert backend.model == "custom-model"

    @patch("httpx.post")
    def test_ollama_chat_validates_input(self, mock_post):
        """测试 Ollama chat 方法调用输入验证"""
        backend = OllamaBackend("You are a helpful assistant")

        # 模拟成功的 HTTP 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Test response"}}
        mock_post.return_value = mock_response

        # 测试正常输入
        result = backend.chat("Hello")
        assert result == "Test response"

        # 测试输入验证（空输入应该被拒绝）
        result = backend.chat("   ")
        assert "Error" in result or "validation" in result.lower()

    @patch("httpx.post")
    def test_ollama_chat_handles_xss(self, mock_post):
        """测试 Ollama chat 拒绝 XSS 输入"""
        backend = OllamaBackend("You are a helpful assistant")

        # 尝试 XSS 攻击
        result = backend.chat('<script>alert("XSS")</script>')
        assert "Error" in result
        # HTTP 请求不应该被调用
        assert not mock_post.called

    def test_ollama_conversation_history(self):
        """测试对话历史管理"""
        backend = OllamaBackend("You are a helpful assistant")
        assert len(backend.history) == 0


class TestSecurityIntegration:
    """集成安全测试 - 验证 P0 修复在实际使用中生效"""

    @patch("subprocess.run")
    def test_claude_end_to_end_security(self, mock_run):
        """端到端测试 Claude 后端的安全性"""
        backend = ClaudeBackend("You are a helpful assistant")

        # 测试各种攻击向量
        attack_vectors = [
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "test\x00injection",
            "a" * 10001,  # 过长输入
        ]

        for attack in attack_vectors:
            result = backend.chat(attack)
            assert "Error" in result, f"Failed to block: {attack}"
            # 确保没有调用实际的后端
            assert not mock_run.called, f"Backend was called with: {attack}"

    @patch("httpx.post")
    def test_ollama_end_to_end_security(self, mock_post):
        """端到端测试 Ollama 后端的安全性"""
        backend = OllamaBackend("You are a helpful assistant")

        # 测试各种攻击向量
        attack_vectors = [
            "<script>alert(1)</script>",
            "javascript:alert(1)",
            "test\x00injection",
            "a" * 10001,  # 过长输入
        ]

        for attack in attack_vectors:
            result = backend.chat(attack)
            assert "Error" in result, f"Failed to block: {attack}"
            # 确保没有调用实际的后端
            assert not mock_post.called, f"Backend was called with: {attack}"


# 标记测试
pytest.mark.unit
pytest.mark.security
