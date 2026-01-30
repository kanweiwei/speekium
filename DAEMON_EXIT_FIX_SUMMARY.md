# Python Daemon 进程退出问题 - 修复总结

## 问题概述

Python daemon 进程 (worker_daemon.py) 经常出现没有正常退出的情况，导致：
1. 旧进程占用 socket 文件
2. 新应用无法启动（卡在"正在启动语音服务"）
3. 需要手动 `kill -9` 强制终止

## 修复内容

### 1. Python 端：添加信号处理器 ✅

**文件**: `worker_daemon.py`

**修改**:
```python
def handle_sigterm(signum, frame):
    """Handle SIGTERM signal for graceful shutdown"""
    logger.info("sigterm_received", signal=signum, pid=os.getpid())
    sys.exit(0)

def handle_sigint(signum, frame):
    """Handle SIGINT signal for graceful shutdown"""
    logger.info("sigint_received", signal=signum, pid=os.getpid())
    sys.exit(0)

# 注册信号处理器
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigint)

# 注册退出处理器
import atexit
atexit.register(cleanup_on_exit)
```

**效果**: 当 Rust 端发送 SIGTERM 信号时，Python 进程能够优雅退出。

---

### 2. Rust 端：添加清理超时机制 ✅

**文件**: `src-tauri/src/daemon/startup.rs`

**修改**:
```rust
pub fn cleanup_daemon() {
    let mut daemon = DAEMON.lock().unwrap();
    if let Some(mut d) = daemon.take() {
        // Try graceful shutdown via socket command (with timeout)
        let _ = d.send_command("exit", serde_json::json!({}));

        // Wait for process to exit with timeout (5 seconds max)
        let timeout = Duration::from_secs(5);
        let start = Instant::now();

        loop {
            match d.process.try_wait() {
                Ok(Some(_)) => {
                    // Process exited normally
                    break;
                }
                Ok(None) => {
                    // Still running
                    if start.elapsed() > timeout {
                        // Timeout: force kill the process
                        #[cfg(unix)]
                        {
                            let _ = d.process.kill();
                            // Give it a moment to terminate
                            std::thread::sleep(Duration::from_millis(100));
                        }
                        // Force wait after kill
                        let _ = d.process.wait();
                        break;
                    }
                    // Wait a bit and check again
                    std::thread::sleep(Duration::from_millis(100));
                }
                Err(_) => {
                    // Error checking process status, assume it's gone
                    break;
                }
            }
        }
    }
}
```

**效果**: 清理函数不会无限期等待，5秒后强制终止进程。

---

### 3. Rust 端：启动前清理旧进程 ✅

**文件**: `src-tauri/src/daemon/process.rs`

**新增函数**:
```rust
/// Clean up any old daemon processes and socket files before starting a new one
fn cleanup_old_daemons() {
    // Clean up socket files first
    let _ = std::fs::remove_file("/tmp/speekium-daemon.sock");
    let _ = std::fs::remove_file("/tmp/speekium-notif.sock");

    // Try to find and kill old worker_daemon processes
    #[cfg(unix)]
    {
        use std::process::Command;

        // Look for python processes running worker_daemon in socket mode
        let output = Command::new("pgrep")
            .args(&["-f", "python.*worker_daemon.*socket"])
            .output();

        if let Ok(output) = output {
            if output.status.success() {
                let pids = String::from_utf8_lossy(&output.stdout);
                for pid_str in pids.lines() {
                    if let Ok(pid) = pid_str.trim().parse::<u32>() {
                        // Try graceful kill first
                        let _ = Command::new("kill")
                            .arg("-TERM")
                            .arg(pid.to_string())
                            .output();

                        std::thread::sleep(Duration::from_millis(100));

                        // Force kill if still alive
                        let _ = Command::new("kill")
                            .arg("-9")
                            .arg(pid.to_string())
                            .output();
                    }
                }
            }
        }
    }
}
```

**调用位置**: 在 `PythonDaemon::new()` 开始时调用

**效果**: 启动新 daemon 前自动清理旧的进程和 socket 文件。

---

## 验证方法

修复后需要测试的场景：

1. **正常关闭应用** → daemon 正确退出
   ```bash
   # 启动应用
   # 正常关闭应用
   # 检查进程是否退出
   ps aux | grep worker_daemon
   ```

2. **应用崩溃** → daemon 能被下次启动清理
   ```bash
   # 强制退出应用 (kill -9)
   # 重新启动应用
   # 应该能正常启动（不会被卡住）
   ```

3. **连续快速关闭/启动** → 无资源泄漏
   ```bash
   # 多次快速关闭和启动应用
   # 检查是否有多个 worker_daemon 进程
   ps aux | grep worker_daemon
   ```

---

## 临时清理脚本

如果仍然遇到问题，可以使用提供的清理脚本：

```bash
./scripts/cleanup_stuck_daemon.sh
```

或手动执行：
```bash
# 查找旧进程
ps aux | grep "python.*worker_daemon socket"

# 杀掉旧进程
kill -9 <PID>

# 清理 socket 文件
rm -f /tmp/speekium-daemon.sock /tmp/speekium-notif.sock
```

---

## 相关文件

| 文件 | 修改类型 |
|------|----------|
| `worker_daemon.py` | 添加信号处理器和 atexit 处理器 |
| `src-tauri/src/daemon/startup.rs` | 添加 cleanup_daemon 超时机制 |
| `src-tauri/src/daemon/process.rs` | 添加 cleanup_old_daemons 函数 |
| `scripts/cleanup_stuck_daemon.sh` | 新建临时清理脚本 |
| `DAEMON_EXIT_ANALYSIS.md` | 问题分析文档 |
