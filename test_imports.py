#!/usr/bin/env python3
"""测试脚本：验证各部分是否正常工作"""

import sys

sys.path.append(".")

print("=" * 50)
print("测试脚本：验证 Speekium 各部分")
print("=" * 50)

# 测试 1：导入模块
print("\n[1/5] 测试模块导入...")
try:
    from config_manager import ConfigManager
    from speekium import VoiceAssistant

    print("✅ speekium 和 config_manager 导入成功")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试 2：加载配置
print("\n[2/5] 测试配置加载...")
try:
    config = ConfigManager.load()
    print("✅ 配置加载成功")
    print(f"   LLM Backend: {config.get('llm_backend', 'ollama')}")
    print(f"   TTS Backend: {config.get('tts_backend', 'edge')}")
except Exception as e:
    print(f"❌ 配置加载失败: {e}")
    sys.exit(1)

# 测试 3：初始化 VoiceAssistant
print("\n[3/5] 测试 VoiceAssistant 初始化...")
try:
    assistant = VoiceAssistant()
    print("✅ VoiceAssistant 实例化成功")
except Exception as e:
    print(f"❌ VoiceAssistant 初始化失败: {e}")
    sys.exit(1)

# 测试 4：检查关键方法是否存在
print("\n[4/5] 检查关键方法...")
methods_to_check = [
    "load_vad",
    "load_asr",
    "load_llm",
    "record_with_vad",
    "transcribe",
    "speak",
]

for method in methods_to_check:
    if hasattr(assistant, method):
        print(f"✅ {method} 存在")
    else:
        print(f"❌ {method} 不存在")

# 测试 5：测试配置文件
print("\n[5/5] 测试 dist 目录...")
import os

if os.path.exists("dist/index.html"):
    print("✅ dist/index.html 存在")
    print(f"   文件大小: {os.path.getsize('dist/index.html')} bytes")
else:
    print("❌ dist/index.html 不存在")

if os.path.exists("dist/assets/index.js"):
    print("✅ dist/assets/index.js 存在")
    print(f"   文件大小: {os.path.getsize('dist/assets/index.js')} bytes")
else:
    print("❌ dist/assets/index.js 不存在")

print("\n" + "=" * 50)
print("测试完成！")
print("=" * 50)
