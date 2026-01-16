use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{TrayIconBuilder, TrayIconEvent},
    webview::WebviewWindowBuilder,
    Emitter, Manager, Runtime, State,
};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use std::process::{Command, Stdio, Child, ChildStdin, ChildStdout, ChildStderr};
use std::io::{BufReader, BufWriter, Write, BufRead, Read};
use std::sync::{Mutex, atomic::{AtomicBool, Ordering}};
use std::path::PathBuf;
use serde::{Deserialize, Serialize};

mod database;
mod audio;
use database::{Database, Session, Message, PaginatedResult};
use audio::AudioRecorder;

// ============================================================================
// Data Structures
// ============================================================================

/// Recording mode enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RecordingMode {
    Continuous,
    PushToTalk,
}

impl RecordingMode {
    /// Convert to string representation
    fn as_str(&self) -> &'static str {
        match self {
            RecordingMode::Continuous => "continuous",
            RecordingMode::PushToTalk => "push-to-talk",
        }
    }

    /// Parse from string
    fn from_str(s: &str) -> Option<Self> {
        match s {
            "continuous" => Some(RecordingMode::Continuous),
            "push-to-talk" => Some(RecordingMode::PushToTalk),
            _ => None,
        }
    }
}

/// Work mode enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum WorkMode {
    Conversation,
    TextInput,
}

impl WorkMode {
    /// Convert to string representation
    fn as_str(&self) -> &'static str {
        match self {
            WorkMode::Conversation => "conversation",
            WorkMode::TextInput => "text-input",
        }
    }

    /// Parse from string
    fn from_str(s: &str) -> Option<Self> {
        match s {
            "conversation" => Some(WorkMode::Conversation),
            "text-input" => Some(WorkMode::TextInput),
            _ => None,
        }
    }
}

/// Application status enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AppStatus {
    Idle,              // 空闲状态
    Listening,         // 自动模式监听中
    Recording,         // 录音中
    AsrProcessing,     // ASR识别中
    LlmProcessing,     // LLM思考中
    TtsProcessing,     // TTS生成中
    Playing,           // TTS播放中
}

impl AppStatus {
    /// Convert to string representation
    fn as_str(&self) -> &'static str {
        match self {
            AppStatus::Idle => "idle",
            AppStatus::Listening => "listening",
            AppStatus::Recording => "recording",
            AppStatus::AsrProcessing => "asr",
            AppStatus::LlmProcessing => "llm",
            AppStatus::TtsProcessing => "tts",
            AppStatus::Playing => "playing",
        }
    }

    /// Parse from string
    fn from_str(s: &str) -> Option<Self> {
        match s {
            "idle" => Some(AppStatus::Idle),
            "listening" => Some(AppStatus::Listening),
            "recording" => Some(AppStatus::Recording),
            "asr" => Some(AppStatus::AsrProcessing),
            "llm" => Some(AppStatus::LlmProcessing),
            "tts" => Some(AppStatus::TtsProcessing),
            "playing" => Some(AppStatus::Playing),
            _ => None,
        }
    }

    /// Check if status allows interruption
    /// Priority 1: Mode switch can interrupt all statuses
    /// Priority 2: Manual stop can interrupt recording
    /// Priority 3: App exit waits for recording, interrupts others
    fn can_be_interrupted(&self, interrupt_priority: u8) -> bool {
        match interrupt_priority {
            1 => true,  // Mode switch: can interrupt everything
            2 => matches!(self, AppStatus::Recording | AppStatus::Listening),  // Manual stop
            3 => !matches!(self, AppStatus::Recording),  // App exit: wait for recording
            _ => false,
        }
    }
}

#[derive(Serialize, Deserialize, Debug)]
struct RecordResult {
    success: bool,
    text: Option<String>,
    language: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ChatResult {
    success: bool,
    content: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct TTSResult {
    success: bool,
    audio_path: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ConfigResult {
    success: bool,
    config: Option<serde_json::Value>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct HealthResult {
    success: bool,
    status: Option<String>,
    command_count: Option<u32>,
    models_loaded: Option<serde_json::Value>,
    error: Option<String>,
}

/// Daemon initialization status for frontend
#[derive(Clone, Serialize)]
struct DaemonStatusPayload {
    status: String,   // "loading" | "ready" | "error"
    message: String,  // User-readable status message
}

// ============================================================================
// Python Daemon Manager
// ============================================================================

/// Daemon execution mode
enum DaemonMode {
    /// Development mode: run Python script directly
    Development { script_path: PathBuf },
    /// Production mode: run PyInstaller-bundled executable
    Production { executable_path: PathBuf },
}

/// Detect daemon execution mode based on environment
/// - In production (app bundle): look for sidecar executable
/// - In development: use Python script
fn detect_daemon_mode() -> Result<DaemonMode, String> {
    let current_exe = std::env::current_exe()
        .map_err(|e| format!("Failed to get current executable path: {}", e))?;

    let exe_dir = current_exe.parent()
        .ok_or_else(|| "Failed to get executable directory".to_string())?;

    println!("🔍 检测守护进程模式...");
    println!("   当前可执行文件: {:?}", current_exe);
    println!("   可执行文件目录: {:?}", exe_dir);

    // Check if we're in development mode (executable is in target/debug or target/release)
    let is_dev_mode = current_exe.to_string_lossy().contains("/target/")
        || current_exe.to_string_lossy().contains("\\target\\");

    println!("   开发模式检测: {}", is_dev_mode);

    // In development mode, prioritize Python script for faster iteration
    if is_dev_mode {
        println!("   🔧 开发模式: 优先使用 Python 脚本");

        // Check for Python script (development mode)
        // In dev mode, the Tauri binary is in src-tauri/target/debug/
        // The Python script is at project root: ../../../worker_daemon.py
        let dev_script_paths = [
            exe_dir.join("../../../worker_daemon.py"),  // From src-tauri/target/debug/
            exe_dir.join("../../worker_daemon.py"),     // Alternative path
            exe_dir.join("../worker_daemon.py"),        // Original relative path
            PathBuf::from("worker_daemon.py"),          // Current directory
        ];

        for script_path in dev_script_paths.iter() {
            if let Ok(canonical) = script_path.canonicalize() {
                println!("✅ 开发模式: 找到 Python 脚本");
                println!("   脚本路径: {:?}", canonical);
                return Ok(DaemonMode::Development { script_path: canonical });
            }
        }
    }

    // Check for sidecar executable
    #[cfg(target_os = "windows")]
    let sidecar_name = "worker_daemon.exe";
    #[cfg(not(target_os = "windows"))]
    let sidecar_name = "worker_daemon";

    // Possible sidecar locations:
    // 1. Contents/Resources/worker_daemon/worker_daemon (macOS bundle, onedir mode)
    // 2. ./worker_daemon/worker_daemon (dev/debug, onedir mode)
    // 3. ./worker_daemon (onefile mode or Windows)
    let sidecar_paths = [
        // onedir mode: Resources/worker_daemon/worker_daemon (macOS bundle)
        exe_dir.join("../Resources/worker_daemon").join(sidecar_name),
        // onedir mode: worker_daemon/worker_daemon (dev/debug directory)
        exe_dir.join("worker_daemon").join(sidecar_name),
        // onefile mode: same directory as main exe
        exe_dir.join(sidecar_name),
    ];

    for sidecar_path in sidecar_paths.iter() {
        // Use is_file() to ensure we found an executable, not a directory
        if sidecar_path.is_file() {
            println!("✅ 生产模式: 找到 sidecar 可执行文件");
            println!("   Sidecar 路径: {:?}", sidecar_path);
            return Ok(DaemonMode::Production { executable_path: sidecar_path.clone() });
        }
    }

    // Fallback: try Python script if not in dev mode but no sidecar found
    if !is_dev_mode {
        println!("   ⚠️  未找到 sidecar，尝试使用 Python 脚本");

        let dev_script_paths = [
            exe_dir.join("../../../worker_daemon.py"),
            exe_dir.join("../../worker_daemon.py"),
            exe_dir.join("../worker_daemon.py"),
            PathBuf::from("worker_daemon.py"),
        ];

        for script_path in dev_script_paths.iter() {
            if let Ok(canonical) = script_path.canonicalize() {
                println!("✅ 找到 Python 脚本（备用）");
                println!("   脚本路径: {:?}", canonical);
                return Ok(DaemonMode::Development { script_path: canonical });
            }
        }
    }

    // Fallback: try the original relative path (will fail if not found, but provides useful error)
    println!("⚠️ 开发模式: 使用默认相对路径");
    let fallback_path = exe_dir.join("../worker_daemon.py");
    Ok(DaemonMode::Development { script_path: fallback_path })
}

struct PythonDaemon {
    process: Child,
    stdin: BufWriter<ChildStdin>,
    stdout: BufReader<ChildStdout>,
}

impl PythonDaemon {
    fn new() -> Result<Self, String> {
        println!("🚀 启动 Python 守护进程...");

        // Detect execution mode
        let daemon_mode = detect_daemon_mode()?;

        // Build PATH environment variable
        // Include common paths for potential external tools
        // Note: ffmpeg is no longer needed since we use torchaudio for audio conversion
        let current_path = std::env::var("PATH").unwrap_or_default();
        let extra_paths = "/opt/homebrew/bin:/usr/local/bin:/usr/bin";
        let enhanced_path = format!("{}:{}", extra_paths, current_path);

        // Build command based on mode
        let mut child = match daemon_mode {
            DaemonMode::Production { ref executable_path } => {
                println!("📦 生产模式: 启动 sidecar 可执行文件");
                // Include _internal directory in PATH for bundled dependencies
                let internal_dir = executable_path.parent()
                    .map(|p| p.join("_internal"))
                    .unwrap_or_default();
                let production_path = format!("{}:{}:{}",
                    internal_dir.display(),
                    extra_paths,
                    current_path
                );
                println!("📂 PATH 包含: {}", internal_dir.display());

                Command::new(&executable_path)
                    .arg("daemon")
                    .env("PATH", production_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| format!("Failed to start sidecar daemon: {} (path: {:?})", e, executable_path))?
            }
            DaemonMode::Development { script_path } => {
                println!("🔧 开发模式: 使用 Python 运行脚本");

                // Try to use venv Python if available (in project root)
                let project_root = script_path.parent().unwrap_or(std::path::Path::new("."));
                let venv_python = project_root.join(".venv/bin/python3");

                let python_cmd = if venv_python.exists() {
                    println!("🐍 使用虚拟环境 Python: {:?}", venv_python);
                    venv_python
                } else {
                    println!("🐍 使用系统 Python: python3");
                    std::path::PathBuf::from("python3")
                };

                Command::new(&python_cmd)
                    .arg(&script_path)
                    .arg("daemon")
                    .env("PATH", enhanced_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| format!("Failed to start Python daemon: {} (python: {:?}, script: {:?})", e, python_cmd, script_path))?
            }
        };

        let stdin = BufWriter::new(
            child.stdin.take().ok_or("Failed to get stdin")?
        );
        let mut stdout = BufReader::new(
            child.stdout.take().ok_or("Failed to get stdout")?
        );
        let stderr = BufReader::new(
            child.stderr.take().ok_or("Failed to get stderr")?
        );

        // Store stderr in global variable for PTT event reader
        {
            let mut ptt_stderr = PTT_STDERR.lock().unwrap();
            *ptt_stderr = Some(stderr);
        }

        // Wait for daemon initialization - read stdout until "ready" event
        // Daemon takes ~18s to load all models, set 25s timeout
        use std::time::{Duration, Instant};
        let start = Instant::now();
        let timeout = Duration::from_secs(25);
        let mut initialized = false;

        println!("⏳ 等待守护进程初始化...");

        while start.elapsed() < timeout {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon exited unexpectedly
                    println!("❌ 守护进程在初始化期间退出");

                    // Try to read stderr to get the error message
                    if let Some(mut stderr_reader) = PTT_STDERR.lock().unwrap().take() {
                        let mut stderr_content = String::new();
                        if let Ok(_) = stderr_reader.read_to_string(&mut stderr_content) {
                            if !stderr_content.is_empty() {
                                println!("📛 守护进程错误输出:\n{}", stderr_content);
                            }
                        }
                    }

                    return Err("Daemon exited during initialization".to_string());
                }
                Ok(_) => {
                    // Parse JSON log events
                    if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(event_type) = event.get("event").and_then(|v| v.as_str()) {
                            println!("📋 守护进程事件: {}", event_type);

                            // Check if this is the "ready" daemon_success event (last init event)
                            if event_type == "daemon_success" {
                                if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                                    if message.contains("就绪") || message.contains("ready") {
                                        initialized = true;
                                        println!("✨ 守护进程初始化完成");
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    println!("❌ 读取守护进程输出失败: {}", e);
                    return Err(format!("Failed to read daemon output: {}", e));
                }
            }
        }

        if !initialized {
            println!("❌ 守护进程初始化超时 (25 秒)");
            return Err("Daemon initialization timeout (25 seconds)".to_string());
        }

        println!("✅ Python 守护进程已启动");

        Ok(PythonDaemon {
            process: child,
            stdin,
            stdout,
        })
    }

    fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
        // Build request
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        println!("📤 发送命令: {}", command);

        // Send to stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        println!("⏳ 等待响应...");

        // Read response from stdout, skip log events
        // Daemon log events have "event" field, command responses have "success" field
        loop {
            // Check if recording should be aborted (for continuous mode)
            if RECORDING_ABORTED.load(Ordering::SeqCst) {
                println!("🚫 Recording aborted during wait");
                RECORDING_ABORTED.store(false, Ordering::SeqCst);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": "Recording cancelled"
                }));
            }

            let mut line = String::new();
            self.stdout.read_line(&mut line)
                .map_err(|e| {
                    println!("❌ 读取响应失败: {}", e);
                    format!("Failed to read response: {}", e)
                })?;

            // Parse JSON
            let result: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| {
                    println!("❌ JSON 解析失败: {} | 原始内容: {}", e, line);
                    format!("Failed to parse JSON: {}", e)
                })?;

            // Check if this is a log event (has "event" field)
            if result.get("event").is_some() {
                println!("📋 跳过日志事件: {}", result.get("event").unwrap().as_str().unwrap_or("unknown"));
                continue;  // Skip log, continue reading next line
            }

            // This is a command response (has "success" field or other response fields)
            println!("📥 收到命令响应: {}", line.trim());
            return Ok(result);
        }
    }

