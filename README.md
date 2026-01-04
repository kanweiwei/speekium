# Speekium

[中文文档](./README_CN.md)

A smart voice assistant that enables natural voice conversations with LLMs.

## Features

- **Voice Activity Detection** - Auto-detects speech start/end using Silero VAD, no button press needed
- **High-Accuracy ASR** - Powered by Alibaba's SenseVoice model, supports Chinese, English, and more
- **Streaming TTS** - Speaks while generating, for faster and more natural responses
- **Pluggable LLM Backend** - Currently supports Claude Code CLI, with Ollama and other backends planned
- **Cross-Platform** - Works on macOS, Linux, and Windows

## How It Works

```
🎤 Microphone Input
    ↓
🔍 Voice Activity Detection (Silero VAD)
    ↓
📝 Speech Recognition (SenseVoice)
    ↓
🤖 LLM Streaming Response
    ↓
🔊 Text-to-Speech (Edge TTS)
    ↓
🎧 Audio Playback
```

## Installation

### Prerequisites

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code) installed and configured
- Microphone

### Setup

```bash
# Clone the repository
git clone https://github.com/user/speekium.git
cd speekium

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Linux Additional Dependencies

```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# Run
python speekium.py
```

Just speak into your microphone after starting. The assistant will automatically detect when you finish speaking and respond.

## Configuration

Edit the configuration at the top of `speekium.py`:

```python
# ASR Model
ASR_MODEL = "iic/SenseVoiceSmall"

# TTS Voice (Edge TTS)
TTS_VOICE = "zh-CN-XiaoyiNeural"  # Options: zh-CN-XiaoxiaoNeural, en-US-JennyNeural, etc.
TTS_RATE = "-15%"                 # Speech rate adjustment

# Streaming output (speak while generating)
USE_STREAMING = True

# VAD Parameters
VAD_THRESHOLD = 0.5           # Voice detection threshold
SILENCE_AFTER_SPEECH = 1.5    # Silence duration to stop recording (seconds)
MAX_RECORDING_DURATION = 30   # Maximum recording duration (seconds)
```

### Available Voices

List all available voices:
```bash
python tts_test.py --list
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Voice Activity Detection | [Silero VAD](https://github.com/snakers4/silero-vad) |
| Speech Recognition | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) (FunASR) |
| Large Language Model | Pluggable (Claude Code CLI, Ollama, etc.) |
| Text-to-Speech | [Edge TTS](https://github.com/rany2/edge-tts) |
| Audio Processing | sounddevice, scipy |

### Supported LLM Backends

| Backend | Status |
|---------|--------|
| [Claude Code CLI](https://github.com/anthropics/claude-code) | ✅ Supported |
| [Ollama](https://ollama.ai) | 🚧 Planned |
| OpenAI API | 🚧 Planned |

## Platform Support

| Platform | Audio Player | Status |
|----------|--------------|--------|
| macOS | afplay | ✅ |
| Linux | ffplay | ✅ |
| Windows | PowerShell SoundPlayer | ✅ |

## License

MIT

## Contributing

Issues and Pull Requests are welcome!
