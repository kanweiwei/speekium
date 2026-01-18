// ============================================================================
// Commands Module
// ============================================================================
// All Tauri commands must be defined in this single file due to Tauri's
// macro limitation. The #[tauri::command] macro generates helper macros
// that are module-private and cannot be accessed across module boundaries,
// even with pub use re-exports.
//
// Commands are organized into logical sections below for maintainability:
// - Recording Commands (9 commands)
// - Chat Commands (4 commands)
// - Config Commands (3 commands)
// - Daemon Commands (2 commands)
// ============================================================================

use tauri::Emitter;
use tauri_plugin_global_shortcut::GlobalShortcutExt;

use crate::types::{RecordingMode, WorkMode, AppStatus, RecordResult, ChatResult, TTSResult, ConfigResult, HealthResult, DaemonStatusPayload};
use crate::daemon::{
    STREAMING_IN_PROGRESS, RECORDING_ABORTED, RECORDING_MODE, WORK_MODE,
    APP_STATUS, DAEMON, CURRENT_PTT_SHORTCUT, APP_HANDLE, call_daemon,
};
use crate::ui;
use crate::shortcuts;
use std::sync::atomic::Ordering;
use std::io::{BufRead, Write};

// ============================================================================
// Recording Commands (9 commands)
// ============================================================================

#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
pub async fn record_audio(app_handle: tauri::AppHandle, mode: String, duration: Option<String>) -> Result<RecordResult, String> {
    // Block recording during streaming operations (TTS, chat streaming)
    if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording blocked: streaming in progress".to_string()),
        });
    }

    // Check if recording should be aborted
    if RECORDING_ABORTED.load(Ordering::SeqCst) {
        RECORDING_ABORTED.store(false, Ordering::SeqCst);
        ui::emit_ptt_state(&app_handle, "idle");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording cancelled".to_string()),
        });
    }

    // Check if recording mode matches
    let current_mode = *RECORDING_MODE.lock().unwrap();
    let is_continuous_mode = mode == "continuous";

    if is_continuous_mode && current_mode != RecordingMode::Continuous {
        ui::emit_ptt_state(&app_handle, "idle");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording mode changed".to_string()),
        });
    }

    // Additional check: if switching FROM continuous, abort immediately
    if !is_continuous_mode && current_mode == RecordingMode::Continuous {
        if RECORDING_ABORTED.load(Ordering::SeqCst) {
            ui::emit_ptt_state(&app_handle, "idle");
            return Ok(RecordResult {
                success: false,
                text: None,
                language: None,
                error: Some("Recording cancelled".to_string()),
            });
        }
    }

    // Handle duration parameter: support numeric string, "auto", or empty
    let duration_val = match duration {
        Some(d) => {
            if d == "auto" {
                3.0
            } else {
                d.parse::<f32>().unwrap_or(3.0)
            }
        },
        None => 3.0
    };

    let args = serde_json::json!({
        "mode": mode,
        "duration": duration_val
    });

    // Send recording start state to all windows (unified state sync)
    ui::emit_ptt_state(&app_handle, "recording");

    let result = call_daemon("record", args);

    // Send processing state
    ui::emit_ptt_state(&app_handle, "processing");

    // Handle result
    let parsed_result = result.and_then(|r| {
        serde_json::from_value(r)
            .map_err(|e| format!("Failed to parse result: {}", e))
    });

    // Send idle state
    ui::emit_ptt_state(&app_handle, "idle");

    parsed_result
}

#[tauri::command]
pub fn set_recording_mode(mode: String) -> Result<(), String> {
    let new_mode = RecordingMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid recording mode: {}", mode))?;

    *RECORDING_MODE.lock().unwrap() = new_mode;

    if new_mode == RecordingMode::Continuous {
        RECORDING_ABORTED.store(false, Ordering::SeqCst);
    } else {
        RECORDING_ABORTED.store(true, Ordering::SeqCst);

        if let Ok(mut daemon_guard) = DAEMON.try_lock() {
            if let Some(ref mut daemon) = *daemon_guard {
                let _ = daemon.send_command_no_wait("interrupt", serde_json::json!({"priority": 1}));
            }
        }
    }

    Ok(())
}

