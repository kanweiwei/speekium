"""
Resource Limiter Module - 资源限制模块

功能：
- 设置进程资源限制（内存、CPU、文件）
- 提供超时装饰器和异步超时支持
- 跨平台兼容（Unix/Linux 应用限制，Windows 优雅降级）
- 集成结构化日志记录

资源限制：
- 内存：500MB（软限制）/ 1GB（硬限制）
- CPU时间：300秒（5分钟）
- 文件大小：100MB
- 文件描述符：1024

安全性：
- 防止资源耗尽攻击（DoS）
- 防止内存泄漏
- 防止CPU占用过高
- 防止文件系统耗尽
"""

import asyncio
import functools
import platform
import signal
import sys
from typing import Any, Callable, TypeVar

from logger import get_logger

logger = get_logger(__name__)

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


class ResourceLimiter:
    """资源限制器类 - 管理系统资源限制"""

    # 资源限制配置（字节）
    MEMORY_SOFT_LIMIT = 500 * 1024 * 1024  # 500MB
    MEMORY_HARD_LIMIT = 1024 * 1024 * 1024  # 1GB
    CPU_TIME_LIMIT = 300  # 300秒（5分钟）
    FILE_SIZE_LIMIT = 100 * 1024 * 1024  # 100MB
    FILE_DESCRIPTOR_LIMIT = 1024  # 最大文件描述符数

    @staticmethod
    def set_limits() -> bool:
        """
        设置进程资源限制

        Returns:
            bool: True if limits were set successfully, False otherwise

        Note:
            - Unix/Linux: 应用所有资源限制
            - Windows: 跳过资源限制（resource 模块不可用）
        """
        # 检查平台兼容性
        if platform.system() == "Windows":
            logger.info(
                "resource_limits_skipped",
                platform="Windows",
                reason="resource module not available on Windows",
            )
            return False

        try:
            import resource

            # 设置内存限制（虚拟内存）
            # 获取当前系统最大限制
            try:
                _, current_max = resource.getrlimit(resource.RLIMIT_AS)
                # 使用较小的值：我们的限制或系统最大值
                soft_limit = min(ResourceLimiter.MEMORY_SOFT_LIMIT, current_max)
                hard_limit = min(ResourceLimiter.MEMORY_HARD_LIMIT, current_max)

                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (soft_limit, hard_limit),
                )
            except (ValueError, OSError) as e:
                # 某些系统（如 macOS）可能不允许设置 RLIMIT_AS
                logger.warning("memory_limit_skip", reason=str(e))

            # 设置 CPU 时间限制
            try:
                resource.setrlimit(
                    resource.RLIMIT_CPU,
                    (ResourceLimiter.CPU_TIME_LIMIT, ResourceLimiter.CPU_TIME_LIMIT),
                )
            except (ValueError, OSError) as e:
                logger.warning("cpu_limit_skip", reason=str(e))

            # 设置文件大小限制
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    (ResourceLimiter.FILE_SIZE_LIMIT, ResourceLimiter.FILE_SIZE_LIMIT),
                )
            except (ValueError, OSError) as e:
                logger.warning("file_size_limit_skip", reason=str(e))

            # 设置文件描述符限制
            try:
                _, current_max = resource.getrlimit(resource.RLIMIT_NOFILE)
                fd_limit = min(ResourceLimiter.FILE_DESCRIPTOR_LIMIT, current_max)
                resource.setrlimit(
                    resource.RLIMIT_NOFILE,
                    (fd_limit, fd_limit),
                )
            except (ValueError, OSError) as e:
                logger.warning("file_descriptor_limit_skip", reason=str(e))

            logger.info(
                "resource_limits_set",
                memory_soft_mb=ResourceLimiter.MEMORY_SOFT_LIMIT // (1024 * 1024),
                memory_hard_mb=ResourceLimiter.MEMORY_HARD_LIMIT // (1024 * 1024),
                cpu_time_sec=ResourceLimiter.CPU_TIME_LIMIT,
                file_size_mb=ResourceLimiter.FILE_SIZE_LIMIT // (1024 * 1024),
                file_descriptors=ResourceLimiter.FILE_DESCRIPTOR_LIMIT,
            )

            # 设置 CPU 超限信号处理器
            signal.signal(signal.SIGXCPU, ResourceLimiter._handle_cpu_timeout)

            return True

        except ImportError:
            logger.warning(
                "resource_limits_unavailable",
                reason="resource module not available",
                platform=platform.system(),
            )
            return False
        except Exception as e:
            logger.error(
                "resource_limits_failed", error=str(e), error_type=type(e).__name__
            )
            return False

    @staticmethod
    def _handle_cpu_timeout(signum: int, frame: Any) -> None:
        """
        CPU 超时信号处理器

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.error(
            "cpu_time_limit_exceeded",
            signal=signum,
            limit_seconds=ResourceLimiter.CPU_TIME_LIMIT,
            action="terminating_process",
        )
        sys.exit(1)

    @staticmethod
    def with_timeout(seconds: int) -> Callable[[F], F]:
        """
        同步函数超时装饰器（仅 Unix/Linux）

        Args:
            seconds: Timeout in seconds

        Returns:
            Decorated function with timeout protection

        Example:
            @ResourceLimiter.with_timeout(30)
            def long_running_task():
                # ... task code ...

        Note:
            - Unix/Linux: 使用 SIGALRM 实现超时
            - Windows: 装饰器不生效（signal.alarm 不可用）
        """

        def decorator(func: F) -> F:
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # Windows 平台跳过超时（signal.alarm 不可用）
                if platform.system() == "Windows":
                    return func(*args, **kwargs)

                def timeout_handler(signum: int, frame: Any) -> None:
                    logger.error(
                        "operation_timeout",
                        function=func.__name__,
                        timeout_seconds=seconds,
                    )
                    raise TimeoutError(
                        f"Operation '{func.__name__}' timed out after {seconds} seconds"
                    )

                # 设置超时信号
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(seconds)

                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    # 恢复原信号处理器
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)

            return wrapper  # type: ignore

        return decorator

    @staticmethod
    async def with_timeout_async(coro: Any, seconds: int, operation_name: str = "async_operation") -> Any:
        """
        异步函数超时保护（跨平台）

        Args:
            coro: Coroutine to execute with timeout
            seconds: Timeout in seconds
            operation_name: Name of the operation for logging

        Returns:
            Result of the coroutine

        Raises:
            asyncio.TimeoutError: If operation times out

        Example:
            result = await ResourceLimiter.with_timeout_async(
                my_async_function(),
                timeout=30,
                operation_name="my_function"
            )
        """
        try:
            return await asyncio.wait_for(coro, timeout=seconds)
        except asyncio.TimeoutError:
            logger.error(
                "async_operation_timeout",
                operation=operation_name,
                timeout_seconds=seconds,
            )
            raise TimeoutError(
                f"Async operation '{operation_name}' timed out after {seconds} seconds"
            )

    @staticmethod
    def get_current_usage() -> dict[str, Any]:
        """
        获取当前资源使用情况

        Returns:
            dict: Current resource usage (memory, CPU time, etc.)

        Note:
            - Unix/Linux: 返回详细资源使用情况
            - Windows: 返回空字典
        """
        if platform.system() == "Windows":
            return {}

        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)

            return {
                "memory_mb": usage.ru_maxrss / 1024,  # KB to MB (Linux)
                "cpu_time_user": usage.ru_utime,
                "cpu_time_system": usage.ru_stime,
                "cpu_time_total": usage.ru_utime + usage.ru_stime,
            }
        except Exception as e:
            logger.warning(
                "resource_usage_unavailable", error=str(e), error_type=type(e).__name__
            )
            return {}


# 便捷函数：初始化资源限制
def initialize_resource_limits() -> bool:
    """
    初始化资源限制（便捷函数）

    Returns:
        bool: True if limits were set successfully

    Usage:
        if __name__ == "__main__":
            initialize_resource_limits()
            # ... main program code ...
    """
    return ResourceLimiter.set_limits()


# 便捷函数：异步超时保护
async def with_timeout(coro: Any, seconds: int, operation_name: str = "operation") -> Any:
    """
    异步超时保护（便捷函数）

    Args:
        coro: Coroutine to execute
        seconds: Timeout in seconds
        operation_name: Name for logging

    Returns:
        Result of the coroutine

    Usage:
        result = await with_timeout(
            my_async_function(),
            timeout=30,
            operation_name="my_function"
        )
    """
    return await ResourceLimiter.with_timeout_async(coro, seconds, operation_name)
