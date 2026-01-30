//! PTT (Push-to-Talk) Event Reader
//!
//! This module handles reading PTT events from socket notifications
//! and forwarding them to the frontend UI.

use std::sync::atomic::Ordering;

use tauri::{Emitter, Manager};
use crate::daemon::PTT_PROCESSING;

// Include tests module
#[cfg(test)]
include!("reader_tests.rs");

// ============================================================================
// PTT Event Reader
// ============================================================================

/// Start PTT (Push-to-Talk) event reader
///
/// Note: PTT events are now handled in the notification listener in `startup.rs`
/// This function is kept for API compatibility but does nothing.
pub fn start_ptt_reader(_app_handle: tauri::AppHandle) {
    // PTT events are now handled in the unified notification listener in startup.rs
    // No need for a separate thread
}

/// Handle a single PTT event
pub fn handle_ptt_event(app_handle: &tauri::AppHandle, event_type: &str, params: &serde_json::Value) {
    // Get main window and floating window
    let main_window = app_handle.get_webview_window("main");
    let overlay_window = app_handle.get_webview_window("ptt-overlay");

    // Send state to floating window and control visibility
    if let Some(ref overlay) = overlay_window {
        match event_type {
            "listening" => {
                // Show overlay in listening state (continuous mode waiting for speech)
                let _ = overlay.set_ignore_cursor_events(false);
                let _ = overlay.show();
                let _ = overlay.emit("ptt-state", "listening");
            }
            "detected" => {
                // Speech detected, transitioning to recording
                let _ = overlay.set_ignore_cursor_events(false);
                let _ = overlay.show();
                let _ = overlay.emit("ptt-state", "detected");
            }
            "recording" => {
                let _ = overlay.set_ignore_cursor_events(false);
                let _ = overlay.show();
                let _ = overlay.emit("ptt-state", "recording");
            }
            "processing" => {
                let _ = overlay.emit("ptt-state", "processing");
            }
            "idle" | "error" => {
                let _ = overlay.hide();
                let _ = overlay.emit("ptt-state", "idle");
            }
            _ => {}
        }
    }

    // Send full event to main window
    if let Some(window) = main_window {
        match event_type {
            "listening" => {
                let _ = window.emit("ptt-state", "listening");
            }
            "detected" => {
                let _ = window.emit("ptt-state", "detected");
            }
            "recording" => {
                let _ = window.emit("ptt-state", "recording");
            }
            "processing" => {
                let _ = window.emit("ptt-state", "processing");
            }
            "idle" => {
                let _ = window.emit("ptt-state", "idle");
            }
            "user_message" => {
                // User speech recognition result - hide overlay, show message
                // Set processing flag to prevent overlay from reappearing
                PTT_PROCESSING.store(true, Ordering::SeqCst);
                let _ = window.emit("ptt-state", "idle");
                if let Some(ref overlay) = overlay_window {
                    let _ = overlay.set_ignore_cursor_events(true);
                    let _ = overlay.hide();
                    let _ = overlay.emit("ptt-state", "idle");
                }
                if let Some(text) = params.get("text").and_then(|v| v.as_str()) {
                    let _ = window.emit("ptt-user-message", text);
                }
            }
            "assistant_chunk" => {
                // LLM streaming response chunk - ensure overlay is hidden
                let _ = window.emit("ptt-state", "idle");
                if let Some(ref overlay) = overlay_window {
                    let _ = overlay.set_ignore_cursor_events(true);
                    let _ = overlay.hide();
                }
                if let Some(content) = params.get("content").and_then(|v| v.as_str()) {
                    let _ = window.emit("ptt-assistant-chunk", content);
                }
            }
            "assistant_done" => {
                // LLM response complete - ensure overlay is hidden
                // Clear processing flag to allow future recordings
                PTT_PROCESSING.store(false, Ordering::SeqCst);
                let _ = window.emit("ptt-state", "idle");
                if let Some(ref overlay) = overlay_window {
                    let _ = overlay.set_ignore_cursor_events(true);
                    let _ = overlay.hide();
                }
                if let Some(content) = params.get("content").and_then(|v| v.as_str()) {
                    let _ = window.emit("ptt-assistant-done", content);
                }
            }
            "audio_chunk" => {
                // TTS audio chunk
                let audio_path = params.get("audio_path").and_then(|v| v.as_str());
                let text = params.get("text").and_then(|v| v.as_str());
                if let (Some(path), Some(txt)) = (audio_path, text) {
                    let _ = window.emit("ptt-audio-chunk", serde_json::json!({
                        "audio_path": path,
                        "text": txt
                    }));
                }
            }
            "error" => {
                // Clear processing flag on error
                PTT_PROCESSING.store(false, Ordering::SeqCst);
                let _ = window.emit("ptt-state", "error");
                if let Some(error) = params.get("error").and_then(|v| v.as_str()) {
                    let _ = window.emit("ptt-error", error);
                }
            }
            _ => {}
        }
    }
}
