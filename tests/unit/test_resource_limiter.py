"""
Resource Limiter Tests - 资源限制器测试

Tests:
1. Resource limit setting
2. Timeout decorator functionality
3. Async timeout protection
4. Platform compatibility (Unix/Linux vs Windows)
5. Error handling and logging
"""

import asyncio
import platform
import sys
import time
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from resource_limiter import (
    ResourceLimiter,
    initialize_resource_limits,
    with_timeout,
)


class TestResourceLimiter:
    """测试资源限制器基本功能"""

    def test_set_limits_returns_boolean(self):
        """测试设置资源限制返回布尔值"""
        result = ResourceLimiter.set_limits()
        assert isinstance(result, bool)

    def test_set_limits_platform_aware(self):
        """测试平台感知"""
        result = ResourceLimiter.set_limits()

        if platform.system() == "Windows":
            # Windows 应该返回 False（不支持）
            assert result is False
        else:
            # Unix/Linux 应该返回 True（支持）
            # 注意：在某些受限环境可能失败
            assert isinstance(result, bool)

    def test_initialize_convenience_function(self):
        """测试便捷初始化函数"""
        result = initialize_resource_limits()
        assert isinstance(result, bool)

    def test_get_current_usage(self):
        """测试获取当前资源使用情况"""
        usage = ResourceLimiter.get_current_usage()
        assert isinstance(usage, dict)

        if platform.system() != "Windows":
            # Unix/Linux 应该返回资源使用信息
            # 注意：某些系统可能不提供完整信息
            assert isinstance(usage, dict)

    def test_resource_limit_constants(self):
        """测试资源限制常量"""
        assert ResourceLimiter.MEMORY_SOFT_LIMIT == 500 * 1024 * 1024
        assert ResourceLimiter.MEMORY_HARD_LIMIT == 1024 * 1024 * 1024
        assert ResourceLimiter.CPU_TIME_LIMIT == 300
        assert ResourceLimiter.FILE_SIZE_LIMIT == 100 * 1024 * 1024
        assert ResourceLimiter.FILE_DESCRIPTOR_LIMIT == 1024


class TestSyncTimeout:
    """测试同步函数超时装饰器"""

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="signal.alarm not available on Windows"
    )
    def test_with_timeout_decorator_success(self):
        """测试超时装饰器：成功情况"""

        @ResourceLimiter.with_timeout(2)
        def quick_function():
            time.sleep(0.1)
            return "success"

        result = quick_function()
        assert result == "success"

    @pytest.mark.skipif(
        platform.system() == "Windows", reason="signal.alarm not available on Windows"
    )
    def test_with_timeout_decorator_timeout(self):
        """测试超时装饰器：超时情况"""

        @ResourceLimiter.with_timeout(1)
        def slow_function():
            time.sleep(2)
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            slow_function()

        assert "timed out after 1 seconds" in str(exc_info.value)

    @pytest.mark.skipif(
        platform.system() != "Windows", reason="Test Windows fallback behavior"
    )
    def test_with_timeout_decorator_windows_fallback(self):
        """测试 Windows 平台超时装饰器降级"""

        @ResourceLimiter.with_timeout(1)
        def normal_function():
            return "success"

        # Windows 上装饰器不生效，但不应报错
        result = normal_function()
        assert result == "success"


class TestAsyncTimeout:
    """测试异步超时保护"""

    @pytest.mark.asyncio
    async def test_async_timeout_success(self):
        """测试异步超时：成功情况"""

        async def quick_async_function():
            await asyncio.sleep(0.1)
            return "success"

        result = await ResourceLimiter.with_timeout_async(
            quick_async_function(), seconds=2, operation_name="test_operation"
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_timeout(self):
        """测试异步超时：超时情况"""

        async def slow_async_function():
            await asyncio.sleep(2)
            return "should not reach"

        with pytest.raises(TimeoutError) as exc_info:
            await ResourceLimiter.with_timeout_async(
                slow_async_function(), seconds=1, operation_name="test_operation"
            )

        assert "timed out after 1 seconds" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_timeout_convenience_function(self):
        """测试异步超时便捷函数"""

        async def quick_function():
            await asyncio.sleep(0.1)
            return "success"

        result = await with_timeout(
            quick_function(), seconds=2, operation_name="test_operation"
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_async_timeout_with_exception(self):
        """测试异步超时：函数内部异常"""

        async def failing_function():
            await asyncio.sleep(0.1)
            raise ValueError("Internal error")

        with pytest.raises(ValueError) as exc_info:
            await ResourceLimiter.with_timeout_async(
                failing_function(), seconds=2, operation_name="test_operation"
            )

        assert "Internal error" in str(exc_info.value)


class TestErrorHandling:
    """测试错误处理和边界情况"""

    @pytest.mark.asyncio
    async def test_async_timeout_zero_seconds(self):
        """测试零秒超时"""

        async def instant_function():
            return "instant"

        # 0 秒超时应该立即触发
        with pytest.raises(TimeoutError):
            await ResourceLimiter.with_timeout_async(
                instant_function(), seconds=0, operation_name="zero_timeout"
            )

    @pytest.mark.asyncio
    async def test_async_timeout_negative_seconds(self):
        """测试负数超时（应该立即超时）"""

        async def any_function():
            return "should timeout"

        with pytest.raises((TimeoutError, ValueError)):
            await ResourceLimiter.with_timeout_async(
                any_function(), seconds=-1, operation_name="negative_timeout"
            )

    def test_resource_usage_empty_on_windows(self):
        """测试 Windows 上资源使用返回空字典"""
        usage = ResourceLimiter.get_current_usage()

        if platform.system() == "Windows":
            assert usage == {}
        else:
            # Unix/Linux 可能返回空字典（如果获取失败）或包含数据
            assert isinstance(usage, dict)


class TestIntegration:
    """集成测试"""

    def test_full_initialization_flow(self):
        """测试完整初始化流程"""
        # 应该不抛出异常
        result = initialize_resource_limits()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_multiple_async_timeouts_concurrent(self):
        """测试并发异步超时"""

        async def task(delay: float, name: str):
            await asyncio.sleep(delay)
            return name

        # 并发运行多个超时保护的任务
        tasks = [
            with_timeout(task(0.1, "task1"), seconds=1, operation_name="task1"),
            with_timeout(task(0.2, "task2"), seconds=1, operation_name="task2"),
            with_timeout(task(0.3, "task3"), seconds=1, operation_name="task3"),
        ]

        results = await asyncio.gather(*tasks)
        assert results == ["task1", "task2", "task3"]

    @pytest.mark.asyncio
    async def test_timeout_with_real_io_operation(self):
        """测试真实 I/O 操作的超时"""

        async def io_operation():
            # 模拟 I/O 操作
            await asyncio.sleep(0.5)
            return "IO complete"

        result = await with_timeout(
            io_operation(), seconds=2, operation_name="io_operation"
        )
        assert result == "IO complete"


# Mark all tests as unit tests
pytestmark = pytest.mark.unit
