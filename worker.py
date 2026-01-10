#!/usr/bin/env python3
"""
Speekium Python Worker - 被 Tauri Rust 后端调用的 Python 脚本

接收命令行参数，执行操作，输出 JSON 结果

Usage:
    python3 worker.py record '{"mode":"push-to-talk","duration":3.0}'
    python3 worker.py chat '{"text":"hello"}'
    python3 worker.py tts '{"text":"hello"}'
"""

import sys
import json
import sounddevice as sd
import numpy as np
from speekium import VoiceAssistant


def record_audio(mode="push-to-talk", duration=3.0):
    """录音并转录

    Args:
        mode: "push-to-talk" 或 "continuous"
        duration: 录音时长（秒）

    Returns:
        dict: {"success": bool, "text": str, "language": str, "error": str}
    """
    try:
        assistant = VoiceAssistant()

        print(f"🎤 开始录音 (mode={mode}, duration={duration}s)...", file=sys.stderr, flush=True)

        if mode == "continuous":
            audio = assistant.record_with_vad()
        else:  # push-to-talk
            audio = sd.rec(
                int(duration * 16000),
                samplerate=16000,
                channels=1,
                dtype='float32'
            )
            sd.wait()
            audio = audio[:, 0]  # 转为 1D 数组

        if audio is None or len(audio) == 0:
            return {"success": False, "error": "No audio recorded"}

        print(f"🔄 识别中...", file=sys.stderr, flush=True)
        text, language = assistant.transcribe(audio)
        print(f"✅ 识别完成: '{text}' ({language})", file=sys.stderr, flush=True)

        return {"success": True, "text": text, "language": language}

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"success": False, "error": str(e)}


def chat_llm(text):
    """LLM 对话

    Args:
        text: 用户输入文本

    Returns:
        dict: {"success": bool, "content": str, "error": str}
    """
    try:
        print(f"💬 LLM 对话: {text}", file=sys.stderr, flush=True)

        assistant = VoiceAssistant()
        backend = assistant.load_llm()
        response = backend.chat(text)

        print(f"✅ LLM 响应: {response[:50]}...", file=sys.stderr, flush=True)

        return {"success": True, "content": response}

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"success": False, "error": str(e)}


def generate_tts(text):
    """生成 TTS 音频

    Args:
        text: 要转换的文本

    Returns:
        dict: {"success": bool, "audio_path": str, "error": str}
    """
    try:
        import asyncio

        print(f"🔊 TTS 生成: {text}", file=sys.stderr, flush=True)

        assistant = VoiceAssistant()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_path = loop.run_until_complete(assistant.generate_audio(text))
        loop.close()

        if audio_path:
            print(f"✅ TTS 完成: {audio_path}", file=sys.stderr, flush=True)
            return {"success": True, "audio_path": audio_path}
        else:
            return {"success": False, "error": "Failed to generate audio"}

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"success": False, "error": str(e)}


def get_config():
    """获取配置

    Returns:
        dict: {"success": bool, "config": dict, "error": str}
    """
    try:
        from config_manager import ConfigManager
        config = ConfigManager.load()
        return {"success": True, "config": config}

    except Exception as e:
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No command specified"}))
        sys.exit(1)

    command = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    # 路由到相应的函数
    if command == "record":
        result = record_audio(
            mode=args.get("mode", "push-to-talk"),
            duration=args.get("duration", 3.0)
        )
    elif command == "chat":
        result = chat_llm(args.get("text", ""))
    elif command == "tts":
        result = generate_tts(args.get("text", ""))
    elif command == "config":
        result = get_config()
    else:
        result = {"success": False, "error": f"Unknown command: {command}"}

    # 输出 JSON 结果到 stdout
    print(json.dumps(result))
