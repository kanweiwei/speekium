# Tauri Build Configuration for Speekium

本文档描述了如何配置和构建带有 Python 后端的 Tauri 应用程序。

## 架构概述

Speerium 使用 **PyInstaller + Tauri Sidecar** 架构：

```
┌─────────────────────────────────────────────────────────┐
│                 Tauri Application                    │
│  ┌─────────────────────────────────────────────────┐  │
│  │   Rust + Webview (Frontend)                  │  │
│  │   - React UI                                 │  │
│  │   - System Integration (Tray, Shortcuts)      │  │
│  └─────────────────────────────────────────────────┘  │
│                      ↓ IPC                         │
│  ┌─────────────────────────────────────────────────┐  │
│  │   Python Sidecar (backend_main.py)            │  │
│  │   - Audio Recorder (VAD/ASR)                │  │
│  │   - LLM Backend (Claude/Ollama)             │  │
│  │   - TTS Engine (Edge/Piper)                  │  │
│  └─────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 构建流程

### 1. 开发模式

```bash
# 启动 Tauri 开发服务器
npm run tauri:dev

# 这将启动：
# - Vite 开发服务器 (localhost:1420)
# - Tauri 应用窗口
# - Rust 后端（无编译）
```

### 2. 生产构建

```bash
# 完整构建流程
npm run tauri:build

# 等同于：
npm run build:python  # 编译 Python 后端
npm run build        # 构建前端
tauri build         # 打包 Tauri 应用
```

### 3. 分步构建

```bash
# 步骤 1: 编译 Python 后端
npm run build:python

# 输出: src-tauri/binaries/speekium-backend-<target-triple>

# 步骤 2: 构建前端
npm run build

# 输出: dist/

# 步骤 3: 打包 Tauri 应用
npm run tauri build

# 输出: src-tauri/target/release/bundle/
```

## 文件结构

```
tauri-prototype/
├── src/                      # React 前端
│   ├── App.tsx
│   ├── useTauriAPI.ts
│   └── main.tsx
├── src-tauri/
│   ├── Cargo.toml            # Rust 依赖
│   ├── tauri.conf.json       # Tauri 配置
│   ├── capabilities/         # 权限配置
│   │   └── default.json
│   └── binaries/           # 编译后的 Python sidecars
│       └── speekium-backend-<target-triple>
├── src-python/              # Python 后端模块
│   ├── backend_main.py      # PyTauri 入口点
│   ├── audio_recorder.py
│   ├── llm_backend.py
│   ├── tts_engine.py
│   └── speekium-backend.spec
├── scripts/
│   └── build_python.py     # PyInstaller 构建脚本
└── package.json            # Node.js 配置
```

## 配置详解

### tauri.conf.json

```json
{
  "bundle": {
    "externalBin": [
      "../binaries/speekium-backend"
    ]
  }
}
```

**关键配置项**：
- `externalBin`: 指定 Python sidecar 二进制文件路径
- 路径相对于 `src-tauri/tauri.conf.json`
- Tauri 会自动追加 target-triple（如 `x86_64-apple-darwin`）

### package.json

```json
{
  "scripts": {
    "build:python": "python scripts/build_python.py",
    "tauri:build": "npm run build:python && tauri build"
  }
}
```

**构建脚本**：
- `build:python`: 编译 Python 后端为独立可执行文件
- `tauri:build`: 完整构建（Python + 前端 + Tauri）

### capabilities/default.json

```json
{
  "permissions": [
    "shell:allow-execute",
    "shell:allow-spawn",
    {
      "identifier": "shell:allow-execute",
      "allow": [
        {
          "name": "binaries/speekium-backend",
          "sidecar": true
        }
      ]
    }
  ]
}
```

**权限说明**：
- `shell:allow-execute`: 允许执行 sidecar
- `shell:allow-spawn`: 允许创建 sidecar 进程
- `sidecar: true`: 标记为 Tauri sidecar（自动处理路径）

## Python 后端构建 (PyInstaller)

### build_python.py 脚本

```python
def get_target_triple():
    """获取 Rust target triple"""
    # 例如: x86_64-apple-darwin, aarch64-apple-darwin
    subprocess.run(["rustc", "-Vv"], ...)

def build_python_backend():
    """编译 Python 为独立可执行文件"""
    pyinstaller --onefile \
        --name speekium-backend-<target-triple> \
        --distpath src-tauri/binaries \
        --clean \
        src-python/backend_main.py
```

**关键参数**：
- `--onefile`: 打包为单个可执行文件
- `--name`: 带有 target-triple 的文件名
- `--distpath`: 输出到 `src-tauri/binaries/`
- `--clean`: 清理旧的构建文件

### PyInstaller Spec 文件

**文件**: `src-python/speerium-backend.spec`

```python
a = Analysis(
    ['src-python/backend_main.py'],
    hiddenimports=[
        "pytauri",
        "pydantic",
        "sounddevice",
        "numpy",
        "torch",
        "scipy",
        "edge_tts",
        "httpx",
        "funasr",
    ],
    ...
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='speekium-backend',
    console=True,  # 保持控制台用于调试
    upx=True,     # 压缩减小体积
)
```

**重要配置**：
- `hiddenimports`: 显式导入 PyTauri 和其他依赖
- `console=True`: 保留控制台输出（调试用）
- `upx=True`: 启用压缩减小可执行文件大小

## 跨平台构建

### macOS

```bash
# 构建 Python sidecar
npm run build:python

