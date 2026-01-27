# Socket IPC 架构设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 创建时间 | 2025-01-27 |
| 分支 | `feature/socket-ipc-architecture` |
| 状态 | 设计中 |
| 负责人 | Claude |

---

## 1. 概述

### 1.1 背景

当前 Speekium 使用 **stdin/stdout** 作为 Tauri (Rust) 与 Python (worker_daemon) 之间的通信机制。这带来了以下问题：

1. **调试困难**：`print()` 输出会破坏通信协议，必须使用 logger
2. **协议耦合**：所有通信混在一个流中，难以扩展
3. **缺乏隔离**：Python 端的任何模块问题都可能影响通信

### 1.2 目标

将通信机制改造为 **Unix Domain Socket / Named Pipe**，实现：

| 目标 | 说明 |
|------|------|
| 释放 stdin/stdout | 方便调试和日志输出 |
| 标准化协议 | 使用 JSON-RPC 2.0，易于扩展和调试 |
| 错误隔离 | 更好的错误隔离和恢复能力 |
| 扩展性 | 为未来独立服务（如 Piper TTS）打好基础 |

### 1.3 范围

**包含**：
- Tauri → worker_daemon 通信改造为 Socket
- 使用 JSON-RPC 2.0 协议
- macOS/Linux 使用 Unix socket，Windows 使用 Named Pipe

**不包含**：
- Piper TTS 独立服务（在 `feature/pluggable-tts-models` 分支）
- 运行时依赖管理（后续阶段）

---

## 2. 架构设计

### 2.1 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Tauri (Rust)                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              PythonDaemon                               │ │
│  │   ├── stdin: BufWriter<ChildStdin>                    │ │
│  │   └── stdout: BufReader<ChildStdout>                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                   │
│                          │ stdin/stdout                      │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Python (worker_daemon)                     │ │
│  │   ├── 读取 stdin: JSON 命令                             │ │
│  │   └── 写入 stdout: JSON 响应                            │ │
│  │   └── stderr: 日志/调试输出                              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 新架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Tauri (Rust)                         │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              SocketDaemonClient                         │ │
│  │   ├── Unix socket / Named Pipe 连接                     │ │
│  │   ├── JSON-RPC 2.0 协议实现                            │ │
│  │   └── 自动重连机制                                       │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │                                   │
│                          │ Socket                            │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Python (worker_daemon)                     │ │
│  │   ├── SocketServer                                      │ │
│  │   │   ├── Unix socket / Named Pipe                      │ │
│  │   │   └── JSON-RPC 2.0 协议处理                        │ │
│  │   ├── 命令处理                                           │ │
│  │   └── stdout/stderr: 完全用于日志和调试                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Socket 路径

| 平台 | Socket 类型 | 路径 |
|------|------------|------|
| macOS | Unix Domain Socket | `/tmp/speekium-daemon.sock` |
| Linux | Unix Domain Socket | `/tmp/speekium-daemon.sock` |
| Windows | Named Pipe | `\\\\.\\pipe\\speekium-daemon` |

---

## 3. JSON-RPC 2.0 协议设计

### 3.1 协议格式

**请求 (Request)**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "record",
  "params": {
    "mode": "push-to-talk",
    "duration": 3.0
  }
}
```

**响应 (Response)**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "success": true,
    "text": "你好世界",
    "language": "zh"
  }
}
```

