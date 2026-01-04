<p align="center">
  <img src="./logo.svg" width="120" height="120" alt="Speekium Logo">
</p>

<h1 align="center">Speekium</h1>

<p align="center">
  <strong>支持多种 LLM 后端的智能语音助手</strong>
</p>

<p align="center">
  <a href="./README.md">English</a> •
  <a href="#安装">安装</a> •
  <a href="#使用">使用</a> •
  <a href="#路线图">路线图</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/github/license/kanweiwei/speekium" alt="License">
  <img src="https://img.shields.io/github/stars/kanweiwei/speekium?style=social" alt="Stars">
</p>

---

## ✨ 特性

- 🎙️ **语音活动检测** — 使用 Silero VAD 自动检测语音起止，无需按键
- 🗣️ **高精度语音识别** — 基于阿里 SenseVoice，支持中文、英文等多语言
- ⚡ **流式语音合成** — 边生成边朗读，响应更快更自然
- 🔌 **可插拔 LLM** — 轻松切换后端（Claude、Ollama、OpenAI...）
- 🖥️ **跨平台** — 支持 macOS、Linux、Windows

## 🔄 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🎤 麦克风 ──▶ 🔍 VAD ──▶ 📝 ASR ──▶ 🤖 LLM               │
│                 (Silero)   (SenseVoice)  (可插拔)           │
│                                            │                │
│                                            ▼                │
│   🎧 扬声器 ◀── 🔊 播放器 ◀── 🗣️ TTS ◀──┘                 │
│                              (Edge TTS)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📦 安装

### 前置要求

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code)（或其他 LLM 后端）
- 麦克风

### 快速开始

```bash
# 克隆
git clone https://github.com/kanweiwei/speekium.git
cd speekium

# 使用 uv 安装（推荐）
uv sync

# 运行
uv run python speekium.py
```

<details>
<summary>备选：pip 安装</summary>

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
python speekium.py
```
</details>

### Linux 额外依赖

```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```

## 🚀 使用

```bash
python speekium.py
```

启动后直接对着麦克风说话即可：
1. 自动检测语音开始
2. 识别语音内容
3. 获取 LLM 回复
4. 朗读回复内容

## ⚙️ 配置

编辑 `speekium.py` 顶部配置：

```python
# 语音识别
ASR_MODEL = "iic/SenseVoiceSmall"

# 语音合成
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 可选: zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural
TTS_RATE = "-15%"

# 流式输出（边生成边朗读）
USE_STREAMING = True

# VAD 参数
VAD_THRESHOLD = 0.5
SILENCE_AFTER_SPEECH = 1.5  # 秒
MAX_RECORDING_DURATION = 30  # 秒
```

查看可用语音：
```bash
python tts_test.py --list
```

### 推荐中文语音

| 语音 | 说明 |
|------|------|
| `zh-CN-XiaoyiNeural` | 小艺（女声，活泼） |
| `zh-CN-XiaoxiaoNeural` | 晓晓（女声，温柔） |
| `zh-CN-YunxiNeural` | 云希（男声） |
| `zh-CN-YunjianNeural` | 云健（男声，播音风格） |

## 🔌 支持的 LLM 后端

| 后端 | 状态 |
|------|------|
| [Claude Code CLI](https://github.com/anthropics/claude-code) | ✅ 已支持 |
| [Ollama](https://ollama.ai) | 🚧 计划中 |
| OpenAI API | 🚧 计划中 |
| 本地模型 | 🚧 计划中 |

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| 语音活动检测 | [Silero VAD](https://github.com/snakers4/silero-vad) |
| 语音识别 | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) |
| 语音合成 | [Edge TTS](https://github.com/rany2/edge-tts) |
| 音频处理 | sounddevice, scipy, numpy |

## 🗺️ 路线图

- [x] 基于 VAD 的语音检测
- [x] SenseVoice 语音识别
- [x] 流式 TTS 输出
- [x] Claude Code CLI 后端
- [ ] Ollama 后端支持
- [ ] OpenAI API 后端
- [ ] 唤醒词检测
- [ ] 多轮对话上下文
- [ ] Web 界面

## 🤝 贡献

欢迎贡献！你可以：

- 🐛 报告 Bug
- 💡 提出建议
- 🔧 提交 PR

## 📄 许可证

[MIT](./LICENSE) © 2025 [kanweiwei](https://github.com/kanweiwei)

---

<p align="center">
  如果觉得有帮助，请给个 ⭐ 支持一下
</p>
