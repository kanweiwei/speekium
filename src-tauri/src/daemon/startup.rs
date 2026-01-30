//! Daemon Startup and Management
//!
//! This module contains functions for daemon lifecycle management:
//! - Async daemon startup with progress reporting
//! - Daemon health checks
//! - Daemon cleanup
//!
//! All communication uses socket-based JSON-RPC protocol.

use std::process::{Command, Stdio};
use std::sync::atomic::Ordering;
use std::time::{Duration, Instant};

use tauri::{Emitter, Manager};
use crate::types::{DaemonMode, DaemonStatusPayload, DownloadProgressPayload};
use crate::ui;

use super::state::{
    DAEMON, DAEMON_READY, STREAMING_IN_PROGRESS,
    APP_HANDLE, WORK_MODE, RECORDING_MODE,
};
use super::process::PythonDaemon;
use super::detector::detect_daemon_mode;
use super::socket_client::{SocketDaemonClient, NotificationListener};
use crate::ptt::handle_ptt_event;

// Include tests module
#[cfg(test)]
include!("startup_tests.rs");

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
                    message: ui::get_daemon_message("ready"),
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
    // Wait for daemon to be ready (no timeout - user can see download progress)
    while !is_daemon_ready() {
        std::thread::sleep(Duration::from_millis(100));
    }

    let mut daemon = DAEMON.lock().unwrap();
    let daemon = daemon.as_mut().ok_or("Daemon not available")?;

    daemon.send_command(command, args)
}

