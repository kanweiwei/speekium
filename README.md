<p align="center">
  <img src="./logo.svg" width="120" height="120" alt="Speekium Logo">
</p>

<h1 align="center">Speekium</h1>

<p align="center">
  <strong>Talk to AI with your voice. Locally. Privately. Open Source.</strong>
</p>

<p align="center">
  <a href="./README_CN.md">中文文档</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#why-speekium">Why Speekium</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="./docs/ci_cd_security.md">Security</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/github/license/kanweiwei/speekium" alt="License">
  <img src="https://img.shields.io/badge/security-0%20vulnerabilities-brightgreen.svg" alt="Security">
  <img src="https://img.shields.io/github/stars/kanweiwei/speekium?style=social" alt="Stars">
</p>

---

> **🎉 NEW: Tauri Desktop App with Advanced Features!**
>
> A modern desktop application with **daemon mode**, **streaming responses**, and **real-time TTS**.
>
> **⚡ One-Click Start**: `./start-tauri.sh` (Recommended!)
>
> Or manual: `cd tauri-prototype && npm run tauri dev`
>
> ### 🚀 Performance Highlights
> - **18x faster** response time (3.5s → 0.2s after first call)
> - **10x better perceived speed** (first character in 0.5s vs 5s)
> - **Edge-to-edge streaming** (LLM + TTS generation while playing)
>
> 📖 **Quick Start**: [QUICK_START_TTS.md](./QUICK_START_TTS.md)
>
> 📚 **Technical Docs**: [DAEMON_MODE.md](./DAEMON_MODE.md) | [STREAMING_MODE.md](./STREAMING_MODE.md) | [TTS_STREAMING_MODE.md](./TTS_STREAMING_MODE.md)

---

## Why Speekium?

| Feature | Speekium | Siri/Alexa | ChatGPT Voice |
|---------|----------|------------|---------------|
| Runs locally | ✅ | ❌ | ❌ |
| Your data stays private | ✅ | ❌ | ❌ |
| Choose your own LLM | ✅ | ❌ | ❌ |
| Open source | ✅ | ❌ | ❌ |
| No wake word needed | ✅ | ❌ | ✅ |
| Works offline (with Ollama) | ✅ | ❌ | ❌ |

**Speekium** is a voice assistant that respects your privacy. All speech processing happens on your machine. You choose which LLM to use — Claude, Ollama, or bring your own.

## Quick Start

**1. Install uv (Python package manager):**

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**2. Run Speekium:**

```bash
git clone https://github.com/kanweiwei/speekium.git
cd speekium
uv sync
uv run python speekium.py
```

That's it. Start talking.

> **Note**: Requires Python 3.10+. First run downloads ~1GB of models.

<details>
<summary>📦 Alternative installation methods</summary>

**Using pip:**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
python speekium.py
```

**Linux dependencies:**
```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```
</details>

## How It Works

```
🎤 You speak
    ↓
🔍 VAD detects voice (Silero)
    ↓
📝 Speech → Text (SenseVoice)
    ↓
🤖 LLM generates response (Claude/Ollama/...)
    ↓
🔊 Text → Speech (Edge TTS)
    ↓
🎧 You hear the response
```

**Key features:**
- **Auto voice detection** — No button press, no wake word
- **Streaming response** — Starts speaking while still generating
- **Pluggable LLM** — Use Claude API, local Ollama, or add your own
- **Multi-language** — Chinese, English, and more

## LLM Backends

### Claude (Default)

Requires [Claude Code CLI](https://github.com/anthropics/claude-code):
```bash
npm install -g @anthropic-ai/claude-code
```

### Ollama (Local & Private)

Run AI completely offline:

```bash
# Install Ollama
brew install ollama  # macOS
ollama pull qwen2.5:7b

# Configure Speekium
# Edit speekium.py:
LLM_BACKEND = "ollama"
OLLAMA_MODEL = "qwen2.5:7b"
```

| Backend | Status |
|---------|--------|
| Claude Code CLI | ✅ Supported |
| Ollama | ✅ Supported |
| OpenAI API | 🚧 Planned |

## Configuration

Edit `speekium.py`:

```python
# LLM Backend
LLM_BACKEND = "claude"  # or "ollama"

# TTS Backend
TTS_BACKEND = "edge"  # "edge" (online, high quality) or "piper" (offline, fast)

# Voice detection sensitivity
VAD_THRESHOLD = 0.5  # Lower = more sensitive
```

### TTS Options

| Backend | Quality | Speed | Offline | Best For |
|---------|---------|-------|---------|----------|
| Edge TTS | High | Medium | ❌ | Normal use |
| Piper | Medium | Fast | ✅ | Offline / Raspberry Pi |

<details>
<summary>🔊 Using Piper TTS (Offline)</summary>

**1. Install piper-tts:**
```bash
pip install piper-tts
```

**2. Download voice models:**
```bash
# Create model directory
mkdir -p ~/.local/share/piper-voices

# Download Chinese voice (from Hugging Face)
# https://huggingface.co/rhasspy/piper-voices/tree/main/zh/zh_CN/huayan/medium
# Download: zh_CN-huayan-medium.onnx and zh_CN-huayan-medium.onnx.json

# Download English voice
# https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/amy/medium
# Download: en_US-amy-medium.onnx and en_US-amy-medium.onnx.json
```

**3. Configure:**
```python
TTS_BACKEND = "piper"
```
</details>

<details>
<summary>🗣️ Available Edge TTS voices</summary>

| Voice | Description |
|-------|-------------|
| `zh-CN-XiaoyiNeural` | Xiaoyi (Female, lively) |
| `zh-CN-XiaoxiaoNeural` | Xiaoxiao (Female, gentle) |
| `zh-CN-YunxiNeural` | Yunxi (Male) |
| `zh-CN-YunjianNeural` | Yunjian (Male, announcer) |

List all voices: `edge-tts --list-voices`
</details>

## Tech Stack

| Component | Technology |
|-----------|------------|
| Voice Detection | [Silero VAD](https://github.com/snakers4/silero-vad) |
| Speech Recognition | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) |
| Text-to-Speech | [Edge TTS](https://github.com/rany2/edge-tts) (online) / [Piper](https://github.com/rhasspy/piper) (offline) |
| Audio | sounddevice, scipy, numpy |

## Roadmap

- [x] VAD-based voice detection
- [x] SenseVoice ASR
- [x] Streaming TTS
- [x] Claude backend
- [x] Ollama backend
- [x] Conversation memory
- [x] Auto language detection
- [ ] OpenAI API backend
- [ ] Wake word detection
- [ ] Web UI

## Troubleshooting

<details>
<summary><b>llvmlite build fails</b></summary>

```bash
# macOS
brew install llvm

# Ubuntu/Debian
sudo apt install llvm-dev

# Or use Python 3.10
uv sync --python 3.10
```
</details>

<details>
<summary><b>No audio input</b></summary>

- Check microphone permissions
- Lower `VAD_THRESHOLD` (e.g., 0.3)
</details>

<details>
<summary><b>Claude CLI not found</b></summary>

```bash
npm install -g @anthropic-ai/claude-code
```
</details>

## Contributing

Contributions welcome!

- 🐛 [Report bugs](https://github.com/kanweiwei/speekium/issues)
- 💡 [Suggest features](https://github.com/kanweiwei/speekium/issues)
- 🔧 Submit pull requests

## License

[MIT](./LICENSE) © 2025 [kanweiwei](https://github.com/kanweiwei)

---

<p align="center">
  <strong>If Speekium helps you, give it a ⭐</strong>
</p>
