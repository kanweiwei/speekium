# 问题诊断报告：卡在"正在启动语音服务"阶段

## 问题描述
应用启动时一直显示"正在启动语音服务..."，无法进入就绪状态

---

## 🔍 根本原因分析

### 启动流程

```
Rust 端 (startup.rs)
    │
    ├─> 1. 发送 "loading" 状态 → "正在启动语音服务..."
    │
    ├─> 2. 启动 Python daemon 进程
    │
    ├─> 3. 等待 socket 连接 (最多 120 秒)
    │    │
    │    └─> 每 100ms 尝试连接 /tmp/speekium-daemon.sock
    │
    ├─> 4. 连接成功后，进行 health check
    │    │
    │    └─> 发送 health 请求到 Python
    │
    └─> 5. 等待 health 返回 status="healthy"
         │
         └─> 如果 status="initializing"，继续等待
              (最多 120 秒)

Python 端 (worker_daemon.py)
    │
    ├─> 1. 启动 socket server
    │
    ├─> 2. 进入初始化流程 (initialize)
    │    │
    │    ├─> 加载 VAD 模型 (Silero VAD, ~60MB)
    │    │    │
    │    │    └─> 如果模型不存在，从 torch.hub 下载
    │    │         │
    │    │         └─> 可能遇到 PyTorch Hub 限流 (403 错误)
    │    │              │
    │    │              └─> 等待 15s, 30s, 45s, 60s, 75s...
    │    │
    │    └─> 加载 ASR 模型 (SenseVoice, ~250MB)
    │         │
    │         └─> 如果模型不存在，从 ModelScope 下载
    │
    └─> 3. 初始化完成后，health 返回 status="healthy"
```

---

## ⚠️ 可能导致卡住的原因

### 1. 模型下载问题 (最常见)

**VAD 模型** (torch.hub):
- 首次启动需要从 GitHub/PyTorch Hub 下载 ~60MB
- 可能遇到限流 (403/rate limit)，会自动重试最多 5 次
- 每次重试等待: 15s, 30s, 45s, 60s, 75s
- **最坏情况**: 下载失败 + 重试 = ~4 分钟

**ASR 模型** (ModelScope):
- 首次启动需要从 ModelScope 下载 ~250MB
- 国内网络环境可能较慢
- 下载时间: 1-5 分钟 (取决于网络)

### 2. 网络问题

- PyTorch Hub 访问受限 (需要访问 GitHub)
- ModelScope 连接超时
- 防火墙/代理设置问题

### 3. 超时配置

| 超时类型 | 时间 | 位置 |
|----------|------|------|
| Socket 连接超时 | 120 秒 | `startup.rs:224` |
| Health check 总等待 | 120 秒 | `startup.rs:224` |
| Python 初始化超时 | 60 秒 | `socket_server.py:446` |

### 4. 其他原因

- Python 环境问题 (依赖缺失)
- 配置文件错误
- 系统资源不足

---

## 🛠️ 诊断步骤

### 1. 查看日志

```bash
# 查看应用日志
# macOS: ~/Library/Logs/speekium/
# 或在应用中查看日志文件
```

### 2. 检查模型是否已下载

```bash
# 检查 VAD 模型
ls -la ~/.cache/torch/hub/snakers4_silero-vad/

# 检查 ASR 模型
ls -la ~/.cache/modelscope/iic/sensevoice-small/
```

### 3. 手动测试 Python daemon

```bash
cd /path/to/speekium
python3 worker_daemon.py socket
```

观察输出，查看卡在哪个步骤。

---

## 💡 解决方案

### 方案 1: 等待模型下载 (首次启动)

首次启动需要下载模型:
- VAD 模型: ~60MB
- ASR 模型: ~250MB

**预期等待时间**: 3-10 分钟 (取决于网络速度)

### 方案 2: 手动下载模型

如果网络问题导致自动下载失败，可以手动下载:

**VAD 模型**:
```bash
# 访问 https://pytorch.org/get-started/locally/
# 或使用代理/镜像
```

**ASR 模型**:
```bash
# 从 ModelScope 手动下载
# https://www.modelscope.cn/models/iic/sensevoice-small
```

### 方案 3: 增加超时时间 (已修复)

超时配置已经增加到 120 秒，如果仍不够，可以进一步增加:

```rust
// startup.rs:224
let max_checks = 2400; // 从 1200 增加到 2400 (240 秒)
```

### 方案 4: 使用国内镜像

如果在中国大陆，考虑使用镜像源加速模型下载。

---

## 📊 状态转换

| Python 状态 | Rust 端行为 | UI 显示 |
|-------------|-----------|---------|
| `assistant = None` | health 返回 `initializing` | 继续等待 |
| 模型加载中 | health 返回 `initializing` | 继续等待 |
| 模型加载完成 | health 返回 `healthy` | 显示"就绪" |
| 加载失败 | 返回 error | 显示错误信息 |

---

## ✅ 验证修复

启动完成后，应该看到:

1. UI 状态从 "正在启动语音服务..." → "就绪"
2. 日志显示 "✅ 所有模型加载完成，进入待命状态"
3. 可以正常使用语音功能

---

## 📝 已知问题

| 问题 | 状态 | 修复计划 |
|------|------|----------|
| PyTorch Hub 限流 | 已知 | 添加重试逻辑 (已实现) |
| ModelScope 慢速 | 已知 | 无需修复 |
| 首次启动时间长 | 设计行为 | 添加进度提示 |
