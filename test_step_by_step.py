#!/usr/bin/env python3
"""逐步测试各个模块"""

import sys
import asyncio

print("=" * 60)
print("逐步测试 Speekium 各个模块")
print("=" * 60)

# 测试 1：导入模块
print("\n[1/6] 测试模块导入...")
try:
    from config_manager import ConfigManager

    print("✅ config_manager 导入成功")
except Exception as e:
    print(f"❌ config_manager 导入失败: {e}")
    sys.exit(1)

try:
    from speekium import VoiceAssistant

    print("✅ speekium 导入成功")
except Exception as e:
    print(f"❌ speekium 导入失败: {e}")
    sys.exit(1)

# 测试 2：加载配置
print("\n[2/6] 测试配置加载...")
try:
    config = ConfigManager.load()
    print(f"✅ 配置加载成功")
    print(f"   LLM Backend: {config.get('llm_backend', 'ollama')}")
    print(f"   TTS Backend: {config.get('tts_backend', 'edge')}")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    sys.exit(1)

# 测试 3：初始化 VoiceAssistant（不加载模型）
print("\n[3/6] 测试 VoiceAssistant 实例化...")
try:
    assistant = VoiceAssistant()
    print("✅ VoiceAssistant 实例化成功")
except Exception as e:
    print(f"❌ VoiceAssistant 实例化失败: {e}")
    sys.exit(1)

# 测试 4：测试 VAD 加载（可能需要时间）
print("\n[4/6] 测试 VAD 模型加载（这可能需要 1-2 分钟）...")
print("提示：如果加载时间过长，请按 Ctrl+C 中断")
try:
    assistant.load_vad()
    print("✅ VAD 模型加载成功")
except Exception as e:
    print(f"❌ VAD 模型加载失败: {e}")
    print("   建议：首次使用会从网络下载模型，请确保网络连接正常")
    sys.exit(1)

print("\n" + "=" * 60)
print("测试完成！如果 VAD 加载超时，可以：")
print("1. 检查网络连接")
print("2. 跳过 VAD 测试，直接测试 ASR 和 LLM")
print("=" * 60)
