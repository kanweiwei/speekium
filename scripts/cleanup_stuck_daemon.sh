#!/bin/bash
# 快速清理 Speekium 旧的进程和 socket 文件
# 用于解决"卡在正在启动语音服务"的问题

echo "🔍 检查 Speekium 相关进程..."

# 查找并杀掉旧的 worker_daemon 进程
OLD_PIDS=$(ps aux | grep -E "python.*worker_daemon socket" | grep -v grep | awk '{print $2}')

if [ -n "$OLD_PIDS" ]; then
    echo "🔪 发现旧的 daemon 进程: $OLD_PIDS"
    echo "$OLD_PIDS" | xargs kill -9
    echo "✅ 已杀掉旧进程"
else
    echo "✅ 没有发现旧的 daemon 进程"
fi

# 清理旧的 socket 文件
echo "🧹 清理旧的 socket 文件..."
rm -f /tmp/speekium-daemon.sock
rm -f /tmp/speekium-notif.sock
rm -f /tmp/speekium-test.sock
echo "✅ Socket 文件已清理"

echo ""
echo "✅ 清理完成！现在可以重新启动应用了"
