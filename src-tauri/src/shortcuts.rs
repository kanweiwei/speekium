// ============================================================================
// Shortcuts Module - Global Shortcut Management
// ============================================================================

use tauri::{Emitter, Manager, Runtime};
use crate::daemon::{CURRENT_PTT_SHORTCUT, PTT_KEY_PRESSED, AUDIO_RECORDER, DAEMON, RECORDING_MODE_CHANNEL};
use crate::types::{RecordingMode, WorkMode, AppStatus};
use crate::audio::AudioRecorder;
use crate::ui;
use std::sync::atomic::Ordering;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

/// Convert hotkey config JSON to Tauri shortcut string
/// e.g., {"key": "Digit3", "modifiers": ["CmdOrCtrl"]} -> "CommandOrControl+3"
pub fn hotkey_config_to_shortcut_string(config: &serde_json::Value) -> Option<String> {
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
pub fn register_ptt_shortcut(app_handle: &tauri::AppHandle, shortcut_str: &str) -> Result<(), String> {
    // Unregister old shortcut if exists
    {
        let mut current = CURRENT_PTT_SHORTCUT.lock().unwrap();
        if let Some(ref old_shortcut_str) = *current {
            if let Ok(old_shortcut) = old_shortcut_str.parse::<Shortcut>() {
                let _ = app_handle.global_shortcut().unregister(old_shortcut);
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

                // Start Rust-side audio recording
                {
                    let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                    if recorder_guard.is_none() {
                        match AudioRecorder::new() {
                            Ok(r) => *recorder_guard = Some(r),
                            Err(_e) => {
                                return;
                            }
                        }
                    }
                    if let Some(ref mut recorder) = *recorder_guard {
                        if let Err(_e) = recorder.start_recording() {
                            return;
                        }
                    }
                }

                // Emit recording state to frontend
                ui::emit_ptt_state_static(app, "recording");

                // Notify Python daemon (for UI state only, no recording) - async mode
                if let Ok(mut daemon_guard) = DAEMON.lock() {
                    if let Some(ref mut daemon) = *daemon_guard {
                        let _ = daemon.send_command_no_wait("ptt_press", serde_json::json!({}));
                    }
                }
            }
            ShortcutState::Released => {
                // Reset key state
                PTT_KEY_PRESSED.store(false, Ordering::SeqCst);

                // Stop Rust-side audio recording and get audio data
                let audio_data = {
                    let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                    if let Some(ref mut recorder) = *recorder_guard {
                        match recorder.stop_recording() {
                            Ok(data) => Some(data),
                            Err(_e) => {
                                None
                            }
                        }
                    } else {
                        None
                    }
                };

                // Emit processing state
                ui::emit_ptt_state_static(app, "processing");

                // Send audio file path to Python daemon for ASR (async, don't wait)
                if let Some(audio) = audio_data {
                    // Determine auto_chat based on work mode (conversation = auto chat, text-input = no chat)
                    let work_mode = *crate::daemon::WORK_MODE.lock().unwrap();
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
                            // Use send_command_no_wait to avoid blocking UI
                            let _ = daemon.send_command_no_wait("ptt_audio", args);
                        }
                    }
                } else {
                    // No audio data, just notify daemon (async, don't wait)
                    if let Ok(mut daemon_guard) = DAEMON.lock() {
                        if let Some(ref mut daemon) = *daemon_guard {
                            // Use send_command_no_wait to avoid blocking UI
                            let _ = daemon.send_command_no_wait("ptt_release", serde_json::json!({}));
                        }
                    }
                }
            }
        }
    }).map_err(|e| format!("Failed to register PTT shortcut: {}", e))?;

    Ok(())
}

/// Write recording mode directly to config file
/// This bypasses the daemon and allows VAD loop to detect mode changes via config polling
pub fn write_recording_mode_to_config(mode: &str) -> Result<(), Box<dyn std::error::Error>> {
    use crate::daemon::APP_HANDLE;
    use std::path::PathBuf;

    // Get config directory from app_data_dir (same as Python daemon)
    let config_dir = if let Some(app_handle) = APP_HANDLE.get() {
        app_handle.path().app_data_dir()
            .map_err(|e| format!("Failed to get app data dir: {}", e))?
    } else {
        // Fallback if APP_HANDLE not set (shouldn't happen in normal operation)
        #[cfg(target_os = "macos")]
        {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join("Library/Application Support/com.speekium.app")
        }
        #[cfg(target_os = "windows")]
        {
            let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(appdata).join("com.speekium.app")
        }
        #[cfg(target_os = "linux")]
        {
            let xdg = std::env::var("XDG_CONFIG_HOME")
                .unwrap_or_else(|_| format!("{}/.config", std::env::var("HOME").unwrap_or_else(|_| ".".to_string())));
            PathBuf::from(xdg).join("com.speekium.app")
        }
        #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
        {
            PathBuf::from(".")
        }
    };

    let config_path = config_dir.join("config.json");

    // Ensure config directory exists
    std::fs::create_dir_all(&config_dir)?;

    // Read existing config or create default if not exists
    let mut config = if config_path.exists() {
        let config_content = std::fs::read_to_string(&config_path)?;
        serde_json::from_str(&config_content)?
    } else {
        // Create minimal default config
        serde_json::json!({})
    };

    // Update recording_mode
    config["recording_mode"] = serde_json::json!(mode);

    // Write back
    std::fs::write(&config_path, serde_json::to_string_pretty(&config)?)?;

    Ok(())
}

