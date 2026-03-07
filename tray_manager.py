"""
Speekium 系统托盘管理器
管理系统托盘图标和菜单
"""

import threading
from collections.abc import Callable

from PIL import Image, ImageDraw


class TrayManager:
    """系统托盘管理器"""

    # 托盘菜单翻译
    TRAY_MENU_ZH = {
        "show_window": "📱 显示主窗口",
        "push_to_talk": "🎤 按键录音模式",
        "continuous": "💬 自由对话模式",
        "start_listening": "▶️ 开始监听",
        "stop_listening": "⏸️ 停止监听",
        "clear_history": "🗑️ 清空对话历史",
        "settings": "⚙️ 设置",
        "quit": "❌ 退出应用",
    }

    TRAY_MENU_EN = {
        "show_window": "📱 Show Window",
        "push_to_talk": "🎤 Push-to-Talk",
        "continuous": "💬 Continuous Mode",
        "start_listening": "▶️ Start Listening",
        "stop_listening": "⏸️ Stop Listening",
        "clear_history": "🗑️ Clear History",
        "settings": "⚙️ Settings",
        "quit": "❌ Quit",
    }

    def __init__(self, language: str = "zh"):
        self.icon = None
        self.is_running = False
        self._lock = threading.Lock()
        self.language = language  # "zh" or "en"

        # 回调函数
        self.on_show_window: Callable | None = None
        self.on_toggle_mode: Callable | None = None
        self.on_start_listening: Callable | None = None
        self.on_stop_listening: Callable | None = None
        self.on_clear_history: Callable | None = None
        self.on_open_settings: Callable | None = None
        self.on_quit: Callable | None = None

        # 状态
        self.current_mode = "continuous"  # "push_to_talk" or "continuous"
        self.is_listening = False

    def create_icon_image(self, color="blue", with_indicator=False):
        """
        创建托盘图标图像

        Args:
            color: 图标颜色
            with_indicator: 是否显示状态指示器
        """
        # 创建64x64的图标
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 绘制麦克风图标
        # 主体
        mic_color = (59, 130, 246, 255) if color == "blue" else (96, 165, 250, 255)
        draw.ellipse([20, 15, 44, 40], fill=mic_color)  # 麦克风头部
        draw.rectangle([28, 35, 36, 48], fill=mic_color)  # 麦克风杆

        # 底座
        draw.ellipse([22, 46, 42, 52], fill=mic_color)

        # 如果监听中，添加绿色指示器
        if with_indicator:
            draw.ellipse([46, 10, 58, 22], fill=(34, 197, 94, 255))  # 绿色圆点

        return image

    def start(
        self,
        on_show_window: Callable | None = None,
        on_toggle_mode: Callable | None = None,
        on_start_listening: Callable | None = None,
        on_stop_listening: Callable | None = None,
        on_clear_history: Callable | None = None,
        on_open_settings: Callable | None = None,
        on_quit: Callable | None = None,
    ):
        """
        启动系统托盘

        Args:
            on_show_window: 显示主窗口回调
            on_toggle_mode: 切换模式回调
            on_start_listening: 开始监听回调
            on_stop_listening: 停止监听回调
            on_clear_history: 清空历史回调
            on_open_settings: 打开设置回调
            on_quit: 退出应用回调
        """
        if self.is_running:
            print("⚠️ 系统托盘已经在运行")
            return

        # 保存回调
        self.on_show_window = on_show_window
        self.on_toggle_mode = on_toggle_mode
        self.on_start_listening = on_start_listening
        self.on_stop_listening = on_stop_listening
        self.on_clear_history = on_clear_history
        self.on_open_settings = on_open_settings
        self.on_quit = on_quit

        try:
            from pystray import Icon, Menu, MenuItem

            # 创建图标
            icon_image = self.create_icon_image()

            # 选择翻译
            menu_text = self.TRAY_MENU_ZH if self.language == "zh" else self.TRAY_MENU_EN

            # 创建菜单
            menu = Menu(
                MenuItem(
                    menu_text["show_window"],
                    self._handle_show_window,
                    default=True,  # 左键默认动作
                ),
                Menu.SEPARATOR,
                MenuItem(
                    menu_text["push_to_talk"],
                    self._handle_push_to_talk_mode,
                    checked=lambda item: self.current_mode == "push_to_talk",
                    radio=True,
                ),
                MenuItem(
                    menu_text["continuous"],
                    self._handle_continuous_mode,
                    checked=lambda item: self.current_mode == "continuous",
                    radio=True,
                ),
                Menu.SEPARATOR,
                MenuItem(
                    menu_text["start_listening"],
                    self._handle_start_listening,
                    enabled=lambda item: not self.is_listening,
                ),
                MenuItem(
                    menu_text["stop_listening"],
                    self._handle_stop_listening,
                    enabled=lambda item: self.is_listening,
                ),
                Menu.SEPARATOR,
                MenuItem(menu_text["clear_history"], self._handle_clear_history),
                MenuItem(menu_text["settings"], self._handle_open_settings),
                Menu.SEPARATOR,
                MenuItem(menu_text["quit"], self._handle_quit),
            )

            # 创建托盘图标
            title = "Speekium - 智能语音助手" if self.language == "zh" else "Speekium - Voice Assistant"
            self.icon = Icon(
                name="Speekium", icon=icon_image, title=title, menu=menu
            )

            # 在新线程中运行（非daemon，保持应用运行）
            def run_icon():
                self.is_running = True
                print("📌 系统托盘已启动")
                self.icon.run()

            tray_thread = threading.Thread(target=run_icon, daemon=False)
            tray_thread.start()

        except ImportError:
            print("❌ pystray 未安装，无法使用系统托盘")
            print("   安装方法: pip install pystray Pillow")
        except Exception as e:
            print(f"❌ 启动系统托盘失败: {e}")

    def stop(self):
        """停止系统托盘"""
        with self._lock:
            if self.icon:
                self.icon.stop()
                self.icon = None
            self.is_running = False
            print("📌 系统托盘已停止")

    def update_mode(self, mode: str):
        """更新当前模式"""
        self.current_mode = mode
        # 更新菜单会自动反映在托盘中

    def update_listening_status(self, is_listening: bool):
        """
        更新监听状态

        Args:
            is_listening: 是否正在监听
        """
        self.is_listening = is_listening

        # 更新图标（添加/移除指示器）
        if self.icon:
            try:
                icon_image = self.create_icon_image(with_indicator=is_listening)
                self.icon.icon = icon_image
            except Exception as e:
                print(f"⚠️ 更新托盘图标失败: {e}")

    def set_language(self, language: str):
        """
        设置托盘菜单语言

        Args:
            language: 语言代码 "zh" 或 "en"
        """
        if language not in ("zh", "en"):
            print(f"⚠️ 不支持的语言: {language}")
            return

        self.language = language
        print(f"🌐 托盘菜单语言已切换到: {'中文' if language == 'zh' else 'English'}")

    # 菜单项处理函数
    def _handle_show_window(self, icon, item):
        """显示主窗口"""
        if self.on_show_window:
            self.on_show_window()

    def _handle_push_to_talk_mode(self, icon, item):
        """切换到按键录音模式"""
        self.current_mode = "push_to_talk"
        if self.on_toggle_mode:
            self.on_toggle_mode("push_to_talk")

    def _handle_continuous_mode(self, icon, item):
        """切换到自由对话模式"""
        self.current_mode = "continuous"
        if self.on_toggle_mode:
            self.on_toggle_mode("continuous")

    def _handle_start_listening(self, icon, item):
        """开始监听"""
        if self.on_start_listening:
            self.on_start_listening()
        self.update_listening_status(True)

    def _handle_stop_listening(self, icon, item):
        """停止监听"""
        if self.on_stop_listening:
            self.on_stop_listening()
        self.update_listening_status(False)

    def _handle_clear_history(self, icon, item):
        """清空对话历史"""
        if self.on_clear_history:
            self.on_clear_history()

    def _handle_open_settings(self, icon, item):
        """打开设置"""
        if self.on_open_settings:
            self.on_open_settings()

    def _handle_quit(self, icon, item):
        """退出应用"""
        if self.on_quit:
            self.on_quit()
        self.stop()
