# Speekium Tauri 快速开始指南

## ✅ 架构重构完成

新架构：**React → Tauri Invoke → Rust → Python Worker**

## 🚀 启动应用

### 开发模式

```bash
cd tauri-prototype
npm run tauri dev
```

**就这么简单！** 不再需要单独启动 Python HTTP server。

### 生产构建

```bash
cd tauri-prototype
npm run tauri:build

# 构建产物:
# - src-tauri/target/release/bundle/macos/Speerium.app (11MB)
# - src-tauri/target/release/bundle/dmg/*.dmg
```

## 🎤 使用功能

### 录音对话

1. 点击 🎤 录音按钮
2. **立即开始说话**（3 秒内）
3. 等待识别结果
4. LLM 自动回复

**录音模式**：
- **按键录音**（推荐）：点击后立即录音 3 秒
- **自动检测**：VAD 检测到语音后开始录音

### 全局快捷键

- **Command+Shift+Space**（macOS）：显示/隐藏窗口
- 左键点击托盘图标：显示/隐藏窗口

### 系统托盘

右键托盘图标显示菜单：
- 显示窗口
- 隐藏窗口
- 退出

## 🔧 技术架构

### 通信流程

```
用户操作 → React (invoke) → Rust (spawn) → Python worker.py → 返回结果
```

### 核心文件

| 文件 | 作用 |
|------|------|
| `worker.py` | Python Worker，处理录音/LLM/TTS |
| `src-tauri/src/lib.rs` | Rust 后端，Tauri 命令 |
| `src/useTauriAPI.ts` | 前端 API，使用 invoke |
| `src/App.tsx` | React 主界面 |

## 🧪 测试

### 测试 Python Worker

```bash
# 配置
python3 worker.py config

# LLM 对话
python3 worker.py chat '{"text":"你好"}'

# TTS 生成
python3 worker.py tts '{"text":"测试"}'
```

### 测试录音

在 Tauri 窗口中：
1. 确保麦克风权限已授予
2. 点击录音按钮
3. 立即说话
4. 观察识别结果

## 📊 对比旧架构

| 项目 | 旧架构（HTTP） | 新架构（Invoke） |
|------|---------------|-----------------|
| 启动 | 2步（Python + Tauri） | 1步（Tauri） |
| 通信 | HTTP fetch | Tauri invoke |
| 延迟 | 10-20ms | <1ms |
| 端口管理 | 需要（8008） | 不需要 |
| CORS | 需要处理 | 不需要 |
| 界面响应 | 阻塞 3 秒 | 非阻塞 |

## ⚠️ 注意事项

1. **Python 依赖**：
   ```bash
   cd /Users/kww/work/opensource/speekium
   uv sync
   ```

2. **麦克风权限**：
   - 系统设置 → 隐私与安全性 → 麦克风
   - 勾选 Terminal/iTerm/Python

3. **Ollama 服务**：
   ```bash
   # 确保 Ollama 正在运行
   ollama serve

   # 确保模型已下载
   ollama pull qwen2.5:1.5b
   ```

## 🐛 问题排查

### 录音没反应

```bash
# 检查麦克风权限
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

### LLM 400 错误

```bash
# 检查 Ollama 服务
curl http://localhost:11434/api/tags

# 检查模型
ollama list
```

### Tauri 编译失败

```bash
# 确保 Node.js 版本正确
nvm use 22.21.1

# 清理重建
cd tauri-prototype
rm -rf node_modules dist
npm install
```

## 📝 更新日志

**2026-01-09**
- ✅ 重构为正确的 Tauri 架构
- ✅ 删除 HTTP server 依赖
- ✅ 解决界面闪烁问题
- ✅ 提升响应速度

---

**快速链接**：
- 详细文档：`REFACTOR_COMPLETE.md`
- 问题分析：`ARCHITECTURE_FIX.md`
- 最终状态：`FINAL_STATUS.md`
