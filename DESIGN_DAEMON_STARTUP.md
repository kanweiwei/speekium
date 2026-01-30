# Daemon 启动流程改进设计

## 问题摘要

当前设计存在以下核心问题：

1. **状态来源混乱**：daemon 状态来自 Rust health_check 和 Python init_progress 两个源头，可能不一致
2. **ready 时机过早**：Rust 端在 assistant 对象创建后立即发送 ready，此时 VAD/ASR 可能还在加载
3. **状态粒度不足**：前端无法区分初始化的具体阶段（VAD加载中 vs ASR加载中）

## 改进方案

### 原则

1. **单一真相来源**：Python daemon 是模型加载状态的唯一权威
2. **明确状态转换**：每个状态有清晰的进入和退出条件
3. **可观测性**：前端可以精确知道当前卡在哪个阶段

### 架构变更

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          状态流转 (改进后)                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Frontend (App.tsx)              Rust (startup.rs)           Python     │
│                                                                         │
│  daemonStatus = 'starting'  │   start_daemon_async()     │            │
│         ↓                   │         │                 │            │
│  等待 daemon-status 事件   │         │                 │            │
│         ↓                   │         ▼                 │            │
│                              │  启动 Python 进程       │            │
│                              │         │                 │            │
│                              │         ▼                 │            │
│                              │  等待 socket 连接       │ socket_server│
│                              │         │                 │ 启动        │
│  收到 'initializing' ◄───────┼─────────┘                 │            │
│  显示 "正在初始化..."         │                           │            │
│         ↓                   │                           │            │
│  收到 'loading_vad' ◄────────┼───────────────────────────┤ VoiceAssistant│
│  显示 "正在加载 VAD..."       │                           │ .__init__() │
│         ↓                   │                           │            │
│  收到 'loading_asr' ◄────────┼───────────────────────────┤ load_vad() │
│  显示 "正在加载 ASR..."       │                           │            │
│         ↓                   │                           │ load_asr() │
│  收到 'ready' ◄──────────────┼───────────────────────────┤            │
│  设置 daemonStatus='ready'   │                           │            │
│  渲染主界面                   │                           │            │
│                              │  DAEMON_READY = true     │            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 关键变更

#### 1. Rust 端：不再主动发送 ready 事件

**删除** (`startup.rs:448-451`)：
```rust
// ❌ 删除这段代码
let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
    status: "ready".to_string(),
    message: ui::get_daemon_message("ready"),
});
```

**原因**：ready 状态应该由 Python 端明确报告，Rust 只负责转发。

#### 2. Rust 端：只转发 Python 的 init_progress 事件

**保留** (`startup.rs:370-390`)：
```rust
"init_progress" => {
    // 直接转发 Python 的 init_progress 事件
    let _ = app_handle_for_thread.emit("daemon-status", DaemonStatusPayload {
        status: stage,  // 使用 Python 报告的 stage
        message,
    });
}
```

#### 3. Python 端：确保 ready 事件在模型真正就绪后发送

**当前代码** (`worker_daemon.py:267-268`)：
```python
self._emit_init_progress("ready", "语音服务已就绪", "Voice service ready")
```

**确认**：这行代码在 `load_vad()` 和 `load_asr()` 之后，是正确的。

#### 4. 前端：增加状态粒度

**修改** (`App.tsx:405`)：
```typescript
// 改进后的状态类型
type DaemonStatus =
  | 'starting'      // 初始状态
  | 'initializing'  // Python 进程已启动
  | 'loading_vad'   // VAD 模型加载中
  | 'loading_asr'   // ASR 模型加载中
  | 'downloading'   // 模型下载中
  | 'ready'         // 完全就绪
  | 'error';        // 错误

const [daemonStatus, setDaemonStatus] = React.useState<DaemonStatus>('starting');
```

#### 5. 前端：事件监听器改进

**修改** (`App.tsx:550-564`)：
```typescript
const unlisten = await listen<{ status: string; message: string }>('daemon-status', (event) => {
  const { status, message } = event.payload;

  // 直接使用 Python 报告的 status
  if (status === 'ready') {
    setDaemonStatus('ready');
    setDaemonReady(true);
  } else if (status === 'error') {
    setDaemonStatus('error');
    setLoadingMessage(message);
  } else if (
    ['starting', 'initializing', 'loading_vad', 'loading_asr',
     'downloading', 'loading_assistant'].includes(status)
  ) {
    setDaemonStatus(status as DaemonStatus);
    setLoadingMessage(message);
  } else {
    // 未知状态，保持当前状态
    console.warn(`[App] Unknown daemon status: ${status}`);
  }
});
```

### 超时配置统一

**修复** 超时不一致问题：

| 组件 | 当前值 | 修改为 | 位置 |
|------|--------|--------|------|
| Python Server | 150s | 150s | 保持不变 |
| Rust Client read | 120s | 150s | `socket_client.rs:158` |
| Rust Client connect | 120s | 150s | `socket_client.rs:148` |

```rust
// socket_client.rs:158
stream.set_read_timeout(Some(Duration::from_secs(150)))  // 120 → 150
```

### 错误处理增强

**新增**：超时时显示更具体的错误信息

```rust
// startup.rs:289-298
if !initialized {
    let error_msg = if health_check_count >= 50 && health_check_count < 150 {
        // 5-15秒：可能是模型首次下载
        "启动超时: 模型可能正在下载，请稍后重试"
    } else if health_check_count < 300 {
        // 15-30秒：可能是 VAD/ASR 加载慢
        "启动超时: 模型加载时间过长，请检查系统资源"
    } else {
        // >30秒：严重问题
        "启动超时: 可能是配置错误或系统问题，请查看日志"
    };
    let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
        status: "error".to_string(),
        message: error_msg.to_string(),
    });
}
```

## 实施步骤

1. **Rust 端修改**
   - [ ] 删除 startup.rs:448-451 的 ready 事件发送
   - [ ] 修改 socket_client.rs:158 超时为 150s
   - [ ] 修改 socket_client.rs:148 连接超时为 150s

2. **前端修改**
   - [ ] 扩展 DaemonStatus 类型
   - [ ] 更新事件监听器逻辑
   - [ ] 更新 LoadingScreen 显示对应状态

3. **验证**
   - [ ] 测试冷启动（首次下载模型）
   - [ ] 测试热启动（模型已缓存）
   - [ ] 测试页面刷新（daemon 已运行）
   - [ ] 测试错误场景（模型损坏）

## 向后兼容

此改动完全向后兼容：
- Python 端无需修改
- Socket 协议无需修改
- 只是调整了状态报告的时机和前端的解析逻辑
