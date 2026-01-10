# Speekium Tauri 迁移 - 完整测试指南

## 概述

本文档提供端到端（E2E）测试指南，验证 Speekium 从 pywebview 迁移到 Tauri 的完整功能。

---

## 🧪 测试环境准备

### 1. 开发模式启动

```bash
cd tauri-prototype
npm run tauri:dev
```

**预期输出**：
```
[Speekium] ===============================================
[Speekium] PyTauri Backend Starting...
[Speekium] Default Config: {'llm_backend': 'ollama', 'ollama_model': 'qwen2.5:1.5b', ...}
[Speekium] ===============================================
[Speekium] Registered Commands:
  Config Commands:
    - config_load
    - config_save
    - config_get
    - config_update
    - config_bulk_update
  Recording Commands:
    - start_recording_vad
    - start_recording_manual
    - stop_recording
    - get_recording_state
  LLM Commands:
    - chat_generator
    - load_llm
    - clear_history
  TTS Commands:
    - generate_tts
    - play_tts
    - stop_audio
```

---

## 🎤 功能测试清单

### ✅ Phase 1: 配置管理

#### 测试 1.1: 加载默认配置
```typescript
// 在浏览器控制台执行
import { loadConfig } from './useTauriAPI';

const result = await loadConfig();
console.log('Config:', result);

// 预期输出
// { success: true, config: { llm_backend: 'ollama', ... } }
```

**验证点**：
- ✅ 默认配置正确加载
- ✅ 所有必需字段存在
- ✅ 类型安全（TypeScript 接口正确）

#### 测试 1.2: 更新配置
```typescript
// 测试 LLM 后端切换
import { saveConfig } from './useTauriAPI';

await saveConfig({
  llm_backend: 'claude',
  ollama_model: 'claude-3.5-sonnet'
});

// 验证：切换到 Claude 后端
```

**验证点**：
- ✅ 配置更新成功
- ✅ 配置文件持久化
- ✅ 重新加载后配置保持

---

### ✅ Phase 2: 录音功能

#### 测试 2.1: 连续录音模式（VAD 自动检测）
```typescript
// 启动录音
const { startRecordingAuto } = useTauriAPI();

const result = await startRecording('continuous', 'auto');

if (result.success && result.text) {
  console.log('识别文本:', result.text);
  console.log('识别语言:', result.language);
}
```

**验证点**：
- ✅ 录音成功启动
- ✅ VAD 自动检测语音开始/结束
- ✅ ASR 识别成功
- ✅ 语言检测正常（auto → zh/en）
- ✅ 录音时长合理（预期 <3 秒）

#### 测试 2.2: 按键录音模式
```typescript
// 启动手动录音
const result = await startRecording('push-to-talk', 'zh');

if (result.success && result.text) {
  console.log('识别文本:', result.text);
}
```

**验证点**：
- ✅ 按键录音成功启动
- ✅ 录音持续时间符合按键时长
- ✅ 识别文本准确

#### 测试 2.3: 录音状态查询
```typescript
// 查询录音状态
const state = await getRecordingState();

console.log('录音状态:', state);
// 预期输出
// { success: true, is_recording: false, mode: 'continuous' | 'push-to-talk' }
```

**验证点**：
- ✅ 状态查询返回正确
- ✅ mode 字段值正确
- ✅ 录音停止后状态更新正确

---

### ✅ Phase 3: 对话功能

#### 测试 3.1: 单轮对话
```typescript
// 发送文本并获取流式响应
import { chatGenerator } from './useTauriAPI';

const chunks = await chatGenerator('你好 Speekium', 'auto');

// 预期：3-5 个 ChatChunk
// { type: 'partial', content: 'This is' }
// { type: 'partial', content: 'This is a' }
// { type: 'partial', content: 'This is a test' }
// { type: 'complete', content: 'This is a test response from PyTauri backend!', audio: null }
```

**验证点**：
- ✅ 流式响应正确（partial → partial → partial → complete）
- ✅ 最后 chunk 类型为 'complete'
- ✅ 流式延迟合理（预期 200-500ms per chunk）
- ✅ 内容连贯性良好

