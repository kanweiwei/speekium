import asyncio
import subprocess

import edge_tts


async def speak(text, voice="zh-CN-XiaoxiaoNeural"):
    """使用 Edge TTS 朗读文本"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save("/tmp/speech.mp3")
    subprocess.run(["afplay", "/tmp/speech.mp3"])  # macOS 自带播放器


async def list_voices():
    """列出所有可用的中文语音"""
    voices = await edge_tts.list_voices()
    chinese_voices = [v for v in voices if v["Locale"].startswith("zh")]
    print("可用的中文语音:")
    for v in chinese_voices:
        print(f"  {v['ShortName']}: {v['FriendlyName']}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        asyncio.run(list_voices())
    else:
        text = sys.argv[1] if len(sys.argv) > 1 else "你好，这是一个测试"
        print(f"正在朗读: {text}")
        asyncio.run(speak(text))
