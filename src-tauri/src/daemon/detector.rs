//! Daemon Detection Module
//!
//! This module handles detecting the daemon execution mode based on environment:
//! - Production (app bundle): look for sidecar executable
//! - Development: use Python script

use crate::types::DaemonMode;

// ============================================================================
// Daemon Detection
// ============================================================================

/// Detect daemon execution mode based on environment
///
/// # Returns
/// - `DaemonMode::Production` with executable path if sidecar is found
/// - `DaemonMode::Development` with script path if Python script is found
///
/// # Search Paths
/// **Development mode** (when executable is in target/):
/// - `../../../worker_daemon.py`
/// - `../../worker_daemon.py`
/// - `../worker_daemon.py`
/// - `worker_daemon.py` (current directory)
///
/// **Production mode**:
/// - `../Resources/worker_daemon/worker_daemon` (macOS bundle, onedir)
/// - `worker_daemon/worker_daemon` (dev/debug directory, onedir)
/// - `worker_daemon` (onefile or Windows)
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
