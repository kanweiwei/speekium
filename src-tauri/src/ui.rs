//! UI-related functionality: tray menu, overlay windows, and event emission

use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{TrayIconBuilder, TrayIconEvent},
    webview::WebviewWindowBuilder,
    Emitter, Manager, Runtime,
};
use std::sync::atomic::Ordering;

// macOS: Set activation policy to Regular (shows app in Dock)
#[cfg(target_os = "macos")]
fn set_activation_policy_regular() {
    use cocoa::foundation::NSUInteger;
    use objc::{msg_send, sel, sel_impl, class};

    // NSApplicationActivationPolicyRegular = 0
    const NS_APPLICATION_ACTIVATION_POLICY_REGULAR: NSUInteger = 0;

    unsafe {
        let nsapp: cocoa::base::id = msg_send![class!(NSApplication), sharedApplication];
        let _: () = msg_send![nsapp, setActivationPolicy: NS_APPLICATION_ACTIVATION_POLICY_REGULAR];
        let _: () = msg_send![nsapp, activateIgnoringOtherApps: true];
    }
}

// macOS: Set activation policy to Accessory (removes app from Dock)
#[cfg(target_os = "macos")]
fn set_activation_policy_accessory() {
    use cocoa::foundation::NSUInteger;
    use objc::{msg_send, sel, sel_impl, class};

    // NSApplicationActivationPolicyAccessory = 1
    const NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY: NSUInteger = 1;

    unsafe {
        let nsapp: cocoa::base::id = msg_send![class!(NSApplication), sharedApplication];
        let _: () = msg_send![nsapp, setActivationPolicy: NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY];
    }
}

// Re-export from lib.rs for use in this module
use crate::PTT_PROCESSING;

// ============================================================================
// PTT Overlay Window
// ============================================================================

/// PTT Overlay window constants
pub const OVERLAY_WIDTH: f64 = 140.0;
pub const OVERLAY_HEIGHT: f64 = 50.0;
pub const BOTTOM_MARGIN: f64 = 60.0;

/// Calculate PTT overlay window position based on current screen size
pub fn calculate_overlay_position<R: Runtime>(
    app: &tauri::AppHandle<R>,
) -> Result<(f64, f64), Box<dyn std::error::Error>> {
    let monitor = app.primary_monitor()?
        .ok_or_else(|| Box::<dyn std::error::Error>::from("No primary monitor found"))?;
    let screen_size = monitor.size();
    let scale_factor = monitor.scale_factor();

    // Validate scale factor
    if scale_factor <= 0.0 {
        return Err(format!("Invalid scale factor: {}", scale_factor).into());
    }

    // Calculate scaled screen dimensions
    let scaled_width = screen_size.width as f64 / scale_factor;
    let scaled_height = screen_size.height as f64 / scale_factor;

    // Calculate bottom center position with boundary validation
    let x = (scaled_width / 2.0 - OVERLAY_WIDTH / 2.0).max(0.0);
    let y = (scaled_height - OVERLAY_HEIGHT - BOTTOM_MARGIN).max(0.0);

    // Final boundary check
    if x + OVERLAY_WIDTH > scaled_width || y + OVERLAY_HEIGHT > scaled_height {
        eprintln!("Warning: PTT overlay position may exceed screen bounds");
    }

    Ok((x, y))
}

/// Create the PTT overlay floating window
pub fn create_ptt_overlay<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    let (x, y) = calculate_overlay_position(app)?;

    // Create PTT floating window (transparent window)
    let _overlay = WebviewWindowBuilder::new(
        app,
        "ptt-overlay",
        tauri::WebviewUrl::App("ptt-overlay.html".into())
    )
    .title("PTT Status")
    .inner_size(OVERLAY_WIDTH, OVERLAY_HEIGHT)
    .position(x, y)
    .always_on_top(true)
    .decorations(false)
    .resizable(false)
    .skip_taskbar(true)
    .focused(false)
    .visible(false)
    .transparent(true)
    .shadow(false)
    .build()?;

    Ok(())
}

// ============================================================================
// PTT State Emission
// ============================================================================

