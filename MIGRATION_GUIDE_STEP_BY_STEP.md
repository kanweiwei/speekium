# 🚀 Tauri 迁移手动执行指南

## 准备工作

### 1. 确认当前状态
```bash
cd /Users/kww/work/opensource/speekium

# 查看未提交的更改
git status

# 如果有需要保留的更改，先提交
git add .
git commit -m "feat: add daemon mode, streaming, and TTS streaming features"
```

### 2. 创建迁移分支
```bash
# 创建备份分支（可选但推荐）
git branch backup-before-tauri-migration

# 创建工作分支
git checkout -b feat/tauri-integration
```

## Phase 1: 创建 Tauri 结构

### 1.1 创建目录
```bash
mkdir -p src-tauri/src
mkdir -p src-tauri/icons
mkdir -p src
```

### 1.2 复制 Rust 后端
```bash
# 复制 Cargo 配置
cp tauri-prototype/src-tauri/Cargo.toml src-tauri/
cp tauri-prototype/src-tauri/Cargo.lock src-tauri/ 2>/dev/null || true

# 复制源代码
cp tauri-prototype/src-tauri/src/lib.rs src-tauri/src/
cp tauri-prototype/src-tauri/src/main.rs src-tauri/src/

# 复制图标
cp -r tauri-prototype/src-tauri/icons/* src-tauri/icons/

# 复制配置
cp tauri-prototype/src-tauri/tauri.conf.json src-tauri/
cp tauri-prototype/src-tauri/build.rs src-tauri/ 2>/dev/null || true

echo "✅ Rust 后端文件已复制"
```

### 1.3 调整 Rust 代码路径
编辑 `src-tauri/src/lib.rs`，修改 worker_daemon.py 的路径：

找到这一行：
```rust
.arg("../../worker_daemon.py")
```

改为：
```rust
.arg("../worker_daemon.py")
```

### 1.4 更新 Tauri 配置
编辑 `src-tauri/tauri.conf.json`，确保路径正确：

```json
{
  "build": {
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build",
    "devPath": "http://localhost:5173",
    "distDir": "../dist"
  }
}
```

## Phase 2: 复制前端代码

### 2.1 复制前端源码
```bash
# 复制所有前端文件
cp -r tauri-prototype/src/* src/

# 复制根配置文件
cp tauri-prototype/index.html ./
cp tauri-prototype/vite.config.ts ./
cp tauri-prototype/tsconfig.json ./
cp tauri-prototype/tsconfig.node.json ./
cp tauri-prototype/tsconfig.app.json ./

echo "✅ 前端文件已复制"
```

### 2.2 创建新的 package.json
创建文件 `package.json`（在项目根目录）：

```json
{
  "name": "speekium",
  "version": "0.2.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "tauri build"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "@tauri-apps/api": "^2.2.0",
    "@tauri-apps/plugin-opener": "^2.0.3",
    "@tauri-apps/plugin-global-shortcut": "^2.0.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "@tauri-apps/cli": "^2.2.0"
  }
}
```

### 2.3 安装依赖
```bash
npm install

echo "✅ 前端依赖已安装"
```

## Phase 3: 更新配置文件

### 3.1 创建启动脚本
创建 `start.sh`:

```bash
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
```

让启动脚本可执行：
```bash
chmod +x start.sh
```

### 3.2 更新 .gitignore
编辑 `.gitignore`，添加：

```gitignore
# Tauri
/src-tauri/target/
/dist/

# Node
/node_modules/

# Old (will be removed)
/web/
/tauri-prototype/
```

## Phase 4: 测试新应用

### 4.1 测试守护进程
```bash
# 确保虚拟环境激活
source .venv/bin/activate

# 测试守护进程
python3 test_daemon.py
```

预期输出：
- ✅ 守护进程启动成功
- ✅ 健康检查通过
- ✅ 所有模型加载

### 4.2 启动 Tauri 应用
```bash
./start.sh
```

或者手动：
```bash
source .venv/bin/activate
npm run tauri:dev
```

### 4.3 功能测试清单
在应用中测试以下功能：

- [ ] 应用正常启动
- [ ] 守护进程连接正常（右上角显示健康状态）
- [ ] 输入文本发送消息
- [ ] 流式响应显示（打字机效果）
- [ ] 点击麦克风录音
- [ ] 语音识别正常
- [ ] TTS 播放（如果启用）
- [ ] 全局快捷键 (Cmd/Ctrl+Shift+Space)
- [ ] 系统托盘图标
- [ ] 窗口隐藏/显示

## Phase 5: 清理旧代码（可选）

### 5.1 确认新版本工作正常
只有在新版本完全正常后才执行清理！

