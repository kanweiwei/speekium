// Module declarations
mod database;
mod audio;
mod types;
mod state;
mod platform;
mod ui;
mod ptt;
mod daemon;
mod api;
mod shortcuts;
mod commands;
mod db_commands;
mod app;

// Public API
pub use app::run;

// Re-export daemon globals for use in other modules
pub use daemon::{
    DAEMON, DAEMON_READY, PTT_STDERR, STREAMING_IN_PROGRESS,
    PTT_PROCESSING, RECORDING_ABORTED, RECORDING_MODE, WORK_MODE, APP_STATUS,
    CURRENT_PTT_SHORTCUT, PTT_KEY_PRESSED, AUDIO_RECORDER,
    RECORDING_MODE_CHANNEL, APP_HANDLE,
    ensure_daemon_running, is_daemon_ready, call_daemon,
    start_daemon_async, start_ptt_reader, cleanup_daemon,
};
