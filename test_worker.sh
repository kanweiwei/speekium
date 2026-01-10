#!/bin/bash

echo "=========================================="
echo "Speekium Worker 功能测试"
echo "=========================================="
echo ""

cd /Users/kww/work/opensource/speekium

echo "测试 1: 配置加载"
python3 worker.py config | python3 -c "import sys, json; data=json.load(sys.stdin); print('  ✓ LLM:', data['config']['llm_backend'], '| TTS:', data['config']['tts_backend'])" 2>/dev/null || echo "  ✗ 失败"
echo ""

echo "测试 2: 录音功能 (模拟 - 需要麦克风)"
echo "  ⏭ 跳过（需要实际麦克风输入）"
echo ""

echo "测试 3: LLM 对话"
python3 worker.py chat '{"text":"你好"}' | python3 -c "import sys, json; data=json.load(sys.stdin); print('  ✓ 响应:', data.get('content', 'N/A')[:50] + '...')" 2>/dev/null || echo "  ✗ 失败"
echo ""

echo "测试 4: TTS 生成"
python3 worker.py tts '{"text":"测试"}' | python3 -c "import sys, json; data=json.load(sys.stdin); print('  ✓ 音频文件:', data.get('audio_path', 'N/A'))" 2>/dev/null || echo "  ✗ 失败"
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="