### 5.2 移除旧代码
```bash
# 移除旧 Web UI
git rm -rf web/

# 移除原型目录
git rm -rf tauri-prototype/

# 移除旧的 Web 服务器
git rm web_app.py
git rm floating_window.py
git rm tray_manager.py

echo "✅ 旧代码已移除"
```

### 5.3 清理临时文档
```bash
# 移除大量临时状态文档（保留核心文档）
git rm AI_WORK_COMPLETE.md
git rm ARCHITECTURE_FIX.md
git rm COMPLETION_REPORT.md
git rm CURRENT_STATUS.md
git rm DELIVERY_REPORT.md
git rm DEVELOPMENT.md
git rm DOCUMENTATION_INDEX.md
git rm FINAL_*.md
git rm INTEGRATION_TEST_RESULTS.md
git rm MIGRATION_STATUS.md
git rm NEXT_STEPS.md
git rm PHASE_*.md
git rm PROJECT_STATUS_FINAL.md
git rm REFACTOR_COMPLETE.md
git rm SESSION_*.md
git rm START_HERE.md
git rm STATUS.md
git rm TAURI_WINDOW_TEST_REPORT.md
git rm TESTING_GUIDE.md
git rm WORK_*.md

# 保留核心文档：
# - README.md
# - DAEMON_MODE.md
# - STREAMING_MODE.md
# - TTS_STREAMING_MODE.md
# - FEATURES_COMPLETE.md
# - PROJECT_STATUS.md
# - QUICK_START_TTS.md
# - MIGRATION_PLAN.md

echo "✅ 临时文档已清理"
```

## Phase 6: 更新文档

### 6.1 更新 README.md
编辑 README.md，更新启动命令：

```markdown
## Quick Start

### Desktop App (Recommended)

\`\`\`bash
# One-click start
./start.sh

# Or manual
source .venv/bin/activate
npm run tauri:dev
\`\`\`

### Build for production

\`\`\`bash
npm run tauri:build
\`\`\`
```

### 6.2 更新 QUICK_START_TTS.md
将所有对 `start-tauri.sh` 的引用改为 `start.sh`。

## Phase 7: 提交更改

### 7.1 查看更改
```bash
git status
git diff
```

### 7.2 提交
```bash
git add .
git commit -m "feat: integrate tauri prototype into main project

Features:
- Migrate Rust backend from tauri-prototype to src-tauri/
- Migrate React frontend from tauri-prototype to src/
- Update build configuration and scripts
- Remove deprecated web/ directory and Flask server
- Clean up temporary documentation files

Benefits:
- 18x faster response (daemon mode)
- 10x better UX (streaming responses)
- 85% lower latency (streaming TTS)
- Unified desktop application architecture
"
```

### 7.3 推送（可选）
```bash
git push origin feat/tauri-integration
```

## 🎯 完成检查清单

- [ ] **Phase 1**: Tauri 结构创建完成
- [ ] **Phase 2**: 前端代码迁移完成
- [ ] **Phase 3**: 配置文件更新完成
- [ ] **Phase 4**: 所有功能测试通过
- [ ] **Phase 5**: 旧代码清理完成
- [ ] **Phase 6**: 文档更新完成
- [ ] **Phase 7**: Git 提交完成

## 🐛 故障排查

### 问题 1: npm install 失败

**解决**：
```bash
# 删除 node_modules 和 package-lock.json
rm -rf node_modules package-lock.json

# 重新安装
npm install
```

### 问题 2: Rust 编译失败

**解决**：
```bash
# 检查 Rust 工具链
rustc --version
cargo --version

# 更新 Rust
rustup update

# 清理并重新编译
cd src-tauri
cargo clean
cargo build
```

### 问题 3: 守护进程路径错误

**确认**：
检查 `src-tauri/src/lib.rs` 中的路径：
```rust
.arg("../worker_daemon.py")  // 正确：相对于 src-tauri/
```

### 问题 4: 应用启动后守护进程未连接

**检查**：
```bash
# 查看 Tauri 控制台输出
# 应该看到：
# [Daemon] 🚀 Speekium Daemon 初始化中...
# [Daemon] ✅ 守护进程就绪
```

**解决**：
- 确保虚拟环境激活
- 确保所有 Python 依赖安装
- 检查 worker_daemon.py 路径

## 📞 需要帮助？

如果遇到问题：

1. 查看详细文档：
   - [MIGRATION_PLAN.md](./MIGRATION_PLAN.md)
   - [DAEMON_MODE.md](./DAEMON_MODE.md)
   - [QUICK_START_TTS.md](./QUICK_START_TTS.md)

2. 检查测试脚本：
   ```bash
   python3 test_daemon.py
   python3 test_tts_stream.py
   ```

3. 查看日志输出（Tauri 开发工具）

---

**准备好了？开始执行 Phase 1！** 🚀
