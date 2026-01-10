# 📦 Tauri 原型迁移到主项目计划

## 🎯 目标

将 `tauri-prototype/` 中成熟的功能迁移到主项目，替换旧的 Web UI，统一为 Tauri 桌面应用。

## 📊 当前项目结构分析

### 主项目结构
```
speekium/
├── speekium.py           # 核心 VoiceAssistant 类
├── backends.py           # LLM 后端（Ollama, Claude）
├── worker_daemon.py      # ✅ 守护进程（已实现）
├── config_manager.py     # 配置管理
├── web/                  # 旧 Web UI（React + Vite）
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── web_app.py            # 旧 Flask Web 服务器
├── tauri-prototype/      # 原型项目（需迁移）
│   ├── src/              # React 前端（成熟版本）
│   ├── src-tauri/        # Rust 后端（成熟版本）
│   └── package.json
└── [其他文件]
```

### 核心功能对比

| 功能 | tauri-prototype | web/ | 建议 |
|------|----------------|------|------|
| 前端框架 | React + TS + Tauri | React + TS + Vite | 使用 tauri-prototype |
| UI 组件 | 自定义简洁 UI | Radix UI 组件库 | 合并优势 |
| 守护进程集成 | ✅ 完整实现 | ❌ 无 | 使用 tauri-prototype |
| 流式响应 | ✅ 完整实现 | ❌ 无 | 使用 tauri-prototype |
| TTS 流式 | ✅ 完整实现 | ❌ 无 | 使用 tauri-prototype |
| 后端架构 | Rust + IPC | Flask HTTP | 使用 tauri-prototype |

## 🔄 迁移策略

### 方案 A：渐进式迁移（推荐）

**优点**：
- 保留旧 Web UI，逐步迁移
- 风险低，可回滚
- 可以同时维护两个版本

**缺点**：
- 迁移周期较长
- 需要维护两套代码

**步骤**：
1. 在主项目根目录创建 `src-tauri/` 目录
2. 迁移 Rust 后端代码
3. 创建新的前端目录 `src/`（基于 tauri-prototype）
4. 更新配置文件
5. 测试完成后，删除 `web/` 和 `tauri-prototype/`

### 方案 B：直接替换（激进）

**优点**：
- 快速完成迁移
- 代码结构清晰

**缺点**：
- 风险较高
- 需要一次性完成所有工作

**步骤**：
1. 备份当前代码
2. 删除 `web/` 目录
3. 将 `tauri-prototype/` 内容移到主项目
4. 重命名和调整路径
5. 测试所有功能

## 📋 详细迁移计划（推荐方案 A）

### Phase 1: 准备工作（1 小时）

#### 1.1 创建备份
```bash
# 备份当前代码
git add .
git commit -m "chore: backup before tauri migration"
git branch backup-before-tauri-migration

# 创建迁移分支
git checkout -b feat/tauri-integration
```

#### 1.2 分析依赖差异
```bash
# 比较 package.json
diff web/package.json tauri-prototype/package.json

# 合并依赖
```

### Phase 2: Rust 后端迁移（2 小时）

#### 2.1 创建主项目 Tauri 结构
```bash
cd /Users/kww/work/opensource/speekium
mkdir -p src-tauri/src
mkdir -p src-tauri/icons
```

#### 2.2 复制 Rust 代码
```bash
# 复制 Cargo 配置
cp tauri-prototype/src-tauri/Cargo.toml src-tauri/
cp tauri-prototype/src-tauri/Cargo.lock src-tauri/

# 复制源代码
cp tauri-prototype/src-tauri/src/lib.rs src-tauri/src/
cp tauri-prototype/src-tauri/src/main.rs src-tauri/src/

# 复制图标
cp -r tauri-prototype/src-tauri/icons/ src-tauri/

# 复制 Tauri 配置
cp tauri-prototype/src-tauri/tauri.conf.json src-tauri/

# 复制构建文件
cp tauri-prototype/src-tauri/build.rs src-tauri/
```

#### 2.3 调整路径配置
修改 `src-tauri/lib.rs` 中的路径：
```rust
// 旧路径（原型）
.arg("../../worker_daemon.py")

// 新路径（主项目）
.arg("../worker_daemon.py")
```

修改 `src-tauri/tauri.conf.json`:
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

### Phase 3: 前端代码迁移（2 小时）

#### 3.1 创建新前端目录
```bash
mkdir -p src
```

#### 3.2 复制前端代码
```bash
# 复制源代码
cp -r tauri-prototype/src/* src/

# 复制配置文件
cp tauri-prototype/index.html ./
cp tauri-prototype/vite.config.ts ./
cp tauri-prototype/tsconfig.json ./
cp tauri-prototype/tsconfig.node.json ./
cp tauri-prototype/tsconfig.app.json ./
```

#### 3.3 合并 package.json
创建新的 `package.json`（在项目根目录）：
```json
{
  "name": "speekium",
  "version": "0.1.0",
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

#### 3.4 更新 vite.config.ts
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
});
```

### Phase 4: 配置文件整理（1 小时）

#### 4.1 更新启动脚本
创建 `start.sh`:
```bash
#!/bin/bash

# 激活虚拟环境
source .venv/bin/activate

# 启动 Tauri 开发服务器
npm run tauri:dev
```

#### 4.2 更新 .gitignore
```
# Tauri
/src-tauri/target
/dist

# Node
/node_modules

# Old web UI (deprecated)
/web/node_modules
/web/dist

# Prototype (will be removed)
/tauri-prototype
```