#### 测试 3.2: 多轮对话（带历史）
```typescript
// 第二轮对话，应该包含第一轮历史
const chunks2 = await chatGenerator('再测试一下', 'auto', [
  { role: 'user', content: '你好 Speekium' },
  { role: 'assistant', content: 'This is a test response' }
]);
```

**验证点**：
- ✅ 上下文正确传递到后端
- ✅ 历史记录保持
- ✅ 多轮对话连贯

#### 测试 3.3: 清空对话历史
```typescript
import { clearHistory } from './useTauriAPI';

await clearHistory();

// 验证：历史应该被清空
```

**验证点**：
- ✅ 历史清空成功
- ✅ 下一次对话重新开始

---

### ✅ Phase 4: TTS 功能

#### 测试 4.1: 在线 TTS 生成
```typescript
// 使用 Edge TTS 生成音频
const result = await invoke('generate_tts', {
  text: 'Speekium 测试 TTS',
  language: 'zh',
  backend: 'edge',
  rate: '+0%'
});

if (result.success && result.audio_base64) {
  console.log('音频数据长度:', result.audio_base64.length);
  
  // 播放音频（如果前端支持）
  const audioBlob = new Blob([base64ToUint8Array(result.audio_base64)], { type: result.format || 'audio/wav' });
  const audioUrl = URL.createObjectURL(audioBlob);
  new Audio(audioUrl).play();
}
```

**验证点**：
- ✅ TTS 音频生成成功
- ✅ Base64 编码正确
- ✅ 音频格式支持（WAV/MP3）
- ✅ 音频播放正常

#### 测试 4.2: 离线 TTS 生成
```typescript
// 使用 Piper TTS（离线模式）
const result = await invoke('generate_tts', {
  text: '离线模式测试',
  language: 'zh',
  backend: 'piper',
  voice: 'zh_CN-huayan-medium'
});

// 验证：离线 TTS 也应该工作
```

**验证点**：
- ✅ Piper TTS 生成成功
- ✅ 离线模式可用
- ✅ 语音模型切换正常

#### 测试 4.3: 音频播放控制
```typescript
// 停止正在播放的音频
await invoke('stop_audio');

// 验证：音频应该立即停止
```

**验证点**：
- ✅ 音频停止命令工作
- ✅ 多个音频不会重叠播放
- ✅ 停止后可以立即播放新音频

---

### ✅ Phase 5: 完整流程测试

#### 测试 5.1: 完整对话流程
```typescript
// 模拟真实用户场景：录音 → 识别 → 对话 → TTS
const { startRecording, chatGenerator, playBase64Audio } = useTauriAPI();

// 1. 开始录音
const recordResult = await startRecording('continuous', 'auto');

if (!recordResult.success) {
  console.error('录音失败:', recordResult.error);
  return;
}

// 2. 发送到 LLM
const chunks = await chatGenerator(recordResult.text, 'zh');

// 3. 找到完整的响应
const completeChunk = chunks.find(c => c.type === 'complete');

if (!completeChunk) {
  console.error('未找到完整响应');
  return;
}

// 4. 播放 TTS 音频
if (completeChunk.audio) {
  const audioBlob = new Blob([base64ToUint8Array(completeChunk.audio)], { type: 'audio/wav' });
  const audioUrl = URL.createObjectURL(audioBlob);
  new Audio(audioUrl).play();
}
```

**验证点**：
- ✅ 录音 → 识别 → 对话 → TTS 全流程打通
- ✅ 每个环节状态正确
- ✅ 错误处理完善
- ✅ 用户体验流畅

#### 测试 5.2: 并发场景
```typescript
// 同时进行录音和对话
const recordPromise = startRecording('continuous', 'auto');
const chatPromise = chatGenerator('并发测试', 'auto');

await Promise.all([recordPromise, chatPromise]);
```

**验证点**：
- ✅ 并发操作正常
- ✅ 无竞态条件
- ✅ 状态管理正确

---

### ✅ Phase 6: 错误处理和边界情况