**错误响应 (Error)**：
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": "unknown_method"
  }
}
```

**通知 (Notification，无响应)**：
```json
{
  "jsonrpc": "2.0",
  "method": "abort_recording",
  "params": {}
}
```

### 3.2 方法映射

| 当前命令 | JSON-RPC 方法 | 说明 |
|---------|---------------|------|
| `record` | `record` | 录音命令 |
| `chat` | `chat` | 聊天命令 |
| `tts` | `tts` | TTS 合成 |
| `config` | `get_config` | 获取配置 |
| `config` | `update_config` | 更新配置 |
| `health` | `health` | 健康检查 |
| `exit` | `shutdown` | 关闭服务 |

### 3.3 错误码

| 错误码 | 说明 |
|-------|------|
| -32700 | Parse error (JSON 解析错误) |
| -32600 | Invalid Request (无效请求) |
| -32601 | Method not found (方法不存在) |
| -32602 | Invalid params (无效参数) |
| -32603 | Internal error (内部错误) |
| -32000 | -32099 | Server error (服务端错误) |

---

## 4. 实现计划

### 4.1 Rust 端改造

**文件**: `src-tauri/src/daemon/socket_client.rs` (新增)

```rust
pub struct SocketDaemonClient {
    socket_path: PathBuf,
    stream: Option<Box<dyn ReadWrite>>,
}

impl SocketDaemonClient {
    pub fn new() -> Result<Self, String>;
    pub fn connect(&mut self) -> Result<(), String>;
    pub fn send_request(&mut self, method: &str, params: Value) -> Result<Value, String>;
    pub fn send_notification(&mut self, method: &str, params: Value) -> Result<(), String>;
}
```

**文件**: `src-tauri/src/daemon/process.rs` (修改)

- 移除 `stdin` / `stdout` 字段
- 移除 `send_command` 方法
- 只保留进程管理和 stderr 读取

### 4.2 Python 端改造

**文件**: `socket_server.py` (新增)

```python
class SocketServer:
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.daemon = SpeekiumDaemon()

    def start(self):
        # 创建 socket
        # 监听连接
        # 处理 JSON-RPC 请求

    def handle_request(self, request: dict) -> dict:
        # 解析 JSON-RPC 请求
        # 调用对应方法
        # 返回响应
```

**文件**: `worker_daemon.py` (修改)

- 移除 stdin/stdout 读取逻辑
- 启动 SocketServer
- 释放 stdout/stderr 用于日志

### 4.3 依赖库

**Rust**:
```toml
[target.'cfg(unix)'.dependencies]
interprocess = "2.2"

[target.'cfg(windows)'.dependencies]
named_pipe = "0.4"
```

**Python**:
```txt
无额外依赖 (使用标准库)
```

---

## 5. 迁移步骤

1. **阶段 1**: 创建 Socket 基础设施
   - Rust: `SocketDaemonClient`
   - Python: `SocketServer`

2. **阶段 2**: 实现 JSON-RPC 协议
   - Rust: 请求/响应序列化
   - Python: 方法路由

3. **阶段 3**: 迁移现有命令
   - 逐个迁移命令方法
   - 保持向后兼容

4. **阶段 4**: 清理旧代码
   - 移除 stdin/stdout 通信
   - 更新测试

5. **阶段 5**: 测试和修复
   - 单元测试
   - 集成测试
   - 性能测试

---

## 6. 实现状态

### 6.1 已完成

| 组件 | 文件 | 状态 |
|------|------|------|
| Rust Socket 客户端 | `src-tauri/src/daemon/socket_client.rs` | ✅ 完成 |
| Rust 进程管理 | `src-tauri/src/daemon/process.rs` | ✅ 已更新 |
| Rust 启动逻辑 | `src-tauri/src/daemon/startup.rs` | ✅ 已更新 |
| Python Socket 服务器 | `socket_server.py` | ✅ 完成 |
| Python 守护进程 | `worker_daemon.py` | ✅ 已更新 |
| 端到端测试 | 集成测试通过 | ✅ 完成 |

### 6.2 编译状态

| 组件 | 状态 |
|------|------|
| Rust (`cargo build`) | ✅ 通过 (有非关键警告) |
| Python (`ruff check`) | ✅ 通过 |

### 6.3 集成测试结果

```bash
Socket ready after 0.3s
Connected!
Health: healthy
Config success: True
Shutdown success: True
=== All tests PASSED! ===
```

---

## 7. 使用方式

### 7.1 启动 Socket 服务器

```bash
# 开发环境
python3 worker_daemon.py socket

