# Speekium Tauri 构建快速入门指南

## 📦 新增文件

1. **src-python/backend_main.py** - PyTauri 后端入口点
2. **src-python/speerium-backend.spec** - PyInstaller spec 配置
3. **scripts/build_python.py** - 自动化 Python 编译脚本
4. **docs/2026-01-08-build-configuration.md** - 完整构建文档

## 🔧 更新文件

1. **src-tauri/tauri.conf.json** - 添加 `externalBin` 配置
2. **package.json** - 添加构建脚本
3. **src-tauri/capabilities/default.json** - 添加 shell 权限

## 🚀 快速开始

### 1. 安装依赖

```bash
# 安装 Node.js 依赖
npm install

# 安装 Python 依赖
pip install pyinstaller pydantic pytauri
```

### 2. 开发模式

```bash
npm run tauri:dev
```

这将启动：
- ✅ Vite 开发服务器（前端）
- ✅ Tauri 应用窗口
- ⚠️  Python 后端需要单独启动（或使用 Mock API）

### 3. 生产构建

```bash
# 一键构建（推荐）
npm run tauri:build

# 这将自动：
# 1. 编译 Python 后端为独立可执行文件
# 2. 构建前端
# 3. 打包 Tauri 应用
```

## 📁 构建输出

### macOS

```bash
# 输出目录
src-tauri/target/release/bundle/dmg/

# 文件名
Speerium_0.1.0_x64.dmg              # Intel
Speerium_0.1.0_aarch64.dmg           # Apple Silicon
Speerium_0.1.0_universal.dmg        # Universal
```

### Windows

```bash
# 输出目录
src-tauri/target/release/bundle/msi/

# 文件名
Speerium_0.1.0_x64_en-US.msi
```

### Linux

```bash
# 输出目录
src-tauri/target/release/bundle/appimage/

# 文件名
Speerium_0.1.0_amd64.AppImage
```

## 🔍 验证构建

### 检查 Python sidecar

```bash
# macOS/Linux
ls -la src-tauri/binaries/

# 应该看到：
# speekium-backend-x86_64-apple-darwin (Intel)
# speekium-backend-aarch64-apple-darwin (Apple Silicon)
```

### 测试 sidecar 运行

```bash
# macOS/Linux
./src-tauri/binaries/speekium-backend-x86_64-apple-darwin

# 应该看到：
# Starting Speekium Backend...
# Speekium Backend ready
```

### 测试 Tauri 应用

```bash
# 运行开发版本
npm run tauri:dev

# 测试功能：
# 1. 窗口是否正常打开
# 2. 前端 UI 是否加载
# 3. 控制台是否有错误
```

## 🐛 故障排除

### 问题：Python 导入错误

```
ImportError: No module named 'pytauri'
```

**解决**：
```bash
pip install pytauri
```

### 问题：PyInstaller 编译失败

```
ERROR: PyInstaller cannot find pytauri
```

**解决**：
```bash
# 在 spec 文件中添加 hiddenimports
# src-python/speerium-backend.spec
hiddenimports=["pytauri", "pydantic"]
```

### 问题：Binary not found during Tauri build

```
Error: Could not find binaries/speekium-backend
```

**解决**：
```bash
# 检查文件名是否正确（必须包含 target-triple）
ls -la src-tauri/binaries/

# 确保文件名如：
# speekium-backend-x86_64-apple-darwin
# speekium-backend-aarch64-apple-darwin
```

### 问题：Permission denied when running sidecar

```
Error: Permission denied (shell:allow-execute)
```

**解决**：
```bash
# 检查 capabilities/default.json
# 确保包含：
"shell:allow-execute",
"shell:allow-spawn"
```

## 📊 构建流程图

```
npm run tauri:build
        ↓
┌─────────────────────┐
│ build:python        │  ← 编译 Python 后端
│ (PyInstaller)       │
└─────────────────────┘
        ↓
    src-tauri/binaries/
    speekium-backend-<target>
        ↓
┌─────────────────────┐
│ build               │  ← 构建前端
│ (Vite)             │
└─────────────────────┘
        ↓
      dist/
        ↓
┌─────────────────────┐
│ tauri build         │  ← 打包应用
│ (Tauri CLI)        │
└─────────────────────┘
        ↓
  src-tauri/target/
  release/bundle/
```

## 🎯 下一步

1. **完善 Python 后端**
   - 实现真实的音频录制功能
   - 集成 LLM 后端（Claude/Ollama）
   - 集成 TTS 引擎

2. **完善前端集成**
   - 实现与 Python sidecar 的 IPC 通信
   - 添加录音、聊天、TTS 等功能
   - 实现状态管理

3. **系统功能**
   - 配置 Tauri 托盘插件
   - 配置全局快捷键
   - 实现悬浮窗功能

4. **测试和优化**
   - 测试所有功能
   - 优化启动速度
   - 减小应用体积

## 📚 详细文档

完整构建和配置文档：[docs/2026-01-08-build-configuration.md](./docs/2026-01-08-build-configuration.md)

## 🔗 相关资源

- [Tauri 官方文档](https://v2.tauri.app/)
- [PyInstaller 文档](https://pyinstaller.org/)
- [PyTauri 文档](https://pytauri.github.io/pytauri/)
- [Speerium 主项目](https://github.com/kanweiwei/speekium)

## ✅ 配置清单

- [x] 配置 `tauri.conf.json` 的 `externalBin`
- [x] 创建 PyInstaller spec 文件
- [x] 创建自动化构建脚本
- [x] 更新 `package.json` 构建脚本
- [x] 配置 `capabilities/default.json` 权限
- [x] 编写完整构建文档
- [x] 创建快速入门指南
- [ ] 实现 Python 后端完整功能
- [ ] 实现前端 IPC 通信
- [ ] 测试跨平台构建
- [ ] 优化应用性能和体积

---

**现在可以开始构建了！** 🎉

```bash
npm run tauri:build
```
