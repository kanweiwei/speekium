use tauri::Manager;

use crate::audio::AudioRecorder;
use crate::daemon::AUDIO_RECORDER;
use crate::database;
use crate::database::Database;
use crate::state::AppState;
use crate::ui;
use crate::shortcuts;
use crate::daemon;

use crate::daemon::{
    APP_HANDLE,
    cleanup_daemon,
};

// ============================================================================
// Application Setup
// ============================================================================

fn setup_app(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
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
}

// ============================================================================
// Window Event Handler
// ============================================================================

fn handle_window_event(window: &tauri::Window, event: &tauri::WindowEvent) {
    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
        // Prevent window close, hide instead
        api.prevent_close();
        window.hide().unwrap();
    }
}

// ============================================================================
// Run Event Handler
// ============================================================================

fn handle_run_event(app_handle: &tauri::AppHandle, event: tauri::RunEvent) {
    // macOS: Show main window when dock icon is clicked
    #[cfg(target_os = "macos")]
    if let tauri::RunEvent::Reopen { .. } = event {
        if let Some(window) = app_handle.get_webview_window("main") {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }

    // Clean up daemon on app exit
    if let tauri::RunEvent::ExitRequested { .. } = event {
        cleanup_daemon();
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build());

    #[cfg(target_os = "macos")]
    {
        builder = builder.plugin(tauri_plugin_macos_permissions::init());
    }

    builder
        .invoke_handler(tauri::generate_handler![
            // Commands module
            crate::commands::greet,
            crate::commands::record_audio,
            crate::commands::set_recording_mode,
            crate::commands::get_recording_mode,
            crate::commands::update_recording_mode,
            crate::commands::get_work_mode,
            crate::commands::set_work_mode,
            crate::commands::get_app_status,
            crate::commands::interrupt_operation,
            crate::commands::chat_llm,
            crate::commands::chat_llm_stream,
            crate::commands::chat_tts_stream,
            crate::commands::generate_tts,
            crate::commands::load_config,
            crate::commands::save_config,
            crate::commands::update_hotkey,
            crate::commands::get_daemon_state,
            crate::commands::daemon_health,
            // API commands
            crate::api::test_ollama_connection,
            crate::api::list_ollama_models,
            crate::api::test_openai_connection,
            crate::api::test_openrouter_connection,
            crate::api::test_custom_connection,
            crate::api::test_zhipu_connection,
            crate::platform::type_text_command,
            // Database commands
            crate::db_commands::db_create_session,
            crate::db_commands::db_list_sessions,
            crate::db_commands::db_get_session,
            crate::db_commands::db_toggle_favorite,
            crate::db_commands::db_update_session,
            crate::db_commands::db_delete_session,
            crate::db_commands::db_add_message,
            crate::db_commands::db_get_messages,
            crate::db_commands::db_delete_message
        ])
        .setup(setup_app)
        .on_window_event(handle_window_event)
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(handle_run_event);
}