    /// Send command without waiting for response (fire-and-forget)
    fn send_command_no_wait(&mut self, command: &str, args: serde_json::Value) -> Result<(), String> {
        // Build request
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        println!("📤 发送命令（不等待响应）: {}", command);

        // Send to stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        println!("✅ 命令已发送（异步模式）");
        Ok(())
    }

    fn health_check(&mut self) -> bool {
        println!("🏥 执行健康检查...");
        match self.send_command("health", serde_json::json!({})) {
            Ok(result) => {
                println!("✅ 健康检查响应: {:?}", result);
                if let Some(obj) = result.as_object() {
                    let success = obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                    println!("🔍 success 字段: {}", success);
                    return success;
                }
                println!("⚠️ 响应不是对象");
                false
            }
            Err(e) => {
                println!("❌ 健康检查失败: {}", e);
                false
            }
        }
    }
}

// Global daemon instance
static DAEMON: Mutex<Option<PythonDaemon>> = Mutex::new(None);

// PTT stderr reader handle
static PTT_STDERR: Mutex<Option<BufReader<ChildStderr>>> = Mutex::new(None);

// Streaming operation flag - prevent health checks from interfering
static STREAMING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

// Current PTT shortcut string (for dynamic update)
static CURRENT_PTT_SHORTCUT: Mutex<Option<String>> = Mutex::new(None);

// PTT key state - prevent key repeat from triggering multiple presses
static PTT_KEY_PRESSED: AtomicBool = AtomicBool::new(false);

// PTT processing flag - prevent overlay from showing during ASR/LLM/TTS processing
static PTT_PROCESSING: AtomicBool = AtomicBool::new(false);

// Recording mode flag - "continuous" or "push-to-talk"
static RECORDING_MODE: Mutex<RecordingMode> = Mutex::new(RecordingMode::PushToTalk);

// Work mode flag - "conversation" or "text-input" (P0-1: Added)
static WORK_MODE: Mutex<WorkMode> = Mutex::new(WorkMode::Conversation);

// Application status (P0-2: Added) - unified state management
static APP_STATUS: Mutex<AppStatus> = Mutex::new(AppStatus::Idle);

// Recording abort flag - signal to stop current recording
static RECORDING_ABORTED: AtomicBool = AtomicBool::new(false);

// Global app handle for shortcut management
static APP_HANDLE: std::sync::OnceLock<tauri::AppHandle> = std::sync::OnceLock::new();

// Global audio recorder (Rust-side recording)
static AUDIO_RECORDER: Mutex<Option<AudioRecorder>> = Mutex::new(None);

fn ensure_daemon_running() -> Result<(), String> {
    let mut daemon = DAEMON.lock().unwrap();

    // If daemon exists, check health first
    if let Some(ref mut d) = *daemon {
        // Skip health check during streaming
        if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
            println!("⏸️ 流式操作进行中，跳过 ensure_daemon 健康检查");
            return Ok(());
        }

        if d.health_check() {
            return Ok(());  // Healthy, return directly
        }

        // Unhealthy, terminate and restart
        println!("⚠️ 守护进程不健康，正在重启...");
        let _ = d.process.kill();
    }

    // Start new daemon
    *daemon = Some(PythonDaemon::new()?);

    Ok(())
}

/// Check if daemon is ready (for commands to check before execution)
fn is_daemon_ready() -> bool {
    let daemon = DAEMON.lock().unwrap();
    let ready = daemon.is_some();
    if !ready {
        println!("⚠️ Daemon not ready: DAEMON is None");
    }
    ready
}

/// Start daemon asynchronously with status events to frontend
/// This allows the UI to show immediately while daemon loads in background
fn start_daemon_async<R: Runtime>(app_handle: tauri::AppHandle<R>) {
    std::thread::spawn(move || {
        println!("🚀 异步启动 Python 守护进程...");

        // Send initial loading status
        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
            status: "loading".to_string(),
            message: "正在启动语音服务...".to_string(),
        });

        // Detect execution mode
        let daemon_mode = match detect_daemon_mode() {
            Ok(mode) => mode,
            Err(e) => {
                println!("❌ 检测守护进程模式失败: {}", e);
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: format!("启动失败: {}", e),
                });
                return;
            }
        };

        // Build PATH environment variable
        let current_path = std::env::var("PATH").unwrap_or_default();
        let extra_paths = "/opt/homebrew/bin:/usr/local/bin:/usr/bin";
        let enhanced_path = format!("{}:{}", extra_paths, current_path);

        // Build command based on mode
        let mut child = match daemon_mode {
            DaemonMode::Production { ref executable_path } => {
                println!("📦 生产模式: 启动 sidecar 可执行文件");
                let internal_dir = executable_path.parent()
                    .map(|p| p.join("_internal"))
                    .unwrap_or_default();
                let production_path = format!("{}:{}:{}",
                    internal_dir.display(),
                    extra_paths,
                    current_path
                );

                match Command::new(&executable_path)
                    .arg("daemon")
                    .env("PATH", production_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                {
                    Ok(child) => child,
                    Err(e) => {
                        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                            status: "error".to_string(),
                            message: format!("启动失败: {}", e),
                        });
                        return;
                    }
                }
            }
            DaemonMode::Development { script_path } => {
                println!("🔧 开发模式: 使用 Python 运行脚本");
                let project_root = script_path.parent().unwrap_or(std::path::Path::new("."));
                let venv_python = project_root.join(".venv/bin/python3");
                let python_cmd = if venv_python.exists() {
                    venv_python
                } else {
                    std::path::PathBuf::from("python3")
                };

                match Command::new(&python_cmd)
                    .arg(&script_path)
                    .arg("daemon")
                    .env("PATH", enhanced_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                {
                    Ok(child) => child,
                    Err(e) => {
                        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                            status: "error".to_string(),
                            message: format!("启动失败: {}", e),
                        });
                        return;
                    }
                }
            }
        };

        // Get stdin/stdout/stderr
        let stdin = match child.stdin.take() {
            Some(s) => BufWriter::new(s),
            None => {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: "无法获取进程输入流".to_string(),
                });
                return;
            }
        };
        let mut stdout = match child.stdout.take() {
            Some(s) => BufReader::new(s),
            None => {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: "无法获取进程输出流".to_string(),
                });
                return;
            }
        };
        let stderr = match child.stderr.take() {
            Some(s) => BufReader::new(s),
            None => {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: "无法获取进程错误流".to_string(),
                });
                return;
            }
        };

        // Store stderr for PTT event reader
        {
            let mut ptt_stderr = PTT_STDERR.lock().unwrap();
            *ptt_stderr = Some(stderr);
        }

        // Wait for daemon initialization with progress updates
        // No timeout - let it load as long as needed
        println!("⏳ 等待守护进程初始化...");
        let mut initialized = false;

        loop {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon exited
                    println!("❌ 守护进程在初始化期间退出");
                    let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                        status: "error".to_string(),
                        message: "语音服务意外退出".to_string(),
                    });
                    return;
                }
                Ok(_) => {
                    // Parse JSON log events and forward status to frontend
                    if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(event_type) = event.get("event").and_then(|v| v.as_str()) {
                            println!("📋 守护进程事件: {}", event_type);

                            // Map daemon events to user-friendly messages
                            let status_message = match event_type {
                                "daemon_initializing" => "正在初始化语音服务...".to_string(),
                                "loading_voice_assistant" => "正在加载语音助手...".to_string(),
                                "loading_asr" | "asr_loaded" => "正在加载语音识别模型...".to_string(),
                                "loading_llm" | "llm_loaded" => "正在加载语言模型...".to_string(),
                                "loading_tts" | "tts_loaded" => "正在加载语音合成模型...".to_string(),
                                "resource_limits_failed" => "资源限制设置失败，继续启动...".to_string(),
                                "daemon_success" => {
                                    if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                                        if message.contains("就绪") || message.contains("ready") {
                                            initialized = true;
                                            "语音服务已就绪".to_string()
                                        } else {
                                            message.to_string()
                                        }
                                    } else {
                                        "初始化成功".to_string()
                                    }
                                }
                                _ => {
                                    // For other events, use message if available
                                    event.get("message")
                                        .and_then(|v| v.as_str())
                                        .unwrap_or("正在加载...")
                                        .to_string()
                                }
                            };

                            // Send progress update to frontend
                            let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                                status: "loading".to_string(),
                                message: status_message,
                            });

                            if initialized {
                                break;
                            }
                        }
                    }
                }
                Err(e) => {
                    println!("❌ 读取守护进程输出失败: {}", e);
                    let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                        status: "error".to_string(),
                        message: format!("读取输出失败: {}", e),
                    });
                    return;
                }
            }
        }

        // Store daemon instance
        {
            let mut daemon = DAEMON.lock().unwrap();
            *daemon = Some(PythonDaemon {
                process: child,
                stdin,
                stdout,
            });
        }

        println!("✅ Python 守护进程已启动");

        // CRITICAL: Load config and sync work_mode/recording_mode to Rust globals
        // This ensures backend state matches config file on startup
        {
            let mut daemon_guard = DAEMON.lock().unwrap();
            if let Some(ref mut daemon) = *daemon_guard {
                match daemon.send_command("config", serde_json::json!({})) {
                    Ok(config_response) => {
                        if let Some(config) = config_response.get("config") {
                            // Sync work_mode from config to Rust WORK_MODE global
                            if let Some(work_mode_str) = config.get("work_mode").and_then(|v| v.as_str()) {
                                if let Some(work_mode) = WorkMode::from_str(work_mode_str) {
                                    let old_mode = *WORK_MODE.lock().unwrap();
                                    *WORK_MODE.lock().unwrap() = work_mode;
                                    println!("🔄 Work mode synced from config: {} → {}", old_mode.as_str(), work_mode.as_str());
                                }
                            }

                            // Sync recording_mode from config to Rust RECORDING_MODE global
                            if let Some(recording_mode_str) = config.get("recording_mode").and_then(|v| v.as_str()) {
                                if let Some(recording_mode) = RecordingMode::from_str(recording_mode_str) {
                                    let old_mode = *RECORDING_MODE.lock().unwrap();
                                    *RECORDING_MODE.lock().unwrap() = recording_mode;
                                    println!("🔄 Recording mode synced from config: {} → {}", old_mode.as_str(), recording_mode.as_str());
                                }
                            }
                        }
                    }
                    Err(e) => {
                        println!("⚠️ Failed to load config during daemon startup: {}", e);
                    }
                }
            }
        }

        // Register PTT shortcut from config (after daemon is ready)
        if let Some(handle) = APP_HANDLE.get() {
            register_ptt_from_config(handle);
        }

        // Send ready status to frontend
        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
            status: "ready".to_string(),
            message: "就绪".to_string(),
        });
    });
}