/// Send PTT state to all windows
///
/// This function emits the current PTT (Push-to-Talk) state to both the main window
/// and the floating overlay window. It also controls the visibility of the overlay
/// window based on the state.
pub fn emit_ptt_state(app_handle: &tauri::AppHandle, state: &str) {
    // Send to main window
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // Send to floating window
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // Control floating window visibility
        match state {
            "listening" | "detected" | "recording" | "processing" => {
                // Don't show overlay if PTT processing (ASR/LLM/TTS) is in progress
                if PTT_PROCESSING.load(Ordering::SeqCst) {
                    return;
                }
                // Recalculate position before showing (in case screen config changed)
                match calculate_overlay_position(app_handle) {
                    Ok((x, y)) => {
                        let _ = overlay.set_position(tauri::Position::Logical(tauri::LogicalPosition { x, y }));
                    }
                    Err(_) => {}
                }
                let _ = overlay.set_ignore_cursor_events(false);
                let _ = overlay.show();
            }
            "idle" | "error" => {
                let _ = overlay.set_ignore_cursor_events(true);
                let _ = overlay.hide();
            }
            _ => {}
        }
    }
}

/// Send PTT state to all windows (static version for shortcut callbacks)
///
/// This is a simplified version of `emit_ptt_state` for use in global shortcut
/// callbacks where the full state checking logic is not needed.
pub fn emit_ptt_state_static(app_handle: &tauri::AppHandle, state: &str) {
    // Send to main window
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // Send to floating window
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // Control floating window visibility
        match state {
            "listening" | "detected" | "recording" | "processing" => {
                let _ = overlay.show();
            }
            "idle" | "error" => {
                let _ = overlay.hide();
            }
            _ => {}
        }
    }
}

// ============================================================================
// Tray Icon
// ============================================================================

/// Create the system tray icon with menu
///
/// This creates a tray icon in the system menu bar/dock with options to:
/// - Show the main window
/// - Hide the main window
/// - Quit the application
///
/// # Arguments
/// * `app` - The Tauri app handle
/// * `cleanup_fn` - A callback function to clean up resources before quitting
pub fn create_tray<R: Runtime, F: Fn() + Send + Sync + 'static>(
    app: &tauri::AppHandle<R>,
    cleanup_fn: F,
) -> tauri::Result<()> {
    // Create menu items
    let show_item = MenuItemBuilder::new("显示窗口").id("show").build(app)?;
    let hide_item = MenuItemBuilder::new("隐藏窗口").id("hide").build(app)?;
    let quit_item = MenuItemBuilder::new("退出").id("quit").build(app)?;

    // Build menu
    let menu = MenuBuilder::new(app)
        .item(&show_item)
        .item(&hide_item)
        .separator()
        .item(&quit_item)
        .build()?;

    // Load tray icon (template icon for macOS menu bar)
    let icon_bytes = include_bytes!("../icons/tray-template.png");
    let icon_image = image::load_from_memory(icon_bytes)
        .expect("Failed to load tray icon");
    let rgba = icon_image.to_rgba8();
    let (width, height) = rgba.dimensions();
    let tray_icon = Image::new_owned(rgba.into_raw(), width, height);

    // Create tray icon
    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .icon(tray_icon)
        .icon_as_template(true)
        .tooltip("Speekium")
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "show" => {
                #[cfg(target_os = "macos")]
                {
                    set_activation_policy_regular();
                }
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "hide" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
                #[cfg(target_os = "macos")]
                {
                    let _ = app.hide();
                    set_activation_policy_accessory();
                }
            }
            "quit" => {
                // Clean up daemon using provided callback
                cleanup_fn();
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button, .. } = event {
                // Only toggle window on left click
                // Right click shows the menu (default behavior)
                if button == tauri::tray::MouseButton::Left {
                    let app = tray.app_handle();
                    if let Some(window) = app.get_webview_window("main") {
                        if window.is_visible().unwrap_or(false) {
                            let _ = window.hide();
                            #[cfg(target_os = "macos")]
                            {
                                let _ = app.hide();
                                set_activation_policy_accessory();
                            }
                        } else {
                            #[cfg(target_os = "macos")]
                            {
                                set_activation_policy_regular();
                            }
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}
