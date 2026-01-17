//! Python Daemon Process Management
//!
//! This module handles the lifecycle and communication with the Python worker daemon
//! that performs ASR, LLM, and TTS operations.

use std::process::{Command, Stdio, Child, ChildStdin, ChildStdout, ChildStderr};
use std::io::{BufReader, BufWriter, Write, BufRead, Read};
use std::sync::{Mutex, atomic::{AtomicBool, Ordering}};

use tauri::{Emitter, Manager};
use crate::types::DaemonMode;
use crate::types::DaemonStatusPayload;

// ============================================================================
// Types and Structs
// ============================================================================

/// Python daemon process wrapper with stdin/stdout communication
pub struct PythonDaemon {
    pub process: Child,
    pub stdin: BufWriter<ChildStdin>,
    pub stdout: BufReader<ChildStdout>,
}

// ============================================================================
// Global State
// ============================================================================

/// Global daemon instance
pub static DAEMON: Mutex<Option<PythonDaemon>> = Mutex::new(None);

/// Daemon ready flag - set to true only after daemon is fully initialized
pub static DAEMON_READY: AtomicBool = AtomicBool::new(false);

/// PTT stderr reader handle
pub static PTT_STDERR: Mutex<Option<BufReader<ChildStderr>>> = Mutex::new(None);

/// Streaming operation flag - prevent health checks from interfering
pub static STREAMING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

/// Global app handle for daemon operations
pub static APP_HANDLE: std::sync::OnceLock<tauri::AppHandle> = std::sync::OnceLock::new();

/// PTT processing flag - prevent overlay from showing during ASR/LLM/TTS processing
pub static PTT_PROCESSING: AtomicBool = AtomicBool::new(false);

/// Recording abort flag - signal to stop current recording
pub static RECORDING_ABORTED: AtomicBool = AtomicBool::new(false);

/// Current recording mode
pub static RECORDING_MODE: Mutex<crate::types::RecordingMode> = Mutex::new(crate::types::RecordingMode::PushToTalk);

/// Current work mode
pub static WORK_MODE: Mutex<crate::types::WorkMode> = Mutex::new(crate::types::WorkMode::Conversation);

/// Application status
pub static APP_STATUS: Mutex<crate::types::AppStatus> = Mutex::new(crate::types::AppStatus::Idle);

/// Current PTT shortcut string (for dynamic update)
pub static CURRENT_PTT_SHORTCUT: Mutex<Option<String>> = Mutex::new(None);

/// PTT key state - prevent key repeat from triggering multiple presses
pub static PTT_KEY_PRESSED: AtomicBool = AtomicBool::new(false);

/// Global audio recorder (Rust-side recording)
pub static AUDIO_RECORDER: Mutex<Option<crate::AudioRecorder>> = Mutex::new(None);

/// Channel for recording mode changes (cross-thread communication)
pub static RECORDING_MODE_CHANNEL: Mutex<Option<std::sync::mpsc::Sender<String>>> = Mutex::new(None);

// ============================================================================
// Daemon Detection
// ============================================================================

