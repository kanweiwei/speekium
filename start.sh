#!/bin/bash

# Speekium Tauri 自动启动脚本
# 日期: 2026-01-09

set -e  # 遇到错误立即退出

echo "================================"
echo "🚀 Speekium Tauri 自动启动脚本"
echo "================================"
echo ""

# 检查是否在正确的目录
if [ ! -d "tauri-prototype" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    echo "   当前目录: $(pwd)"
    echo "   应该在: /Users/kww/work/opensource/speekium"
    exit 1
fi

echo "✅ 当前目录正确"
echo ""

# 进入 tauri-prototype 目录
cd tauri-prototype

echo "📦 步骤 1/3: 检查依赖..."
if [ ! -d "node_modules" ] || [ ! -d "node_modules/@tauri-apps/cli" ]; then
    echo "⚠️  依赖未安装或不完整，开始安装..."
    echo ""

    # 清理旧依赖
    rm -rf node_modules package-lock.json

    # 安装依赖
    echo "正在安装依赖（可能需要几分钟）..."
    npm install

    echo ""
    echo "✅ 依赖安装完成"
else
    echo "✅ 依赖已安装"
fi

echo ""
echo "🔍 步骤 2/3: 检查端口..."

# 检查端口 1420 是否被占用
if lsof -ti:1420 >/dev/null 2>&1; then
    echo "⚠️  端口 1420 已被占用，正在清理..."
    lsof -ti:1420 | xargs kill -9 2>/dev/null || true
    sleep 1
    echo "✅ 端口已清理"
else
    echo "✅ 端口可用"
fi

echo ""
echo "🚀 步骤 3/3: 启动 Tauri 应用..."
echo ""
echo "================================"
echo "正在启动 Tauri 开发服务器..."
echo "================================"
echo ""
echo "📝 注意事项:"
echo "   - 首次启动可能需要几分钟（编译 Rust）"
echo "   - 窗口会自动弹出"
echo "   - 按 Ctrl+C 停止服务器"
echo ""
echo "🎯 测试步骤:"
echo "   1. 等待 Tauri 窗口弹出"
echo "   2. 点击 🎤 录音按钮"
echo "   3. 说话 3 秒"
echo "   4. 观察界面是否流畅、无闪烁"
echo ""
echo "================================"
echo ""

# 启动 Tauri
npm run tauri dev
