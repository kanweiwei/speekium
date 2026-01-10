import argparse
import asyncio
import base64
import os
import sys

import webview

sys.path.append(".")

from config_manager import ConfigManager
from floating_window import FloatingWindowManager
from hotkey_manager import HotkeyManager
from mode_manager import RecordingMode
from speekium import (
    VoiceAssistant,
)
from tray_manager import TrayManager


class Api:
    """Python API 暴露给 React"""

    def __init__(self):
        self.config = ConfigManager.load()
        self.assistant = None
        self._init_assistant()
        self.window = None
        self.floating_window = None

        # 新增管理器
        self.hotkey_manager = HotkeyManager()
        self.floating_manager = FloatingWindowManager()
        self.tray_manager = TrayManager()

    def set_window(self, window):
        self.window = window

    def _init_assistant(self):
        """根据配置初始化助手"""
        self.assistant = VoiceAssistant()

        # 设置全局配置
        llm_backend = self.config.get("llm_backend", "ollama")
        ollama_model = self.config.get("ollama_model", "qwen2.5:1.5b")
        ollama_base_url = self.config.get("ollama_base_url", "http://localhost:11434")
        tts_backend = self.config.get("tts_backend", "edge")
        tts_rate = self.config.get("tts_rate", "+0%")
        vad_threshold = self.config.get("vad_threshold", 0.7)
        max_history = self.config.get("max_history", 10)

        print("Loading models...")
        try:
            self.assistant.load_vad()
        except Exception as e:
            print(f"Warning: Failed to load VAD: {e}")

        try:
            self.assistant.load_asr()
        except Exception as e:
            print(f"Warning: Failed to load ASR: {e}")

        try:
            self.assistant.load_llm()
        except Exception as e:
            print(f"Warning: Failed to load LLM: {e}")

        print("Models loaded")

    def start_recording(self) -> dict:
        """开始录音并返回识别结果"""
        try:
            if self.window:
                self.window.state.is_recording = True

            audio = self.assistant.record_with_vad()

            if audio is None:
                if self.window:
                    self.window.state.is_recording = False
                return {"success": False, "message": "未检测到语音"}

            text, language = self.assistant.transcribe(audio)

            if self.window:
                self.window.state.is_recording = False

            return {
                "success": True,
                "text": text,
                "language": language,
                "audio_length": len(audio) / 16000,
            }
        except Exception as e:
            if self.window:
                self.window.state.is_recording = False
            return {"success": False, "message": str(e)}

    def clear_history(self) -> None:
        """清空对话历史"""
        if self.assistant and self.assistant.llm_backend:
            self.assistant.llm_backend.clear_history()

    def get_status(self) -> dict:
        """获取当前状态"""
        history_count = 0
        if self.assistant and self.assistant.llm_backend:
            history_count = len(self.assistant.llm_backend.history) // 2

        return {
            "is_recording": False,
            "is_processing": False,
            "is_speaking": False,
            "history_count": history_count,
            "llm_backend": self.config.get("llm_backend", "ollama"),
            "tts_backend": self.config.get("tts_backend", "edge"),
        }

    def get_config(self) -> dict:
        """获取当前配置"""
        return self.config

    def save_config(self, new_config: dict) -> None:
        """保存配置（不重启）"""
        self.config.update(new_config)
        ConfigManager.save(self.config)

    def restart_assistant(self) -> None:
        """重启助手以应用配置"""
        print("Restarting assistant...")
        self._init_assistant()

    # ===== 模式管理 API =====
    def get_mode(self) -> dict:
        """获取当前录音模式"""
        return self.assistant.mode_manager.get_status()

    def set_mode(self, mode: str) -> None:
        """设置录音模式 (push_to_talk 或 continuous)"""
        new_mode = (
            RecordingMode.PUSH_TO_TALK if mode == "push_to_talk" else RecordingMode.CONTINUOUS
        )
        self.assistant.mode_manager.set_mode(new_mode)
        self.tray_manager.update_mode(mode)

    def toggle_mode(self) -> dict:
        """切换录音模式"""
        self.assistant.mode_manager.toggle_mode()
        return self.get_mode()

    # ===== 悬浮窗管理 API =====
    def show_floating_window(self) -> None:
        """显示悬浮窗"""
        self.floating_manager.show()

    def hide_floating_window(self) -> None:
        """隐藏悬浮窗"""
        self.floating_manager.hide()

    # ===== 窗口管理 API =====
    def show_main_window(self) -> None:
        """显示主窗口"""
        if self.window:
            self.window.show()

    def hide_main_window(self) -> None:
        """隐藏主窗口"""
        if self.window:
            self.window.hide()

    def chat_generator(self, text: str, language: str):
        """流式响应生成器（返回 list 以支持 pywebview）"""
        backend = self.assistant.load_llm()

        if backend is None:
            return [{"type": "error", "content": "LLM backend not loaded"}]

        response_text = ""
        try:

            def run_async_stream():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self._collect_chunks_with_tts(backend.chat_stream(text), language)
                    )
                finally:
                    loop.close()

            return run_async_stream()
        except Exception as e:
            return [{"type": "error", "content": str(e)}]

    async def _collect_chunks(self, async_stream):
        """收集异步流中的所有chunks"""
        chunks = []
        async for chunk in async_stream:
            chunks.append(chunk)
        return chunks

    async def _collect_chunks_with_tts(self, async_stream, language):
        """收集chunks并生成TTS音频"""
        result = []
        response_text = ""

        # 收集所有文本chunks
        async for sentence in async_stream:
            response_text += sentence
            result.append({"type": "partial", "content": sentence})

        # 生成完整响应的TTS音频
        if response_text:
            try:
                audio_file = await self.assistant.generate_audio(response_text, language)
                if audio_file and os.path.exists(audio_file):
                    # 读取音频文件并转换为base64
                    with open(audio_file, "rb") as f:
                        audio_data = base64.b64encode(f.read()).decode("utf-8")

                    # 删除临时文件
                    os.unlink(audio_file)

                    # 确定音频格式
                    audio_format = "audio/mpeg" if audio_file.endswith(".mp3") else "audio/wav"

                    result.append(
                        {
                            "type": "complete",
                            "content": response_text,
                            "audio": audio_data,
                            "audioFormat": audio_format,
                        }
                    )
                else:
                    result.append({"type": "complete", "content": response_text})
            except Exception as e:
                print(f"⚠️ TTS generation failed: {e}")
                result.append({"type": "complete", "content": response_text})
        else:
            result.append({"type": "complete", "content": response_text})

        return result


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Speekium Web App")
    parser.add_argument(
        "--dev",
        action="store_true",
        help="开发模式：使用 Vite 开发服务器 (需要先运行 npm run dev)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5173,
        help="Vite 开发服务器端口 (默认: 5173)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="启动时显示主窗口（默认隐藏到托盘）",
    )
    args = parser.parse_args()

    api = Api()

    # 根据模式选择 URL
    if args.dev:
        url = f"http://localhost:{args.port}"
        print(f"🔧 开发模式: 连接到 Vite 开发服务器 {url}")
        print("⚠️  请确保已运行: cd web && npm run dev")
    else:
        url = "dist/index.html"
        print("📦 生产模式: 使用编译后的静态文件")

    # 窗口事件处理
    def on_closing():
        """窗口关闭事件 - 隐藏到托盘而不是退出"""
        print("📌 主窗口关闭，隐藏到系统托盘")
        main_window.hide()
        return False  # 阻止窗口关闭

    # 创建主窗口
    main_window = webview.create_window(
        title="Speekium",
        url=url,
        js_api=api,
        width=1200,
        height=800,
        min_size=(800, 600),
        resizable=True,
        hidden=not args.show,  # 根据参数决定是否显示
    )

    # 设置窗口关闭事件
    main_window.events.closing += on_closing

    api.set_window(main_window)

    # 初始化窗口状态
    main_window.state.is_recording = False
    main_window.state.is_processing = False
    main_window.state.is_speaking = False
    main_window.state.history_count = 0
    main_window.state.llm_backend = api.config.get("llm_backend", "ollama")
    main_window.state.tts_backend = api.config.get("tts_backend", "edge")

    # 创建悬浮窗
    api.floating_manager.create_window()

    # 设置快捷键回调
    def on_hotkey_press():
        """快捷键按下 - 开始录音并显示悬浮窗"""
        if api.assistant.mode_manager.start_recording():
            api.floating_manager.show()

    def on_hotkey_release():
        """快捷键松开 - 停止录音并隐藏悬浮窗"""
        if api.assistant.mode_manager.stop_recording():
            api.floating_manager.hide()
            # TODO: 触发录音处理流程

    # 启动快捷键监听
    api.hotkey_manager.start(on_press=on_hotkey_press, on_release=on_hotkey_release)

    # 设置托盘回调
    def show_main_window():
        if main_window:
            main_window.show()

    def toggle_mode(mode: str):
        api.set_mode(mode)

    def quit_app():
        # 停止所有服务
        api.hotkey_manager.stop()
        api.tray_manager.stop()
        # 销毁窗口
        if main_window:
            main_window.destroy()
        # 退出
        sys.exit(0)

    # 暂时禁用系统托盘（pystray与pywebview在macOS上事件循环冲突）
    # TODO: 使用rumps库重新实现macOS托盘支持
    # api.tray_manager.start(
    #     on_show_window=show_main_window,
    #     on_toggle_mode=toggle_mode,
    #     on_clear_history=api.clear_history,
    #     on_quit=quit_app,
    # )
    print("⚠️  系统托盘暂时禁用（macOS兼容性问题）")

    # 启动webview
    print("🚀 准备启动webview...")
    print(f"   主窗口URL: {url}")
    print(f"   主窗口hidden状态: {not args.show}")
    print("   如果窗口未显示，请检查系统托盘图标（右上角蓝色麦克风）")
    webview.start(debug=True)


if __name__ == "__main__":
    main()
