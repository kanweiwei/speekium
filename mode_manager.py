"""
Speekium 录音模式管理器
支持两种模式：
1. 按键录音模式 (Push-to-Talk): 按住快捷键录音，松开发送
2. 自由对话模式 (Continuous): 自动VAD检测，持续监听
"""

import threading
from collections.abc import Callable
from enum import Enum


class RecordingMode(Enum):
    """录音模式枚举"""

    PUSH_TO_TALK = "push_to_talk"  # 按键录音模式
    CONTINUOUS = "continuous"  # 自由对话模式


class ModeManager:
    """录音模式管理器"""

    def __init__(self, initial_mode: RecordingMode = RecordingMode.CONTINUOUS):
        self.current_mode = initial_mode
        self._lock = threading.Lock()
        self._mode_change_callbacks = []

        # 按键录音状态
        self.is_recording = False
        self.recording_lock = threading.Lock()

    def get_mode(self) -> RecordingMode:
        """获取当前模式"""
        with self._lock:
            return self.current_mode

    def set_mode(self, mode: RecordingMode):
        """
        切换模式

        Args:
            mode: 新的录音模式
        """
        with self._lock:
            if self.current_mode == mode:
                return

            old_mode = self.current_mode
            self.current_mode = mode

            print(f"🔄 模式切换: {old_mode.value} → {mode.value}")

            # 触发回调
            self._notify_mode_change(old_mode, mode)

    def toggle_mode(self):
        """切换到另一种模式"""
        with self._lock:
            if self.current_mode == RecordingMode.PUSH_TO_TALK:
                new_mode = RecordingMode.CONTINUOUS
            else:
                new_mode = RecordingMode.PUSH_TO_TALK

            self.set_mode(new_mode)

    def is_push_to_talk(self) -> bool:
        """是否为按键录音模式"""
        return self.get_mode() == RecordingMode.PUSH_TO_TALK

    def is_continuous(self) -> bool:
        """是否为自由对话模式"""
        return self.get_mode() == RecordingMode.CONTINUOUS

    def start_recording(self):
        """开始录音 (仅按键模式使用)"""
        with self.recording_lock:
            if self.is_push_to_talk() and not self.is_recording:
                self.is_recording = True
                print("🎤 按键录音开始...")
                return True
            return False

    def stop_recording(self):
        """停止录音 (仅按键模式使用)"""
        with self.recording_lock:
            if self.is_push_to_talk() and self.is_recording:
                self.is_recording = False
                print("⏹️  按键录音停止")
                return True
            return False

    def add_mode_change_callback(self, callback: Callable[[RecordingMode, RecordingMode], None]):
        """
        添加模式切换回调

        Args:
            callback: 回调函数 callback(old_mode, new_mode)
        """
        self._mode_change_callbacks.append(callback)

    def _notify_mode_change(self, old_mode: RecordingMode, new_mode: RecordingMode):
        """通知所有回调函数模式已切换"""
        for callback in self._mode_change_callbacks:
            try:
                callback(old_mode, new_mode)
            except Exception as e:
                print(f"⚠️ 模式切换回调错误: {e}")

    def get_status(self) -> dict:
        """获取当前状态"""
        return {
            "mode": self.current_mode.value,
            "is_recording": self.is_recording if self.is_push_to_talk() else False,
            "mode_name": "按键录音" if self.is_push_to_talk() else "自由对话",
        }
