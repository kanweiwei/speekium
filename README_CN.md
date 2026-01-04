# Speekium

智能语音助手，通过自然语音与大语言模型进行对话交互。

## 特性

- **VAD 语音检测** - 使用 Silero VAD 自动检测语音起止，无需手动按键
- **高精度语音识别** - 基于阿里 SenseVoice 模型，支持中文、英文等多语言
- **流式语音合成** - 边生成边朗读，响应更快速自然
- **可插拔 LLM 后端** - 当前支持 Claude Code CLI，后续将支持 Ollama 等
- **跨平台支持** - macOS、Linux、Windows

## 工作流程

```
🎤 麦克风输入
    ↓
🔍 VAD 检测人声（Silero VAD）
    ↓
📝 语音识别（SenseVoice）
    ↓
🤖 LLM 流式回复
    ↓
🔊 TTS 语音合成（Edge TTS）
    ↓
🎧 音频播放
```

## 安装

### 前置要求

- Python 3.10+
- [Claude Code CLI](https://github.com/anthropics/claude-code) 已安装并配置
- 麦克风设备

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/user/speekium.git
cd speekium

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

### Linux 额外依赖

```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev ffmpeg

# Fedora
sudo dnf install portaudio-devel ffmpeg
```

## 使用

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动
python speekium.py
```

启动后直接对着麦克风说话即可，无需按键。说完后会自动识别并回复。

## 配置

编辑 `speekium.py` 顶部的配置项：

```python
# 语音识别模型
ASR_MODEL = "iic/SenseVoiceSmall"

# TTS 语音（Edge TTS）
TTS_VOICE = "zh-CN-XiaoyiNeural"  # 可选: zh-CN-XiaoxiaoNeural, zh-CN-YunxiNeural 等
TTS_RATE = "-15%"                 # 语速调整

# 流式输出（边生成边朗读）
USE_STREAMING = True

# VAD 参数
VAD_THRESHOLD = 0.5           # 语音检测阈值
SILENCE_AFTER_SPEECH = 1.5    # 静音多久停止录音（秒）
MAX_RECORDING_DURATION = 30   # 最大录音时长（秒）
```

### 可用的中文语音

| 语音 | 说明 |
|------|------|
| `zh-CN-XiaoyiNeural` | 小艺（女声，活泼） |
| `zh-CN-XiaoxiaoNeural` | 晓晓（女声，温柔） |
| `zh-CN-YunxiNeural` | 云希（男声） |
| `zh-CN-YunjianNeural` | 云健（男声，新闻播报风格） |

查看所有可用语音：
```bash
python tts_test.py --list
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 语音活动检测 | [Silero VAD](https://github.com/snakers4/silero-vad) |
| 语音识别 | [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) (FunASR) |
| 大语言模型 | 可插拔（Claude Code CLI、Ollama 等） |
| 语音合成 | [Edge TTS](https://github.com/rany2/edge-tts) |
| 音频处理 | sounddevice, scipy |

### 支持的 LLM 后端

| 后端 | 状态 |
|------|------|
| [Claude Code CLI](https://github.com/anthropics/claude-code) | ✅ 已支持 |
| [Ollama](https://ollama.ai) | 🚧 计划中 |
| OpenAI API | 🚧 计划中 |

## 平台支持

| 平台 | 音频播放 | 状态 |
|------|----------|------|
| macOS | afplay | ✅ |
| Linux | ffplay | ✅ |
| Windows | PowerShell SoundPlayer | ✅ |

## License

MIT

## 贡献

欢迎提交 Issue 和 Pull Request！