fn call_daemon(command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    // Check if daemon is ready (don't block waiting for it)
    if !is_daemon_ready() {
        return Err("语音服务正在启动中，请稍候...".to_string());
    }

    let mut daemon = DAEMON.lock().unwrap();
    let daemon = daemon.as_mut().ok_or("Daemon not available")?;

    daemon.send_command(command, args)
}

/// Start PTT (Push-to-Talk) event reader
/// Listen to Python daemon stderr in background thread, parse PTT events and forward to frontend
fn start_ptt_reader<R: Runtime>(app_handle: tauri::AppHandle<R>) {
    std::thread::spawn(move || {
        println!("🎧 PTT 事件读取器启动");

        loop {
            // Get stderr reader
            let line = {
                let mut ptt_stderr = PTT_STDERR.lock().unwrap();
                if let Some(ref mut stderr) = *ptt_stderr {
                    let mut line = String::new();
                    match stderr.read_line(&mut line) {
                        Ok(0) => {
                            println!("🔚 PTT: stderr EOF - 守护进程可能已退出");
                            break;
                        }
                        Ok(_) => Some(line),
                        Err(e) => {
                            println!("❌ PTT: 读取 stderr 失败: {}", e);
                            None
                        }
                    }
                } else {
                    // stderr not ready yet, wait a bit
                    drop(ptt_stderr);
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    continue;
                }
            };

            if let Some(line) = line {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }

                // Try to parse as JSON PTT event
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(ptt_event) = event.get("ptt_event").and_then(|v| v.as_str()) {
                        println!("🎤 PTT 事件: {}", ptt_event);

                        // Get main window and floating window
                        let main_window = app_handle.get_webview_window("main");
                        let overlay_window = app_handle.get_webview_window("ptt-overlay");

                        // Debug: check if overlay window exists
                        if overlay_window.is_none() {
                            println!("⚠️ PTT overlay 窗口不存在！");
                        }

                        // Send state to floating window and control visibility
                        if let Some(ref overlay) = overlay_window {
                            match ptt_event {
                                "listening" => {
                                    // Show overlay in listening state (continuous mode waiting for speech)
                                    println!("🎤 PTT: 显示 overlay (listening)");
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    match overlay.show() {
                                        Ok(_) => println!("✅ overlay.show() 成功"),
                                        Err(e) => println!("❌ overlay.show() 失败: {}", e),
                                    }
                                    let _ = overlay.emit("ptt-state", "listening");
                                }
                                "detected" => {
                                    // Speech detected, transitioning to recording
                                    println!("🎤 PTT: 显示 overlay (detected)");
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    match overlay.show() {
                                        Ok(_) => println!("✅ overlay.show() 成功"),
                                        Err(e) => println!("❌ overlay.show() 失败: {}", e),
                                    }
                                    let _ = overlay.emit("ptt-state", "detected");
                                }
                                "recording" => {
                                    println!("🎤 PTT: 显示 overlay (recording)");
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    match overlay.show() {
                                        Ok(_) => println!("✅ overlay.show() 成功"),
                                        Err(e) => println!("❌ overlay.show() 失败: {}", e),
                                    }
                                    let _ = overlay.emit("ptt-state", "recording");
                                }
                                "processing" => {
                                    println!("🎤 PTT: 处理中，不显示 overlay");
                                    let _ = overlay.emit("ptt-state", "processing");
                                }
                                "idle" | "error" => {
                                    println!("🎤 PTT: 隐藏 overlay");
                                    let _ = overlay.hide();
                                    let _ = overlay.emit("ptt-state", "idle");
                                }
                                _ => {}
                            }
                        }

                        // Send full event to main window
                        if let Some(window) = main_window {
                            match ptt_event {
                                "listening" => {
                                    // Main window also receives listening state
                                    let _ = window.emit("ptt-state", "listening");
                                }
                                "detected" => {
                                    // Main window also receives detected state
                                    let _ = window.emit("ptt-state", "detected");
                                }
                                "recording" => {
                                    let _ = window.emit("ptt-state", "recording");
                                }
                                "processing" => {
                                    let _ = window.emit("ptt-state", "processing");
                                }
                                "idle" => {
                                    let _ = window.emit("ptt-state", "idle");
                                }
                                "user_message" => {
                                    // User speech recognition result - hide overlay, show message
                                    // Set processing flag to prevent overlay from reappearing
                                    PTT_PROCESSING.store(true, Ordering::SeqCst);
                                    println!("🎤 用户消息事件 - 隐藏浮动窗口，设置 PTT_PROCESSING=true");
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        println!("🎤 调用 overlay.hide()");
                                        // First make it ignore cursor events, then hide
                                        let _ = overlay.set_ignore_cursor_events(true);
                                        match overlay.hide() {
                                            Ok(_) => println!("🎤浮动窗口已隐藏"),
                                            Err(e) => println!("❌ 隐藏浮动窗口失败: {}", e),
                                        }
                                        let _ = overlay.emit("ptt-state", "idle");
                                    } else {
                                        println!("⚠️ 浮动窗口不存在");
                                    }
                                    if let Some(text) = event.get("text").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-user-message", text);
                                    }
                                }
                                "assistant_chunk" => {
                                    // LLM streaming response chunk - ensure overlay is hidden
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        let _ = overlay.set_ignore_cursor_events(true);
                                        let _ = overlay.hide();
                                    }
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-chunk", content);
                                    }
                                }
                                "assistant_done" => {
                                    // LLM response complete - ensure overlay is hidden
                                    // Clear processing flag to allow future recordings
                                    PTT_PROCESSING.store(false, Ordering::SeqCst);
                                    println!("🎤 Assistant 完成事件 - 清除 PTT_PROCESSING 标志");
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        let _ = overlay.set_ignore_cursor_events(true);
                                        let _ = overlay.hide();
                                    }
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-done", content);
                                    }
                                }
                                "audio_chunk" => {
                                    // TTS audio chunk
                                    let audio_path = event.get("audio_path").and_then(|v| v.as_str());
                                    let text = event.get("text").and_then(|v| v.as_str());
                                    if let (Some(path), Some(txt)) = (audio_path, text) {
                                        let _ = window.emit("ptt-audio-chunk", serde_json::json!({
                                            "audio_path": path,
                                            "text": txt
                                        }));
                                    }
                                }
                                "error" => {
                                    // Clear processing flag on error
                                    PTT_PROCESSING.store(false, Ordering::SeqCst);
                                    println!("🎤 PTT 错误事件 - 清除 PTT_PROCESSING 标志");
                                    let _ = window.emit("ptt-state", "error");
                                    if let Some(error) = event.get("error").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-error", error);
                                    }
                                }
                                _ => {
                                    println!("⚠️ PTT: 未知事件类型: {}", ptt_event);
                                }
                            }
                        }
                    }
                } else {
                    // Not a PTT event JSON, output as regular log
                    println!("📋 daemon stderr: {}", line);
                }
            }
        }

        println!("🛑 PTT 事件读取器退出");
    });
}

// ============================================================================
// App State (for Database)
// ============================================================================

pub struct AppState {
    pub db: Database,
}

// ============================================================================
// Text Input Commands (macOS)
// ============================================================================

