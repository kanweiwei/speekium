use tauri::{Emitter, Manager, State};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};
use std::io::{BufRead, Write};
use std::sync::atomic::Ordering;

mod database;
mod audio;
mod types;
mod state;
mod platform;
mod ui;
mod daemon;
mod api;
mod shortcuts;

use database::{Database, Session, Message, PaginatedResult};
use audio::AudioRecorder;

// Re-export daemon globals for use in other modules
pub use daemon::{
    DAEMON, DAEMON_READY, PTT_STDERR, STREAMING_IN_PROGRESS,
    PTT_PROCESSING, RECORDING_ABORTED, RECORDING_MODE, WORK_MODE, APP_STATUS,
    CURRENT_PTT_SHORTCUT, PTT_KEY_PRESSED, AUDIO_RECORDER,
    RECORDING_MODE_CHANNEL, APP_HANDLE,
    ensure_daemon_running, is_daemon_ready, call_daemon,
    start_daemon_async, start_ptt_reader, cleanup_daemon,
};
use types::{RecordingMode, WorkMode, AppStatus, DaemonStatusPayload};
use types::{RecordResult, ChatResult, TTSResult, ConfigResult, HealthResult};
use state::AppState;

// ============================================================================
// Database Commands
// ============================================================================

#[tauri::command]
async fn db_create_session(
    state: State<'_, AppState>,
    title: String,
) -> Result<Session, String> {
    state.db.create_session(title)
}

#[tauri::command]
async fn db_list_sessions(
    state: State<'_, AppState>,
    page: i32,
    page_size: i32,
    filter_favorite: Option<bool>,
) -> Result<PaginatedResult<Session>, String> {
    state.db.list_sessions_filtered(page, page_size, filter_favorite)
}

#[tauri::command]
async fn db_get_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<Session, String> {
    state.db.get_session(&session_id)
}

#[tauri::command]
async fn db_toggle_favorite(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.toggle_favorite(&session_id)
}

#[tauri::command]
async fn db_update_session(
    state: State<'_, AppState>,
    session_id: String,
    title: String,
) -> Result<Session, String> {
    state.db.update_session(&session_id, title)
}

#[tauri::command]
async fn db_delete_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.delete_session(&session_id)
}

#[tauri::command]
async fn db_add_message(
    state: State<'_, AppState>,
    session_id: String,
    role: String,
    content: String,
) -> Result<Message, String> {
    state.db.add_message(&session_id, &role, &content)
}

#[tauri::command]
async fn db_get_messages(
    state: State<'_, AppState>,
    session_id: String,
    page: i32,
    page_size: i32,
) -> Result<PaginatedResult<Message>, String> {
    state.db.get_messages(&session_id, page, page_size)
}

