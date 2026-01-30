# Daemon 启动流程问题修复总结

## 问题症状

前端卡在"正在启动语音服务..."加载界面，无法进入主界面。

---

## 根本原因分析

### 问题 1: notification socket 时序错误 ❌

**问题描述**：Rust 端的 NotificationListener 启动太晚

**原时序**：
```
Rust startup.rs:
  1. 启动 Python 进程 (第 194-253 行)
  2. health_check 循环等待 (第 264-287 行)
  3. health_check 通过后存储 daemon (第 317-324 行)
  4. 启动 NotificationListener (第 332-344 行) ← 太晚了!

Python worker_daemon.py (并行执行):
  1. 创建 command socket
  2. 尝试连接 notification socket ← 此时 Rust listener 还没启动!
     └─ 连接失败，进入重试队列
  3. 开始 initialize()
  4. emit init_progress("ready") ← 消息进入队列，无法立即发送
```

**问题影响**：
- Python daemon 发送的 init_progress 事件无法立即到达 Rust
- 即使后续通过 reconnection 连接上，ready 事件可能在超时后发送
- 前端永远收不到 ready 事件，卡在加载界面

---

### 问题 2: worker_daemon.py 中 notification socket 连接缺失 ❌

**问题描述**：`run_daemon_socket()` 绕过了 `SocketServer.start()`，导致 notification socket 从未连接

**原代码**：
```python
# worker_daemon.py:1298-1316
server._setup_socket()                    # 只设置 command socket
server.running = True
accept_task = asyncio.create_task(server._accept_loop())
init_task = asyncio.create_task(self.initialize())  # ← 直接初始化
```

**缺失的代码**（原 `SocketServer.start()` 中的）：
```python
await self._connect_notification_socket()           # ← 缺失!
self._notification_reconnect_task = asyncio.create_task(
    self._notification_maintenance_loop()           # ← 缺失!
)
```

---

## 修复方案

### 修复 1: Rust 端 - 提前启动 NotificationListener

**文件**: `src-tauri/src/daemon/startup.rs`

**变更**: 将 NotificationListener 的启动从 health_check 通过后移到 Python 进程启动前

**修改前** (第 326-344 行):
```rust
// Store daemon instance...
// Start notification listener BEFORE marking daemon ready
let notification_rx = {
    let mut listener = NotificationListener::with_default_path();
    // ...
};
```

**修改后** (移到第 193 行之前):
```rust
// CRITICAL: Start notification listener BEFORE spawning Python process
let notification_rx = {
    let mut listener = NotificationListener::with_default_path();
    // ...
};

// Build command based on mode
let child = match daemon_mode { ...
```

---

### 修复 2: Python 端 - 在初始化前连接 notification socket

**文件**: `worker_daemon.py`

**变更**: 在 `initialize()` 之前添加 notification socket 连接

**修改** (第 1297-1312 行):
```python
# Setup socket (synchronous)
server._setup_socket()
server.running = True

# CRITICAL: Connect to notification socket BEFORE initialization
notification_connected = await server._connect_notification_socket()
if notification_connected:
    self._log("✅ 通知 socket 已连接")
else:
    self._log("⚠️  通知 socket 连接失败，进度更新可能不可用")

# Start background reconnection task
server._notification_reconnect_task = asyncio.create_task(
    server._notification_maintenance_loop()
)

# Start accepting connections in background
accept_task = asyncio.create_task(server._accept_loop())

# Initialize models in parallel with accept loop
init_task = asyncio.create_task(self.initialize())
```

---

### 修复 3: 统一超时配置

**文件**: `src-tauri/src/daemon/socket_client.rs`

**变更**:
- 连接超时: 120s → 150s
- 读取超时: 120s → 150s
- 最大健康检查次数: 1200 → 1500

---

### 修复 4: 删除 Rust 端主动发送的 ready 事件

**文件**: `src-tauri/src/daemon/startup.rs`

**变更**: 删除第 447-451 行的 ready 事件发送

**原因**: ready 状态应由 Python 端的 `init_progress` 明确报告，确保模型真正就绪

---

## 修复后的正确时序

```
Rust startup.rs:
  1. 启动 NotificationListener (第 193 行) ← 最先启动
     └─ 创建 /tmp/speekium-notif.sock
     └─ 开始监听连接
  2. 启动 Python 进程 (第 210+ 行)
  3. health_check 循环等待
  4. health_check 通过后存储 daemon
  5. 启动通知处理线程

Python worker_daemon.py:
  1. 创建 command socket
  2. 连接 notification socket ← Rust 已准备好!
     └─ 连接成功
  3. 启动 background reconnection task
  4. 启动 accept loop
  5. 开始 initialize()
     ├─ emit init_progress("starting") ← 立即发送到 Rust
     ├─ emit init_progress("loading_vad") ← 立即发送到 Rust
     ├─ emit init_progress("loading_asr") ← 立即发送到 Rust
     └─ emit init_progress("ready") ← 立即发送到 Rust

Rust notification thread:
  └─ 接收 init_progress 事件
  └─ 转发为 daemon-status 事件

Frontend:
  └─ 收到 daemon-status "ready"
  └─ 渲染主界面
```

---

## 测试验证

1. ✅ 编译通过
2. ⏳ 需要测试:
   - 冷启动（首次运行，需下载模型）
   - 热启动（模型已缓存）
   - 页面刷新（daemon 已运行）

---

## 相关文件

| 文件 | 修改内容 |
|------|----------|
| `src-tauri/src/daemon/startup.rs` | 提前启动 NotificationListener，删除主动 ready |
| `src-tauri/src/daemon/socket_client.rs` | 统一超时为 150s |
| `worker_daemon.py` | 初始化前连接 notification socket |
