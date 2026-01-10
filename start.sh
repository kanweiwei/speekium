#!/bin/bash
set -e

echo "🚀 Starting Speekium..."

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# 检查依赖
if ! command -v npm &> /dev/null; then
    echo "❌ npm not found. Please install Node.js"
    exit 1
fi

# 启动 Tauri
echo "🔧 Starting Tauri development server..."
npm run tauri:dev
