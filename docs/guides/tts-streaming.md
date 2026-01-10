# 🚀 Speekium TTS 流式功能快速上手

## 5 分钟体验最新功能

### 📦 前置条件

```bash
# 1. 确保虚拟环境已激活
source .venv/bin/activate

# 2. 确保 Ollama 正在运行（如果使用本地 LLM）
# 在另一个终端运行：
ollama serve

# 3. 确保已安装所有依赖
cd the main project
npm install
```

### ⚡ 一键启动

```bash
# 从项目根目录
./start-tauri.sh
```

就这么简单！应用会自动：
1. 激活 Python 虚拟环境
2. 启动 Tauri 开发服务器
3. 启动守护进程（预加载所有模型）
4. 打开桌面应用

### 🎯 体验三大功能

#### 1️⃣ 守护进程模式（后台运行，响应飞快）

**测试方法**：
```bash
# 在新终端测试守护进程
python3 test_daemon.py
```

**预期效果**：
- ✅ 模型加载：~10 秒（仅首次）
- ✅ 后续响应：~50ms（快 18 倍！）
- ✅ 健康检查通过

#### 2️⃣ 流式响应（打字机效果）

**如何启用**：
在应用中输入文本并发送，默认就是流式模式！

**预期效果**：
- ✅ 0.5 秒看到第一个字
- ✅ 逐句显示，像真人打字
- ✅ 不用等待完整响应

**关键代码**（前端）：
```typescript
// 默认启用流式
await chatGenerator(text);  // useStreaming = true
```

#### 3️⃣ TTS 边生成边播放（最新功能！）

**如何启用**：
```typescript
// 在 useTauriAPI.ts 中
await chatGenerator(text, 'auto', true, true);
//                                ↑    ↑
//                         流式模式  启用 TTS 流式
```

**测试方法**：
```bash
# 测试 TTS 流式功能
python3 test_tts_stream.py
```

**预期效果**：
- ✅ 1 秒后听到第一句话（传统需要 7 秒！）
- ✅ 边生成边播放，无需等待
- ✅ 音频文件自动保存到临时目录

### 📊 性能对比一览

| 功能 | 旧方式 | 新方式 | 提升 |
|------|--------|--------|------|
| **响应速度** | 3.5s | **0.2s** | **18x** |
| **首字显示** | 5s | **0.5s** | **10x** |
| **首个音频** | 7s | **1s** | **7x** |

## 🎨 UI 使用技巧

### 发送文本消息

1. 在输入框输入文字
2. 点击发送按钮或按 Enter
3. 立即看到流式响应（打字机效果）

### 启用语音输入

1. 点击麦克风按钮
2. 说话（自动 VAD 检测）
3. 等待识别结果
4. 自动发送给 LLM

### 查看系统状态

- 右上角显示守护进程健康状态
- 绿色图标 = 健康
- 红色图标 = 需要重启

### 快捷键

- `Command/Ctrl + Shift + Space`: 显示/隐藏窗口
- （全局快捷键，任何时候都可用）

## 🔧 配置选项

### 切换 LLM 后端

编辑 `config.json`:
```json
{
  "llm_backend": "ollama",  // 或 "claude"
  "ollama_model": "qwen2.5:1.5b"
}
```

### 切换 TTS 引擎

```json
{
  "tts_backend": "edge",  // 或 "piper"
  "edge_voice": "zh-CN-XiaoxiaoNeural"
}
```

### 调整 VAD 敏感度

```json
{
  "vad_threshold": 0.7,  // 0.0-1.0，越高越不敏感
  "vad_min_silence_duration_ms": 500
}
```

## 🐛 常见问题

### Q1: 启动后没有反应？

**A**: 检查守护进程是否正常启动
```bash
# 查看日志
cd the main project
npm run tauri dev
# 观察控制台输出，应该看到 "✅ 守护进程就绪"
```

### Q2: 音频不播放？

**A**: 检查音频队列状态
```bash
# 在浏览器开发者工具中
console.log('[Audio Queue]')
# 应该看到音频队列的日志
```

**常见原因**：
- 临时音频文件被清理
- 浏览器权限问题
- 音频格式不支持

**解决方法**：
- 使用 Piper TTS（更可靠）
- 检查浏览器控制台错误

### Q3: 响应很慢？

**A**: 检查模型是否预加载
```bash
# 健康检查
python3 -c "
import subprocess, json
p = subprocess.Popen(['python3', 'worker_daemon.py', 'daemon'],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
import time; time.sleep(15)
p.stdin.write(json.dumps({'command':'health','args':{}}) + '\n')
p.stdin.flush()
print(p.stdout.readline())
"
```

**预期输出**：
```json
{"success": true, "models_loaded": {"vad": true, "asr": true, "llm": true}}
```

### Q4: 内存占用高？

**A**: 这是正常的！守护进程预加载了所有模型
- VAD: ~50MB
- ASR: ~200MB
- LLM: ~200-500MB（取决于模型）

**总计**: 约 500MB 是正常的

**优点**: 响应速度提升 18 倍

## 📚 深入学习

想了解更多技术细节？查看以下文档：

- **[DAEMON_MODE.md](./DAEMON_MODE.md)** - 守护进程架构详解
- **[STREAMING_MODE.md](./STREAMING_MODE.md)** - 流式响应实现细节
- **[TTS_STREAMING_MODE.md](./TTS_STREAMING_MODE.md)** - TTS 流式技术方案
- **[FEATURES_COMPLETE.md](./FEATURES_COMPLETE.md)** - 完整功能总结

## 🎉 开始使用

```bash
# 1. 启动应用
./start-tauri.sh

# 2. 输入消息测试流式响应
# 3. 点击麦克风测试语音输入
# 4. 体验边生成边播放的语音输出

# 享受全新的语音助手体验！🚀
```

---

**有问题？** 查看 [GitHub Issues](https://github.com/kanweiwei/speekium/issues) 或提交新问题。