/// Start the recording mode event dispatcher thread
/// This thread listens for mode changes from the channel and emits events to the frontend
pub fn start_recording_mode_dispatcher<R: Runtime>(app: &tauri::AppHandle<R>) {
    use std::sync::mpsc;

    let (tx, rx) = mpsc::channel::<String>();

    // Store the sender in the global static
    *RECORDING_MODE_CHANNEL.lock().unwrap() = Some(tx);

    let app_handle = app.clone();

    // Spawn a thread to listen for mode changes and emit events
    std::thread::spawn(move || {
        while let Ok(mode_str) = rx.recv() {
            // Emit the event to the frontend
            // This is called from a dedicated thread, but emit() is safe here
            // as it handles cross-thread communication internally
            if let Err(_e) = app_handle.emit("recording-mode-changed", &mode_str) {
            }
        }
    });
}

pub fn register_shortcuts<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
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

        // Acquire lock, toggle mode, extract name, then release immediately
        let _mode_name = {
            let mut work_mode = crate::daemon::WORK_MODE.lock().unwrap();
            *work_mode = match *work_mode {
                WorkMode::Conversation => WorkMode::TextInput,
                WorkMode::TextInput => WorkMode::Conversation,
            };
            match *work_mode {
                WorkMode::Conversation => "conversation",
                WorkMode::TextInput => "text-input",
            }
        }; // Lock released here

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

        // Acquire lock, toggle mode, extract name, then release immediately
        let mode_name = {
            let mut recording_mode = crate::daemon::RECORDING_MODE.lock().unwrap();
            *recording_mode = match *recording_mode {
                RecordingMode::PushToTalk => RecordingMode::Continuous,
                RecordingMode::Continuous => RecordingMode::PushToTalk,
            };
            match *recording_mode {
                RecordingMode::PushToTalk => "push-to-talk",
                RecordingMode::Continuous => "continuous",
            }
        }; // Lock released here

        // Write directly to config file to notify VAD loop (bypasses daemon lock)
        if let Err(_e) = write_recording_mode_to_config(mode_name) {
        }

        // Send to channel for cross-thread event dispatch (non-blocking, safe)
        // The dedicated dispatcher thread will emit the event to the frontend
        if let Some(tx) = RECORDING_MODE_CHANNEL.lock().unwrap().as_ref() {
            let _ = tx.send(mode_name.to_string()); // Non-blocking send
        } else {
        }
    }).map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to register recording mode shortcut: {}", e)))?;

    // PTT shortcut will be registered after daemon starts and config is loaded
    // See register_ptt_from_config() which is called after daemon initialization

    Ok(())
}

/// Register PTT shortcut from daemon config
pub fn register_ptt_from_config(app_handle: &tauri::AppHandle) {
    // Check current recording mode - only register PTT shortcut in push-to-talk mode
    // IMPORTANT: Release the lock immediately after checking to avoid deadlock
    let should_register = {
        let recording_mode = crate::daemon::RECORDING_MODE.lock().unwrap();
        *recording_mode != RecordingMode::Continuous
    };

    if !should_register {
        return;
    }

    // Check if recording is in progress - if so, skip to avoid deadlock
    let is_recording = {
        let status = crate::daemon::APP_STATUS.lock().unwrap();
        matches!(*status, AppStatus::Recording | AppStatus::Listening)
    };

    if is_recording {
        // Use default shortcut without calling daemon
        let _ = register_ptt_shortcut(app_handle, "Alt+3");
        return;
    }

    // Try to get daemon lock with timeout - if can't get it, skip daemon call
    // Use try_lock to avoid blocking
    if let Ok(mut daemon_guard) = crate::daemon::DAEMON.try_lock() {
        if let Some(ref mut daemon) = *daemon_guard {
            match daemon.send_command("config", serde_json::json!({})) {
                Ok(config_result) => {
                    if let Some(config) = config_result.get("config") {
                        if let Some(hotkey_config) = config.get("push_to_talk_hotkey") {
                            if let Some(shortcut_str) = hotkey_config_to_shortcut_string(hotkey_config) {
                                if let Err(_e) = register_ptt_shortcut(app_handle, &shortcut_str) {
                                    // Fallback to default
                                    let _ = register_ptt_shortcut(app_handle, "Alt+3");
                                }
                                return;
                            }
                        }
                    }
                }
                Err(_e) => {
                }
            }
        }
    } else {
    }

    // Fallback to default shortcut
    if let Err(_e) = register_ptt_shortcut(app_handle, "Alt+3") {
    }
}
