# 模型加载进度显示修复

## 问题

用户只能看到"正在启动语音服务..."，但看不到 VAD/ASR 模型初始化和加载的详细进度。

## 根本原因

- Python 端的 `initialize()` 方法中有日志输出（`logger.info("preloading_vad_model")` 等）
- 但这些日志输出到 `stderr`，Rust 端没有读取
- Rust 端只通过 socket 的 `health_check()` 判断是否 ready
- 只显示固定的 "正在加载语音助手..." 消息，没有反映实际加载阶段

## 修复方案：通过 Socket 通知发送进度

### Python 端修改 (`worker_daemon.py`)

**新增方法 `_emit_init_progress()`**:
```python
def _emit_init_progress(self, stage: str, message_zh: str, message_en: str = ""):
    """Emit initialization progress via socket notification to Rust frontend"""
    if self.socket_server:
        self.socket_server.broadcast_notification("init_progress", {
            "stage": stage,
            "message_zh": message_zh,
            "message_en": message_en or message_zh,
        })
```

**修改 `initialize()` 方法**，在各阶段发送进度通知：
- `starting`: "正在初始化语音服务..."
- `loading_assistant`: "正在加载语音助手..."
- `loading_vad`: "正在加载语音活动检测模型..."
- `loading_asr`: "正在加载语音识别模型..."
- `llm_skipped`: "LLM 后端将在需要时加载"
- `ready`: "语音服务已就绪"
- `error`: 初始化失败时的错误信息

### Rust 端修改 (`startup.rs`)

在通知监听线程中添加对 `init_progress` 事件的处理：

```rust
"init_progress" => {
    // Handle initialization progress from Python daemon
    if let Some(params) = notification.get("params") {
        let stage = params.get("stage")
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();
        let message = if let Some(msg_zh) = params.get("message_zh").and_then(|v| v.as_str()) {
            msg_zh.to_string()
        } else if let Some(msg_en) = params.get("message_en").and_then(|v| v.as_str()) {
            msg_en.to_string()
        } else {
            ui::get_daemon_message("loading")
        };

        // Forward init progress as daemon-status event
        let _ = app_handle_for_thread.emit("daemon-status", DaemonStatusPayload {
            status: stage,
            message,
        });
    }
}
```

## 效果

修复后，前端会收到并显示详细的加载进度：

```
正在初始化语音服务...
    ↓
正在加载语音助手...
    ↓
正在加载语音活动检测模型...
    ↓
正在加载语音识别模型...
    ↓
语音服务已就绪
```

## 相关文件

| 文件 | 修改类型 |
|------|----------|
| `worker_daemon.py` | 添加 `_emit_init_progress()` 方法，修改 `initialize()` |
| `src-tauri/src/daemon/startup.rs` | 添加 `init_progress` 事件处理 |
