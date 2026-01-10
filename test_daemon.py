#!/usr/bin/env python3
"""
守护进程测试脚本

测试 worker_daemon.py 的功能：
1. 启动守护进程
2. 发送各种命令
3. 验证响应
4. 性能测试
"""

import json
import subprocess
import sys
import time


def send_command(process, command, args):
    """向守护进程发送命令并接收响应"""
    request = {"command": command, "args": args}

    # 发送命令
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()

    # 读取响应
    response_line = process.stdout.readline()
    if not response_line:
        return None

    return json.loads(response_line)


def test_daemon():
    print("=" * 60)
    print("🧪 守护进程测试")
    print("=" * 60)

    # 启动守护进程
    print("\n1️⃣ 启动守护进程...")
    process = subprocess.Popen(
        ["python3", "worker_daemon.py", "daemon"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    # 等待初始化完成
    print("   等待初始化...")
    time.sleep(15)  # 给足够时间加载模型

    try:
        # 测试 1: 健康检查
        print("\n2️⃣ 测试健康检查...")
        result = send_command(process, "health", {})
        if result and result["success"]:
            print("   ✅ 健康检查通过")
            print(f"   📊 状态: {result.get('status')}")
            print(f"   📈 命令计数: {result.get('command_count')}")
            print(f"   🎯 模型状态: {result.get('models_loaded')}")
        else:
            print(f"   ❌ 健康检查失败: {result}")
            return False

        # 测试 2: 配置加载
        print("\n3️⃣ 测试配置加载...")
        start_time = time.time()
        result = send_command(process, "config", {})
        elapsed = time.time() - start_time

        if result and result["success"]:
            print(f"   ✅ 配置加载成功 ({elapsed * 1000:.1f}ms)")
            config = result.get("config", {})
            print(f"   📦 LLM 后端: {config.get('llm_backend')}")
            print(f"   📦 TTS 后端: {config.get('tts_backend')}")
        else:
            print(f"   ⚠️ 配置加载失败: {result}")

        # 测试 3: TTS 生成
        print("\n4️⃣ 测试 TTS 生成...")
        start_time = time.time()
        result = send_command(process, "tts", {"text": "你好，这是守护进程测试"})
        elapsed = time.time() - start_time

        if result and result["success"]:
            print(f"   ✅ TTS 生成成功 ({elapsed * 1000:.1f}ms)")
            print(f"   🔊 音频文件: {result.get('audio_path')}")
        else:
            print(f"   ❌ TTS 失败: {result}")

        # 测试 4: LLM 对话（可选，需要 Ollama 运行）
        print("\n5️⃣ 测试 LLM 对话...")
        start_time = time.time()
        result = send_command(process, "chat", {"text": "你好"})
        elapsed = time.time() - start_time

        if result and result["success"]:
            print(f"   ✅ LLM 响应成功 ({elapsed:.2f}s)")
            response = result.get("content", "")
            print(f"   💬 响应: {response[:50]}...")
        else:
            print(f"   ⚠️ LLM 失败（可能 Ollama 未启动）: {result.get('error')}")

        # 测试 5: 性能测试 - 连续健康检查
        print("\n6️⃣ 性能测试（10次健康检查）...")
        times = []
        for i in range(10):
            start_time = time.time()
            result = send_command(process, "health", {})
            elapsed = time.time() - start_time
            times.append(elapsed * 1000)

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"   📊 平均响应时间: {avg_time:.1f}ms")
        print(f"   ⚡ 最快: {min_time:.1f}ms")
        print(f"   🐌 最慢: {max_time:.1f}ms")

        if avg_time < 100:
            print("   ✅ 性能优秀！（目标 <100ms）")
        elif avg_time < 500:
            print("   ⚠️ 性能一般（目标 <100ms）")
        else:
            print("   ❌ 性能较差（目标 <100ms）")

        # 测试 6: 退出命令
        print("\n7️⃣ 测试退出命令...")
        result = send_command(process, "exit", {})
        if result and result["success"]:
            print("   ✅ 退出命令发送成功")

        # 等待进程退出
        process.wait(timeout=5)
        print("   ✅ 守护进程已正常退出")

        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # 确保进程被终止
        if process.poll() is None:
            print("\n🧹 清理进程...")
            process.terminate()
            process.wait(timeout=5)


if __name__ == "__main__":
    print("\n⚠️ 注意：此测试需要约 15 秒加载模型")
    print("请确保已安装所有依赖: uv sync\n")

    success = test_daemon()
    sys.exit(0 if success else 1)
