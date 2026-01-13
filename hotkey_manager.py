"""
Speekium 全局快捷键管理器
支持跨平台全局快捷键监听和动态热键更新
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

        # 当前热键配置
        self.current_hotkey_config = None

        # 快捷键状态
        self.modifier_pressed = False
        self.main_key_pressed = False
        self.was_triggered = False  # 防止重复触发

        # 当前激活的键（用于动态更新）
        self.active_modifier_key = None
        self.active_main_key = None

        # 回调函数
        self.on_hotkey_press = None
        self.on_hotkey_release = None

        # 检测操作系统
        self.is_macos = platform.system() == "Darwin"

    def parse_hotkey_config(self, config: dict) -> tuple:
        """
        解析热键配置为 pynput 格式

        Args:
            config: dict with structure {
                'modifiers': ['CmdOrCtrl', 'Shift'],
                'key': 'Digit1'
            }

        Returns:
            tuple: (modifier_key_name, main_key_char)
        """
        from pynput import keyboard

        modifiers = config.get('modifiers', [])
        key_code = config.get('key', 'Digit1')

        # 确定主修饰键
        modifier_key = None
        if 'CmdOrCtrl' in modifiers:
            modifier_key = keyboard.Key.cmd if self.is_macos else keyboard.Key.ctrl
        elif 'Shift' in modifiers:
            modifier_key = keyboard.Key.shift
        elif 'Alt' in modifiers:
            modifier_key = keyboard.Key.alt

        # 解析主键
        main_key_char = None
        if key_code.startswith('Digit'):
            main_key_char = key_code.replace('Digit', '')
        elif key_code.startswith('Key'):
            main_key_char = key_code.replace('Key', '').lower()
        else:
            # 特殊键
            main_key_char = key_code.lower()

        return (modifier_key, main_key_char)

    def start(self, hotkey_config: dict | None = None, on_press: Callable | None = None, on_release: Callable | None = None):
        """
        启动全局快捷键监听

        Args:
            hotkey_config: dict with hotkey configuration
            on_press: 快捷键按下时的回调函数
            on_release: 快捷键松开时的回调函数
        """
        with self._lock:
            if self.is_running:
                print("⚠️ 快捷键监听已经在运行")
                return

            # 设置默认热键配置（如果没有提供）
            if hotkey_config is None:
                hotkey_config = {
                    'modifiers': ['CmdOrCtrl'],
                    'key': 'Digit1',
                    'displayName': '⌘1'
                }

            self.current_hotkey_config = hotkey_config
            self.on_hotkey_press = on_press
            self.on_hotkey_release = on_release

            try:
                from pynput import keyboard

                # 解析热键配置
                self.active_modifier_key, self.active_main_key = self.parse_hotkey_config(hotkey_config)

                def on_key_press(key):
                    try:
                        # 更新修饰键状态
                        is_modifier = False
                        if self.active_modifier_key:
                            if key == self.active_modifier_key:
                                self.modifier_pressed = True
                                is_modifier = True

                        # 更新主键状态
                        is_main_key = False
                        if hasattr(key, 'char') and key.char == self.active_main_key:
                            self.main_key_pressed = True
                            is_main_key = True

                        # 检查完整快捷键组合
                        self._check_hotkey_combination()

                    except Exception as e:
                        print(f"⚠️ 按键处理错误: {e}")

                def on_key_release(key):
                    try:
                        # 更新修饰键状态
                        released_modifier = self.active_modifier_key and key == self.active_modifier_key
                        released_main = hasattr(key, 'char') and key.char == self.active_main_key

                        if released_modifier:
                            self.modifier_pressed = False
                        elif released_main:
                            self.main_key_pressed = False

                        # 如果松开了修饰键或主键，触发释放回调
                        if (released_modifier or released_main) and self.was_triggered:
                            self._check_hotkey_release()

                    except Exception as e:
                        print(f"⚠️ 按键释放处理错误: {e}")

                # 创建监听器
                self.listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)

                # 启动监听器
                self.listener.start()
                self.is_running = True

                # Note: Removed print to avoid interfering with daemon JSON responses
                # Logger will be added by the caller

            except ImportError:
                # Note: These prints only show on error
                print("❌ pynput 未安装，无法使用全局快捷键")
                print("   安装方法: pip install pynput")
                return
            except Exception as e:
                # Note: This print only shows on error
                print(f"❌ 启动快捷键监听失败: {e}")
                return

    def update_hotkey(self, new_hotkey_config: dict) -> tuple[bool, str | None]:
        """
        动态更新热键配置

        Args:
            new_hotkey_config: dict with new hotkey configuration

        Returns:
            tuple[bool, str | None]: (success, error_message)
                - success: True if update succeeded, False otherwise
                - error_message: Error message if failed, None otherwise
        """
        try:
            # 保存回调函数（在锁外保存，避免死锁）
            with self._lock:
                on_press = self.on_hotkey_press
                on_release = self.on_hotkey_release
                is_running = self.is_running

            # 在锁外停止和启动，避免死锁
            if is_running:
                self.stop()

            self.start(new_hotkey_config, on_press, on_release)

            return True, None
        except Exception as e:
            return False, str(e)

    def stop(self):
        """停止快捷键监听"""
        with self._lock:
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.is_running = False
            self.modifier_pressed = False
            self.main_key_pressed = False
            self.was_triggered = False
            # Note: Removed print to avoid interfering with daemon JSON responses

    def _check_hotkey_combination(self):
        """检查完整的快捷键组合是否被按下"""
        is_hotkey_active = self.modifier_pressed and self.main_key_pressed

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
        return self.modifier_pressed and self.main_key_pressed
