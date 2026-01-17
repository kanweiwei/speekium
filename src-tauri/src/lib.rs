use tauri::{Manager, State};

mod database;
mod audio;
mod types;
mod state;
mod platform;
mod ui;
mod daemon;
mod api;
mod shortcuts;
mod commands;

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
            // Commands module
            commands::greet,
            commands::record_audio,
            commands::set_recording_mode,
            commands::get_recording_mode,
            commands::update_recording_mode,
            commands::get_work_mode,
            commands::set_work_mode,
            commands::get_app_status,
            commands::interrupt_operation,
            commands::chat_llm,
            commands::chat_llm_stream,
            commands::chat_tts_stream,
            commands::generate_tts,
            commands::load_config,
            commands::save_config,
            commands::update_hotkey,
            commands::get_daemon_state,
            commands::daemon_health,
            // API commands
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
