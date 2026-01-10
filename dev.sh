#!/bin/bash

echo "=================================================="
echo "Speekium 开发模式启动脚本"
echo "=================================================="
echo ""

# 检查是否在正确的目录
if [ ! -f "web/package.json" ]; then
    echo "❌ 错误：必须在项目根目录运行此脚本"
    echo "   当前目录: $(pwd)"
    exit 1
fi

# 清理旧的进程
echo "[1/3] 清理旧进程..."
pkill -f "vite.*dev"
pkill -f "web_app.py"

# 检查端口占用
echo "[2/3] 检查端口占用..."
PORT=5173
if lsof -ti:$PORT > /dev/null; then
    echo "❌ 端口 $PORT 已被占用"
    echo "   请先停止占用该端口的进程"
    lsof -ti:$PORT
    exit 1
fi

# 启动前端开发服务器
echo "[3/3] 启动前端开发服务器..."
cd web
echo "   启动 Vite 开发服务器（端口 $PORT）..."
npm run dev &
FRONTEND_PID=$!

# 等待前端启动
echo ""
echo "⏳ 等待前端启动（10秒）..."
sleep 10

# 检查前端是否启动成功
if ps -p $FRONTEND_PID > /dev/null; then
    echo "✅ 前端开发服务器已启动"
    echo "   PID: $FRONTEND_PID"
    echo "   URL: http://localhost:$PORT"
    echo ""
else
    echo "❌ 前端启动失败"
    kill $FRONTEND_PID 2>/dev/null
    exit 1
fi

# 返回项目根目录
cd ..

# 启动后端
echo ""
echo "[4/4] 启动后端（开发模式）..."
echo "   启动 Python 后端（--dev 模式）..."
python web_app.py --dev &
BACKEND_PID=$!

# 保存 PID 用于清理
echo $FRONTEND_PID > .frontend_dev.pid
echo $BACKEND_PID > .backend_dev.pid

echo ""
echo "=================================================="
echo "🎉 开发模式已启动！"
echo "=================================================="
echo ""
echo "📖 测试地址："
echo "   前端开发服务器: http://localhost:$PORT"
echo "   应用窗口: 已自动打开"
echo ""
echo "🛠️ 命令："
echo "   Ctrl+C 停止所有服务"
echo ""
echo "✨ 特性："
echo "   ✅ 前端热重载 (Vite HMR)"
echo "   ✅ 浏览器开发者工具 (右键 → 检查元素)"
echo "   ✅ 实时调试"
echo ""
echo "=================================================="
echo ""

# 清理函数
cleanup() {
    echo ""
    echo "⏹️  正在停止服务..."

    # 读取并终止进程
    if [ -f .frontend_dev.pid ]; then
        kill $(cat .frontend_dev.pid) 2>/dev/null
        rm -f .frontend_dev.pid
        echo "✅ 前端开发服务器已停止"
    fi

    if [ -f .backend_dev.pid ]; then
        kill $(cat .backend_dev.pid) 2>/dev/null
        rm -f .backend_dev.pid
        echo "✅ 后端服务已停止"
    fi

    # 清理相关进程
    pkill -f "vite.*dev"
    pkill -f "web_app.py.*--dev"

    echo ""
    echo "✅ 所有服务已停止"
    exit 0
}

# 捕获 Ctrl+C
trap cleanup SIGINT SIGTERM

# 等待任一进程结束
wait -n

# 如果任一进程意外退出，清理所有进程
cleanup
