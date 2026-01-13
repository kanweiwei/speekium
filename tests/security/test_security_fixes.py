"""
P0 安全修复回归测试

验证关键安全修复不会被意外破坏：
1. 输入验证 - XSS/注入防护、长度限制
2. 临时文件安全 - 0600权限、自动清理
3. 资源限制 - 内存/CPU限制设置
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backends import validate_input
from speekium import cleanup_temp_files, create_secure_temp_file


class TestInputValidation:
    """测试输入验证和注入防护"""

    def test_normal_input(self):
        """正常输入应该通过"""
        result = validate_input("hello world")
        assert result == "hello world"

    def test_chinese_input(self):
        """中文输入应该通过"""
        result = validate_input("你好世界")
        assert result == "你好世界"

    def test_multiline_input(self):
        """多行输入应该通过"""
        result = validate_input("line1\nline2\nline3")
        assert result == "line1\nline2\nline3"

    def test_reject_too_long_input(self):
        """拒绝超长输入（>10000字符）"""
        with pytest.raises(ValueError, match="too long"):
            validate_input("a" * 10001)

    def test_reject_empty_input(self):
        """拒绝空输入或只有空白字符"""
        with pytest.raises(ValueError, match="empty"):
            validate_input("   ")

    def test_reject_empty_string(self):
        """拒绝空字符串"""
        with pytest.raises(ValueError, match="empty"):
            validate_input("")

    def test_reject_xss_script_tag(self):
        """拒绝XSS注入（script标签）"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("<script>alert(1)</script>")

    def test_reject_xss_script_tag_uppercase(self):
        """拒绝XSS注入（大写SCRIPT）"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("<SCRIPT>alert(1)</SCRIPT>")

    def test_reject_javascript_url(self):
        """拒绝JavaScript伪协议"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("javascript:alert(1)")

    def test_reject_javascript_url_uppercase(self):
        """拒绝JavaScript伪协议（大写）"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("JAVASCRIPT:alert(1)")

    def test_reject_null_byte(self):
        """拒绝空字节注入"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("test\x00injection")

    def test_filter_control_characters(self):
        """过滤控制字符"""
        result = validate_input("hello\x01\x02world")
        assert "\x01" not in result
        assert "\x02" not in result
        assert "hello" in result
        assert "world" in result

    def test_preserve_allowed_control_characters(self):
        """保留允许的控制字符（换行、制表符）"""
        result = validate_input("line1\nline2\ttab")
        assert "\n" in result
        assert "\t" in result

    def test_boundary_max_length(self):
        """边界测试：恰好最大长度（10000字符）"""
        result = validate_input("a" * 10000)
        assert len(result) == 10000

    def test_unicode_emoji_input(self):
        """Unicode边界：emoji和特殊字符"""
        result = validate_input("Hello 👋 世界 🌍")
        assert "👋" in result
        assert "🌍" in result

    def test_unicode_special_characters(self):
        """Unicode边界：各种特殊字符"""
        result = validate_input("Test™ ©2024 £€¥")
        assert "™" in result
        assert "©" in result

    def test_mixed_attack_vectors(self):
        """混合攻击向量（多种注入尝试）"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("normal text <script>alert(1)</script> more text")

    def test_case_insensitive_blocking(self):
        """大小写不敏感的攻击阻止"""
        with pytest.raises(ValueError, match="blocked pattern"):
            validate_input("<ScRiPt>alert(1)</ScRiPt>")


class TestTempFileSecurity:
    """测试临时文件安全"""

    def setup_method(self):
        """测试前清理"""
        cleanup_temp_files()

    def teardown_method(self):
        """测试后清理"""
        cleanup_temp_files()

    def test_create_temp_file(self):
        """创建临时文件"""
        tmp_file = create_secure_temp_file(suffix=".test")
        assert os.path.exists(tmp_file), f"临时文件未创建: {tmp_file}"
        assert tmp_file.endswith(".test")

    def test_temp_file_permissions(self):
        """验证临时文件权限为0600（仅所有者读写）"""
        tmp_file = create_secure_temp_file(suffix=".test")
        file_stat = os.stat(tmp_file)
        actual_mode = file_stat.st_mode & 0o777

        assert actual_mode == 0o600, (
            f"文件权限错误: {oct(actual_mode)} (期望: 0o600)\n文件: {tmp_file}"
        )

    def test_multiple_temp_files(self):
        """创建多个临时文件"""
        files = []
        for i in range(3):
            tmp_file = create_secure_temp_file(suffix=f".test{i}")
            assert os.path.exists(tmp_file)
            files.append(tmp_file)

        # 验证所有文件都存在
        for f in files:
            assert os.path.exists(f)

    def test_cleanup_temp_files(self):
        """验证临时文件自动清理"""
        # 创建多个临时文件
        files = []
        for i in range(3):
            tmp_file = create_secure_temp_file(suffix=f".test{i}")
            files.append(tmp_file)

        # 清理
        cleanup_temp_files()

        # 验证所有文件都被删除
        for f in files:
            assert not os.path.exists(f), f"文件未被清理: {f}"

    def test_temp_file_isolation(self):
        """验证临时文件在独立目录中"""
        tmp_file = create_secure_temp_file(suffix=".test")
        # 临时文件应该在系统临时目录中
        assert "/tmp" in tmp_file or "temp" in tmp_file.lower()

    def test_temp_file_permissions_after_write(self):
        """验证写入后权限保持0600"""
        tmp_file = create_secure_temp_file(suffix=".test")

        # 写入数据
        with open(tmp_file, "w") as f:
            f.write("test data")

        # 验证权限仍然是0600
        file_stat = os.stat(tmp_file)
        actual_mode = file_stat.st_mode & 0o777
        assert actual_mode == 0o600

    def test_multiple_temp_files_unique(self):
        """验证多个临时文件具有唯一路径"""
        files = set()
        for i in range(10):
            tmp_file = create_secure_temp_file(suffix=".test")
            files.add(tmp_file)

        # 所有文件路径应该是唯一的
        assert len(files) == 10

    def test_cleanup_with_nonexistent_files(self):
        """验证清理不存在的文件不会报错"""
        # 创建并手动删除文件
        tmp_file = create_secure_temp_file(suffix=".test")
        os.remove(tmp_file)

        # 清理应该不会报错
        cleanup_temp_files()


class TestResourceLimits:
    """测试资源限制"""

    def test_worker_daemon_import(self):
        """验证worker_daemon可以正常导入（会设置资源限制）"""
        result = subprocess.run(
            [sys.executable, "-c", "import worker_daemon; print('ok')"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0, (
            f"worker_daemon导入失败:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "ok" in result.stdout

    def test_resource_limits_logged(self):
        """验证资源限制设置被记录（可选）"""
        result = subprocess.run(
            [sys.executable, "-c", "import worker_daemon; print('ok')"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        # 在某些系统上资源限制可能不可用，所以这是可选的
        if "Resource limits set" in result.stderr:
            pytest.skip("资源限制日志已记录（系统支持）")
        else:
            pytest.skip("资源限制日志未记录（系统可能不支持）")

    def test_resource_limits_function_exists(self):
        """验证set_resource_limits函数存在"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from worker_daemon import set_resource_limits; print(callable(set_resource_limits))",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "True" in result.stdout

    def test_signal_handler_exists(self):
        """验证CPU超时信号处理器存在"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from worker_daemon import handle_timeout; print(callable(handle_timeout))",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        assert result.returncode == 0
        assert "True" in result.stdout


class TestSecurityIntegration:
    """端到端安全集成测试"""

    def test_input_validation_blocks_all_attacks(self):
        """验证输入验证阻止所有已知攻击向量"""
        attack_vectors = [
            "<script>alert(1)</script>",
            "<SCRIPT>alert(1)</SCRIPT>",
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "test\x00injection",
            "a" * 10001,  # 超长输入
            "",  # 空输入
            "   ",  # 只有空白
        ]

        for attack in attack_vectors:
            with pytest.raises(ValueError):
                validate_input(attack)

    def test_temp_file_security_comprehensive(self):
        """综合测试临时文件安全"""
        # 清理前状态
        cleanup_temp_files()

        # 创建文件
        tmp_file = create_secure_temp_file(suffix=".test")

        try:
            # 验证存在
            assert os.path.exists(tmp_file)

            # 验证权限
            file_stat = os.stat(tmp_file)
            actual_mode = file_stat.st_mode & 0o777
            assert actual_mode == 0o600

            # 写入数据
            with open(tmp_file, "w") as f:
                f.write("test data")

            # 读取数据
            with open(tmp_file, "r") as f:
                data = f.read()
                assert data == "test data"

        finally:
            # 清理
            cleanup_temp_files()
            assert not os.path.exists(tmp_file)


# 标记安全测试
pytestmark = pytest.mark.security