#[cfg(target_os = "macos")]
fn char_to_key_code(ch: char) -> Option<u16> {
    // macOS virtual key codes
    // Reference: https://cdecl.org/wiki/Virtual_Key_Codes
    match ch {
        // Letters (A-Z) - all map to same key code, shift determines case
        'a'..='z' | 'A'..='Z' => Some(0),  // kVK_ANSI_A

        // Numbers (0-9)
        '0' => Some(29),  // kVK_ANSI_0
        '1'..='9' => Some(((ch as u8) - (b'1') + 18) as u16),  // kVK_ANSI_1 through kVK_ANSI_9

        // Special characters
        ' ' => Some(49),   // kVK_Space
        '\n' | '\r' => Some(36),  // kVK_Return
        '\t' => Some(48),  // kVK_Tab
        '.' => Some(47),   // kVK_ANSI_Period
        ',' => Some(43),   // kVK_ANSI_Comma
        '?' => Some(44),   // kVK_ANSI_Slash (with shift)
        '!' => Some(18),   // kVK_ANSI_1 (with shift)
        '@' => Some(19),   // kVK_ANSI_2 (with shift)
        '#' => Some(20),   // kVK_ANSI_3 (with shift)
        '$' => Some(21),   // kVK_ANSI_4 (with shift)
        '%' => Some(23),   // kVK_ANSI_5 (with shift)
        '^' => Some(22),   // kVK_ANSI_6 (with shift)
        '&' => Some(26),   // kVK_ANSI_7 (with shift)
        '*' => Some(28),   // kVK_ANSI_8 (with shift)
        '(' => Some(25),   // kVK_ANSI_9 (with shift)
        ')' => Some(29),   // kVK_ANSI_0 (with shift)
        '-' => Some(27),   // kVK_ANSI_Minus
        '_' => Some(27),   // kVK_ANSI_Minus (with shift)
        '=' => Some(24),   // kVK_ANSI_Equal
        '+' => Some(24),   // kVK_ANSI_Equal (with shift)
        '[' => Some(33),   // kVK_ANSI_LeftBracket
        ']' => Some(30),   // kVK_ANSI_RightBracket
        '{' => Some(33),   // kVK_ANSI_LeftBracket (with shift)
        '}' => Some(30),   // kVK_ANSI_RightBracket (with shift)
        '\\' => Some(42),  // kVK_ANSI_Backslash
        '|' => Some(42),   // kVK_ANSI_Backslash (with shift)
        ';' => Some(41),   // kVK_ANSI_Semicolon
        ':' => Some(41),   // kVK_ANSI_Semicolon (with shift)
        '\'' => Some(39),  // kVK_ANSI_Quote
        '"' => Some(39),   // kVK_ANSI_Quote (with shift)
        '`' => Some(50),   // kVK_ANSI_Grave
        '~' => Some(50),   // kVK_ANSI_Grave (with shift)
        '/' => Some(44),   // kVK_ANSI_Slash
        '<' => Some(43),   // kVK_ANSI_Comma (with shift)
        '>' => Some(47),   // kVK_ANSI_Period (with shift)

        _ => None,  // Unsupported character
    }
}

#[cfg(target_os = "macos")]
fn type_text(text: &str) -> Result<(), String> {
    use cocoa::appkit::NSPasteboard;
    use cocoa::base::{id, nil};
    use cocoa::foundation::NSString as CFString;
    use core_graphics::event::{CGEvent, CGEventTapLocation, CGEventFlags};
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use objc::{msg_send, sel, sel_impl, class};

    println!("⌨️  使用剪贴板输入文字: {}", text);

    // 1. Save current clipboard content
    let pasteboard: id = unsafe { msg_send![class!(NSPasteboard), generalPasteboard] };

    // Use NSPasteboardTypeString constant
    let pasteboard_type = unsafe { CFString::alloc(nil).init_str("public.utf8-plain-text") };
    let old_content: id = unsafe { msg_send![pasteboard, stringForType: pasteboard_type] };

    println!("📋 已保存旧剪贴板内容");

    // Define clipboard restoration function
    let restore_clipboard = || -> Result<(), String> {
        if old_content != nil {
            unsafe {
                let _: () = msg_send![pasteboard, clearContents];
                let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
                let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
                let success: bool = msg_send![pasteboard, setString: old_content forType: pasteboard_type];

                if !success {
                    eprintln!("⚠️  警告：剪贴板恢复失败，用户数据可能丢失");
                    return Err("Failed to restore clipboard".to_string());
                }
            }
            println!("🔄 已恢复原剪贴板内容");
        }
        Ok(())
    };

    // 2. Set new content to clipboard
    let ns_string = unsafe { CFString::alloc(nil).init_str(text) };

    unsafe {
        let _: () = msg_send![pasteboard, clearContents];
        let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
        let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
        let success: bool = msg_send![pasteboard, setString: ns_string forType: pasteboard_type];

        if !success {
            println!("⚠️  剪贴板设置失败");
            // Attempt to restore clipboard
            let _ = restore_clipboard();
            return Err("Failed to set clipboard content".to_string());
        }
    }

    println!("✅ 已设置新剪贴板内容");

    // 3. Create event source
    let event_source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
        .map_err(|e| format!("Failed to create event source: {:?}", e))?;

    // 4. Simulate Cmd+V keypress
    // Cmd key code is 55 (kVK_Command)
    let cmd_key_code: u16 = 55;
    // V key code is 9 (kVK_ANSI_V)
    let v_key_code: u16 = 9;

    // Press Cmd
    let cmd_down = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, true)
        .map_err(|e| format!("Failed to create Cmd key down event: {:?}", e))?;
    cmd_down.set_flags(CGEventFlags::CGEventFlagCommand);
    cmd_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 Cmd");

    // Press V (with Cmd flag)
    let v_down = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, true)
        .map_err(|e| format!("Failed to create V key down event: {:?}", e))?;
    v_down.set_flags(CGEventFlags::CGEventFlagCommand);
    v_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 V");

    // Release V
    let v_up = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, false)
        .map_err(|e| format!("Failed to create V key up event: {:?}", e))?;
    v_up.set_flags(CGEventFlags::CGEventFlagCommand);
    v_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 V");

    // Release Cmd
    let cmd_up = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, false)
        .map_err(|e| format!("Failed to create Cmd key up event: {:?}", e))?;
    cmd_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 Cmd");

    // Wait for paste to complete
    std::thread::sleep(std::time::Duration::from_millis(50));

    // 5. Restore original clipboard content
    restore_clipboard()?;

    println!("⌨️  文字输入完成");
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn type_text(_text: &str) -> Result<(), String> {
    Err("Text input is only supported on macOS".to_string())
}

#[tauri::command]
async fn type_text_command(text: String) -> Result<String, String> {
    println!("⌨️  Typing text: {} ({} chars)", text, text.chars().count());

    type_text(&text)?;

    Ok(format!("Typed {} characters", text.chars().count()))
}

// ============================================================================
// Database Commands
// ============================================================================

#[tauri::command]
async fn db_create_session(
    state: State<'_, AppState>,
    title: String,
) -> Result<Session, String> {
    state.db.create_session(title)
}

#[tauri::command]
async fn db_list_sessions(
    state: State<'_, AppState>,
    page: i32,
    page_size: i32,
    filter_favorite: Option<bool>,
) -> Result<PaginatedResult<Session>, String> {
    state.db.list_sessions_filtered(page, page_size, filter_favorite)
}

#[tauri::command]
async fn db_get_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<Session, String> {
    state.db.get_session(&session_id)
}

#[tauri::command]
async fn db_toggle_favorite(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.toggle_favorite(&session_id)
}

#[tauri::command]
async fn db_update_session(
    state: State<'_, AppState>,
    session_id: String,
    title: String,
) -> Result<Session, String> {
    state.db.update_session(&session_id, title)
}

#[tauri::command]
async fn db_delete_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.delete_session(&session_id)
}

#[tauri::command]
async fn db_add_message(
    state: State<'_, AppState>,
    session_id: String,
    role: String,
    content: String,
) -> Result<Message, String> {
    state.db.add_message(&session_id, &role, &content)
}

#[tauri::command]
async fn db_get_messages(
    state: State<'_, AppState>,
    session_id: String,
    page: i32,
    page_size: i32,
) -> Result<PaginatedResult<Message>, String> {
    state.db.get_messages(&session_id, page, page_size)
}

#[tauri::command]
async fn db_delete_message(
    state: State<'_, AppState>,
    message_id: String,
) -> Result<bool, String> {
    state.db.delete_message(&message_id)
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn record_audio(app_handle: tauri::AppHandle, mode: String, duration: Option<String>) -> Result<RecordResult, String> {
    // Block recording during streaming operations (TTS, chat streaming)
    if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
        println!("⏸️ Recording blocked: streaming operation in progress");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording blocked: streaming in progress".to_string()),
        });
    }

    // Check if recording should be aborted
    if RECORDING_ABORTED.load(Ordering::SeqCst) {
        println!("🚫 Recording aborted by mode change");
        RECORDING_ABORTED.store(false, Ordering::SeqCst);
        // Send idle state to hide floating window
        emit_ptt_state(&app_handle, "idle");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording cancelled".to_string()),
        });
    }

    // Check if recording mode matches
    let current_mode = *RECORDING_MODE.lock().unwrap();
    let is_continuous_mode = mode == "continuous";

    if is_continuous_mode && current_mode != RecordingMode::Continuous {
        println!("🚫 Continuous recording aborted (mode changed to {})", current_mode.as_str());
        // Send idle state to hide floating window
        emit_ptt_state(&app_handle, "idle");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording mode changed".to_string()),
        });
    }

    // 🔧 Additional check: if switching FROM continuous, abort immediately
    if !is_continuous_mode && current_mode == RecordingMode::Continuous {
        // Just switched from continuous to push-to-talk
        // Check if there's a recording in progress by checking the abort flag
        if RECORDING_ABORTED.load(Ordering::SeqCst) {
            println!("🚫 Recording aborted (mode changed from continuous)");
            emit_ptt_state(&app_handle, "idle");
            return Ok(RecordResult {
                success: false,
                text: None,
                language: None,
                error: Some("Recording cancelled".to_string()),
            });
        }
    }

    // Handle duration parameter: support numeric string, "auto", or empty
    let duration_val = match duration {
        Some(d) => {
            if d == "auto" {
                3.0  // "auto" 默认为 3 秒
            } else {
                d.parse::<f32>().unwrap_or(3.0)
            }
        },
        None => 3.0
    };

    let args = serde_json::json!({
        "mode": mode,
        "duration": duration_val
    });

    println!("🎤 调用守护进程: record {} (current mode: {})", args, current_mode.as_str());

    // Send recording start state to all windows (unified state sync)
    emit_ptt_state(&app_handle, "recording");

    let result = call_daemon("record", args);

    // Send processing state
    emit_ptt_state(&app_handle, "processing");

    // Handle result
    let parsed_result = result.and_then(|r| {
        serde_json::from_value(r)
            .map_err(|e| format!("Failed to parse result: {}", e))
    });

    // Send idle state
    emit_ptt_state(&app_handle, "idle");

    parsed_result
}

