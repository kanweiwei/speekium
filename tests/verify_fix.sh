#!/bin/bash
#
# PTT 超时问题修复验证脚本
#
# 使用方法:
#   1. 重新编译 Rust 代码
#   2. 运行测试套件
#   3. 手动测试 PTT 功能
#

set -e  # 遇到错误立即退出

echo "============================================================"
echo "PTT 超时问题修复验证"
echo "============================================================"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="/Users/kww/work/opensource/speekium"
cd "$PROJECT_ROOT"

echo ""
echo "步骤 1: 运行单元测试..."
echo "============================================================"
if python3 tests/test_socket_timeout.py; then
    echo -e "${GREEN}✅ 单元测试通过${NC}"
else
    echo -e "${RED}❌ 单元测试失败${NC}"
    exit 1
fi

echo ""
echo "步骤 2: 运行集成测试..."
echo "============================================================"
if python3 tests/test_ptt_blocking.py; then
    echo -e "${GREEN}✅ 集成测试通过${NC}"
else
    echo -e "${RED}❌ 集成测试失败${NC}"
    exit 1
fi

echo ""
echo "步骤 3: 检查 Rust 代码编译..."
echo "============================================================"
cd "$PROJECT_ROOT/src-tauri"
echo "检查代码语法..."
if cargo check --quiet 2>&1 | grep -q "error"; then
    echo -e "${RED}❌ Rust 代码有错误${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Rust 代码检查通过${NC}"
fi

echo ""
echo "步骤 4: 重新编译 Rust 代码..."
echo "============================================================"
echo -e "${YELLOW}注意: 首次编译可能需要几分钟...${NC}"
if cargo build --release; then
    echo -e "${GREEN}✅ Rust 代码编译成功${NC}"
else
    echo -e "${RED}❌ Rust 代码编译失败${NC}"
    exit 1
fi

echo ""
echo "============================================================"
echo "验证完成!"
echo "============================================================"
echo -e "${GREEN}✅ 所有测试通过${NC}"
echo -e "${GREEN}✅ 代码编译成功${NC}"
echo ""
echo "下一步操作:"
echo "  1. 启动应用: npm run tauri dev"
echo "  2. 使用 PTT 热键进行测试"
echo "  3. 验证长时间操作不会超时"
echo ""
echo "测试建议:"
echo "  - 进行多次 PTT 操作 (10-20次)"
echo "  - 测试不同长度的对话 (短句/长句)"
echo "  - 测试网络波动情况"
echo "  - 观察是否有超时错误"
echo ""
echo "如果仍有问题,请查看:"
echo "  - 测试报告: tests/TDD_FIX_REPORT.md"
echo "  - 日志文件: ~/Library/Logs/speekium/"
echo "============================================================"