#[tauri::command]
pub fn get_work_mode() -> Result<String, String> {
    let mode = *WORK_MODE.lock().unwrap();
    Ok(mode.as_str().to_string())
}

#[tauri::command]
pub fn set_work_mode(mode: String) -> Result<(), String> {
    let new_mode = WorkMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid work mode: {}", mode))?;

    let _old_mode = *WORK_MODE.lock().unwrap();
    *WORK_MODE.lock().unwrap() = new_mode;

    Ok(())
}

#[tauri::command]
pub fn get_recording_mode() -> Result<String, String> {
    let mode = *RECORDING_MODE.lock().unwrap();
    Ok(match mode {
        RecordingMode::PushToTalk => "push-to-talk".to_string(),
        RecordingMode::Continuous => "continuous".to_string(),
    })
}

#[tauri::command]
pub fn get_app_status() -> Result<String, String> {
    let status = *APP_STATUS.lock().unwrap();
    Ok(status.as_str().to_string())
}

#[tauri::command]
pub fn interrupt_operation(priority: u8) -> Result<String, String> {
    let current_status = *APP_STATUS.lock().unwrap();

    if current_status.can_be_interrupted(priority) {
        match current_status {
            AppStatus::Recording => {
                RECORDING_ABORTED.store(true, Ordering::SeqCst);
            }
            AppStatus::Listening => {}
            AppStatus::LlmProcessing | AppStatus::TtsProcessing | AppStatus::Playing => {
                match call_daemon("interrupt", serde_json::json!({"priority": priority})) {
                    Ok(_) => {}
                    Err(_e) => {}
                }
            }
            _ => {}
        }

        if priority <= 2 {
            *APP_STATUS.lock().unwrap() = AppStatus::Idle;
        }

        Ok(format!("Interrupted: {}", current_status.as_str()))
    } else {
        Err(format!(
            "Cannot interrupt status {} with priority {}",
            current_status.as_str(),
            priority
        ))
    }
}

#[tauri::command]
pub fn update_recording_mode(mode: String) -> Result<(), String> {
    let current_mode = match mode.as_str() {
        "push-to-talk" => Ok(RecordingMode::PushToTalk),
        "continuous" => Ok(RecordingMode::Continuous),
        _ => Err(format!("Invalid recording mode: {}", mode)),
    }?;

    if let Err(_e) = shortcuts::write_recording_mode_to_config(&mode) {}

    if let Ok(mut daemon_guard) = DAEMON.try_lock() {
        if let Some(ref mut daemon) = *daemon_guard {
            let _ = daemon.send_command_no_wait("set_recording_mode", serde_json::json!({
                "mode": mode
            }));
        }
    }

    let is_recording = {
        let status = APP_STATUS.lock().unwrap();
        matches!(*status, AppStatus::Recording | AppStatus::Listening)
    };

    if !is_recording {
        if let Some(handle) = APP_HANDLE.get() {
            match current_mode {
                RecordingMode::PushToTalk => {
                    let handle_clone = handle.clone();
                    std::thread::spawn(move || {
                        shortcuts::register_ptt_from_config(&handle_clone);
                    });
                }
                RecordingMode::Continuous => {
                    let mut current = CURRENT_PTT_SHORTCUT.lock().unwrap();
                    if let Some(ref shortcut_str) = *current {
                        if let Ok(shortcut) = shortcut_str.parse::<tauri_plugin_global_shortcut::Shortcut>() {
                            let _ = handle.global_shortcut().unregister(shortcut);
                        }
                    }
                    *current = None;
                }
            }
        }
    }

    Ok(())
}

// ============================================================================
// Chat Commands (4 commands)
// ============================================================================