/// Set recording mode (continuous or push-to-talk)
#[tauri::command]
fn set_recording_mode(mode: String) -> Result<(), String> {
    println!("🎛️ Setting recording mode to: {}", mode);

    // Parse mode from string
    let new_mode = RecordingMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid recording mode: {}", mode))?;

    // Update global recording mode
    *RECORDING_MODE.lock().unwrap() = new_mode;

    // Clear or set abort flag based on mode
    if new_mode == RecordingMode::Continuous {
        // Switching to continuous: clear abort flag to allow new recordings
        RECORDING_ABORTED.store(false, Ordering::SeqCst);
        println!("✅ Cleared abort flag (switched to continuous)");
    } else {
        // Switching away from continuous: abort any ongoing recording
        RECORDING_ABORTED.store(true, Ordering::SeqCst);
        println!("🛑 Aborting continuous recording (switched to {})", new_mode.as_str());

        // 🔧 Fix: Send interrupt signal asynchronously to avoid blocking UI
        // Use try_lock to prevent deadlock
        if let Ok(mut daemon_guard) = DAEMON.try_lock() {
            if let Some(ref mut daemon) = *daemon_guard {
                match daemon.send_command_no_wait("interrupt", serde_json::json!({"priority": 1})) {
                    Ok(_) => println!("📤 Interrupt signal sent to Python daemon"),
                    Err(e) => println!("❌ Failed to send interrupt: {}", e),
                }
            }
        } else {
            println!("⚠️ Daemon busy, interrupt signal deferred (will be picked up by next recording check)");
        }
    }

    Ok(())
}

/// Get current work mode
#[tauri::command]
fn get_work_mode() -> Result<String, String> {
    let mode = *WORK_MODE.lock().unwrap();
    Ok(mode.as_str().to_string())
}

/// Set work mode (conversation or text-input)
#[tauri::command]
fn set_work_mode(mode: String) -> Result<(), String> {
    println!("🎛️ Setting work mode to: {}", mode);

    // Parse mode from string
    let new_mode = WorkMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid work mode: {}", mode))?;

    // Update global work mode
    let old_mode = *WORK_MODE.lock().unwrap();
    *WORK_MODE.lock().unwrap() = new_mode;

    println!("✅ Work mode changed: {} → {}", old_mode.as_str(), new_mode.as_str());

    Ok(())
}

/// Get current recording mode
#[tauri::command]
fn get_recording_mode() -> Result<String, String> {
    let mode = *RECORDING_MODE.lock().unwrap();
    Ok(match mode {
        RecordingMode::PushToTalk => "push-to-talk".to_string(),
        RecordingMode::Continuous => "continuous".to_string(),
    })
}


/// Get current application status
#[tauri::command]
fn get_app_status() -> Result<String, String> {
    let status = *APP_STATUS.lock().unwrap();
    Ok(status.as_str().to_string())
}

/// Transition application status with validation
fn transition_status(new_status: AppStatus) -> Result<(), String> {
    let current_status = *APP_STATUS.lock().unwrap();

    // Validate transition
    let valid_transition = match (current_status, new_status) {
        // From Idle
        (AppStatus::Idle, AppStatus::Listening) => true,
        (AppStatus::Idle, AppStatus::Recording) => true,

        // From Listening
        (AppStatus::Listening, AppStatus::Recording) => true,  // VAD detected speech
        (AppStatus::Listening, AppStatus::Idle) => true,       // Stop listening

        // From Recording
        (AppStatus::Recording, AppStatus::AsrProcessing) => true,
        (AppStatus::Recording, AppStatus::Idle) => true,       // Recording aborted

        // From ASR
        (AppStatus::AsrProcessing, AppStatus::Idle) => true,    // Text input mode done
        (AppStatus::AsrProcessing, AppStatus::LlmProcessing) => true,  // Conversation mode

        // From LLM
        (AppStatus::LlmProcessing, AppStatus::TtsProcessing) => true,
        (AppStatus::LlmProcessing, AppStatus::Idle) => true,    // TTS disabled or failed

        // From TTS
        (AppStatus::TtsProcessing, AppStatus::Playing) => true,
        (AppStatus::TtsProcessing, AppStatus::Idle) => true,    // TTS failed

        // From Playing
        (AppStatus::Playing, AppStatus::Idle) => true,
        (AppStatus::Playing, AppStatus::Listening) => true,     // Auto mode continues

        // Same status (no-op)
        _ if current_status == new_status => true,

        // Invalid transitions
        _ => false,
    };

    if !valid_transition {
        return Err(format!(
            "Invalid status transition: {} → {}",
            current_status.as_str(),
            new_status.as_str()
        ));
    }

    // Log transition
    if current_status != new_status {
        println!("📊 Status transition: {} → {}", current_status.as_str(), new_status.as_str());
    }

    // Update status
    *APP_STATUS.lock().unwrap() = new_status;

    Ok(())
}

/// Interrupt current operation with priority
#[tauri::command]
fn interrupt_operation(priority: u8) -> Result<String, String> {
    let current_status = *APP_STATUS.lock().unwrap();

    println!("🚨 Interrupt request (priority {}): current status = {}", priority, current_status.as_str());

    if current_status.can_be_interrupted(priority) {
        // Perform interrupt based on current status
        match current_status {
            AppStatus::Recording => {
                RECORDING_ABORTED.store(true, Ordering::SeqCst);
                println!("✅ Recording interrupted (priority {})", priority);
            }
            AppStatus::Listening => {
                // Stop listening logic will be handled by the recording loop
                println!("✅ Listening will stop (priority {})", priority);
            }
            AppStatus::LlmProcessing | AppStatus::TtsProcessing | AppStatus::Playing => {
                // Send interrupt signal to Python daemon
                println!("📤 Sending interrupt signal to Python daemon (priority {})", priority);
                match call_daemon("interrupt", serde_json::json!({"priority": priority})) {
                    Ok(_) => {
                        println!("✅ Interrupt signal sent to Python daemon");
                    }
                    Err(e) => {
                        println!("⚠️ Failed to send interrupt to Python daemon: {}", e);
                        // Continue anyway, as the interrupt flag may have been set elsewhere
                    }
                }
            }
            _ => {
                println!("ℹ️ No interrupt needed for status: {}", current_status.as_str());
            }
        }

        // Transition to Idle based on priority
        if priority <= 2 {
            *APP_STATUS.lock().unwrap() = AppStatus::Idle;
        }

        Ok(format!("Interrupted: {}", current_status.as_str()))
    } else {
        Err(format!(
            "Cannot interrupt status {} with priority {}",
            current_status.as_str(),
            priority
        ))
    }
}

/// Send PTT state to all windows
fn emit_ptt_state(app_handle: &tauri::AppHandle, state: &str) {
    // Send to main window
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // Send to floating window
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // Control floating window visibility
        match state {
            "listening" | "detected" | "recording" | "processing" => {
                // Show overlay for listening, detected, recording, processing states
                // Don't show overlay if PTT processing (ASR/LLM/TTS) is in progress
                if PTT_PROCESSING.load(Ordering::SeqCst) {
                    println!("🚫 PTT 正在处理中，跳过显示浮动窗口 (state: {})", state);
                    return;
                }
                // Recalculate position before showing (in case screen config changed)
                match calculate_overlay_position(app_handle) {
                    Ok((x, y)) => {
                        if let Err(e) = overlay.set_position(tauri::Position::Logical(tauri::LogicalPosition { x, y })) {
                            eprintln!("❌ Failed to set PTT overlay position: {}", e);
                        }
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to calculate PTT overlay position: {}, showing anyway", e);
                    }
                }
                let _ = overlay.set_ignore_cursor_events(false);
                let _ = overlay.show();
            }
            "idle" | "error" => {
                // Force hide overlay - use set_ignore_cursor_events to make it "invisible"
                let _ = overlay.set_ignore_cursor_events(true);
                let _ = overlay.hide();
            }
            _ => {}
        }
    }
}

