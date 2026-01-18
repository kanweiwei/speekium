//! Python Daemon Process Management
//!
//! This module handles the lifecycle and communication with the Python worker daemon
//! that performs ASR, LLM, and TTS operations.
//!
//! # Module Structure
//!
//! - [`state`] - Global state variables
//! - [`detector`] - Daemon execution mode detection
//! - [`process`] - PythonDaemon struct and communication methods
//! - [`startup`] - Async daemon startup and management functions
//!
//! # Public API
//!
//! The main public exports are:
//! - Global state variables (DAEMON, DAEMON_READY, etc.)
//! - `ensure_daemon_running()` - Ensure daemon is running
//! - `is_daemon_ready()` - Check if daemon is ready
//! - `call_daemon()` - Send command to daemon
//! - `cleanup_daemon()` - Cleanup daemon resources
//! - `start_daemon_async()` - Start daemon asynchronously
//! - `start_ptt_reader()` - Start PTT event reader (re-exported from ptt module)

mod state;
mod detector;
mod process;
mod startup;

// Re-export ptt module for PTT functionality
pub use crate::ptt::start_ptt_reader;

// ============================================================================
// Public API - Global State
// ============================================================================

/// Global daemon instance
pub use state::DAEMON;

/// Daemon ready flag
pub use state::DAEMON_READY;

/// PTT stderr reader handle
pub use state::PTT_STDERR;

/// Streaming operation flag
pub use state::STREAMING_IN_PROGRESS;

/// Global app handle for daemon operations
pub use state::APP_HANDLE;

/// PTT processing flag
pub use state::PTT_PROCESSING;

/// Recording abort flag
pub use state::RECORDING_ABORTED;

/// Current recording mode
pub use state::RECORDING_MODE;

/// Current work mode
pub use state::WORK_MODE;

/// Application status
pub use state::APP_STATUS;

/// Current PTT shortcut string
pub use state::CURRENT_PTT_SHORTCUT;

/// PTT key state
pub use state::PTT_KEY_PRESSED;

/// Global audio recorder
pub use state::AUDIO_RECORDER;

/// Recording mode change channel
pub use state::RECORDING_MODE_CHANNEL;

// ============================================================================
// Public API - Types
// ============================================================================


// ============================================================================
// Public API - Functions
// ============================================================================

/// Ensure daemon is running, restart if necessary
pub use startup::ensure_daemon_running;

/// Check if daemon is ready
pub use startup::is_daemon_ready;

/// Call daemon command and wait for response
pub use startup::call_daemon;

/// Cleanup daemon and release resources
pub use startup::cleanup_daemon;

/// Start daemon asynchronously
pub use startup::start_daemon_async;