#### 4.3 更新 README.md
添加新的启动说明：
```markdown
## Quick Start

### Using Tauri Desktop App (Recommended)

\`\`\`bash
# One-click start
./start.sh

# Or manual
source .venv/bin/activate
npm install
npm run tauri:dev
\`\`\`
```

### Phase 5: 测试验证（2 小时）

#### 5.1 功能测试清单
- [ ] 守护进程正常启动
- [ ] 健康检查通过
- [ ] 语音录音功能
- [ ] 流式 LLM 响应
- [ ] TTS 流式播放
- [ ] 全局快捷键
- [ ] 系统托盘
- [ ] 配置加载

#### 5.2 性能测试
```bash
# 测试守护进程
python3 test_daemon.py

# 测试 TTS 流式
python3 test_tts_stream.py

# 启动完整应用
./start.sh
```

### Phase 6: 清理工作（1 小时）

#### 6.1 删除旧代码
```bash
# 确认新版本工作正常后
git rm -rf web/
git rm -rf tauri-prototype/
git rm web_app.py
git rm floating_window.py
git rm tray_manager.py
```

#### 6.2 更新文档
- 更新 README.md
- 更新 QUICK_START_TTS.md
- 创建 MIGRATION_COMPLETE.md

#### 6.3 提交代码
```bash
git add .
git commit -m "feat: migrate tauri prototype to main project

- Move Rust backend from tauri-prototype/ to src-tauri/
- Move React frontend from tauri-prototype/src/ to src/
- Update build configuration
- Remove deprecated web/ directory
- Update documentation

Features:
- Daemon mode (18x faster response)
- Streaming responses (10x better UX)
- Streaming TTS (85% latency reduction)
"

git push origin feat/tauri-integration
```

## 🔍 关键文件映射

### Rust 后端
| 原型文件 | 主项目文件 | 说明 |
|---------|-----------|------|
| `tauri-prototype/src-tauri/src/lib.rs` | `src-tauri/src/lib.rs` | 主逻辑 |
| `tauri-prototype/src-tauri/src/main.rs` | `src-tauri/src/main.rs` | 入口 |
| `tauri-prototype/src-tauri/Cargo.toml` | `src-tauri/Cargo.toml` | 依赖 |
| `tauri-prototype/src-tauri/tauri.conf.json` | `src-tauri/tauri.conf.json` | 配置 |

### 前端代码
| 原型文件 | 主项目文件 | 说明 |
|---------|-----------|------|
| `tauri-prototype/src/App.tsx` | `src/App.tsx` | 主组件 |
| `tauri-prototype/src/useTauriAPI.ts` | `src/useTauriAPI.ts` | API Hook |
| `tauri-prototype/src/main.tsx` | `src/main.tsx` | 入口 |
| `tauri-prototype/index.html` | `index.html` | HTML |
| `tauri-prototype/vite.config.ts` | `vite.config.ts` | Vite 配置 |

### 配置文件
| 原型文件 | 主项目文件 | 说明 |
|---------|-----------|------|
| `tauri-prototype/package.json` | `package.json` | 合并依赖 |
| `tauri-prototype/tsconfig.json` | `tsconfig.json` | TS 配置 |

## ⚠️ 注意事项

### 1. 路径调整
- Python 守护进程路径：`../../worker_daemon.py` → `../worker_daemon.py`
- 前端资源路径：保持相对路径不变
- 构建输出路径：`dist` 目录位于项目根

### 2. 依赖冲突
- `web/` 和 `tauri-prototype/` 使用不同版本的 React
- 需要统一到 React 18
- Tauri 插件版本需要匹配

### 3. 配置文件
- `config.json` 保持在项目根目录
- Tauri 配置路径需要相对于 `src-tauri/`

### 4. 测试覆盖
- 守护进程测试脚本路径不变
- Tauri 应用测试需要完整启动

## 📊 预估时间

| 阶段 | 预估时间 | 说明 |
|------|---------|------|
| Phase 1: 准备 | 1 小时 | 备份、分析 |
| Phase 2: Rust 迁移 | 2 小时 | 复制、调整 |
| Phase 3: 前端迁移 | 2 小时 | 复制、配置 |
| Phase 4: 配置整理 | 1 小时 | 脚本、文档 |
| Phase 5: 测试验证 | 2 小时 | 功能、性能 |
| Phase 6: 清理工作 | 1 小时 | 删除、提交 |
| **总计** | **9 小时** | 一天完成 |

## ✅ 完成标准

- [ ] Tauri 应用正常启动
- [ ] 所有功能测试通过
- [ ] 性能测试达标
- [ ] 文档更新完成
- [ ] 旧代码清理完成
- [ ] Git 历史清晰
- [ ] CI/CD 配置更新（如果有）

## 🚀 开始迁移

准备好了吗？让我们开始吧！

```bash
# 1. 创建备份
git add .
git commit -m "chore: backup before migration"
git checkout -b feat/tauri-integration

# 2. 开始 Phase 1
# (参考上面的详细步骤)
```

---

**需要帮助？** 参考以下文档：
- [Tauri 官方文档](https://tauri.app/v1/guides/)
- [DAEMON_MODE.md](./DAEMON_MODE.md)
- [STREAMING_MODE.md](./STREAMING_MODE.md)
- [TTS_STREAMING_MODE.md](./TTS_STREAMING_MODE.md)