#[tauri::command]
async fn chat_llm(text: String) -> Result<ChatResult, String> {
    let args = serde_json::json!({
        "text": text
    });

    println!("💬 调用守护进程: chat");

    let result = call_daemon("chat", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn chat_llm_stream(
    window: tauri::Window,
    text: String
) -> Result<(), String> {
    println!("💬 调用守护进程: chat_stream");

    // Set streaming operation flag
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // Handle streaming response in separate thread
    std::thread::spawn(move || {
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                let _ = window.emit("chat-error", "Daemon not available");
                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                return;
            }
        };

        // Send streaming command
        let request = serde_json::json!({
            "command": "chat_stream",
            "args": {"text": text}
        });

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            let _ = window.emit("chat-error", format!("Write error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            let _ = window.emit("chat-error", format!("Flush error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        // Loop to read streaming output
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon may have crashed
                    let _ = window.emit("chat-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_) => {
                    // Parse JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        // Skip log events (have "event" field)
                        if chunk.get("event").is_some() {
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "chunk" => {
                                // Send text chunk to frontend
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-chunk", content);
                                }
                            }
                            "done" => {
                                // Streaming response complete
                                let _ = window.emit("chat-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // Error
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {
                                println!("⚠️ Unknown chunk type: {}", chunk_type);
                            }
                        }
                    }
                }
                Err(e) => {
                    let _ = window.emit("chat-error", format!("Read error: {}", e));
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
async fn chat_tts_stream(
    window: tauri::Window,
    text: String,
    auto_play: Option<bool>
) -> Result<(), String> {
    println!("💬🔊 调用守护进程: chat_tts_stream");

    // Set streaming operation flag
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // Handle streaming response in separate thread
    std::thread::spawn(move || {
        println!("🧵 TTS 流式线程启动");
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                println!("❌ TTS 流式线程：守护进程不可用");
                let _ = window.emit("tts-error", "Daemon not available");
                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                return;
            }
        };

        println!("🔒 TTS 流式线程：已获取守护进程锁");

        // Send streaming command
        let request = serde_json::json!({
            "command": "chat_tts_stream",
            "args": {
                "text": text.clone(),
                "auto_play": auto_play.unwrap_or(true)
            }
        });

        println!("📤 TTS 流式线程：发送命令 - {}", text);

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            println!("❌ TTS 流式线程：写入失败 - {}", e);
            let _ = window.emit("tts-error", format!("Write error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            println!("❌ TTS 流式线程：刷新失败 - {}", e);
            let _ = window.emit("tts-error", format!("Flush error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        println!("✅ TTS 流式线程：命令已发送，开始读取响应...");

        // Loop to read streaming output
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon may have crashed
                    println!("❌ TTS 流式线程：读到 EOF");
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(n) => {
                    println!("📥 TTS 流式线程：读到 {} 字节: {}", n, line.trim());

                    // Parse JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        println!("✅ TTS 流式线程：JSON 解析成功: {:?}", chunk);

                        // Skip log events (have "event" field)
                        if chunk.get("event").is_some() {
                            println!("⏭️ TTS 流式线程：跳过日志事件");
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");
                        println!("🔍 TTS 流式线程：chunk_type = {}", chunk_type);

                        match chunk_type {
                            "text_chunk" => {
                                // Send text chunk to frontend
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-text-chunk", content);
                                }
                            }
                            "audio_chunk" => {
                                // Send audio chunk to frontend
                                if let Some(audio_path) = chunk.get("audio_path").and_then(|v| v.as_str()) {
                                    let text = chunk.get("text").and_then(|v| v.as_str()).unwrap_or("");
                                    let _ = window.emit("tts-audio-chunk", serde_json::json!({
                                        "audio_path": audio_path,
                                        "text": text
                                    }));
                                }
                            }
                            "done" => {
                                // Streaming response complete
                                let _ = window.emit("tts-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // Error
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {
                                println!("⚠️ TTS 流式线程：Unknown chunk type: {}", chunk_type);
                            }
                        }
                    } else {
                        println!("❌ TTS 流式线程：JSON 解析失败，原始内容: {}", line.trim());
                    }
                }
                Err(e) => {
                    println!("❌ TTS 流式线程：读取错误: {}", e);
                    let _ = window.emit("tts-error", format!("Read error: {}", e));
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
async fn generate_tts(text: String) -> Result<TTSResult, String> {
    let args = serde_json::json!({
        "text": text
    });

    println!("🔊 调用守护进程: tts");

    let result = call_daemon("tts", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn load_config() -> Result<ConfigResult, String> {
    println!("⚙️ 调用守护进程: config");

    let result = call_daemon("config", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn save_config(config: serde_json::Value) -> Result<serde_json::Value, String> {
    println!("💾 调用守护进程: save_config, work_mode = {}", config.get("work_mode").and_then(|v| v.as_str()).unwrap_or("MISSING"));

    // Pass config directly, do not re-wrap
    // Frontend already passed { config: updatedConfig }
    // Pass config directly as parameter to Python daemon
    call_daemon("save_config", config)
}

#[tauri::command]
async fn update_hotkey(hotkey_config: serde_json::Value) -> Result<serde_json::Value, String> {
    let display_name = hotkey_config.get("displayName").and_then(|v| v.as_str()).unwrap_or("unknown");
    println!("⌨️  调用守护进程: update_hotkey, hotkey = {}", display_name);

    // Update daemon config
    let result = call_daemon("update_hotkey", hotkey_config.clone())?;

    // Also update Tauri global shortcut
    if let Some(shortcut_str) = hotkey_config_to_shortcut_string(&hotkey_config) {
        if let Some(app_handle) = APP_HANDLE.get() {
            if let Err(e) = register_ptt_shortcut(app_handle, &shortcut_str) {
                println!("❌ 更新 Tauri PTT 快捷键失败: {}", e);
            } else {
                println!("✅ Tauri PTT 快捷键已更新: {}", shortcut_str);
            }
        } else {
            println!("⚠️ APP_HANDLE 未初始化");
        }
    } else {
        println!("⚠️ 无法解析快捷键配置");
    }

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn get_daemon_state() -> Result<serde_json::Value, String> {
    // Get comprehensive daemon state
    println!("📊 调用守护进程: get_daemon_state");

    let result = call_daemon("get_daemon_state", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn daemon_health() -> Result<HealthResult, String> {
    // Check if there is an ongoing streaming operation
    if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
        println!("⏸️ 流式操作进行中，跳过健康检查");
        return Ok(HealthResult {
            success: true,
            status: Some("streaming".to_string()),
            command_count: None,
            models_loaded: None,
            error: None,
        });
    }

    println!("🏥 守护进程健康检查");

    let result = call_daemon("health", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn test_ollama_connection(base_url: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 Ollama 连接: {} ({})", base_url, model);

    // Use reqwest to test Ollama connection directly
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    // Test 1: Check if Ollama service is running
    let tags_url = format!("{}/api/tags", base_url);
    let response = client
        .get(&tags_url)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ Ollama 服务运行正常");

                // Test 2: Check if specified model exists
                let models = resp.json::<serde_json::Value>()
                    .await
                    .map_err(|e| format!("Failed to parse models list: {}", e))?;

                if let Some(models_array) = models.get("models").and_then(|m| m.as_array()) {
                    let model_exists = models_array.iter().any(|m| {
                        m.get("name")
                            .and_then(|n| n.as_str())
                            .map(|n| n.starts_with(&model) || n == model)
                            .unwrap_or(false)
                    });

                    if model_exists {
                        println!("✅ 模型 {} 已安装", model);
                        return Ok(serde_json::json!({
                            "success": true,
                            "message": format!("连接成功，模型 {} 已安装", model)
                        }));
                    } else {
                        println!("⚠️ 模型 {} 未找到", model);
                        return Ok(serde_json::json!({
                            "success": false,
                            "error": format!("模型 {} 未安装，请先运行: ollama pull {}", model, model)
                        }));
                    }
                } else {
                    return Ok(serde_json::json!({
                        "success": false,
                        "error": "无法解析模型列表"
                    }));
                }
            } else {
                println!("❌ Ollama 服务返回错误: {}", resp.status());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("Ollama 服务返回错误状态: {}", resp.status())
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接 Ollama 失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("无法连接到 Ollama 服务: {}", e)
            }));
        }
    }
}

/// Get list of installed Ollama models
#[tauri::command]
async fn list_ollama_models(baseUrl: String) -> Result<Vec<String>, String> {
    println!("📋 获取 Ollama 模型列表: {}", baseUrl);

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let tags_url = format!("{}/api/tags", baseUrl);
    let response = client
        .get(&tags_url)
        .send()
        .await
        .map_err(|e| format!("Failed to connect to Ollama: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("Ollama returned error status: {}", response.status()));
    }

    let data = response.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    let models = data.get("models")
        .and_then(|m| m.as_array())
        .ok_or_else(|| "No models found in response".to_string())?;

    let model_names: Vec<String> = models.iter()
        .filter_map(|m| m.get("name"))
        .filter_map(|n| n.as_str())
        .map(|s| s.to_string())
        .collect();

    println!("✅ 找到 {} 个模型", model_names.len());
    for model in &model_names {
        println!("  - {}", model);
    }

    Ok(model_names)
}

/// Test OpenAI API connection
#[tauri::command]
async fn test_openai_connection(api_key: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 OpenAI 连接: model={}", model);

    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your OpenAI API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    let response = client
        .post("https://api.openai.com/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ OpenAI API 连接成功");
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "OpenAI API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                println!("❌ OpenAI API 错误: {} - {}", status, error_text);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test OpenRouter API connection
#[tauri::command]
async fn test_openrouter_connection(api_key: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 OpenRouter 连接: model={}", model);

    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your OpenRouter API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    let response = client
        .post("https://openrouter.ai/api/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ OpenRouter API 连接成功");
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "OpenRouter API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                println!("❌ OpenRouter API 错误: {} - {}", status, error_text);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test Custom OpenAI-compatible API connection
#[tauri::command]
async fn test_custom_connection(api_key: String, base_url: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 Custom API 连接: url={}, model={}", base_url, model);

    if base_url.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "Base URL is empty. Please enter your custom API URL."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    // Ensure base_url doesn't end with /chat/completions
    let url = if base_url.ends_with("/chat/completions") {
        base_url
    } else {
        format!("{}/chat/completions", base_url.trim_end_matches('/'))
    };

    let mut request = client
        .post(&url)
        .header("Content-Type", "application/json");

    // Only add Authorization header if api_key is provided
    if !api_key.is_empty() {
        request = request.header("Authorization", format!("Bearer {}", api_key));
    }

    let response = request
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ Custom API 连接成功");
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "Custom API connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                println!("❌ Custom API 错误: {} - {}", status, error_text);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

/// Test ZhipuAI API connection
#[tauri::command]
async fn test_zhipu_connection(api_key: String, base_url: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 ZhipuAI 连接: url={}, model={}", base_url, model);

    if api_key.is_empty() {
        return Ok(serde_json::json!({
            "success": false,
            "error": "API Key is empty. Please enter your ZhipuAI API key."
        }));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let payload = serde_json::json!({
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Hi"
            }
        ],
        "max_tokens": 1
    });

    // Ensure base_url doesn't end with /chat/completions
    let url = if base_url.ends_with("/chat/completions") {
        base_url
    } else {
        format!("{}/chat/completions", base_url.trim_end_matches('/'))
    };

    let response = client
        .post(&url)
        .header("Content-Type", "application/json")
        .header("Authorization", format!("Bearer {}", api_key))
        .json(&payload)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ ZhipuAI 连接成功");
                return Ok(serde_json::json!({
                    "success": true,
                    "message": "ZhipuAI connection successful"
                }));
            } else {
                let status = resp.status();
                let error_text = resp.text().await.unwrap_or_else(|_| "Unknown error".to_string());
                println!("❌ ZhipuAI 错误: {} - {}", status, error_text);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("API error: {} - {}", status, error_text)
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("Connection failed: {}", e)
            }));
        }
    }
}

// ============================================================================
// Global Shortcuts
// ============================================================================

/// Send PTT state to all windows (static version for shortcut callbacks)
fn emit_ptt_state_static(app_handle: &tauri::AppHandle, state: &str) {
    // Send to main window
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // Send to floating window
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // Control floating window visibility
        match state {
            "listening" | "detected" | "recording" | "processing" => {
                // Show overlay for listening, detected, recording, processing states
                let _ = overlay.show();
            }
            "idle" | "error" => {
                let _ = overlay.hide();
            }
            _ => {}
        }
    }
}

/// Convert hotkey config JSON to Tauri shortcut string
/// e.g., {"key": "Digit3", "modifiers": ["CmdOrCtrl"]} -> "CommandOrControl+3"
fn hotkey_config_to_shortcut_string(config: &serde_json::Value) -> Option<String> {
    let key = config.get("key")?.as_str()?;
    let modifiers = config.get("modifiers")?.as_array()?;

    let mut parts = Vec::new();

    for modifier in modifiers {
        if let Some(m) = modifier.as_str() {
            match m {
                "CmdOrCtrl" | "CommandOrControl" => parts.push("CommandOrControl"),
                "Shift" => parts.push("Shift"),
                "Alt" | "Option" => parts.push("Alt"),
                "Ctrl" | "Control" => parts.push("Control"),
                _ => {}
            }
        }
    }

    // Convert key code to Tauri format
    let tauri_key = match key {
        // Digits
        "Digit0" => "0",
        "Digit1" => "1",
        "Digit2" => "2",
        "Digit3" => "3",
        "Digit4" => "4",
        "Digit5" => "5",
        "Digit6" => "6",
        "Digit7" => "7",
        "Digit8" => "8",
        "Digit9" => "9",
        // Letters
        k if k.starts_with("Key") => &k[3..],
        // Function keys
        k if k.starts_with("F") && k.len() <= 3 => k,
        // Special keys
        "Space" => "Space",
        "Enter" => "Enter",
        "Escape" => "Escape",
        "Backspace" => "Backspace",
        "Tab" => "Tab",
        "ArrowUp" => "Up",
        "ArrowDown" => "Down",
        "ArrowLeft" => "Left",
        "ArrowRight" => "Right",
        // Punctuation
        "Minus" => "-",
        "Equal" => "=",
        "BracketLeft" => "[",
        "BracketRight" => "]",
        "Backslash" => "\\",
        "Semicolon" => ";",
        "Quote" => "'",
        "Comma" => ",",
        "Period" => ".",
        "Slash" => "/",
        "Backquote" => "`",
        _ => key,
    };

    parts.push(tauri_key);
    Some(parts.join("+"))
}

/// Register or update PTT shortcut
fn register_ptt_shortcut(app_handle: &tauri::AppHandle, shortcut_str: &str) -> Result<(), String> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

    // Unregister old shortcut if exists
    {
        let mut current = CURRENT_PTT_SHORTCUT.lock().unwrap();
        if let Some(ref old_shortcut_str) = *current {
            if let Ok(old_shortcut) = old_shortcut_str.parse::<Shortcut>() {
                let _ = app_handle.global_shortcut().unregister(old_shortcut);
                println!("🔄 注销旧 PTT 快捷键: {}", old_shortcut_str);
            }
        }
        *current = Some(shortcut_str.to_string());
    }

    // Parse and register new shortcut
    let ptt_shortcut: Shortcut = shortcut_str.parse()
        .map_err(|e| format!("Failed to parse shortcut '{}': {:?}", shortcut_str, e))?;

    app_handle.global_shortcut().on_shortcut(ptt_shortcut, move |app, _shortcut, event| {
        match event.state() {
            ShortcutState::Pressed => {
                // Filter out key repeat - only handle first press
                if PTT_KEY_PRESSED.swap(true, Ordering::SeqCst) {
                    // Already pressed, ignore key repeat
                    return;
                }
                println!("🎤 PTT: Key pressed (Tauri)");

                // Start Rust-side audio recording
                {
                    let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                    if recorder_guard.is_none() {
                        match AudioRecorder::new() {
                            Ok(r) => *recorder_guard = Some(r),
                            Err(e) => {
                                println!("❌ Failed to create AudioRecorder: {}", e);
                                return;
                            }
                        }
                    }
                    if let Some(ref mut recorder) = *recorder_guard {
                        if let Err(e) = recorder.start_recording() {
                            println!("❌ Failed to start recording: {}", e);
                            return;
                        }
                    }
                }

                // Emit recording state to frontend
                emit_ptt_state_static(app, "recording");

                // Notify Python daemon (for UI state only, no recording) - async mode
                if let Ok(mut daemon_guard) = DAEMON.lock() {
                    if let Some(ref mut daemon) = *daemon_guard {
                        match daemon.send_command_no_wait("ptt_press", serde_json::json!({})) {
                            Ok(_) => println!("✅ PTT press command sent (async)"),
                            Err(e) => println!("❌ PTT press command failed: {}", e),
                        }
                    }
                }
            }
            ShortcutState::Released => {
                // Reset key state
                PTT_KEY_PRESSED.store(false, Ordering::SeqCst);
                println!("🎤 PTT: Key released (Tauri)");

                // Stop Rust-side audio recording and get audio data
                let audio_data = {
                    let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                    if let Some(ref mut recorder) = *recorder_guard {
                        match recorder.stop_recording() {
                            Ok(data) => Some(data),
                            Err(e) => {
                                println!("❌ Failed to stop recording: {}", e);
                                None
                            }
                        }
                    } else {
                        None
                    }
                };

                // Emit processing state
                emit_ptt_state_static(app, "processing");

                // Send audio file path to Python daemon for ASR (async, don't wait)
                if let Some(audio) = audio_data {
                    println!("📤 Sending audio file ({:.2}s) to Python: {}",
                             audio.duration_secs, audio.file_path);

                    // Determine auto_chat based on work mode (conversation = auto chat, text-input = no chat)
                    let work_mode = *WORK_MODE.lock().unwrap();
                    let auto_chat = work_mode == WorkMode::Conversation;

                    if let Ok(mut daemon_guard) = DAEMON.lock() {
                        if let Some(ref mut daemon) = *daemon_guard {
                            let args = serde_json::json!({
                                "audio_path": audio.file_path,
                                "sample_rate": audio.sample_rate,
                                "duration": audio.duration_secs,
                                "auto_chat": auto_chat,
                                "use_tts": true
                            });
                            println!("🎤 Work mode: {:?}, auto_chat: {}", work_mode, auto_chat);
                            // Use send_command_no_wait to avoid blocking UI
                            match daemon.send_command_no_wait("ptt_audio", args) {
                                Ok(_) => println!("✅ PTT audio command sent (async)"),
                                Err(e) => println!("❌ PTT audio command failed: {}", e),
                            }
                        }
                    }
                } else {
                    // No audio data, just notify daemon (async, don't wait)
                    if let Ok(mut daemon_guard) = DAEMON.lock() {
                        if let Some(ref mut daemon) = *daemon_guard {
                            // Use send_command_no_wait to avoid blocking UI
                            match daemon.send_command_no_wait("ptt_release", serde_json::json!({})) {
                                Ok(_) => println!("✅ PTT release command sent (async)"),
                                Err(e) => println!("❌ PTT release command failed: {}", e),
                            }
                        }
                    }
                }
            }
        }
    }).map_err(|e| format!("Failed to register PTT shortcut: {}", e))?;

    println!("✅ PTT 快捷键已注册: {}", shortcut_str);
    Ok(())
}

fn register_shortcuts<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

    // Register show/hide window shortcut: Command+Shift+Space
    let toggle_shortcut: Shortcut = "CommandOrControl+Shift+Space".parse().unwrap();

    let app_handle = app.clone();
    app.global_shortcut().on_shortcut(toggle_shortcut, move |_app, _shortcut, _event| {
        if let Some(window) = app_handle.get_webview_window("main") {
            if window.is_visible().unwrap_or(false) {
                let _ = window.hide();
            } else {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    }).map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to register toggle shortcut: {}", e)))?;

    // Register Alt+1: Toggle work mode (conversation <-> text-input)
    let work_mode_shortcut: Shortcut = "Alt+1".parse().unwrap();
    app.global_shortcut().on_shortcut(work_mode_shortcut, move |_app, _shortcut, event| {
        // Only trigger on press, not release (to avoid double toggle)
        if event.state() != ShortcutState::Pressed {
            return;
        }

        println!("🔄 工作模式切换快捷键触发 (Alt+1)");

        // Acquire lock, toggle mode, extract name, then release immediately
        let mode_name = {
            let mut work_mode = WORK_MODE.lock().unwrap();
            *work_mode = match *work_mode {
                WorkMode::Conversation => WorkMode::TextInput,
                WorkMode::TextInput => WorkMode::Conversation,
            };
            match *work_mode {
                WorkMode::Conversation => "conversation",
                WorkMode::TextInput => "text-input",
            }
        }; // Lock released here

        println!("✅ 工作模式已切换为: {}", mode_name);

        // Don't save config here to avoid deadlock in shortcut callback thread
        // Frontend polling will detect the change and trigger save
        // Note: Config will be saved by frontend when it detects the mode change
    }).map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to register work mode shortcut: {}", e)))?;

    // Register Alt+2: Toggle recording mode (push-to-talk <-> continuous)
    let recording_mode_shortcut: Shortcut = "Alt+2".parse().unwrap();
    app.global_shortcut().on_shortcut(recording_mode_shortcut, move |_app, _shortcut, event| {
        // Only trigger on press, not release (to avoid double toggle)
        if event.state() != ShortcutState::Pressed {
            return;
        }

        println!("🔄 录音模式切换快捷键触发 (Alt+2)");

        // Acquire lock, toggle mode, extract name, then release immediately
        let mode_name = {
            let mut recording_mode = RECORDING_MODE.lock().unwrap();
            *recording_mode = match *recording_mode {
                RecordingMode::PushToTalk => RecordingMode::Continuous,
                RecordingMode::Continuous => RecordingMode::PushToTalk,
            };
            match *recording_mode {
                RecordingMode::PushToTalk => "push-to-talk",
                RecordingMode::Continuous => "continuous",
            }
        }; // Lock released here

        println!("✅ 录音模式已切换为: {}", mode_name);

        // Don't update daemon or modify shortcuts here to avoid deadlock
        // Frontend polling will detect the change and handle:
        // 1. Saving config
        // 2. Updating daemon recording mode
        // 3. Registering/unregistering PTT shortcut
        // Note: All side effects handled by frontend to avoid lock conflicts
    }).map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to register recording mode shortcut: {}", e)))?;

    println!("✅ 全局快捷键已注册:");
    println!("   • Command+Shift+Space - 显示/隐藏窗口");
    println!("   • Alt+1 - 切换工作模式 (对话模式/文字输入模式)");
    println!("   • Alt+2 - 切换录音模式 (按键录音/连续录音)");

    // PTT shortcut will be registered after daemon starts and config is loaded
    // See register_ptt_from_config() which is called after daemon initialization

    Ok(())
}

/// Register PTT shortcut from daemon config
fn register_ptt_from_config(app_handle: &tauri::AppHandle) {
    // Check current recording mode - only register PTT shortcut in push-to-talk mode
    // IMPORTANT: Release the lock immediately after checking to avoid deadlock
    let should_register = {
        let recording_mode = RECORDING_MODE.lock().unwrap();
        *recording_mode != RecordingMode::Continuous
    };

    if !should_register {
        println!("⏭️  跳过 PTT 快捷键注册 (当前为连续录音模式)");
        return;
    }

    // Check if recording is in progress - if so, skip to avoid deadlock
    let is_recording = {
        let status = APP_STATUS.lock().unwrap();
        matches!(*status, AppStatus::Recording | AppStatus::Listening)
    };

    if is_recording {
        println!("⏭️  跳过 PTT 快捷键注册 (正在录音)");
        // Use default shortcut without calling daemon
        println!("⚠️ 使用默认 PTT 快捷键: Alt+3");
        let _ = register_ptt_shortcut(app_handle, "Alt+3");
        return;
    }

    // Try to get daemon lock with timeout - if can't get it, skip daemon call
    // Use try_lock to avoid blocking
    if let Ok(mut daemon_guard) = DAEMON.try_lock() {
        if let Some(ref mut daemon) = *daemon_guard {
            match daemon.send_command("config", serde_json::json!({})) {
                Ok(config_result) => {
                    if let Some(config) = config_result.get("config") {
                        if let Some(hotkey_config) = config.get("push_to_talk_hotkey") {
                            if let Some(shortcut_str) = hotkey_config_to_shortcut_string(hotkey_config) {
                                if let Err(e) = register_ptt_shortcut(app_handle, &shortcut_str) {
                                    println!("❌ 注册 PTT 快捷键失败: {}", e);
                                    // Fallback to default
                                    let _ = register_ptt_shortcut(app_handle, "Alt+3");
                                }
                                return;
                            }
                        }
                    }
                }
                Err(e) => {
                    println!("❌ 获取配置失败: {}", e);
                }
            }
        }
    } else {
        println!("⚠️ 无法获取 daemon 锁，使用默认 PTT 快捷键");
    }

    // Fallback to default shortcut
    println!("⚠️ 使用默认 PTT 快捷键: Alt+3");
    if let Err(e) = register_ptt_shortcut(app_handle, "Alt+3") {
        println!("❌ 注册默认 PTT 快捷键失败: {}", e);
    }
}

// ============================================================================
// Tray Icon
// ============================================================================

fn create_tray<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
    // Create menu items
    let show_item = MenuItemBuilder::new("显示窗口").id("show").build(app)?;
    let hide_item = MenuItemBuilder::new("隐藏窗口").id("hide").build(app)?;
    let quit_item = MenuItemBuilder::new("退出").id("quit").build(app)?;

    // Build menu
    let menu = MenuBuilder::new(app)
        .item(&show_item)
        .item(&hide_item)
        .separator()
        .item(&quit_item)
        .build()?;

    // Load tray icon (template icon for macOS menu bar)
    let icon_bytes = include_bytes!("../icons/tray-template.png");
    let icon_image = image::load_from_memory(icon_bytes)
        .expect("Failed to load tray icon");
    let rgba = icon_image.to_rgba8();
    let (width, height) = rgba.dimensions();
    let tray_icon = Image::new_owned(rgba.into_raw(), width, height);

    // Create tray icon
    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .icon(tray_icon)
        .icon_as_template(true)
        .tooltip("Speekium")
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "hide" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }
            "quit" => {
                // Clean up daemon
                cleanup_daemon();
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { .. } = event {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}

// ============================================================================
// Cleanup
// ============================================================================

fn cleanup_daemon() {
    println!("🧹 清理守护进程...");

    let mut daemon = DAEMON.lock().unwrap();
    if let Some(mut d) = daemon.take() {
        // Send exit command
        let _ = d.send_command("exit", serde_json::json!({}));

        // Wait for process to exit
        let _ = d.process.wait();

        println!("✅ 守护进程已关闭");
    }
}

// ============================================================================
// PTT Overlay Window
// ============================================================================

// PTT Overlay window constants
const OVERLAY_WIDTH: f64 = 140.0;
const OVERLAY_HEIGHT: f64 = 50.0;
const BOTTOM_MARGIN: f64 = 60.0;

/// Calculate PTT overlay window position based on current screen size
fn calculate_overlay_position<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(f64, f64), Box<dyn std::error::Error>> {
    let monitor = app.primary_monitor()?.ok_or_else(|| Box::<dyn std::error::Error>::from("No primary monitor found"))?;
    let screen_size = monitor.size();
    let scale_factor = monitor.scale_factor();

    // Validate scale factor
    if scale_factor <= 0.0 {
        return Err(format!("Invalid scale factor: {}", scale_factor).into());
    }

    // Calculate scaled screen dimensions
    let scaled_width = screen_size.width as f64 / scale_factor;
    let scaled_height = screen_size.height as f64 / scale_factor;

    // Calculate bottom center position with boundary validation
    let x = (scaled_width / 2.0 - OVERLAY_WIDTH / 2.0).max(0.0);
    let y = (scaled_height - OVERLAY_HEIGHT - BOTTOM_MARGIN).max(0.0);

    // Final boundary check
    if x + OVERLAY_WIDTH > scaled_width || y + OVERLAY_HEIGHT > scaled_height {
        eprintln!("⚠️ Warning: Calculated PTT overlay position may exceed screen bounds");
    }

    Ok((x, y))
}

fn create_ptt_overlay<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    // Calculate initial position
    let (x, y) = calculate_overlay_position(app)?;
    println!("🔧 创建 PTT overlay 窗口，位置: ({}, {})", x, y);

    // Create PTT floating window (transparent window)
    let overlay = WebviewWindowBuilder::new(
        app,
        "ptt-overlay",
        tauri::WebviewUrl::App("ptt-overlay.html".into())
    )
    .title("PTT Status")
    .inner_size(OVERLAY_WIDTH, OVERLAY_HEIGHT)
    .position(x, y)
    .always_on_top(true)
    .decorations(false)
    .resizable(false)
    .skip_taskbar(true)
    .focused(false)
    .visible(false)
    .transparent(true)
    .shadow(false)  // Disable window shadow for better transparency
    .build()?;

    println!("✅ PTT 浮动窗口已创建 ({}x{} @ {}, {})", OVERLAY_WIDTH, OVERLAY_HEIGHT, x, y);
    println!("🔍 Overlay label: {:?}", overlay.label());

    // Verify window can be retrieved immediately after creation
    if let Some(retrieved) = app.get_webview_window("ptt-overlay") {
        println!("✅ 窗口创建后立即检索成功");
    } else {
        println!("❌ 窗口创建后立即检索失败！");
    }

    Ok(())
}

// ============================================================================
// Main Entry Point
// ============================================================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build());

    // Add macOS permissions plugin
    #[cfg(target_os = "macos")]
    {
        builder = builder.plugin(tauri_plugin_macos_permissions::init());
    }

    builder
        .invoke_handler(tauri::generate_handler![
            greet,
            record_audio,
            set_recording_mode,
            get_recording_mode,
            update_recording_mode,
            get_work_mode,
            set_work_mode,
            get_app_status,
            interrupt_operation,
            chat_llm,
            chat_llm_stream,
            chat_tts_stream,
            generate_tts,
            load_config,
            save_config,
            update_hotkey,
            get_daemon_state,
            daemon_health,
            test_ollama_connection,
            list_ollama_models,
            test_openai_connection,
            test_openrouter_connection,
            test_custom_connection,
            test_zhipu_connection,
            type_text_command,
            // Database commands
            db_create_session,
            db_list_sessions,
            db_get_session,
            db_toggle_favorite,
            db_update_session,
            db_delete_session,
            db_add_message,
            db_get_messages,
            db_delete_message
        ])
        .setup(|app| {
            // Initialize AudioRecorder singleton (only once at startup)
            // This triggers microphone permission request on first access
            // cpal 0.17 fixes the repeated permission popup issue
            {
                let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                if recorder_guard.is_none() {
                    match AudioRecorder::new() {
                        Ok(r) => {
                            *recorder_guard = Some(r);
                            println!("✅ AudioRecorder 已初始化");
                        }
                        Err(e) => {
                            println!("⚠️ AudioRecorder 初始化失败: {}", e);
                        }
                    }
                }
            }

            // Initialize database
            let db_path = database::get_database_path(app.handle())
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to get database path: {}", e)))?;

            let db = Database::new(db_path)
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to initialize database: {}", e)))?;

            app.manage(AppState { db });
            println!("✅ 数据库已初始化");

            // Create tray icon
            create_tray(app.handle())?;

            // Register shortcuts
            register_shortcuts(app.handle())?;

            // Store app handle globally for shortcut management
            let _ = APP_HANDLE.set(app.handle().clone());

            // Start daemon asynchronously (non-blocking)
            // This allows the UI to show immediately while daemon loads in background
            // PTT shortcut registration happens after daemon is ready (inside start_daemon_async)
            start_daemon_async(app.handle().clone());

            // Start PTT event reader (listen to Python daemon stderr)
            // This will wait for stderr to be available from daemon
            start_ptt_reader(app.handle().clone());

            // Create PTT floating state window
            if let Err(e) = create_ptt_overlay(app.handle()) {
                println!("⚠️ 创建 PTT 浮动窗口失败: {}", e);
            }

            println!("✅ Speekium 应用已启动 (异步守护进程模式)");

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Prevent window close, hide instead
                api.prevent_close();
                window.hide().unwrap();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            // macOS: Show main window when dock icon is clicked
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen { .. } = &event {
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }

            // Clean up daemon on app exit
            if let tauri::RunEvent::ExitRequested { .. } = &event {
                cleanup_daemon();
            }
        });
}
/// Update recording mode and handle PTT shortcut registration
/// This should be called from frontend when it detects a mode change
/// Note: This does NOT modify RECORDING_MODE state - the shortcut callback already did that
#[tauri::command]
fn update_recording_mode(mode: String) -> Result<(), String> {
    println!("Handling recording mode change: {}", mode);

    // Parse mode
    let current_mode = match mode.as_str() {
        "push-to-talk" => Ok(RecordingMode::PushToTalk),
        "continuous" => Ok(RecordingMode::Continuous),
        _ => Err(format!("Invalid recording mode: {}", mode)),
    }?;

    println!("Processing side effects for mode: {:?}", current_mode);

    // IMPORTANT: Use try_lock to avoid blocking - if daemon is busy, skip the update
    // This is critical because update_recording_mode may be called during recording
    if let Ok(mut daemon_guard) = DAEMON.try_lock() {
        if let Some(ref mut daemon) = *daemon_guard {
            let _ = daemon.send_command_no_wait("set_recording_mode", serde_json::json!({
                "mode": mode
            }));
            println!("Sent recording mode update to daemon");
        }
    } else {
        println!("Daemon busy, skipping recording mode update (will retry on next poll)");
    }

    // Handle PTT shortcut registration/unregistration
    // CRITICAL: Only handle shortcuts when NOT recording to avoid deadlock
    let is_recording = {
        let status = APP_STATUS.lock().unwrap();
        matches!(*status, AppStatus::Recording | AppStatus::Listening)
    };

    if !is_recording {
        if let Some(handle) = APP_HANDLE.get() {
            match current_mode {
                RecordingMode::PushToTalk => {
                    // Register PTT shortcut asynchronously (spawn in background)
                    let handle_clone = handle.clone();
                    std::thread::spawn(move || {
                        register_ptt_from_config(&handle_clone);
                        println!("PTT shortcut registered (switched to push-to-talk)");
                    });
                }
                RecordingMode::Continuous => {
                    // Unregister PTT shortcut
                    let mut current = CURRENT_PTT_SHORTCUT.lock().unwrap();
                    if let Some(ref shortcut_str) = *current {
                        if let Ok(shortcut) = shortcut_str.parse::<Shortcut>() {
                            let _ = handle.global_shortcut().unregister(shortcut);
                            println!("PTT shortcut unregistered (switched to continuous)");
                        }
                    }
                    *current = None;
                }
            }
        }
    } else {
        println!("Skipping PTT shortcut update (recording in progress)");
    }

    Ok(())
}

