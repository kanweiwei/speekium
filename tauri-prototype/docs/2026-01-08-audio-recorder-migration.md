# 录音功能迁移文档

## 概述

将 Speekium 的录音功能从 pywebview 迁移到 Tauri + PyTauri 后端。

## 已完成的工作

### 1. 创建音频录制模块

**文件**: `src-python/audio_recorder.py`
- **AudioRecorder 类**: 完整的录音管理器
- **支持模式**:
  - `continuous`: VAD 自动检测语音开始/结束
  - `push-to-talk`: 手动控制录音
- **异步方法**: 所有操作都是 async，避免阻塞
- **错误处理**: 完整的异常捕获和日志记录

### 2. Python 模块初始化

**文件**: `src-python/__init__.py`
- **导入**: VAD (Silero), ASR (SenseVoice)
- **配置**: 采样率、语言检测、模型路径

### 3. 后端集成

**更新**: `tauri-prototype/backend.py`
- **新增导入**:
  ```python
  from src_python.audio_recorder import AudioRecorder
  ```
- **新命令**:
  - `start_recording_vad` - VAD 自动录音
  - `start_recording_manual` - 手动录音
  - `stop_recording` - 停止录音
  - `get_recording_state` - 获取录音状态

## 使用方法

### 连续模式（自动检测）

```typescript
import { invoke } from '@tauri-apps/api/core';

const result = await invoke('start_recording_vad', {
  mode: 'continuous',
  language: 'auto'
});

// result:
// {
//   success: true,
//   text: "识别的文字",
//   language: "zh"
//   duration: 3.5  // 秒
//   sample_rate: 16000
// }
```

### 按键录音模式

```typescript
import { invoke } from '@tauri-apps/api/core';

const result = await invoke('start_recording_manual', {
  mode: 'push-to-talk',
  language: 'zh'
});

// result:
// {
//   success: true,
//   text: "识别的文字",
//   language: "zh"
// }
```

### 获取录音状态

```typescript
import { invoke } from '@tauri-apps/api/core';

const state = await invoke('get_recording_state');

// result:
// {
//   is_recording: true/false,
//   mode: "continuous" | "push-to-talk",
//   duration: 3.5,  // 如果正在录音
//   sample_rate: 16000,
// }
```

### 停止录音

```typescript
import { invoke } from '@tauri-apps/api/core';

await invoke('stop_recording');
```

## 对比原实现

### pywebview (原有)

```python
# web_app.py
window.api.start_recording()
window.evaluate_js('window.state.is_recording = true')
```

### Tauri (新)

```python
# backend.py
@commands.command()
async def start_recording_vad(body: RecordingRequest, app_handle: AppHandle) -> RecordingResult:
    recorder = AudioRecorder()
    result = await recorder.record_vad_async()
    return result
```

```typescript
// useTauriAPI.ts
const { startRecording } = useTauriAPI();

const result = await startRecording('continuous', 'auto');
```

## 优势

1. **模块化**: 音频录制逻辑独立，易于测试和维护
2. **异步设计**: 使用 async/await，避免阻塞主线程
3. **错误处理**: 完整的异常捕获和日志输出
4. **状态管理**: 清晰的录音状态接口
5. **多模式支持**: VAD 自动检测 + 手动控制

## 测试验证

### 基本功能测试

```bash
# 测试 VAD 录音
python -c "
from src_python.audio_recorder import AudioRecorder
import asyncio

async def test():
    recorder = AudioRecorder()
    print('Testing VAD recording...')
    await recorder.record_vad_async(duration=3)
    print('VAD recording completed')

asyncio.run(test())
"

# 测试手动录音
python -c "
from src_python.audio_recorder import AudioRecorder
import asyncio

async def test():
    recorder = AudioRecorder()
    print('Testing manual recording...')
    await recorder.record_interrupt_async(duration=3)
    print('Manual recording completed')

asyncio.run(test())
"
```

### 集成测试

```typescript
// tauri-prototype/src/useTauriAPI.ts

// 测试连续录音
const result = await startRecording('continuous', 'auto');
console.log('Recording result:', result);

// 检查状态
const state = await getRecordingState();
console.log('Recording state:', state);
```

## 已知限制

1. **音频 I/O**: 需要处理麦克风权限（Tauri 请求）
2. **跨平台**: Windows/macOS/Linux 麦克风可能不同
3. **调试**: 音频录制调试需要特殊工具

## 下一步

1. ✅ 测试音频录制功能
2. ⏳ 实现 LLM 后端集成
3. ⏳ 实现 TTS 音频播放
4. ⏳ 完整端到端流程测试

---

**迁移完成日期**: 2026-01-08
**状态**: 音频录制模块已迁移