/// Detect daemon execution mode based on environment
/// - In production (app bundle): look for sidecar executable
/// - In development: use Python script
pub fn detect_daemon_mode() -> Result<DaemonMode, String> {
    let current_exe = std::env::current_exe()
        .map_err(|e| format!("Failed to get current executable path: {}", e))?;

    let exe_dir = current_exe.parent()
        .ok_or_else(|| "Failed to get executable directory".to_string())?;

    // Check if we're in development mode (executable is in target/debug or target/release)
    let is_dev_mode = current_exe.to_string_lossy().contains("/target/")
        || current_exe.to_string_lossy().contains("\\target\\");

    // In development mode, prioritize Python script for faster iteration
    if is_dev_mode {
        // Check for Python script (development mode)
        // In dev mode, the Tauri binary is in src-tauri/target/debug/
        // The Python script is at project root: ../../../worker_daemon.py
        let dev_script_paths = [
            exe_dir.join("../../../worker_daemon.py"),  // From src-tauri/target/debug/
            exe_dir.join("../../worker_daemon.py"),     // Alternative path
            exe_dir.join("../worker_daemon.py"),        // Original relative path
            std::path::PathBuf::from("worker_daemon.py"),          // Current directory
        ];

        for script_path in dev_script_paths.iter() {
            if let Ok(canonical) = script_path.canonicalize() {
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
            return Ok(DaemonMode::Production { executable_path: sidecar_path.clone() });
        }
    }

    // Fallback: try Python script if not in dev mode but no sidecar found
    if !is_dev_mode {
        let dev_script_paths = [
            exe_dir.join("../../../worker_daemon.py"),
            exe_dir.join("../../worker_daemon.py"),
            exe_dir.join("../worker_daemon.py"),
            std::path::PathBuf::from("worker_daemon.py"),
        ];

        for script_path in dev_script_paths.iter() {
            if let Ok(canonical) = script_path.canonicalize() {
                return Ok(DaemonMode::Development { script_path: canonical });
            }
        }
    }

    // Fallback: try the original relative path (will fail if not found, but provides useful error)
    let fallback_path = exe_dir.join("../worker_daemon.py");
    Ok(DaemonMode::Development { script_path: fallback_path })
}

// ============================================================================
// PythonDaemon Implementation
// ============================================================================

impl PythonDaemon {
    /// Create a new PythonDaemon instance
    pub fn new() -> Result<Self, String> {
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
                // Include _internal directory in PATH for bundled dependencies
                let internal_dir = executable_path.parent()
                    .map(|p| p.join("_internal"))
                    .unwrap_or_default();
                let production_path = format!("{}:{}:{}",
                    internal_dir.display(),
                    extra_paths,
                    current_path
                );

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
                // Try to use venv Python if available (in project root)
                let project_root = script_path.parent().unwrap_or(std::path::Path::new("."));
                let venv_python = project_root.join(".venv/bin/python3");

                let python_cmd = if venv_python.exists() {
                    venv_python
                } else {
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

        while start.elapsed() < timeout {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon exited unexpectedly
                    // Try to read stderr to get the error message
                    if let Some(mut stderr_reader) = PTT_STDERR.lock().unwrap().take() {
                        let mut stderr_content = String::new();
                        if let Ok(_) = stderr_reader.read_to_string(&mut stderr_content) {
                            if !stderr_content.is_empty() {
                            }
                        }
                    }

                    return Err("Daemon exited during initialization".to_string());
                }
                Ok(_) => {
                    // Parse JSON log events
                    if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(event_type) = event.get("event").and_then(|v| v.as_str()) {
                            // Check if this is the "ready" daemon_success event (last init event)
                            if event_type == "daemon_success" {
                                if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                                    if message.contains("就绪") || message.contains("ready") {
                                        initialized = true;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    return Err(format!("Failed to read daemon output: {}", e));
                }
            }
        }

        if !initialized {
            return Err("Daemon initialization timeout (25 seconds)".to_string());
        }

        Ok(PythonDaemon {
            process: child,
            stdin,
            stdout,
        })
    }

    /// Send command to daemon and wait for response
    pub fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
        // Build request
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        // Send to stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        // Read response from stdout, skip log events
        // Daemon log events have "event" field, command responses have "success" field
        loop {
            // Check if recording should be aborted (for continuous mode)
            if RECORDING_ABORTED.load(Ordering::SeqCst) {
                RECORDING_ABORTED.store(false, Ordering::SeqCst);
                return Ok(serde_json::json!({
                    "success": false,
                    "error": "Recording cancelled"
                }));
            }

            let mut line = String::new();
            self.stdout.read_line(&mut line)
                .map_err(|e| {
                    format!("Failed to read response: {}", e)
                })?;

            // Parse JSON
            let result: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| {
                    format!("Failed to parse JSON: {}", e)
                })?;

            // Check if this is a log event (has "event" field)
            if result.get("event").is_some() {
                continue;  // Skip log, continue reading next line
            }

            // This is a command response (has "success" field or other response fields)
            return Ok(result);
        }
    }

    /// Send command without waiting for response (fire-and-forget)
    pub fn send_command_no_wait(&mut self, command: &str, args: serde_json::Value) -> Result<(), String> {
        // Build request
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        // Send to stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        Ok(())
    }

    /// Check if daemon is healthy
    pub fn health_check(&mut self) -> bool {
        match self.send_command("health", serde_json::json!({})) {
            Ok(result) => {
                if let Some(obj) = result.as_object() {
                    let success = obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                    return success;
                }
                false
            }
            Err(_e) => {
                false
            }
        }
    }
}

// ============================================================================
// Daemon Management Functions
// ============================================================================

/// Ensure daemon is running, restart if necessary
pub fn ensure_daemon_running() -> Result<(), String> {
    let mut daemon = DAEMON.lock().unwrap();

    // If daemon exists, check health first
    if let Some(ref mut d) = *daemon {
        // Skip health check during streaming
        if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
            return Ok(());
        }

        if d.health_check() {
            // Daemon is already running and healthy
            // Send ready event to frontend in case it's waiting
            if let Some(handle) = APP_HANDLE.get() {
                let _ = handle.emit("daemon-status", DaemonStatusPayload {
                    status: "ready".to_string(),
                    message: "就绪".to_string(),
                });
            }
            return Ok(());  // Healthy, return directly
        }

        // Unhealthy, terminate and restart
        let _ = d.process.kill();
    }

    // Start new daemon
    *daemon = Some(PythonDaemon::new()?);

    Ok(())
}

/// Check if daemon is ready (for commands to check before execution)
pub fn is_daemon_ready() -> bool {
    let ready = DAEMON_READY.load(std::sync::atomic::Ordering::Acquire);
    ready
}

