# Speekium Daemon 通信协议

## 版本
v1.0

## 输出规范
| 输出 | 用途 |
|------|------|
| stdout | JSON 数据（命令/响应/事件） |
| stderr | 日志（logger 输出，不参与通信） |

---

## 消息格式

### 请求 (Request)
```json
{
  "v": 1,
  "id": 1,
  "method": "chat",
  "params": {
    "message": "hello"
  }
}
```

### 响应 (Response)
```json
{
  "v": 1,
  "id": 1,
  "result": {
    "response": "hi"
  }
}
```

### 错误 (Error)
```json
{
  "v": 1,
  "id": 1,
  "error": {
    "code": -32600,
    "message": "Invalid Request"
  }
}
```

### 事件 (Event) - 服务端推送
```json
{
  "v": 1,
  "type": "event",
  "event": "model_loaded",
  "data": {
    "model": "VAD"
  }
}
```

---

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| v | integer | 是 | 协议版本，当前为 1 |
| id | integer/string | 是 | 请求 ID，用于匹配响应 |
| method | string | 是 | 方法名 |
| params | object | 否 | 方法参数 |
| result | object | 否 | 成功响应数据 |
| error | object | 否 | 错误信息 |
| type | string | 是 | 消息类型：request/response/event |
| event | string | 是 | 事件名称（仅 event 类型） |
| data | object | 否 | 事件数据（仅 event 类型） |

---

## 错误码

| 码 | 说明 |
|-----|------|
| -32700 | Parse error - JSON 解析失败 |
| -32600 | Invalid Request - 无效请求 |
| -32601 | Method not found - 方法不存在 |
| -32602 | Invalid params - 参数无效 |
| -32603 | Internal error - 内部错误 |

---

## 命令列表

| 方法 | 说明 | 参数 |
|------|------|------|
| chat | 发送聊天消息 | `{message: string}` |
| chat_stream | 流式聊天 | `{message: string}` |
| transcribe | 语音转文字 | `{audio_path: string}` |
| tts | 文字转语音 | `{text: string, language: string}` |
| ping | 心跳检测 | `{}` |
| config | 获取配置 | `{}` |
| health | 健康检查 | `{}` |

---

## 事件列表

| 事件 | 说明 | 数据 |
|------|------|------|
| daemon_initializing | 守护进程初始化中 | - |
| model_loading | 模型加载中 | `{model: string}` |
| model_loaded | 模型加载完成 | `{model: string}` |
| daemon_ready | 守护进程就绪 | - |
| transcription | 语音转文字结果 | `{text: string}` |
| tts_chunk | TTS 流式输出 | `{chunk: string}` |
| tts_done | TTS 完成 | - |
| error | 错误事件 | `{error: string}` |

---

## 心跳机制

客户端每 30 秒发送 `ping` 请求，守护进程响应 `pong`。

```
客户端 → {"method": "ping", "id": 1} → 守护进程
客户端 ← {"id": 1, "result": {"pong": true}} ← 守护进程
```

---

## 示例

### 聊天请求
```bash
echo '{"v":1,"id":1,"method":"chat","params":{"message":"你好"}}' | python worker_daemon.py daemon
```

### 响应
```json
{"v":1,"id":1,"result":{"response":"你好！有什么可以帮你的？","audio":null}}
```

---

## 演进策略

1. **版本协商**：客户端首次请求携带版本，守护进程返回支持的版本
2. **向后兼容**：新增字段不破坏旧逻辑
3. **版本降级**：不支持时返回错误码 `-32000`