#### 测试 6.1: 网络错误处理
```typescript
// 模拟网络错误（如果使用 Ollama 本地后端）
// 通过修改配置使后端不可用
await saveConfig({
  ollama_base_url: 'http://invalid-url'
});

const result = await chatGenerator('测试错误处理', 'auto');

if (!result.success) {
  console.log('错误被正确捕获:', result.error);
}
```

**验证点**：
- ✅ 网络错误正确返回
- ✅ 错误消息清晰
- ✅ 用户界面正常降级

#### 测试 6.2: 长文本处理
```typescript
// 测试超长文本（1000+ 字符）
const longText = 'A'.repeat(1000);

const chunks = await chatGenerator(longText, 'auto');

// 验证：流式响应应该正常工作
```

**验证点**：
- ✅ 长文本不超时
- ✅ 流式传输稳定
- ✅ 内存占用合理

#### 测试 6.3: 特殊字符处理
```typescript
// 测试表情符号、特殊字符、多语言混合
const specialText = '你好 🌍 世界 Hello 🌎';

const chunks = await chatGenerator(specialText, 'auto');

// 验证：特殊字符正确处理
```

**验证点**：
- ✅ 特殊字符不导致错误
- ✅ 多语言混合正常
- ✅ 表情符号正确显示

---

### ✅ Phase 7: 性能和稳定性

#### 测试 7.1: 响应时间
```typescript
// 测量端到端响应时间
console.time('对话响应时间');

const start = Date.now();
const chunks = await chatGenerator('性能测试', 'auto');
const end = Date.now();

console.timeEnd('对话响应时间');
console.log('总耗时:', end - start, 'ms');

// 预期：<3 秒
```

**验证点**：
- ✅ 响应时间在合理范围内
- ✅ 流式传输稳定
- ✅ 无明显延迟

#### 测试 7.2: 内存和 CPU 占用
```bash
# 使用系统监控工具
# macOS
top -pid $(pgrep -f speekium-backend | head -1)

# Linux
htop -p speekium-backend

# Windows
任务管理器 -> 性能选项
```

**验证点**：
- ✅ CPU 占用合理（预期 <50% 单核）
- ✅ 内存占用稳定（预期 <200MB）
- ✅ 无内存泄漏

#### 测试 7.3: 长时间运行
```bash
# 运行 1 小时持续测试
for i in {1..360}; do
  await chatGenerator(`持续测试 ${i}`, 'auto');
  await new Promise(r => setTimeout(r, 1000));
done;

console.log('完成 360 次对话循环');
```

**验证点**：
- ✅ 无崩溃或重启
- ✅ 性能保持稳定
- ✅ 内存无泄漏

---

## 🐛 常见问题和排查

### 问题 1: Python 后端未启动
**症状**: 调用 Tauri 命令失败
**解决**:
```bash
# 检查 Python 进程
ps aux | grep python

# 如果没有运行，启动后端
cd tauri-prototype
python src-python/backend_main.py --port 8008
```

### 问题 2: 音频权限问题
**症状**: 录音失败，提示无麦克风权限
**解决**:
```typescript
// macOS
await invoke('request_microphone_permission');

// Windows/Linux
// 检查系统设置中的麦克风权限
```

### 问题 3: TTS 音频不播放
**症状**: TTS 生成成功但无声音
**解决**:
```typescript
// 检查音频数据格式
if (result.audio_base64) {
  const header = result.audio_base64.substring(0, 10);
  console.log('音频格式:', header); // 应该包含 'data:audio/wav;base64,'
  
  // 验证 Blob 创建
  try {
    const audioBlob = new Blob([base64ToUint8Array(result.audio_base64.substring(23))], { type: 'audio/wav' });
    const audio = new Audio(audioBlob);
    console.log('音频时长:', audio.duration, '秒');
  }
}
```

### 问题 4: 配置文件损坏
**症状**: 加载配置失败或显示异常值
**解决**:
```bash
# 删除损坏的配置文件
rm ~/Library/Application\ Support/com.speekium.app/config.json.backup

# 或重置为默认配置
cd tauri-prototype
python -c "import sys; sys.path.insert(0, '.'); import backend; backend.main()" 
```

---

