#!/bin/bash
# Speekium Tauri 应用启动脚本 (守护进程模式)

set -e  # 遇到错误立即退出

echo "======================================"
echo "🚀 Speekium Tauri 启动"
echo "======================================"

# 检查依赖
echo ""
echo "1️⃣ 检查依赖..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm 未安装"
    exit 1
fi

if ! command -v cargo &> /dev/null; then
    echo "❌ Rust/Cargo 未安装"
    exit 1
fi

echo "✅ 所有依赖已就绪"

# 检查 Python 依赖
echo ""
echo "2️⃣ 检查 Python 环境..."

if [ ! -d ".venv" ]; then
    echo "⚠️ Python 虚拟环境未找到，正在创建..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
else
    source .venv/bin/activate
fi

echo "✅ Python 环境已激活"

# 检查 Node 依赖
echo ""
echo "3️⃣ 检查 Node 依赖..."

if [ ! -d "node_modules" ]; then
    echo "⚠️ Node 依赖未安装，正在安装..."
    npm install
else
    echo "✅ Node 依赖已安装"
fi

# 启动应用
echo ""
echo "4️⃣ 启动 Tauri 应用..."
echo "   模式: 守护进程 (快速响应)"
echo "   快捷键: Cmd+Shift+Space (显示/隐藏)"
echo ""

npm run tauri dev