#[tauri::command]
pub async fn chat_llm(text: String) -> Result<ChatResult, String> {
    let args = serde_json::json!({ "text": text });

    let result = call_daemon("chat", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
pub async fn chat_llm_stream(
    window: tauri::Window,
    text: String
) -> Result<(), String> {
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    std::thread::spawn(move || {
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                let _ = window.emit("chat-error", "Daemon not available");
                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                return;
            }
        };

        let request = serde_json::json!({
            "command": "chat_stream",
            "args": {"text": text}
        });

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            let _ = window.emit("chat-error", format!("Write error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            let _ = window.emit("chat-error", format!("Flush error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    let _ = window.emit("chat-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_) => {
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        if chunk.get("event").is_some() {
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "chunk" => {
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-chunk", content);
                                }
                            }
                            "done" => {
                                let _ = window.emit("chat-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    let _ = window.emit("chat-error", format!("Read error: {}", e));
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub async fn chat_tts_stream(
    window: tauri::Window,
    text: String,
    auto_play: Option<bool>
) -> Result<(), String> {
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    std::thread::spawn(move || {
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                let _ = window.emit("tts-error", "Daemon not available");
                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                return;
            }
        };

        let request = serde_json::json!({
            "command": "chat_tts_stream",
            "args": {
                "text": text.clone(),
                "auto_play": auto_play.unwrap_or(true)
            }
        });

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            let _ = window.emit("tts-error", format!("Write error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            let _ = window.emit("tts-error", format!("Flush error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_n) => {
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        if chunk.get("event").is_some() {
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "text_chunk" => {
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-text-chunk", content);
                                }
                            }
                            "audio_chunk" => {
                                if let Some(audio_path) = chunk.get("audio_path").and_then(|v| v.as_str()) {
                                    let text = chunk.get("text").and_then(|v| v.as_str()).unwrap_or("");
                                    let _ = window.emit("tts-audio-chunk", serde_json::json!({
                                        "audio_path": audio_path,
                                        "text": text
                                    }));
                                }
                            }
                            "done" => {
                                let _ = window.emit("tts-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    let _ = window.emit("tts-error", format!("Read error: {}", e));
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
            }
        }
    });

    Ok(())
}

#[tauri::command]
pub async fn generate_tts(text: String) -> Result<TTSResult, String> {
    let args = serde_json::json!({ "text": text });

    let result = call_daemon("tts", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

// ============================================================================
// Config Commands (3 commands)
// ============================================================================

#[tauri::command]
pub async fn load_config() -> Result<ConfigResult, String> {
    let result = call_daemon("config", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
pub async fn save_config(config: serde_json::Value) -> Result<serde_json::Value, String> {
    call_daemon("save_config", config)
}

#[tauri::command]
pub async fn update_hotkey(hotkey_config: serde_json::Value) -> Result<serde_json::Value, String> {
    let _display_name = hotkey_config.get("displayName").and_then(|v| v.as_str()).unwrap_or("unknown");

    let result = call_daemon("update_hotkey", hotkey_config.clone())?;

    if let Some(shortcut_str) = shortcuts::hotkey_config_to_shortcut_string(&hotkey_config) {
        if let Some(app_handle) = APP_HANDLE.get() {
            if let Err(_e) = shortcuts::register_ptt_shortcut(app_handle, &shortcut_str) {}
        }
    }

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

// ============================================================================
// Daemon Commands (2 commands)
// ============================================================================

#[tauri::command]
pub async fn get_daemon_state() -> Result<serde_json::Value, String> {
    let result = call_daemon("get_daemon_state", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
pub async fn daemon_health(app: tauri::AppHandle) -> Result<HealthResult, String> {
    if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
        return Ok(HealthResult {
            success: true,
            status: Some("streaming".to_string()),
            command_count: None,
            models_loaded: None,
            error: None,
        });
    }

    let result = call_daemon("health", serde_json::json!({}))?;

    let health_result: HealthResult = serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))?;

    if health_result.success {
        let _ = app.emit("daemon-status", DaemonStatusPayload {
            status: "ready".to_string(),
            message: "就绪".to_string(),
        });
    }

    Ok(health_result)
}
