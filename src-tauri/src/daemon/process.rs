//! Python Daemon Process Management
//!
//! This module contains the PythonDaemon struct which wraps the Python
//! worker daemon process and provides methods for communication.

use std::process::{Command, Stdio, Child, ChildStdin, ChildStdout};
use std::io::{BufReader, BufWriter, Write, BufRead, Read};
use std::sync::atomic::Ordering;

use super::state::{PTT_STDERR, RECORDING_ABORTED};
use super::detector::detect_daemon_mode;

// ============================================================================
// PythonDaemon Struct
// ============================================================================

/// Python daemon process wrapper with stdin/stdout communication
pub struct PythonDaemon {
    pub process: Child,
    pub stdin: BufWriter<ChildStdin>,
    pub stdout: BufReader<ChildStdout>,
}

// ============================================================================
// PythonDaemon Implementation
// ============================================================================

impl PythonDaemon {
    /// Create a new PythonDaemon instance
    ///
    /// This will:
    /// 1. Detect the daemon mode (production/development)
    /// 2. Spawn the daemon process
    /// 3. Wait for initialization (up to 25 seconds)
    /// 4. Return the PythonDaemon instance with stdin/stdout handles
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
                    .arg("daemon")
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
