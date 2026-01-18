//! Daemon Startup and Management
//!
//! This module contains functions for daemon lifecycle management:
//! - Async daemon startup with progress reporting
//! - Daemon health checks
//! - Daemon cleanup

use std::process::{Command, Stdio};
use std::io::{BufReader, BufWriter, BufRead};
use std::sync::atomic::Ordering;
use std::time::{Duration, Instant};

use tauri::{Emitter, Manager};
use crate::types::{DaemonMode, DaemonStatusPayload};

use super::state::{
    DAEMON, DAEMON_READY, PTT_STDERR, STREAMING_IN_PROGRESS,
    APP_HANDLE, WORK_MODE, RECORDING_MODE, AUDIO_RECORDER,
};
use super::process::PythonDaemon;
use super::detector::detect_daemon_mode;

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
    let ready = DAEMON_READY.load(Ordering::Acquire);
    ready
}

/// Call daemon command and wait for response
pub fn call_daemon(command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    // Wait for daemon to be ready (up to 30 seconds)
    let start = Instant::now();
    let timeout = Duration::from_secs(30);

    while !is_daemon_ready() {
        if start.elapsed() > timeout {
            return Err("语音服务启动超时，请重启应用".to_string());
        }
        std::thread::sleep(Duration::from_millis(100));
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
///
/// This allows the UI to show immediately while daemon loads in background.
/// `on_ready` is an optional callback called after daemon is fully initialized.
///
/// # Progress Events
/// - `loading` with "正在启动语音服务..." message
/// - `loading` with various progress messages during model loading
/// - `ready` with "就绪" message when daemon is ready
/// - `error` if startup fails
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

        // Get config directory for daemon
        let config_dir = match app_handle.path().app_data_dir() {
            Ok(dir) => dir,
            Err(e) => {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: format!("无法获取配置目录: {}", e),
                });
                return;
            }
        };

        // Build PATH environment variable
        let current_path = std::env::var("PATH").unwrap_or_default();
        let extra_paths = "/opt/homebrew/bin:/usr/local/bin:/usr/bin";
        let enhanced_path = format!("{}:{}", extra_paths, current_path);

        // Convert config_dir to string for environment variable
        let config_dir_str = config_dir.to_string_lossy().to_string();

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
                    .env("SPEEKIUM_CONFIG_DIR", &config_dir_str)
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
                    .env("SPEEKIUM_CONFIG_DIR", &config_dir_str)
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
        DAEMON_READY.store(true, Ordering::Release);

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
