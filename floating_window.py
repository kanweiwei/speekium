"""
Speekium 悬浮窗管理器
管理独立的录音状态悬浮窗口
"""

import webview
import os
from typing import Optional, Callable
import threading


class FloatingWindowManager:
    """悬浮窗管理器 - 管理录音状态的小悬浮窗"""

    def __init__(self):
        self.window: Optional[webview.Window] = None
        self.is_visible = False
        self._lock = threading.Lock()
        self.api = None

    def create_window(self):
        """创建悬浮窗"""
        if self.window:
            return

        # 悬浮窗HTML路径
        html_path = os.path.join(os.path.dirname(__file__), "web", "floating.html")

        # 如果floating.html不存在，使用内联HTML
        if not os.path.exists(html_path):
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Recording</title>
                <style>
                    * {
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }
                    body {
                        width: 240px;
                        height: 100px;
                        background: rgba(0, 0, 0, 0.7);
                        backdrop-filter: blur(20px);
                        border-radius: 16px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                        color: white;
                        overflow: hidden;
                    }
                    .status {
                        font-size: 14px;
                        margin-bottom: 12px;
                        opacity: 0.9;
                    }
                    .waveform {
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        gap: 3px;
                        height: 30px;
                    }
                    .bar {
                        width: 4px;
                        background: linear-gradient(to top, #3b82f6, #60a5fa);
                        border-radius: 2px;
                        animation: wave 1s ease-in-out infinite;
                    }
                    .bar:nth-child(1) { animation-delay: 0s; }
                    .bar:nth-child(2) { animation-delay: 0.1s; }
                    .bar:nth-child(3) { animation-delay: 0.2s; }
                    .bar:nth-child(4) { animation-delay: 0.3s; }
                    .bar:nth-child(5) { animation-delay: 0.4s; }
                    .bar:nth-child(6) { animation-delay: 0.3s; }
                    .bar:nth-child(7) { animation-delay: 0.2s; }
                    .bar:nth-child(8) { animation-delay: 0.1s; }
                    @keyframes wave {
                        0%, 100% { height: 8px; }
                        50% { height: 28px; }
                    }
                </style>
            </head>
            <body>
                <div class="status">🎤 录音中...</div>
                <div class="waveform">
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                    <div class="bar"></div>
                </div>
            </body>
            </html>
            """
            url = html_content
        else:
            url = html_path

        # 创建悬浮窗
        self.window = webview.create_window(
            title="Recording",
            url=url,
            width=240,
            height=100,
            frameless=True,  # 无边框
            on_top=True,     # 置顶
            resizable=False,
            minimized=False,
            hidden=True,     # 初始隐藏
        )

        print("✅ 悬浮窗已创建")

    def show(self):
        """显示悬浮窗"""
        with self._lock:
            if self.window and not self.is_visible:
                try:
                    self.window.show()
                    self.is_visible = True
                    print("👁️  悬浮窗显示")
                except Exception as e:
                    print(f"⚠️ 显示悬浮窗失败: {e}")

    def hide(self):
        """隐藏悬浮窗"""
        with self._lock:
            if self.window and self.is_visible:
                try:
                    self.window.hide()
                    self.is_visible = False
                    print("🙈 悬浮窗隐藏")
                except Exception as e:
                    print(f"⚠️ 隐藏悬浮窗失败: {e}")

    def toggle(self):
        """切换悬浮窗显示状态"""
        if self.is_visible:
            self.hide()
        else:
            self.show()

    def update_status(self, status: str):
        """更新悬浮窗状态文本"""
        if self.window:
            try:
                # 通过JavaScript更新状态
                js_code = f"document.querySelector('.status').textContent = '{status}';"
                self.window.evaluate_js(js_code)
            except Exception as e:
                print(f"⚠️ 更新悬浮窗状态失败: {e}")

    def destroy(self):
        """销毁悬浮窗"""
        with self._lock:
            if self.window:
                try:
                    self.window.destroy()
                    self.window = None
                    self.is_visible = False
                    print("🗑️  悬浮窗已销毁")
                except Exception as e:
                    print(f"⚠️ 销毁悬浮窗失败: {e}")


class FloatingWindowApi:
    """悬浮窗的Python API（预留，目前悬浮窗很简单不需要复杂API）"""

    def __init__(self, manager: FloatingWindowManager):
        self.manager = manager

    def get_status(self) -> dict:
        """获取悬浮窗状态"""
        return {
            "is_visible": self.manager.is_visible
        }
