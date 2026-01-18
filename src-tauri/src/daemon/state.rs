//! Daemon Global State
//!
//! This module contains all global state variables used for daemon management
//! and application coordination.

use std::sync::{Mutex, atomic::AtomicBool};
use std::io::BufReader;

use std::process::ChildStderr;

// ============================================================================
// Global State
// ============================================================================

/// Global daemon instance
pub static DAEMON: Mutex<Option<super::process::PythonDaemon>> = Mutex::new(None);

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
pub static AUDIO_RECORDER: Mutex<Option<crate::audio::AudioRecorder>> = Mutex::new(None);

/// Channel for recording mode changes (cross-thread communication)
pub static RECORDING_MODE_CHANNEL: Mutex<Option<std::sync::mpsc::Sender<String>>> = Mutex::new(None);