/// Call daemon command and wait for response
pub fn call_daemon(command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    // Wait for daemon to be ready (up to 30 seconds)
    let start = std::time::Instant::now();
    let timeout = std::time::Duration::from_secs(30);

    while !is_daemon_ready() {
        if start.elapsed() > timeout {
            return Err("语音服务启动超时，请重启应用".to_string());
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    let mut daemon = DAEMON.lock().unwrap();
    let daemon = daemon.as_mut().ok_or("Daemon not available")?;

    daemon.send_command(command, args)
}

/// Cleanup daemon and release resources
pub fn cleanup_daemon() {
    // First, clean up AUDIO_RECORDER to release the microphone
    {
        #[cfg(target_os = "macos")]
        {
            let mut recorder = AUDIO_RECORDER.lock().unwrap();
            if let Some(mut audio_rec) = recorder.take() {
                if audio_rec.is_recording() {
                    let _ = audio_rec.stop_recording();
                }
            }
        }
    }

    // Then clean up the daemon
    let mut daemon = DAEMON.lock().unwrap();
    if let Some(mut d) = daemon.take() {
        // Send exit command
        let _ = d.send_command("exit", serde_json::json!({}));

        // Wait for process to exit
        let _ = d.process.wait();
    }
}

// ============================================================================
// Async Daemon Startup
// ============================================================================

/// Start daemon asynchronously with status events to frontend
/// This allows the UI to show immediately while daemon loads in background
/// `on_ready` is an optional callback called after daemon is fully initialized
pub fn start_daemon_async(app_handle: tauri::AppHandle, on_ready: Option<impl Fn() + Send + Sync + 'static>) {
    std::thread::spawn(move || {
        // Send initial loading status
        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
            status: "loading".to_string(),
            message: "正在启动语音服务...".to_string(),
        });

        // Detect execution mode
        let daemon_mode = match detect_daemon_mode() {
            Ok(mode) => mode,
            Err(e) => {
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
        let mut initialized = false;

        loop {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon exited
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
                                if let Some(work_mode) = crate::types::WorkMode::from_str(work_mode_str) {
                                    *WORK_MODE.lock().unwrap() = work_mode;
                                }
                            }

                            // Sync recording_mode from config to Rust RECORDING_MODE global
                            if let Some(recording_mode_str) = config.get("recording_mode").and_then(|v| v.as_str()) {
                                if let Some(recording_mode) = crate::types::RecordingMode::from_str(recording_mode_str) {
                                    *RECORDING_MODE.lock().unwrap() = recording_mode;
                                }
                            }
                        }
                    }
                    Err(_e) => {
                    }
                }
            }
        }

        // Mark daemon as ready - this allows commands to be executed
        DAEMON_READY.store(true, std::sync::atomic::Ordering::Release);

        // Send ready status to frontend
        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
            status: "ready".to_string(),
            message: "就绪".to_string(),
        });

        // Call on_ready callback if provided (e.g., to register PTT shortcuts)
        if let Some(callback) = on_ready {
            callback();
        }
    });
}

// ============================================================================
// PTT Event Reader
// ============================================================================

/// Start PTT (Push-to-Talk) event reader
/// Listen to Python daemon stderr in background thread, parse PTT events and forward to frontend
pub fn start_ptt_reader(app_handle: tauri::AppHandle) {
    std::thread::spawn(move || {
        loop {
            // Get stderr reader
            let line = {
                let mut ptt_stderr = PTT_STDERR.lock().unwrap();
                if let Some(ref mut stderr) = *ptt_stderr {
                    let mut line = String::new();
                    match stderr.read_line(&mut line) {
                        Ok(0) => {
                            break;
                        }
                        Ok(_) => Some(line),
                        Err(_e) => {
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
                        // Get main window and floating window
                        let main_window = app_handle.get_webview_window("main");
                        let overlay_window = app_handle.get_webview_window("ptt-overlay");

                        // Send state to floating window and control visibility
                        if let Some(ref overlay) = overlay_window {
                            match ptt_event {
                                "listening" => {
                                    // Show overlay in listening state (continuous mode waiting for speech)
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    let _ = overlay.show();
                                    let _ = overlay.emit("ptt-state", "listening");
                                }
                                "detected" => {
                                    // Speech detected, transitioning to recording
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    let _ = overlay.show();
                                    let _ = overlay.emit("ptt-state", "detected");
                                }
                                "recording" => {
                                    let _ = overlay.set_ignore_cursor_events(false);
                                    let _ = overlay.show();
                                    let _ = overlay.emit("ptt-state", "recording");
                                }
                                "processing" => {
                                    let _ = overlay.emit("ptt-state", "processing");
                                }
                                "idle" | "error" => {
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
                                    let _ = window.emit("ptt-state", "listening");
                                }
                                "detected" => {
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
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        let _ = overlay.set_ignore_cursor_events(true);
                                        let _ = overlay.hide();
                                        let _ = overlay.emit("ptt-state", "idle");
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
                                    let _ = window.emit("ptt-state", "error");
                                    if let Some(error) = event.get("error").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-error", error);
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
    });
}