# 生产环境 (打包后)
./worker_daemon socket
```

### 7.2 连接方式

**自动连接**：Rust 端会自动检测并连接 Socket

**手动测试**：
```bash
# 运行测试客户端
python3 test_socket_client.py

# 使用 socat (macOS/Linux)
echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | socat - /tmp/speekium-daemon.sock
```

---

## 8. 问题记录

| 时间 | 问题描述 | 解决方案 | 状态 |
|------|---------|---------|------|
| 2025-01-27 | Rust 编译警告 (未使用导入) | 移除未使用的导入 | ✅ 已修复 |
| 2025-01-27 | Rust 编译警告 (未读变量) | 移除未使用的变量 | ✅ 已修复 |
| 2025-01-27 | Python async 方法调用缺少 await | 添加 await 关键字 | ✅ 已修复 |
| 2025-01-27 | Socket 服务器未响应 | accept_loop 未设置 server.running=True | ✅ 已修复 |
| 2025-01-27 | 模型初始化阻塞 accept_loop | 使用 asyncio.create_task 并行运行 | ✅ 已修复 |
| 2025-01-27 | sock_accept 无限阻塞 | 添加 asyncio.wait_for 超时 | ✅ 已修复 |
| 2025-01-27 | 守护进程未在 shutdown 后退出 | 关闭 server_socket 解除阻塞 | ✅ 已修复 |
| 2025-01-27 | 命令参数错误 ("daemon" vs "socket") | 修改启动参数为 "socket" | ✅ 已修复 |
| 2025-01-27 | get_daemon_state 属性错误 | 修复 `tts_backend` → `_tts_backend` | ✅ 已修复 |

---

## 9. 变更历史

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2025-01-27 | 0.1 | 初始版本 |
| 2025-01-27 | 0.2 | 实现 Rust + Python Socket 通信 |
| 2025-01-27 | 0.3 | 修复编译警告，更新文档 |
| 2025-01-27 | 0.4 | 完成 Socket IPC 实现，端到端测试通过 |
| 2025-01-27 | 1.0 | Socket IPC 架构实现完成，所有测试通过 |
| 2025-01-27 | 1.1 | 修复 get_daemon_state 属性错误，全部测试通过 |

## 10. 最终测试结果

### 10.1 完整集成测试 (2025-01-27)

```
============================================================
Socket IPC Integration Test
============================================================
✅ Socket created: /tmp/speekium-daemon.sock
✅ Connected!
✅ Health check: PASSED
✅ Config command: PASSED
✅ Model status command: PASSED
✅ Daemon state command: PASSED
✅ Shutdown command: PASSED
============================================================
All tests PASSED!
============================================================
```

### 10.2 功能验证

| 功能 | 状态 | 说明 |
|------|------|------|
| Unix Socket 创建 | ✅ | `/tmp/speekium-daemon.sock` |
| JSON-RPC 2.0 协议 | ✅ | 请求/响应格式正确 |
| 健康检查 | ✅ | 返回模型加载状态 |
| 配置获取 | ✅ | 返回完整配置信息 |
| 模型状态查询 | ✅ | VAD/ASR/LLM/TTS 状态 |
| 守护进程状态 | ✅ | 运行状态/录音状态/命令计数 |
| 优雅关闭 | ✅ | 正确清理资源并退出 |

### 10.3 编译状态

| 组件 | 状态 |
|------|------|
| Rust (`cargo build`) | ✅ 通过 (仅非关键警告) |
| Python (`ruff check`) | ✅ 通过 |

## 11. 使用说明

### 11.1 开发环境运行

```bash
# 使用虚拟环境中的 Python
.venv/bin/python3 worker_daemon.py socket
```

### 11.2 生产环境运行

```bash
# Tauri 会自动启动 sidecar daemon
# 使用打包后的可执行文件
```

### 11.3 手动测试

```bash
# 运行集成测试
.venv/bin/python3 test_socket_integration.py

# 使用 socat 测试 (macOS/Linux)
echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | socat - /tmp/speekium-daemon.sock
```
