"""
Speekium 全局快捷键管理器
支持跨平台全局快捷键监听
"""

import platform
import threading
from collections.abc import Callable


class HotkeyManager:
    """全局快捷键管理器"""

    def __init__(self):
        self.listener = None
        self.is_running = False
        self._lock = threading.Lock()

        # 快捷键状态
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.cmd_pressed = False  # macOS Command key
        self.was_triggered = False  # 防止重复触发

        # 回调函数
        self.on_hotkey_press = None
        self.on_hotkey_release = None

        # 检测操作系统
        self.is_macos = platform.system() == "Darwin"

    def start(self, on_press: Callable | None = None, on_release: Callable | None = None):
        """
        启动全局快捷键监听

        Args:
            on_press: 快捷键按下时的回调函数
            on_release: 快捷键松开时的回调函数
        """
        if self.is_running:
            print("⚠️ 快捷键监听已经在运行")
            return

        self.on_hotkey_press = on_press
        self.on_hotkey_release = on_release

        try:
            from pynput import keyboard

            def on_key_press(key):
                try:
                    # 更新修饰键状态
                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        self.ctrl_pressed = True
                    elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                        self.alt_pressed = True
                    elif key == keyboard.Key.cmd or key == keyboard.Key.cmd_r:
                        self.cmd_pressed = True

                    # 检查完整快捷键组合
                    self._check_hotkey_combination()

                except Exception as e:
                    print(f"⚠️ 按键处理错误: {e}")

            def on_key_release(key):
                try:
                    # 更新修饰键状态
                    released_cmd = key == keyboard.Key.cmd or key == keyboard.Key.cmd_r
                    released_alt = key == keyboard.Key.alt_l or key == keyboard.Key.alt_r

                    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                        self.ctrl_pressed = False
                    elif released_alt:
                        self.alt_pressed = False
                    elif released_cmd:
                        self.cmd_pressed = False

                    # 如果松开了 Cmd 或 Alt，触发释放回调
                    if (released_cmd or released_alt) and self.was_triggered:
                        self._check_hotkey_release()

                except Exception as e:
                    print(f"⚠️ 按键释放处理错误: {e}")

            # 创建监听器
            self.listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)

            # 启动监听器
            self.listener.start()
            self.is_running = True

            modifier_key = "Cmd" if self.is_macos else "Ctrl"
            print(f"⌨️  全局快捷键监听已启动: {modifier_key} + Alt")

        except ImportError:
            print("❌ pynput 未安装，无法使用全局快捷键")
            print("   安装方法: pip install pynput")
            return
        except Exception as e:
            print(f"❌ 启动快捷键监听失败: {e}")
            return

    def stop(self):
        """停止快捷键监听"""
        with self._lock:
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.is_running = False
            print("⌨️  全局快捷键监听已停止")

    def _check_hotkey_combination(self):
        """检查完整的快捷键组合是否被按下"""
        # macOS: Cmd + Alt
        # Windows/Linux: Ctrl + Alt
        is_hotkey_active = (
            self.cmd_pressed if self.is_macos else self.ctrl_pressed
        ) and self.alt_pressed

        if is_hotkey_active and not self.was_triggered and self.on_hotkey_press:
            try:
                self.was_triggered = True
                self.on_hotkey_press()
            except Exception as e:
                print(f"⚠️ 快捷键按下回调错误: {e}")

    def _check_hotkey_release(self):
        """检查快捷键是否被松开"""
        # 任一键松开时触发
        if self.was_triggered and self.on_hotkey_release:
            try:
                self.was_triggered = False
                self.on_hotkey_release()
            except Exception as e:
                print(f"⚠️ 快捷键松开回调错误: {e}")

    def is_hotkey_active(self) -> bool:
        """检查快捷键是否当前激活"""
        return (self.cmd_pressed if self.is_macos else self.ctrl_pressed) and self.alt_pressed