/// Cleanup daemon and release resources
///
/// This function attempts graceful shutdown first, then forces kill if needed.
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
                        #[cfg(windows)]
                        {
                            let _ = d.process.kill();
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
/// - `ready` with "就绪" message when daemon is ready
/// - `error` if startup fails
///
/// # Communication
/// All events from daemon (download progress, PTT events) come through socket notifications.
pub fn start_daemon_async(app_handle: tauri::AppHandle, on_ready: Option<impl Fn() + Send + Sync + 'static>) {
    std::thread::spawn(move || {
        // Send initial loading status
        let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
            status: "loading".to_string(),
            message: ui::get_daemon_message("starting"),
        });

        // Detect execution mode
        let daemon_mode = match detect_daemon_mode() {
            Ok(mode) => mode,
            Err(e) => {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "error".to_string(),
                    message: format!("{}: {}", ui::get_daemon_message("startup_failed"), e),
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
                    message: format!("{}: {}", ui::get_daemon_message("config_dir_error"), e),
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

        // CRITICAL: Start notification listener BEFORE spawning Python process
        // This ensures the notification socket is ready when Python daemon tries to connect
        let notification_rx = {
            let mut listener = NotificationListener::with_default_path();
            match listener.start() {
                Ok(rx) => rx,
                Err(e) => {
                    let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                        status: "error".to_string(),
                        message: format!("Failed to start notification listener: {}", e),
                    });
                    return;
                }
            }
        };

        // Build command based on mode
        let child = match daemon_mode {
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
                    .arg("socket")
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
                            message: format!("{}: {}", ui::get_daemon_message("startup_failed"), e),
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
                    .arg("socket")
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
                            message: format!("{}: {}", ui::get_daemon_message("startup_failed"), e),
                        });
                        return;
                    }
                }
            }
        };

        // Get socket path for daemon communication
        let socket_path = SocketDaemonClient::default_socket_path();

        // Wait for daemon initialization with socket health check
        let mut socket_client = SocketDaemonClient::new(socket_path.clone());
        let mut health_check_count = 0;
        let max_checks = 1500; // 150 seconds (1500 * 100ms) - enough for model loading and downloads
        let mut initialized = false;

        while health_check_count < max_checks {
            match socket_client.connect() {
                Ok(_) => {
                    // Connected, try health check
                    if socket_client.health_check() {
                        initialized = true;
                        break;
                    }
                }
                Err(_) => {
                    // Not ready yet, wait and retry
                }
            }
            std::thread::sleep(Duration::from_millis(100));
            health_check_count += 1;

            // Send loading status every 5 seconds
            if health_check_count % 50 == 0 {
                let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                    status: "loading".to_string(),
                    message: ui::get_daemon_message("loading_assistant"),
                });
            }
        }

        if !initialized {
            let _ = app_handle.emit("daemon-status", DaemonStatusPayload {
                status: "error".to_string(),
                message: format!(
                    "{}. {}",
                    ui::get_daemon_message("startup_failed"),
                    "可能原因: 1) 模型正在下载(首次启动) 2) 系统资源不足 3) 配置错误. 请查看日志了解详情"
                ),
            });
            return;
        }

        // Store daemon instance with socket client
        {
            let mut daemon = DAEMON.lock().unwrap();
            *daemon = Some(PythonDaemon {
                process: child,
                socket_client,
            });
        }

        // Spawn thread to handle notifications from the dedicated notification socket
        // (NotificationListener was already started before spawning Python process)
        {
            let app_handle_for_thread = app_handle.clone();
            std::thread::spawn(move || {
                loop {
                    match notification_rx.recv() {
                        Ok(notification) => {
                            if let Some(method) = notification.get("method").and_then(|v| v.as_str()) {
                                match method {
                                    "download_progress" => {
                                        if let Some(params) = notification.get("params") {
                                            let event_type = params.get("event_type")
                                                .and_then(|v| v.as_str())
                                                .unwrap_or("unknown")
                                                .to_string();
                                            let model = params.get("model")
                                                .and_then(|v| v.as_str())
                                                .unwrap_or("Unknown")
                                                .to_string();
                                            let percent = params.get("percent")
                                                .and_then(|v| v.as_i64())
                                                .map(|v| v as u32);
                                            let speed = params.get("speed")
                                                .and_then(|v| v.as_str())
                                                .map(|s| s.to_string());
                                            let total_size = params.get("total_size")
                                                .and_then(|v| v.as_str())
                                                .map(|s| s.to_string());

                                            let _ = app_handle_for_thread.emit("download-progress", DownloadProgressPayload {
                                                event_type,
                                                model,
                                                percent,
                                                speed,
                                                total_size,
                                                downloaded: None,
                                                total: None,
                                            });
                                        }
                                    }
                                    "init_progress" => {
                                        // Handle initialization progress from Python daemon
                                        if let Some(params) = notification.get("params") {
                                            let stage = params.get("stage")
                                                .and_then(|v| v.as_str())
                                                .unwrap_or("unknown")
                                                .to_string();
                                            let message = if let Some(msg_zh) = params.get("message_zh").and_then(|v| v.as_str()) {
                                                msg_zh.to_string()
                                            } else if let Some(msg_en) = params.get("message_en").and_then(|v| v.as_str()) {
                                                msg_en.to_string()
                                            } else {
                                                ui::get_daemon_message("loading")
                                            };

                                            // Forward init progress as daemon-status event
                                            let _ = app_handle_for_thread.emit("daemon-status", DaemonStatusPayload {
                                                status: stage,
                                                message,
                                            });
                                        }
                                    }
                                    "ptt_event" => {
                                        // Handle PTT events
                                        if let Some(params) = notification.get("params") {
                                            if let Some(event_type) = params.get("event_type").and_then(|v| v.as_str()) {
                                                handle_ptt_event(&app_handle_for_thread, event_type, params);
                                            }
                                        }
                                    }
                                    _ => {
                                        // Other notification types can be handled here
                                    }
                                }
                            }
                        }
                        Err(_) => {
                            // Channel closed, exit thread
                            break;
                        }
                    }
                }
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
        // NOTE: We DO NOT send "ready" event here anymore.
        // The "ready" event will be forwarded from Python's init_progress notification
        // when models are actually loaded (VAD, ASR completed).
        DAEMON_READY.store(true, Ordering::Release);

        // Call on_ready callback if provided (e.g., to register PTT shortcuts)
        if let Some(callback) = on_ready {
            callback();
        }
    });
}
