#!/bin/bash

# Speekium 开发环境停止脚本

echo "🛑 Stopping Speekium Development Environment"
echo "============================================"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 停止后端服务器
if [ -f /tmp/speekium-backend.pid ]; then
    BACKEND_PID=$(cat /tmp/speekium-backend.pid)
    if kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${YELLOW}→${NC} Stopping backend server (PID: $BACKEND_PID)..."
        kill $BACKEND_PID
        rm /tmp/speekium-backend.pid
        echo -e "${GREEN}✓${NC} Backend server stopped"
    else
        echo -e "${YELLOW}!${NC} Backend server not running"
        rm /tmp/speekium-backend.pid
    fi
else
    # 尝试查找并停止
    PIDS=$(lsof -ti :8008 2>/dev/null)
    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}→${NC} Found backend process, stopping..."
        echo $PIDS | xargs kill
        echo -e "${GREEN}✓${NC} Backend server stopped"
    else
        echo -e "${YELLOW}!${NC} No backend server running on port 8008"
    fi
fi

# 停止测试服务器
if [ -f /tmp/speekium-web.pid ]; then
    WEB_PID=$(cat /tmp/speekium-web.pid)
    if kill -0 $WEB_PID 2>/dev/null; then
        echo -e "${YELLOW}→${NC} Stopping web server (PID: $WEB_PID)..."
        kill $WEB_PID
        rm /tmp/speekium-web.pid
        echo -e "${GREEN}✓${NC} Web server stopped"
    else
        echo -e "${YELLOW}!${NC} Web server not running"
        rm /tmp/speekium-web.pid
    fi
else
    # 尝试查找并停止
    PIDS=$(lsof -ti :8080 2>/dev/null)
    if [ ! -z "$PIDS" ]; then
        echo -e "${YELLOW}→${NC} Found web process, stopping..."
        echo $PIDS | xargs kill
        echo -e "${GREEN}✓${NC} Web server stopped"
    else
        echo -e "${YELLOW}!${NC} No web server running on port 8080"
    fi
fi

# 清理日志文件（可选）
if [ "$1" == "--clean" ]; then
    echo -e "${YELLOW}→${NC} Cleaning log files..."
    rm -f /tmp/speekium-*.log
    echo -e "${GREEN}✓${NC} Logs cleaned"
fi

echo -e "\n${GREEN}✓ Development environment stopped${NC}"
echo ""
