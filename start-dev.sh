#!/bin/bash

# Speekium 开发环境启动脚本
# 用途：同时启动后端服务器和前端测试页面

set -e

echo "🚀 Starting Speekium Development Environment"
echo "=============================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 Python 后端服务器
echo -e "\n${YELLOW}[1/4]${NC} Checking Python backend..."
if lsof -i :8008 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Backend server already running on port 8008"
else
    echo -e "${YELLOW}→${NC} Starting backend server..."
    python3 backend_server.py > /tmp/speekium-backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/speekium-backend.pid
    sleep 3

    if curl -s http://localhost:8008/health > /dev/null; then
        echo -e "${GREEN}✓${NC} Backend server started (PID: $BACKEND_PID)"
    else
        echo -e "${RED}✗${NC} Failed to start backend server"
        echo "Check logs: tail -f /tmp/speekium-backend.log"
        exit 1
    fi
fi

# 检查 Ollama
echo -e "\n${YELLOW}[2/4]${NC} Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Ollama is running"
    MODEL=$(curl -s http://localhost:11434/api/tags | python3 -c "import json, sys; data=json.load(sys.stdin); print(data['models'][0]['name'] if data.get('models') else 'none')")
    echo -e "  Model: ${GREEN}${MODEL}${NC}"
else
    echo -e "${RED}✗${NC} Ollama is not running"
    echo "  Please start Ollama: ollama serve"
    exit 1
fi

# 启动测试服务器
echo -e "\n${YELLOW}[3/4]${NC} Starting test web server..."
if lsof -i :8080 > /dev/null 2>&1; then
    echo -e "${YELLOW}!${NC} Port 8080 already in use, killing existing process..."
    lsof -ti :8080 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

cd tauri-prototype
python3 -m http.server 8080 > /tmp/speekium-web.log 2>&1 &
WEB_PID=$!
echo $WEB_PID > /tmp/speekium-web.pid
sleep 2

if lsof -i :8080 > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Web server started (PID: $WEB_PID)"
else
    echo -e "${RED}✗${NC} Failed to start web server"
    exit 1
fi

# 测试 API
echo -e "\n${YELLOW}[4/4]${NC} Testing API endpoints..."
CONFIG=$(curl -s http://localhost:8008/api/config | python3 -c "import json, sys; data=json.load(sys.stdin); print('✓' if data.get('success') else '✗')")
echo -e "  Config endpoint: ${GREEN}${CONFIG}${NC}"

CHAT=$(curl -s -X POST http://localhost:8008/api/chat -H "Content-Type: application/json" -d '{"text":"test"}' | python3 -c "import json, sys; data=json.load(sys.stdin); print('✓' if len(data)>0 else '✗')")
echo -e "  Chat endpoint: ${GREEN}${CHAT}${NC}"

# 完成
echo -e "\n${GREEN}=============================================="
echo -e "✓ Development environment ready!${NC}"
echo -e "\n📝 Access points:"
echo -e "  • Test page:   ${GREEN}http://localhost:8080/test-api.html${NC}"
echo -e "  • Backend API: ${GREEN}http://localhost:8008${NC}"
echo -e "  • Ollama API:  ${GREEN}http://localhost:11434${NC}"

echo -e "\n📊 Logs:"
echo -e "  • Backend: ${YELLOW}tail -f /tmp/speekium-backend.log${NC}"
echo -e "  • Web:     ${YELLOW}tail -f /tmp/speekium-web.log${NC}"

echo -e "\n🛑 To stop:"
echo -e "  • Run: ${YELLOW}./stop-dev.sh${NC}"
echo -e "  • Or:  ${YELLOW}kill \$(cat /tmp/speekium-*.pid)${NC}"

echo -e "\n💡 Next steps:"
echo -e "  1. Open http://localhost:8080/test-api.html in your browser"
echo -e "  2. Test the chat functionality"
echo -e "  3. When ready, upgrade Node.js and run 'npm run tauri dev'"

# 打开浏览器（可选）
if command -v open > /dev/null 2>&1; then
    echo -e "\n${YELLOW}Opening browser...${NC}"
    sleep 1
    open http://localhost:8080/test-api.html
fi

echo ""
