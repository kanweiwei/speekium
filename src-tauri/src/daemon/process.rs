//! Python Daemon Process Management
//!
//! This module contains the PythonDaemon struct which wraps the Python
//! worker daemon process and provides socket-based communication.

use std::process::{Command, Stdio, Child};
use std::sync::atomic::Ordering;
use std::time::Duration;

use super::state::RECORDING_ABORTED;
use super::detector::detect_daemon_mode;
use super::socket_client::SocketDaemonClient;

// ============================================================================
// Helper Functions
// ============================================================================

/// Clean up any old daemon processes and socket files before starting a new one
///
/// This helps prevent issues where:
/// - Old daemon processes are still running
/// - Old socket files block new connections
fn cleanup_old_daemons() {
    // Clean up socket files first (in case processes are already dead)
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
                        // Try to kill the old process gracefully
                        let _ = Command::new("kill")
                            .arg("-TERM")
                            .arg(pid.to_string())
                            .output();

                        // Give it a moment to exit
                        std::thread::sleep(Duration::from_millis(100));

                        // If still alive, force kill
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

// ============================================================================
// PythonDaemon Struct
// ============================================================================

/// Python daemon process wrapper with socket communication
pub struct PythonDaemon {
    pub process: Child,
    pub socket_client: SocketDaemonClient,
}

// ============================================================================
// PythonDaemon Implementation
// ============================================================================

impl PythonDaemon {
    /// Create a new PythonDaemon instance
    ///
    /// This will:
    /// 1. Detect the daemon mode (production/development)
    /// 2. Spawn the daemon process in socket mode
    /// 3. Wait for initialization with health check
    /// 4. Return the PythonDaemon instance with socket client
    pub fn new() -> Result<Self, String> {
        // Clean up any old daemon processes and socket files first
        cleanup_old_daemons();

        // Detect execution mode
        let daemon_mode = detect_daemon_mode()?;

        // Build PATH environment variable
        // Include common paths for potential external tools
        // Note: ffmpeg is no longer needed since we use torchaudio for audio conversion
        let current_path = std::env::var("PATH").unwrap_or_default();
        let extra_paths = "/opt/homebrew/bin:/usr/local/bin:/usr/bin";
        let enhanced_path = format!("{}:{}", extra_paths, current_path);

        // Build command based on mode
        let child = match daemon_mode {
            crate::types::DaemonMode::Production { ref executable_path } => {
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
                    .arg("socket")
                    .env("PATH", production_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| format!("Failed to start sidecar daemon: {} (path: {:?})", e, executable_path))?
            }
            crate::types::DaemonMode::Development { script_path } => {
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
                    .arg("socket")
                    .env("PATH", enhanced_path)
                    .stdin(Stdio::piped())
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .spawn()
                    .map_err(|e| format!("Failed to start Python daemon: {} (python: {:?}, script: {:?})", e, python_cmd, script_path))?
            }
        };

        // Get socket path
        let socket_path = SocketDaemonClient::default_socket_path();

        // Create socket client and wait for daemon to be ready
        let mut socket_client = SocketDaemonClient::new(socket_path.clone());

        // Wait for socket connection and health check
        // No timeout - let it load as long as needed (user can see download progress)
        let max_attempts = 1200; // 120 seconds
        let mut attempts = 0;

        while attempts < max_attempts {
            match socket_client.connect() {
                Ok(_) => {
                    if socket_client.health_check() {
                        break;
                    }
                }
                Err(_) => {
                    // Socket not ready yet, wait and retry
                }
            }
            attempts += 1;
            std::thread::sleep(std::time::Duration::from_millis(100));
        }

        if attempts >= max_attempts {
            return Err("Daemon failed to initialize within timeout".to_string());
        }

        Ok(PythonDaemon {
            process: child,
            socket_client,
        })
    }

    /// Send command to daemon and wait for response
    pub fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
        // Check if recording should be aborted (for continuous mode)
        if RECORDING_ABORTED.load(Ordering::SeqCst) {
            RECORDING_ABORTED.store(false, Ordering::SeqCst);
            return Ok(serde_json::json!({
                "success": false,
                "error": "Recording cancelled"
            }));
        }

        // Use socket-based JSON-RPC communication
        self.socket_client.send_request(command, args)
    }

    /// Send command without waiting for response (fire-and-forget)
    pub fn send_command_no_wait(&mut self, command: &str, args: serde_json::Value) -> Result<(), String> {
        // Use socket-based JSON-RPC notification
        self.socket_client.send_notification(command, args)
    }

    /// Check if daemon is healthy
    pub fn health_check(&mut self) -> bool {
        self.socket_client.health_check()
    }

    /// Get reference to socket client for notification reading
    pub fn socket_client(&mut self) -> &mut SocketDaemonClient {
        &mut self.socket_client
    }
}
