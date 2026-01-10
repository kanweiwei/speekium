# Speekium Tauri 架构问题及解决方案

## 问题总结

### 问题 1：为什么使用 HTTP Server？❌ 错误架构

**当前（错误）**:
```
React 前端 → fetch('http://127.0.0.1:8008') → Python HTTP Server (backend_server.py)
```

**为什么错误**：
1. Tauri 提供了原生的 `invoke` 系统，不需要 HTTP
2. HTTP 增加不必要的延迟
3. 需要管理端口、处理 CORS
4. pywebview 需要 HTTP，但 Tauri **不需要**

**原因**：快速原型时直接复用了 pywebview 的 HTTP server代码

###问题 2：界面闪烁、无法停止录音

**根本原因**：阻塞的 HTTP 调用

```typescript
// useTauriAPI.ts:64
await fetchAPI('/api/record', ...)  // 阻塞 3 秒
```

```python
# backend_server.py:52-60
audio = sd.rec(int(3.0 * 16000), ...)
sd.wait()  # 阻塞 3 秒
```

**导致**：
1. 前端等待 3 秒，界面冻结
2. 状态更新导致界面闪烁
3. 无法中断录音（固定 3 秒）
4. 麦克风在录音，但没有进度反馈

## 正确架构：Tauri Invoke + Python Subprocess ✅

```
React 前端 → invoke() → Rust 后端 → subprocess → Python Worker
```

**优势**：
- ✅ 无 HTTP 开销
- ✅ 无端口管理
- ✅ 无 CORS 问题
- ✅ 符合 Tauri 最佳实践
- ✅ 可以实现进度反馈和中断

## 实施步骤

### 1. 创建 Python Worker (`worker.py`)
### 2. 修改 Rust 后端添加 Commands (`lib.rs`)
### 3. 修改前端使用 `invoke` (`useTauriAPI.ts`)
### 4. 停止并清理旧的 HTTP server

详细实现见下文...