# 输出: src-tauri/binaries/speekium-backend-aarch64-apple-darwin (Apple Silicon)
#       src-tauri/binaries/speerium-backend-x86_64-apple-darwin (Intel)

# 构建 Tauri 应用
npm run tauri build -- --target universal-apple-darwin

# 输出: src-tauri/target/release/bundle/dmg/Speerium_<version>_universal.dmg
```

### Windows

```bash
# 构建 Python sidecar
npm run build:python:windows

# 输出: src-tauri/binaries/speerium-backend-x86_64-pc-windows-msvc.exe

# 构建 Tauri 应用
npm run tauri build -- --target x86_64-pc-windows-msvc

# 输出: src-tauri/target/release/bundle/msi/Speerium_<version>_x64_en-US.msi
```

### Linux

```bash
# 构建 Python sidecar
npm run build:python:linux

# 输出: src-tauri/binaries/speerium-backend-x86_64-unknown-linux-gnu

# 构建 Tauri 应用
npm run tauri build

# 输出: src-tauri/target/release/bundle/appimage/Speekium_<version>_amd64.AppImage
```

## 目标平台 (Target Triples)

| 平台 | Target Triple | 示例 |
|-------|--------------|--------|
| macOS (Intel) | `x86_64-apple-darwin` | `speekium-backend-x86_64-apple-darwin` |
| macOS (Apple Silicon) | `aarch64-apple-darwin` | `speekium-backend-aarch64-apple-darwin` |
| Windows (x64) | `x86_64-pc-windows-msvc` | `speerium-backend-x86_64-pc-windows-msvc.exe` |
| Linux (x64) | `x86_64-unknown-linux-gnu` | `speerium-backend-x86_64-unknown-linux-gnu` |

**获取当前平台的 target triple**:
```bash
rustc -Vv | grep host
```

## 调试和故障排除

### 检查 Python sidecar 是否存在

```bash
# macOS/Linux
ls -la src-tauri/binaries/

# Windows
dir src-tauri\binaries\
```

### 测试 Python sidecar 直接运行

```bash
# macOS/Linux
./src-tauri/binaries/speekium-backend-x86_64-apple-darwin

# Windows
src-tauri\binaries\speekium-backend-x86_64-pc-windows-msvc.exe
```

### 检查 Tauri 构建日志

```bash
# 查看详细构建输出
npm run tauri build -- --verbose
```

### 常见问题

**问题 1**: "Binary not found during build"
- **原因**: 二进制文件命名不符合 target-triple 规范
- **解决**: 确保文件名包含正确的 target-triple

**问题 2**: "Permission denied when running sidecar"
- **原因**: 缺少 shell 权限
- **解决**: 检查 `capabilities/default.json` 包含 `shell:allow-execute` 和 `shell:allow-spawn`

**问题 3**: PyInstaller 编译失败
- **原因**: 缺少依赖或 hidden-imports
- **解决**: 检查 `src-python/speerium-backend.spec` 的 hiddenimports 配置

**问题 4**: 应用体积过大
- **原因**: PyInstaller 包含了完整的 Python 运行时
- **解决**:
  - 使用 `--onefile` 选项
  - 启用 `upx=True` 压缩
  - 在 spec 文件中排除不需要的模块

## 生产部署

### macOS

```bash
# 构建 Universal DMG
npm run tauri build -- --target universal-apple-darwin

# 输出文件位置
open src-tauri/target/release/bundle/dmg/
```

### Windows

```bash
# 构建 MSI 安装包
npm run tauri build -- --target x86_64-pc-windows-msvc

# 输出文件位置
explorer src-tauri\target\release\bundle\msi\
```

### Linux

```bash
# 构建 AppImage
npm run tauri build

# 输出文件位置
ls -lh src-tauri/target/release/bundle/appimage/
```

## 性能优化

### 减小应用体积

1. **使用 PyInstaller spec 文件**（而非命令行）
   - 控制包含的模块
   - 排除未使用的依赖

2. **启用 UPX 压缩**
   ```python
   exe = EXE(..., upx=True)
   ```

3. **排除不必要的模块**
   ```python
   excludes=['matplotlib', 'scipy', 'pandas', 'tkinter']
   ```

### 加速构建

1. **使用缓存**
   - PyInstaller 会缓存分析结果
   - 重复构建时更快

2. **并行构建**
   - Tauri 默认并行编译 Rust 代码
   - 可通过 `--jobs N` 控制线程数

## 参考资源

- [Tauri 官方文档 - Sidecar](https://v2.tauri.app/develop/sidecar/)
- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
- [PyTauri 文档](https://pytauri.github.io/pytauri/)
- [示例项目 - Tauri Python Sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar)

## 总结

本配置提供了：

✅ **自动化构建流程**: 一键构建 Python + 前端 + Tauri
✅ **跨平台支持**: macOS、Windows、Linux
✅ **权限管理**: 完整的 capabilities 配置
✅ **调试友好**: 控制台输出和详细日志
✅ **生产就绪**: 优化的打包和部署流程

**下一步**: 运行 `npm run tauri:build` 构建您的第一个生产版本！
