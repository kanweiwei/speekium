"""
Progress tracking 单元测试

测试下载进度追踪功能：
1. DownloadProgressTracker - HuggingFace 模型下载进度
2. ModelScopeProgressCallback - ModelScope 模型下载进度
3. 速度计算和格式化
4. 日志记录验证
"""

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@dataclass
class MockProgress:
    """模拟 huggingface_hub.utils.Progress 对象"""

    def __init__(self, downloaded: int, total: int):
        self.downloaded: int = downloaded
        self.total: int = total


class TestDownloadProgressTracker:
    """测试 DownloadProgressTracker 类"""

    def test_init(self):
        """测试初始化"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        assert tracker.model_name == "test-model"
        assert tracker.downloaded_bytes == 0
        assert tracker.total_bytes == 0
        assert tracker.last_emit_time == 0
        assert tracker.start_time == 0
        assert tracker.file_count == 0
        assert tracker.total_files == 0

    def test_start(self):
        """测试 start 方法"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")

        with patch("speekium.progress.logger") as mock_logger:
            tracker.start()

            assert tracker.start_time > 0
            assert tracker.last_emit_time == 0
            mock_logger.info.assert_called_once_with(
                "download_started", model="test-model", status="downloading"
            )

    def test_on_progress_throttling(self):
        """测试进度更新节流（0.5秒间隔）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()

        with patch("speekium.progress.logger") as mock_logger:
            progress = MockProgress(1024, 10240)

            # 第一次调用应该记录日志
            tracker.on_progress(progress)
            assert mock_logger.info.call_count == 1

            # 立即第二次调用应该被节流
            mock_logger.reset_mock()
            tracker.on_progress(progress)
            assert mock_logger.info.call_count == 0

    def test_on_progress_with_zero_total(self):
        """测试 total 为 0 时的进度更新"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            progress = MockProgress(1024, 0)
            tracker.on_progress(progress)

            # total 为 0 时不应该记录进度日志
            mock_logger.info.assert_not_called()

    def test_on_progress_speed_formatting(self):
        """测试速度格式化（MB/s）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            # 模拟 2MB/s 的速度（需要 > 1024*1024 才会显示为 MB/s）
            with patch("time.time", return_value=tracker.start_time + 1.0):
                progress = MockProgress(2 * 1024 * 1024, 10 * 1024 * 1024)
                tracker.on_progress(progress)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert call_args[1]["speed"] == "2.0 MB/s"
                assert call_args[1]["percent"] == 20

    def test_on_progress_size_formatting_bytes(self):
        """测试字节大小格式化（字节）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            progress = MockProgress(512, 1000)
            tracker.on_progress(progress)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[1]["total_size"] == "1000 B"

    def test_on_progress_size_formatting_kb(self):
        """测试字节大小格式化（KB）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            progress = MockProgress(50 * 1024, 100 * 1024)
            tracker.on_progress(progress)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert "KB" in call_args[1]["total_size"]

    def test_on_progress_size_formatting_mb(self):
        """测试字节大小格式化（MB）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            progress = MockProgress(5 * 1024 * 1024, 10 * 1024 * 1024)
            tracker.on_progress(progress)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert "MB" in call_args[1]["total_size"]

    def test_on_progress_speed_formatting_bytes_per_second(self):
        """测试速度格式化（B/s）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            with patch("time.time", return_value=tracker.start_time + 1.0):
                progress = MockProgress(512, 1000)
                tracker.on_progress(progress)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert "B/s" in call_args[1]["speed"]

    def test_on_progress_speed_formatting_kb_per_second(self):
        """测试速度格式化（KB/s）"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            with patch("time.time", return_value=tracker.start_time + 1.0):
                progress = MockProgress(50 * 1024, 100 * 1024)
                tracker.on_progress(progress)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert "KB/s" in call_args[1]["speed"]

    def test_complete(self):
        """测试 complete 方法"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()

        with patch("speekium.progress.logger") as mock_logger:
            tracker.complete()

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[1]["model"] == "test-model"
            assert call_args[1]["status"] == "completed"
            assert "elapsed_seconds" in call_args[1]

    def test_complete_without_start(self):
        """测试未调用 start 时的 complete"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")

        with patch("speekium.progress.logger") as mock_logger:
            tracker.complete()

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[1]["elapsed_seconds"] == 0

    def test_progress_without_downloaded_attribute(self):
        """测试 progress 对象没有 downloaded 属性"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            # 创建一个只有 total 属性的对象
            # MagicMock 的 hasattr 删除属性后返回 False，但代码会用 0 作为默认值
            progress = MagicMock()
            del progress.downloaded
            progress.total = 1024

            tracker.on_progress(progress)
            # 代码会使用 downloaded=0 作为默认值，仍然会记录日志
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[1]["downloaded"] == 0

    def test_progress_without_total_attribute(self):
        """测试 progress 对象没有 total 属性"""
        from speekium.progress import DownloadProgressTracker

        tracker = DownloadProgressTracker("test-model")
        tracker.start()
        tracker.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            # 创建一个只有 downloaded 属性的对象
            progress = MagicMock()
            progress.downloaded = 512
            del progress.total

            tracker.on_progress(progress)
            # 没有 total 属性时应该不记录进度
            mock_logger.info.assert_not_called()


class TestModelScopeProgressCallback:
    """测试 ModelScopeProgressCallback 类"""

    def test_init(self):
        """测试初始化"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)
        assert callback.filename == "test.bin"
        assert callback.file_size == 1024
        assert callback.model_name == "SenseVoice ASR"
        assert callback.downloaded == 0
        assert callback.last_emit_time == 0

    def test_init_with_custom_model_name(self):
        """测试使用自定义模型名称初始化"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024, model_name="Custom Model")
        assert callback.model_name == "Custom Model"

    def test_update(self):
        """测试 update 方法"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            callback.update(512)

            assert callback.downloaded == 512
            mock_logger.info.assert_called_once()

            call_args = mock_logger.info.call_args
            assert call_args[1]["model"] == "SenseVoice ASR"
            assert call_args[1]["percent"] == 50

    def test_update_throttling(self):
        """测试进度更新节流"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            # 第一次调用应该记录日志
            callback.update(100)
            assert mock_logger.info.call_count == 1

            # 立即第二次调用应该被节流
            mock_logger.reset_mock()
            callback.update(100)
            assert mock_logger.info.call_count == 0

    def test_update_with_zero_file_size(self):
        """测试 file_size 为 0 时的更新"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 0)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            callback.update(512)

            # file_size 为 0 时不应该记录进度日志
            mock_logger.info.assert_not_called()

    def test_update_accumulates_downloaded(self):
        """测试 downloaded 累积"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)

        callback.update(256)
        assert callback.downloaded == 256

        callback.update(256)
        assert callback.downloaded == 512

        callback.update(512)
        assert callback.downloaded == 1024

    def test_update_speed_calculation(self):
        """测试速度计算（MB/s）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 10 * 1024 * 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            # 模拟 1 秒后下载 2MB（需要 > 1024*1024 才会显示为 MB/s）
            with patch("time.time", return_value=callback.start_time + 1.0):
                callback.update(2 * 1024 * 1024)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert call_args[1]["speed"] == "2.0 MB/s"

    def test_end(self):
        """测试 end 方法"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)

        with patch("speekium.progress.logger") as mock_logger:
            callback.end()

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[1]["model"] == "SenseVoice ASR"
            assert call_args[1]["status"] == "completed"
            assert "elapsed_seconds" in call_args[1]

    def test_end_elapsed_time(self):
        """测试 end 方法计算经过时间"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1024)

        # 模拟经过 2.5 秒
        with patch("time.time", return_value=callback.start_time + 2.5):
            with patch("speekium.progress.logger") as mock_logger:
                callback.end()

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert call_args[1]["elapsed_seconds"] == 2

    def test_modelscope_size_formatting_bytes(self):
        """测试字节大小格式化（字节）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1000)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            callback.update(500)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert call_args[1]["total_size"] == "1000 B"

    def test_modelscope_size_formatting_kb(self):
        """测试字节大小格式化（KB）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 100 * 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            callback.update(50 * 1024)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert "KB" in call_args[1]["total_size"]

    def test_modelscope_size_formatting_mb(self):
        """测试字节大小格式化（MB）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 10 * 1024 * 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            callback.update(5 * 1024 * 1024)

            call_args = mock_logger.info.call_args
            assert call_args is not None
            assert "MB" in call_args[1]["total_size"]

    def test_modelscope_speed_formatting_bps(self):
        """测试速度格式化（B/s）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 1000)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            with patch("time.time", return_value=callback.start_time + 1.0):
                callback.update(512)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert "B/s" in call_args[1]["speed"]

    def test_modelscope_speed_formatting_kbps(self):
        """测试速度格式化（KB/s）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 100 * 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            with patch("time.time", return_value=callback.start_time + 1.0):
                callback.update(50 * 1024)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert "KB/s" in call_args[1]["speed"]

    def test_modelscope_speed_formatting_mbps(self):
        """测试速度格式化（MB/s）"""
        from speekium.progress import ModelScopeProgressCallback

        callback = ModelScopeProgressCallback("test.bin", 10 * 1024 * 1024)
        callback.last_emit_time = 0  # 强制触发日志

        with patch("speekium.progress.logger") as mock_logger:
            with patch("time.time", return_value=callback.start_time + 1.0):
                callback.update(5 * 1024 * 1024)

                call_args = mock_logger.info.call_args
                assert call_args is not None
                assert "MB/s" in call_args[1]["speed"]
