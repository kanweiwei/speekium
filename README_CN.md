<p align="center">
  <img src="./logo.svg" width="120" height="120" alt="Speekium Logo">
</p>

<h1 align="center">Speekium</h1>

<p align="center">
  <strong>用语音和 AI 对话。本地运行。隐私保护。开源免费。</strong>
</p>

<p align="center">
  <a href="./README.md">English</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#为什么选择-speekium">为什么选择</a> •
  <a href="#路线图">路线图</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/github/license/kanweiwei/speekium" alt="License">
  <img src="https://img.shields.io/github/stars/kanweiwei/speekium?style=social" alt="Stars">
</p>

---

## 为什么选择 Speekium？

| 特性 | Speekium | Siri/小爱 | ChatGPT 语音 |
|------|----------|-----------|--------------|
| 本地运行 | ✅ | ❌ | ❌ |
| 数据隐私保护 | ✅ | ❌ | ❌ |
| 自选 LLM 模型 | ✅ | ❌ | ❌ |
| 开源免费 | ✅ | ❌ | ❌ |
| 无需唤醒词 | ✅ | ❌ | ✅ |
| 离线使用 (Ollama) | ✅ | ❌ | ❌ |

**Speekium** 是一个尊重隐私的语音助手。所有语音处理都在本地完成。你可以自由选择使用 Claude、Ollama 或其他 LLM。

## 快速开始

**1. 安装 uv（Python 包管理器）：**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. 运行 Speekium：**

```bash
git clone https://github.com/kanweiwei/speekium.git
cd speekium
uv sync
uv run python speekium.py
```

就这么简单，开始说话吧。

> **注意**：需要 Python 3.10+。首次运行会下载约 1GB 的模型。

<details>
<summary>📦 其他安装方式</summary>

**使用 pip：**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
python speekium.py
```

**Linux 依赖：**
```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```
</details>

## 工作原理

```
🎤 你说话
    ↓
🔍 VAD 检测语音 (Silero)
    ↓
📝 语音 → 文字 (SenseVoice)
    ↓
🤖 LLM 生成回复 (Claude/Ollama/...)
    ↓
🔊 文字 → 语音 (Edge TTS)
    ↓
🎧 你听到回复
```

**核心特性：**
- **自动语音检测** — 无需按键，无需唤醒词
- **流式响应** — 边生成边朗读，更快更自然
- **可插拔 LLM** — Claude API、本地 Ollama，或自己扩展
- **多语言支持** — 中文、英文等

## LLM 后端

### Claude（默认）

需要安装 [Claude Code CLI](https://github.com/anthropics/claude-code)：
```bash
npm install -g @anthropic-ai/claude-code
```

### Ollama（本地 & 隐私）

完全离线运行 AI：

```bash
# 安装 Ollama
brew install ollama  # macOS
ollama pull qwen2.5:7b

# 配置 Speekium
# 编辑 speekium.py：
LLM_BACKEND = "ollama"
OLLAMA_MODEL = "qwen2.5:7b"
```

| 后端 | 状态 |
|------|------|
| Claude Code CLI | ✅ 已支持 |
| Ollama | ✅ 已支持 |
| OpenAI API | 🚧 计划中 |

## 配置

编辑 `speekium.py`：

```python
# LLM 后端
LLM_BACKEND = "claude"  # 或 "ollama"

# TTS 后端
TTS_BACKEND = "edge"  # "edge"（在线，高质量）或 "piper"（离线，快速）

# 语音检测灵敏度
VAD_THRESHOLD = 0.5  # 越低越敏感
```

### TTS 选项

| 后端 | 质量 | 速度 | 离线 | 适用场景 |
|------|------|------|------|----------|
| Edge TTS | 高 | 中等 | ❌ | 日常使用 |
| Piper | 中等 | 快 | ✅ | 离线 / 树莓派 |

<details>
<summary>🔊 使用 Piper TTS（离线）</summary>

**1. 安装 piper-tts：**
```bash
pip install piper-tts
```

**2. 下载语音模型：**
```bash
# 创建模型目录
mkdir -p ~/.local/share/piper-voices

# 下载中文语音（从 Hugging Face）
# https://huggingface.co/rhasspy/piper-voices/tree/main/zh/zh_CN/huayan/medium
# 下载：zh_CN-huayan-medium.onnx 和 zh_CN-huayan-medium.onnx.json

# 下载英文语音
# https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/amy/medium
# 下载：en_US-amy-medium.onnx 和 en_US-amy-medium.onnx.json
```

**3. 配置：**
```python
TTS_BACKEND = "piper"
```
</details>

<details>
<summary>🗣️ Edge TTS 推荐语音</summary>

| 语音 | 说明 |
|------|------|
| `zh-CN-XiaoyiNeural` | 小艺（女声，活泼） |
| `zh-CN-XiaoxiaoNeural` | 晓晓（女声，温柔） |
| `zh-CN-YunxiNeural` | 云希（男声） |
| `zh-CN-YunjianNeural` | 云健（男声，播音风格） |

查看所有语音：`edge-tts --list-voices`
</details>

## 技术栈

| 组件 | 技术 |
|------|------|
| 语音活动检测 | [Silero VAD](https://github.com/snakers4/silero-vad) |
| 语音识别 | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) |
| 语音合成 | [Edge TTS](https://github.com/rany2/edge-tts)（在线）/ [Piper](https://github.com/rhasspy/piper)（离线） |
| 音频处理 | sounddevice, scipy, numpy |

## 路线图

- [x] 基于 VAD 的语音检测
- [x] SenseVoice 语音识别
- [x] 流式 TTS 输出
- [x] Claude 后端
- [x] Ollama 后端
- [x] 对话记忆
- [x] 多语言自动识别
- [ ] OpenAI API 后端
- [ ] 唤醒词检测
- [ ] Web 界面

## 常见问题

<details>
<summary><b>llvmlite 编译失败</b></summary>

```bash
# macOS
brew install llvm

# Ubuntu/Debian
sudo apt install llvm-dev

# 或使用 Python 3.10
uv sync --python 3.10
```
</details>

<details>
<summary><b>检测不到麦克风</b></summary>

- 检查麦克风权限
- 降低 `VAD_THRESHOLD`（如 0.3）
</details>

<details>
<summary><b>找不到 Claude CLI</b></summary>

```bash
npm install -g @anthropic-ai/claude-code
```
</details>

## 贡献

欢迎贡献！

- 🐛 [报告 Bug](https://github.com/kanweiwei/speekium/issues)
- 💡 [提出建议](https://github.com/kanweiwei/speekium/issues)
- 🔧 提交 PR

## 许可证

[MIT](./LICENSE) © 2025 [kanweiwei](https://github.com/kanweiwei)

---

<p align="center">
  <strong>如果觉得有帮助，请给个 ⭐ 支持一下</strong>
</p>
