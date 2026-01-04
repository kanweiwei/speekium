<p align="center">
  <img src="./logo.svg" width="120" height="120" alt="Speekium Logo">
</p>

<h1 align="center">Speekium</h1>

<p align="center">
  <strong>A smart voice assistant with pluggable LLM backends</strong>
</p>

<p align="center">
  <a href="./README_CN.md">中文文档</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#roadmap">Roadmap</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/github/license/kanweiwei/speekium" alt="License">
  <img src="https://img.shields.io/github/stars/kanweiwei/speekium?style=social" alt="Stars">
</p>

---

## ✨ Features

- 🎙️ **Voice Activity Detection** — Auto-detects speech start/end using Silero VAD, no button press needed
- 🗣️ **High-Accuracy ASR** — Powered by Alibaba's SenseVoice, supports Chinese, English, and more
- ⚡ **Streaming TTS** — Speaks while generating for faster, more natural responses
- 🔌 **Pluggable LLM** — Swap backends easily (Claude, Ollama, OpenAI...)
- 🖥️ **Cross-Platform** — Works on macOS, Linux, and Windows

## 🔄 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   🎤 Microphone ──▶ 🔍 VAD ──▶ 📝 ASR ──▶ 🤖 LLM           │
│                      (Silero)    (SenseVoice)  (Pluggable)  │
│                                                    │        │
│                                                    ▼        │
│   🎧 Speaker ◀── 🔊 Player ◀── 🗣️ TTS ◀─────────┘         │
│                                 (Edge TTS)                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code) (or other LLM backend)
- Microphone

### Quick Start

```bash
# Clone
git clone https://github.com/kanweiwei/speekium.git
cd speekium

# Setup with uv (recommended)
uv sync

# Run
uv run python speekium.py
```

<details>
<summary>Alternative: pip install</summary>

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
python speekium.py
```
</details>

### Linux Dependencies

```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```

## 🚀 Usage

```bash
python speekium.py
```

Just speak into your microphone. The assistant will:
1. Detect when you start speaking
2. Recognize your speech
3. Get a response from the LLM
4. Speak the response back to you

## ⚙️ Configuration

Edit the top of `speekium.py`:

```python
# ASR
ASR_MODEL = "iic/SenseVoiceSmall"

# TTS
TTS_VOICE = "zh-CN-XiaoyiNeural"  # or: en-US-JennyNeural, etc.
TTS_RATE = "-15%"

# Streaming (speak while generating)
USE_STREAMING = True

# VAD
VAD_THRESHOLD = 0.5
SILENCE_AFTER_SPEECH = 1.5  # seconds
MAX_RECORDING_DURATION = 30  # seconds
```

List available TTS voices:
```bash
python tts_test.py --list
```

## 🔌 Supported LLM Backends

| Backend | Status |
|---------|--------|
| [Claude Code CLI](https://github.com/anthropics/claude-code) | ✅ Supported |
| [Ollama](https://ollama.ai) | 🚧 Planned |
| OpenAI API | 🚧 Planned |
| Local LLMs | 🚧 Planned |

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Voice Activity Detection | [Silero VAD](https://github.com/snakers4/silero-vad) |
| Speech Recognition | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) |
| Text-to-Speech | [Edge TTS](https://github.com/rany2/edge-tts) |
| Audio Processing | sounddevice, scipy, numpy |

## 🗺️ Roadmap

- [x] VAD-based voice detection
- [x] SenseVoice ASR integration
- [x] Streaming TTS output
- [x] Claude Code CLI backend
- [ ] Ollama backend support
- [ ] OpenAI API backend
- [ ] Wake word detection
- [ ] Multi-turn conversation context
- [ ] Web UI

## 🤝 Contributing

Contributions are welcome! Feel free to:

- 🐛 Report bugs
- 💡 Suggest features
- 🔧 Submit pull requests

## 📄 License

[MIT](./LICENSE) © 2025 [kanweiwei](https://github.com/kanweiwei)

---

<p align="center">
  If you find this project helpful, please consider giving it a ⭐
</p>