## 📊 测试报告模板

### 每日测试记录

```
日期: 2026-01-XX
测试人员: [你的名字]

Phase 1: 配置管理
  ✅ 默认配置加载 - 通过
  ✅ 配置更新 - 通过
  ✅ 配置持久化 - 通过

Phase 2: 录音功能
  ✅ 连续录音 - 通过
  ✅ 按键录音 - 通过
  ✅ 录音状态查询 - 通过
  ⚠️ 录音超时问题 - 待修复

Phase 3: 对话功能
  ✅ 单轮对话 - 通过
  ✅ 多轮对话 - 通过
  ✅ 清空历史 - 通过
  ✅ 流式响应 - 通过

Phase 4: TTS 功能
  ✅ 在线 TTS - 通过
  ✅ 离线 TTS - 待测试
  ✅ 音频播放 - 通过

Phase 5: 完整流程
  ✅ 端到端测试 - 通过

性能指标:
  - 平均响应时间: 1.2 秒
  - 内存占用: 150MB
  - CPU 占用: 35%

问题清单:
  - [ ] PENDING: 录音超时优化
  - [ ] PENDING: 离线 TTS 集成
```

---

## 🚀 快速测试命令

### 单元测试

```bash
# 配置加载
curl -X POST http://localhost:1420/config_load

# 录音测试
curl -X POST http://localhost:1420/start_recording_vad \
  -H "Content-Type: application/json" \
  -d '{"mode": "continuous", "language": "auto"}'

# 对话测试
curl -X POST http://localhost:1420/chat_generator \
  -H "Content-Type: application/json" \
  -d '{"text": "测试", "language": "auto"}'

# TTS 测试
curl -X POST http://localhost:1420/generate_tts \
  -H "Content-Type: application/json" \
  -d '{"text": "测试 TTS", "language": "zh", "backend": "edge"}'
```

### 集成测试

```bash
# 完整流程测试脚本
# test-full-flow.sh
#!/bin/bash

echo "=== 开始完整流程测试 ==="

# 1. 配置测试
echo "[1/5] 测试配置加载..."
curl -s http://localhost:1420/config_load

# 2. 录音测试
echo "[2/5] 测试录音功能..."
curl -s -X POST http://localhost:1420/start_recording_vad \
  -H "Content-Type: application/json" \
  -d '{"mode": "continuous", "language": "auto"}'

# 3. 对话测试
echo "[3/5] 测试对话功能..."
curl -s -X POST http://localhost:1420/chat_generator \
  -H "Content-Type: application/json" \
  -d '{"text": "你好", "language": "auto"}'

# 4. TTS 测试
echo "[4/5] 测试 TTS 功能..."
curl -s -X POST http://localhost:1420/generate_tts \
  - H "Content-Type: application/json" \
  -d '{"text": "测试", "language": "zh", "backend": "edge"}'

echo "=== 测试完成 ==="
```

---

## 📋 测试验收标准

### 功能完整性
- [ ] 所有核心功能可用（录音、识别、对话、TTS）
- [ ] 所有 API 命令响应正常
- [ ] 错误处理完善
- [ ] 性能指标达标

### 质量标准
- [ ] 无致命错误
- [ ] 无数据丢失
- [ ] 用户体验流畅
- [ ] 跨平台一致性

### 性能标准
- [ ] 响应时间 <3 秒（单轮）
- [ ] 内存占用 <300MB
- [ ] CPU 占用 <60%
- [ ] 无内存泄漏

### 稳定性标准
- [ ] 连续运行 1 小时无崩溃
- [ ] 100 轮对话无错误
- [ ] 长时间运行稳定

---

## 🎯 下一步行动

### 立即行动
1. ✅ 开始手动功能测试
2. ⏳ 修复发现的问题
3. ⏳ 性能优化
4. ⏳ 边缘情况处理

### 后续优化
1. ⏳ 添加更多测试用例
2. ⏳ 实现自动化测试
3. ⏳ 性能监控和告警
4. ⏳ 用户反馈收集

---

**测试完成标准**: 所有 3 个 Phase 全部通过，性能和质量指标达标。
