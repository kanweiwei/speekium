//! PTT (Push-to-Talk) Event Reader
//!
//! This module handles reading PTT events from the Python daemon stderr
//! and forwarding them to the frontend UI.

use std::sync::atomic::Ordering;
use std::io::BufRead;

use tauri::{Emitter, Manager};
use crate::daemon::PTT_STDERR;
use crate::daemon::PTT_PROCESSING;

// ============================================================================
// PTT Event Reader
// ============================================================================

/// Start PTT (Push-to-Talk) event reader
///
/// Listen to Python daemon stderr in background thread, parse PTT events and forward to frontend.
///
/// # Events
/// - `listening` - Continuous mode waiting for speech
/// - `detected` - Speech detected, transitioning to recording
/// - `recording` - Currently recording
/// - `processing` - Processing recorded audio
/// - `idle` - Ready state
/// - `user_message` - User speech recognition result
/// - `assistant_chunk` - LLM streaming response chunk
/// - `assistant_done` - LLM response complete
/// - `audio_chunk` - TTS audio chunk
/// - `error` - Error occurred
pub fn start_ptt_reader(app_handle: tauri::AppHandle) {
    std::thread::spawn(move || {
        loop {
            // Get stderr reader
            let line = {
                let mut ptt_stderr = PTT_STDERR.lock().unwrap();
                if let Some(ref mut stderr) = *ptt_stderr {
                    let mut line = String::new();
                    match stderr.read_line(&mut line) {
                        Ok(0) => {
                            break;
                        }
                        Ok(_) => Some(line),
                        Err(_e) => {
                            None
                        }
                    }
                } else {
                    // stderr not ready yet, wait a bit
                    drop(ptt_stderr);
                    std::thread::sleep(std::time::Duration::from_millis(100));
                    continue;
                }
            };

            if let Some(line) = line {
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }

                // Try to parse as JSON PTT event
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(ptt_event) = event.get("ptt_event").and_then(|v| v.as_str()) {
                        // Get main window and floating window
                        let main_window = app_handle.get_webview_window("main");
                        let overlay_window = app_handle.get_webview_window("ptt-overlay");

                        // Send state to floating window and control visibility
                        if let Some(ref overlay) = overlay_window {
                            match ptt_event {
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
                            match ptt_event {
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
                                    if let Some(text) = event.get("text").and_then(|v| v.as_str()) {
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
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
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
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-done", content);
                                    }
                                }
                                "audio_chunk" => {
                                    // TTS audio chunk
                                    let audio_path = event.get("audio_path").and_then(|v| v.as_str());
                                    let text = event.get("text").and_then(|v| v.as_str());
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
                                    if let Some(error) = event.get("error").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-error", error);
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
    });
}
