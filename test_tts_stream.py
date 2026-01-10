#!/usr/bin/env python3
"""
测试 TTS 流式功能
直接测试守护进程的 chat_tts_stream 命令
"""

import json
import subprocess
import sys
import time


def test_tts_stream():
    """测试 TTS 流式对话"""
    print("=" * 60)
    print("🧪 测试 TTS 流式功能")
    print("=" * 60)

    # 启动守护进程
    print("\n1️⃣ 启动守护进程...")
    daemon = subprocess.Popen(
        ["python3", "worker_daemon.py", "daemon"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,  # 将 stderr 输出到控制台
        text=True,
        bufsize=1,
    )

    # 等待初始化
    print("⏳ 等待模型加载（约 15 秒）...")
    time.sleep(15)

    # 测试健康检查
    print("\n2️⃣ 健康检查...")
    request = {"command": "health", "args": {}}
    daemon.stdin.write(json.dumps(request) + "\n")
    daemon.stdin.flush()

    response = json.loads(daemon.stdout.readline())
    if response.get("success"):
        print("✅ 守护进程健康")
        print(f"   - 已处理命令: {response.get('command_count', 0)}")
        print(f"   - 模型状态: {response.get('models_loaded', {})}")
    else:
        print("❌ 健康检查失败:", response.get("error"))
        daemon.terminate()
        return

    # 测试 TTS 流式对话
    print("\n3️⃣ 测试 TTS 流式对话...")
    print("📤 发送: 介绍一下量子计算")

    request = {
        "command": "chat_tts_stream",
        "args": {"text": "用三句话介绍一下量子计算", "auto_play": True},
    }

    daemon.stdin.write(json.dumps(request) + "\n")
    daemon.stdin.flush()

    print("\n📥 流式响应:")
    text_chunks = []
    audio_chunks = []

    while True:
        line = daemon.stdout.readline()
        if not line:
            print("❌ 守护进程意外关闭")
            break

        try:
            chunk = json.loads(line)
            chunk_type = chunk.get("type")

            if chunk_type == "text_chunk":
                content = chunk.get("content", "")
                text_chunks.append(content)
                print(f"   📝 文本: {content}")

            elif chunk_type == "audio_chunk":
                audio_path = chunk.get("audio_path", "")
                text = chunk.get("text", "")
                audio_chunks.append({"path": audio_path, "text": text})
                print(f"   🔊 音频: {text[:30]}... → {audio_path}")

            elif chunk_type == "done":
                print("\n✅ 流式响应完成")
                break

            elif chunk_type == "error":
                error = chunk.get("error", "Unknown error")
                print(f"\n❌ 错误: {error}")
                break

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析错误: {e}")
            print(f"   原始数据: {line}")
            continue

    # 统计
    print("\n📊 统计:")
    print(f"   - 文本片段: {len(text_chunks)}")
    print(f"   - 音频片段: {len(audio_chunks)}")
    print(f"   - 完整文本: {''.join(text_chunks)}")

    # 验证音频文件
    print("\n4️⃣ 验证音频文件...")
    import os

    for i, audio in enumerate(audio_chunks, 1):
        if os.path.exists(audio["path"]):
            size = os.path.getsize(audio["path"])
            print(f"   ✅ 音频 {i}: {audio['text'][:30]}... ({size} bytes)")
        else:
            print(f"   ❌ 音频 {i}: 文件不存在 - {audio['path']}")

    # 退出守护进程
    print("\n5️⃣ 关闭守护进程...")
    request = {"command": "exit", "args": {}}
    daemon.stdin.write(json.dumps(request) + "\n")
    daemon.stdin.flush()

    daemon.wait(timeout=5)
    print("✅ 守护进程已关闭")

    print("\n" + "=" * 60)
    print("✅ TTS 流式测试完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_tts_stream()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