#[tauri::command]
async fn db_delete_message(
    state: State<'_, AppState>,
    message_id: String,
) -> Result<bool, String> {
    state.db.delete_message(&message_id)
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn record_audio(app_handle: tauri::AppHandle, mode: String, duration: Option<String>) -> Result<RecordResult, String> {
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
        // Send idle state to hide floating window
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
        // Send idle state to hide floating window
        ui::emit_ptt_state(&app_handle, "idle");
        return Ok(RecordResult {
            success: false,
            text: None,
            language: None,
            error: Some("Recording mode changed".to_string()),
        });
    }

    // 🔧 Additional check: if switching FROM continuous, abort immediately
    if !is_continuous_mode && current_mode == RecordingMode::Continuous {
        // Just switched from continuous to push-to-talk
        // Check if there's a recording in progress by checking the abort flag
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
                3.0  // "auto" 默认为 3 秒
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

/// Set recording mode (continuous or push-to-talk)
#[tauri::command]
fn set_recording_mode(mode: String) -> Result<(), String> {

    // Parse mode from string
    let new_mode = RecordingMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid recording mode: {}", mode))?;

    // Update global recording mode
    *RECORDING_MODE.lock().unwrap() = new_mode;

    // Clear or set abort flag based on mode
    if new_mode == RecordingMode::Continuous {
        // Switching to continuous: clear abort flag to allow new recordings
        RECORDING_ABORTED.store(false, Ordering::SeqCst);
    } else {
        // Switching away from continuous: abort any ongoing recording
        RECORDING_ABORTED.store(true, Ordering::SeqCst);

        // 🔧 Fix: Send interrupt signal asynchronously to avoid blocking UI
        // Use try_lock to prevent deadlock
        if let Ok(mut daemon_guard) = DAEMON.try_lock() {
            if let Some(ref mut daemon) = *daemon_guard {
                let _ = daemon.send_command_no_wait("interrupt", serde_json::json!({"priority": 1}));
            }
        } else {
        }
    }

    Ok(())
}

/// Get current work mode
#[tauri::command]
fn get_work_mode() -> Result<String, String> {
    let mode = *WORK_MODE.lock().unwrap();
    Ok(mode.as_str().to_string())
}

/// Set work mode (conversation or text-input)
#[tauri::command]
fn set_work_mode(mode: String) -> Result<(), String> {

    // Parse mode from string
    let new_mode = WorkMode::from_str(mode.as_str())
        .ok_or_else(|| format!("Invalid work mode: {}", mode))?;

    // Update global work mode
    let _old_mode = *WORK_MODE.lock().unwrap();
    *WORK_MODE.lock().unwrap() = new_mode;


    Ok(())
}

/// Get current recording mode
#[tauri::command]
fn get_recording_mode() -> Result<String, String> {
    let mode = *RECORDING_MODE.lock().unwrap();
    Ok(match mode {
        RecordingMode::PushToTalk => "push-to-talk".to_string(),
        RecordingMode::Continuous => "continuous".to_string(),
    })
}


/// Get current application status
#[tauri::command]
fn get_app_status() -> Result<String, String> {
    let status = *APP_STATUS.lock().unwrap();
    Ok(status.as_str().to_string())
}

/// Transition application status with validation
#[allow(dead_code)]
fn transition_status(new_status: AppStatus) -> Result<(), String> {
    let current_status = *APP_STATUS.lock().unwrap();

    // Validate transition
    let valid_transition = match (current_status, new_status) {
        // From Idle
        (AppStatus::Idle, AppStatus::Listening) => true,
        (AppStatus::Idle, AppStatus::Recording) => true,

        // From Listening
        (AppStatus::Listening, AppStatus::Recording) => true,  // VAD detected speech
        (AppStatus::Listening, AppStatus::Idle) => true,       // Stop listening

        // From Recording
        (AppStatus::Recording, AppStatus::AsrProcessing) => true,
        (AppStatus::Recording, AppStatus::Idle) => true,       // Recording aborted

        // From ASR
        (AppStatus::AsrProcessing, AppStatus::Idle) => true,    // Text input mode done
        (AppStatus::AsrProcessing, AppStatus::LlmProcessing) => true,  // Conversation mode

        // From LLM
        (AppStatus::LlmProcessing, AppStatus::TtsProcessing) => true,
        (AppStatus::LlmProcessing, AppStatus::Idle) => true,    // TTS disabled or failed

        // From TTS
        (AppStatus::TtsProcessing, AppStatus::Playing) => true,
        (AppStatus::TtsProcessing, AppStatus::Idle) => true,    // TTS failed

        // From Playing
        (AppStatus::Playing, AppStatus::Idle) => true,
        (AppStatus::Playing, AppStatus::Listening) => true,     // Auto mode continues

        // Same status (no-op)
        _ if current_status == new_status => true,

        // Invalid transitions
        _ => false,
    };

    if !valid_transition {
        return Err(format!(
            "Invalid status transition: {} → {}",
            current_status.as_str(),
            new_status.as_str()
        ));
    }

    // Log transition
    if current_status != new_status {
    }

    // Update status
    *APP_STATUS.lock().unwrap() = new_status;

    Ok(())
}

/// Interrupt current operation with priority
#[tauri::command]
fn interrupt_operation(priority: u8) -> Result<String, String> {
    let current_status = *APP_STATUS.lock().unwrap();


    if current_status.can_be_interrupted(priority) {
        // Perform interrupt based on current status
        match current_status {
            AppStatus::Recording => {
                RECORDING_ABORTED.store(true, Ordering::SeqCst);
            }
            AppStatus::Listening => {
                // Stop listening logic will be handled by the recording loop
            }
            AppStatus::LlmProcessing | AppStatus::TtsProcessing | AppStatus::Playing => {
                // Send interrupt signal to Python daemon
                match call_daemon("interrupt", serde_json::json!({"priority": priority})) {
                    Ok(_) => {
                    }
                    Err(_e) => {
                        // Continue anyway, as the interrupt flag may have been set elsewhere
                    }
                }
            }
            _ => {
            }
        }

        // Transition to Idle based on priority
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
async fn chat_llm(text: String) -> Result<ChatResult, String> {
    let args = serde_json::json!({
        "text": text
    });


    let result = call_daemon("chat", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn chat_llm_stream(
    window: tauri::Window,
    text: String
) -> Result<(), String> {

    // Set streaming operation flag
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // Handle streaming response in separate thread
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

        // Send streaming command
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

        // Loop to read streaming output
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon may have crashed
                    let _ = window.emit("chat-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_) => {
                    // Parse JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        // Skip log events (have "event" field)
                        if chunk.get("event").is_some() {
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "chunk" => {
                                // Send text chunk to frontend
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-chunk", content);
                                }
                            }
                            "done" => {
                                // Streaming response complete
                                let _ = window.emit("chat-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // Error
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {
                            }
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
async fn chat_tts_stream(
    window: tauri::Window,
    text: String,
    auto_play: Option<bool>
) -> Result<(), String> {

    // Set streaming operation flag
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // Handle streaming response in separate thread
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


        // Send streaming command
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


        // Loop to read streaming output
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon may have crashed
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_n) => {

                    // Parse JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {

                        // Skip log events (have "event" field)
                        if chunk.get("event").is_some() {
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "text_chunk" => {
                                // Send text chunk to frontend
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-text-chunk", content);
                                }
                            }
                            "audio_chunk" => {
                                // Send audio chunk to frontend
                                if let Some(audio_path) = chunk.get("audio_path").and_then(|v| v.as_str()) {
                                    let text = chunk.get("text").and_then(|v| v.as_str()).unwrap_or("");
                                    let _ = window.emit("tts-audio-chunk", serde_json::json!({
                                        "audio_path": audio_path,
                                        "text": text
                                    }));
                                }
                            }
                            "done" => {
                                // Streaming response complete
                                let _ = window.emit("tts-done", ());
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // Error
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-error", error);
                                }
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            _ => {
                            }
                        }
                    } else {
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
async fn generate_tts(text: String) -> Result<TTSResult, String> {
    let args = serde_json::json!({
        "text": text
    });


    let result = call_daemon("tts", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn load_config() -> Result<ConfigResult, String> {

    let result = call_daemon("config", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn save_config(config: serde_json::Value) -> Result<serde_json::Value, String> {

    // Pass config directly, do not re-wrap
    // Frontend already passed { config: updatedConfig }
    // Pass config directly as parameter to Python daemon
    call_daemon("save_config", config)
}

#[tauri::command]
async fn update_hotkey(hotkey_config: serde_json::Value) -> Result<serde_json::Value, String> {
    let _display_name = hotkey_config.get("displayName").and_then(|v| v.as_str()).unwrap_or("unknown");

    // Update daemon config
    let result = call_daemon("update_hotkey", hotkey_config.clone())?;

    // Also update Tauri global shortcut
    if let Some(shortcut_str) = shortcuts::hotkey_config_to_shortcut_string(&hotkey_config) {
        if let Some(app_handle) = APP_HANDLE.get() {
            if let Err(_e) = shortcuts::register_ptt_shortcut(app_handle, &shortcut_str) {
            } else {
            }
        } else {
        }
    } else {
    }

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn get_daemon_state() -> Result<serde_json::Value, String> {
    // Get comprehensive daemon state

    let result = call_daemon("get_daemon_state", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn daemon_health(app: tauri::AppHandle) -> Result<HealthResult, String> {
    // Check if there is an ongoing streaming operation
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

    // If daemon is healthy, emit daemon-status event for frontend
    // This is important when page is refreshed - frontend needs to know daemon is ready
    if health_result.success {
        let _ = app.emit("daemon-status", DaemonStatusPayload {
            status: "ready".to_string(),
            message: "就绪".to_string(),
        });
    }

    Ok(health_result)
}

// ============================================================================
// Main Entry Point
// ============================================================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build());

    // Add macOS permissions plugin
    #[cfg(target_os = "macos")]
    {
        builder = builder.plugin(tauri_plugin_macos_permissions::init());
    }

    builder
        .invoke_handler(tauri::generate_handler![
            greet,
            record_audio,
            set_recording_mode,
            get_recording_mode,
            update_recording_mode,
            get_work_mode,
            set_work_mode,
            get_app_status,
            interrupt_operation,
            chat_llm,
            chat_llm_stream,
            chat_tts_stream,
            generate_tts,
            load_config,
            save_config,
            update_hotkey,
            get_daemon_state,
            daemon_health,
            api::test_ollama_connection,
            api::list_ollama_models,
            api::test_openai_connection,
            api::test_openrouter_connection,
            api::test_custom_connection,
            api::test_zhipu_connection,
            platform::type_text_command,
            // Database commands
            db_create_session,
            db_list_sessions,
            db_get_session,
            db_toggle_favorite,
            db_update_session,
            db_delete_session,
            db_add_message,
            db_get_messages,
            db_delete_message
        ])
        .setup(|app| {
            // Initialize AudioRecorder singleton (only once at startup)
            // This triggers microphone permission request on first access
            // cpal 0.17 fixes the repeated permission popup issue
            {
                let mut recorder_guard = AUDIO_RECORDER.lock().unwrap();
                if recorder_guard.is_none() {
                    match AudioRecorder::new() {
                        Ok(r) => {
                            *recorder_guard = Some(r);
                        }
                        Err(_e) => {
                        }
                    }
                }
            }

            // Initialize database
            let db_path = database::get_database_path(app.handle())
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to get database path: {}", e)))?;

            let db = Database::new(db_path)
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to initialize database: {}", e)))?;

            app.manage(AppState { db });

            // Create tray icon
            ui::create_tray(app.handle(), cleanup_daemon)?;

            // Store app handle globally BEFORE starting dispatcher
            let _ = APP_HANDLE.set(app.handle().clone());

            // Start recording mode event dispatcher
            shortcuts::start_recording_mode_dispatcher(app.handle());

            // Register shortcuts
            shortcuts::register_shortcuts(app.handle())?;

            // Start daemon asynchronously (non-blocking)
            // This allows the UI to show immediately while daemon loads in background
            // PTT shortcut registration happens after daemon is ready (via callback)
            let app_handle_for_callback = app.handle().clone();
            daemon::start_daemon_async(app.handle().clone(), Some(move || {
                shortcuts::register_ptt_from_config(&app_handle_for_callback);
            }));

            // Start PTT event reader (listen to Python daemon stderr)
            // This will wait for stderr to be available from daemon
            daemon::start_ptt_reader(app.handle().clone());

            // Create PTT floating state window
            if let Err(_e) = ui::create_ptt_overlay(app.handle()) {
            }


            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Prevent window close, hide instead
                api.prevent_close();
                window.hide().unwrap();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            // macOS: Show main window when dock icon is clicked
            #[cfg(target_os = "macos")]
            if let tauri::RunEvent::Reopen { .. } = &event {
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }

            // Clean up daemon on app exit
            if let tauri::RunEvent::ExitRequested { .. } = &event {
                cleanup_daemon();
            }
        });
}
/// Update recording mode and handle PTT shortcut registration
/// This should be called from frontend when it detects a mode change
/// Note: This does NOT modify RECORDING_MODE state - the shortcut callback already did that
#[tauri::command]
fn update_recording_mode(mode: String) -> Result<(), String> {

    // Parse mode
    let current_mode = match mode.as_str() {
        "push-to-talk" => Ok(RecordingMode::PushToTalk),
        "continuous" => Ok(RecordingMode::Continuous),
        _ => Err(format!("Invalid recording mode: {}", mode)),
    }?;


    // IMPORTANT: Write directly to config file FIRST so VAD loop can detect mode change immediately
    // This ensures VAD recording stops promptly when switching from continuous to push-to-talk
    if let Err(_e) = shortcuts::write_recording_mode_to_config(&mode) {
    }

    // Also notify daemon (for UI state sync)
    if let Ok(mut daemon_guard) = DAEMON.try_lock() {
        if let Some(ref mut daemon) = *daemon_guard {
            let _ = daemon.send_command_no_wait("set_recording_mode", serde_json::json!({
                "mode": mode
            }));
        }
    } else {
    }

    // Handle PTT shortcut registration/unregistration
    // CRITICAL: Only handle shortcuts when NOT recording to avoid deadlock
    let is_recording = {
        let status = APP_STATUS.lock().unwrap();
        matches!(*status, AppStatus::Recording | AppStatus::Listening)
    };

    if !is_recording {
        if let Some(handle) = APP_HANDLE.get() {
            match current_mode {
                RecordingMode::PushToTalk => {
                    // Register PTT shortcut asynchronously (spawn in background)
                    let handle_clone = handle.clone();
                    std::thread::spawn(move || {
                        shortcuts::register_ptt_from_config(&handle_clone);
                    });
                }
                RecordingMode::Continuous => {
                    // Unregister PTT shortcut
                    let mut current = CURRENT_PTT_SHORTCUT.lock().unwrap();
                    if let Some(ref shortcut_str) = *current {
                        if let Ok(shortcut) = shortcut_str.parse::<Shortcut>() {
                            let _ = handle.global_shortcut().unregister(shortcut);
                        }
                    }
                    *current = None;
                }
            }
        }
    } else {
    }

    Ok(())
}

