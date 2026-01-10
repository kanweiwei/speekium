#!/bin/bash
# 简单的 TTS 流式测试脚本

echo "启动守护进程..."
python3 worker_daemon.py daemon &
DAEMON_PID=$!

echo "等待模型加载..."
sleep 15

echo "发送健康检查..."
echo '{"command": "health", "args": {}}' | nc localhost 12345 2>/dev/null || {
    # 如果 nc 不可用，直接用管道
    echo '{"command": "health", "args": {}}'
}

echo "等待响应..."
sleep 2

echo "发送 TTS 流式命令..."
echo '{"command": "chat_tts_stream", "args": {"text": "用一句话介绍量子计算", "auto_play": true}}'

echo "等待 5 秒..."
sleep 5

echo "关闭守护进程..."
kill $DAEMON_PID
wait $DAEMON_PID 2>/dev/null

echo "测试完成"
