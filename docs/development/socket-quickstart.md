# Socket IPC Quick Start

## 快速开始

### 1. 启动 Socket 服务器

```bash
# 方式 1: 使用默认 socket 路径 (推荐)
python3 worker_daemon.py socket

# 方式 2: 使用自定义路径
python3 worker_daemon.py socket /tmp/my-socket.sock

# 方式 3: 旧模式 (stdin/stdout) - 向后兼容
python3 worker_daemon.py daemon
```

### 2. 测试 Socket 连接

```bash
# 运行测试客户端
python3 test_socket_client.py

# 运行单元测试
python3 test_socket_server.py
```

### 3. 使用示例

#### Python 客户端

```python
import socket
import json
import platform

# 获取 socket 路径
if platform.system() == "Windows":
    socket_path = r"\\.\pipe\speekium-daemon"
else:
    socket_path = "/tmp/speekium-daemon.sock"

# 连接到 socket
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(socket_path)

# 发送 JSON-RPC 请求
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "health",
    "params": {}
}
sock.sendall((json.dumps(request) + "\n").encode("utf-8"))

# 接收响应
response = sock.recv(4096).decode("utf-8")
print(f"Response: {response}")

sock.close()
```

#### 命令行测试 (macOS/Linux)

```bash
# 使用 netcat 测试
echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | nc -U /tmp/speekium-daemon.sock

# 使用 socat 测试
echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | socat - UNIX-CONNECT:/tmp/speekium-daemon.sock
```

## 常见问题

### Q: Socket 文件在哪里？

**macOS/Linux:** `/tmp/speekium-daemon.sock`
**Windows:** `\\.\pipe\speekium-daemon`

### Q: 如何检查 socket 是否存在？

```bash
# macOS/Linux
ls -l /tmp/speekium-daemon.sock

# Windows PowerShell
Get-ChildItem \\.\pipe\ | Where-Object Name -like "*speekium*"
```

### Q: 连接被拒绝？

1. 检查守护进程是否在运行：`ps aux | grep worker_daemon`
2. 检查 socket 文件是否存在
3. 查看守护进程日志

### Q: 权限被拒绝？

```bash
# macOS/Linux: 检查 socket 权限
ls -l /tmp/speekium-daemon.sock
# 应该显示: srw------- (0600)

# 如果权限不对，删除旧文件重新启动守护进程
rm /tmp/speekium-daemon.sock
python3 worker_daemon.py socket
```

## 调试技巧

### 启用详细日志

```bash
# 设置日志级别为 DEBUG
LOG_LEVEL=DEBUG python3 worker_daemon.py socket
```

### 查看实时日志

```bash
# 守护进程会将日志输出到 stderr
python3 worker_daemon.py socket 2>&1 | tee daemon.log
```

### 测试单个方法

```bash
# 健康检查
echo '{"jsonrpc":"2.0","id":1,"method":"health","params":{}}' | nc -U /tmp/speekium-daemon.sock

# 获取配置
echo '{"jsonrpc":"2.0","id":2,"method":"get_config","params":{}}' | nc -U /tmp/speekium-daemon.sock

# 模型状态
echo '{"jsonrpc":"2.0","id":3,"method":"model_status","params":{}}' | nc -U /tmp/speekium-daemon.sock
```

## 迁移指南

### 从 stdin/stdout 迁移到 Socket

**旧方式 (stdin/stdout):**
```bash
python3 worker_daemon.py daemon
```

**新方式 (Socket):**
```bash
python3 worker_daemon.py socket
```

**代码变化:**
- ✅ Python 端：无需修改，自动支持
- ⏳ Rust 端：需要实现 Socket 客户端（待完成）

## 下一步

1. ✅ Python Socket 服务器完成
2. ⏳ Rust Socket 客户端实现
3. ⏳ Tauri 集成
4. ⏳ 完整测试
5. ⏳ 移除旧代码

## 文档

- [完整实现指南](socket-implementation-guide.md)
- [集成测试计划](socket-integration-test.md)
- [实现总结](socket-implementation-summary.md)
- [架构设计](socket-ipc-architecture.md)

## 支持

如有问题，请查看文档或提交 Issue。
