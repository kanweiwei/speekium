# 🚀 Tauri 迁移快速参考

## ⚡ 快速开始（5 分钟版本）

```bash
# 1. 创建备份分支
git checkout -b feat/tauri-integration

# 2. 创建目录
mkdir -p src-tauri/src src-tauri/icons src

# 3. 复制文件（一键执行）
cp tauri-prototype/src-tauri/Cargo.toml src-tauri/
cp tauri-prototype/src-tauri/src/*.rs src-tauri/src/
cp -r tauri-prototype/src-tauri/icons/* src-tauri/icons/
cp tauri-prototype/src-tauri/tauri.conf.json src-tauri/
cp -r tauri-prototype/src/* src/
cp tauri-prototype/*.html tauri-prototype/*.ts tauri-prototype/*.json ./

# 4. 修改 src-tauri/src/lib.rs 路径
sed -i '' 's|../../worker_daemon.py|../worker_daemon.py|g' src-tauri/src/lib.rs

# 5. 创建 package.json（复制下面内容）
# 6. 安装依赖
npm install

# 7. 测试
./start.sh  # 或 npm run tauri:dev
```

## 📋 关键文件清单

### 必须复制
- ✅ `src-tauri/src/lib.rs` - 主逻辑
- ✅ `src-tauri/src/main.rs` - 入口
- ✅ `src-tauri/Cargo.toml` - Rust 依赖
- ✅ `src-tauri/tauri.conf.json` - Tauri 配置
- ✅ `src/App.tsx` - React 主组件
- ✅ `src/useTauriAPI.ts` - API Hook
- ✅ `src/main.tsx` - 前端入口
- ✅ `index.html` - HTML 模板
- ✅ `vite.config.ts` - Vite 配置
- ✅ `package.json` - Node 依赖

### 必须修改
- ⚠️ `src-tauri/src/lib.rs` - 修改 Python 路径
- ⚠️ `src-tauri/tauri.conf.json` - 检查构建路径
- ⚠️ `package.json` - 创建新的（合并依赖）

## 🎯 package.json 模板

```json
{
  "name": "speekium",
  "version": "0.2.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
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

## 🧪 测试命令

```bash
# 1. 测试守护进程
source .venv/bin/activate
python3 test_daemon.py

# 2. 测试 TTS 流式
python3 test_tts_stream.py

# 3. 启动完整应用
./start.sh

# 4. 手动启动
npm run tauri:dev
```

## 🔧 故障排查速查

| 问题 | 解决方案 |
|------|---------|
| npm install 失败 | `rm -rf node_modules package-lock.json && npm install` |
| Rust 编译失败 | `cd src-tauri && cargo clean && cargo build` |
| 守护进程未连接 | 检查 lib.rs 中路径是否为 `../worker_daemon.py` |
| 端口被占用 | 修改 vite.config.ts 中的端口号 |
| 虚拟环境问题 | `source .venv/bin/activate` |

## 📁 目录结构对比

### 迁移前
```
speekium/
├── web/              # 旧 Web UI
├── tauri-prototype/  # 原型
└── *.py              # Python 代码
```

### 迁移后
```
speekium/
├── src/              # React 前端
├── src-tauri/        # Rust 后端
├── dist/             # 构建输出
└── *.py              # Python 代码（保持不变）
```

## ⚠️ 关键注意事项

1. **路径修改**：`../../worker_daemon.py` → `../worker_daemon.py`
2. **依赖版本**：React 18, Tauri 2.x
3. **虚拟环境**：必须激活才能运行
4. **端口冲突**：默认 5173，可修改
5. **Git 分支**：建议在新分支操作

## 🎉 完成标准

- [ ] `npm run tauri:dev` 正常启动
- [ ] 守护进程健康检查通过
- [ ] 流式响应正常显示
- [ ] TTS 播放正常
- [ ] 全局快捷键工作
- [ ] 系统托盘显示

## 📚 详细文档

- **完整指南**：[MIGRATION_GUIDE_STEP_BY_STEP.md](./MIGRATION_GUIDE_STEP_BY_STEP.md)
- **迁移计划**：[MIGRATION_PLAN.md](./MIGRATION_PLAN.md)
- **功能文档**：[FEATURES_COMPLETE.md](./FEATURES_COMPLETE.md)

---

**准备好了吗？** 复制上面的命令开始执行！ 🚀
