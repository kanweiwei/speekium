//! UI-related functionality: tray menu, overlay windows, and event emission

use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{TrayIconBuilder, TrayIconEvent},
    webview::WebviewWindowBuilder,
    Emitter, Manager, Runtime,
};
use std::sync::atomic::Ordering;
use std::path::PathBuf;

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
// Config & Language
// ============================================================================

/// Get the config directory path
fn get_config_dir() -> Result<PathBuf, String> {
    #[cfg(target_os = "macos")]
    {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
        return Ok(PathBuf::from(home).join("Library/Application Support/com.speekium.app"));
    }
    #[cfg(target_os = "windows")]
    {
        let appdata = std::env::var("APPDATA").unwrap_or_else(|_| ".".to_string());
        return Ok(PathBuf::from(appdata).join("com.speekium.app"));
    }
    #[cfg(target_os = "linux")]
    {
        let xdg = std::env::var("XDG_CONFIG_HOME")
            .unwrap_or_else(|_| format!("{}/.config", std::env::var("HOME").unwrap_or_else(|_| ".".to_string())));
        return Ok(PathBuf::from(xdg).join("com.speekium.app"));
    }
    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        Err("Unsupported platform".to_string())
    }
}

/// Get system language code
/// Returns "en" for English locales, "zh" for Chinese locales, default to "en"
fn get_system_language() -> &'static str {
    // Try to get system language from environment variables
    #[cfg(target_os = "macos")]
    {
        if let Ok(lang) = std::env::var("LANG") {
            if lang.starts_with("en") {
                return "en";
            } else if lang.starts_with("zh") {
                return "zh";
            }
        }
    }
    #[cfg(target_os = "windows")]
    {
        if let Ok(lang) = std::env::var("LANG") {
            if lang.contains("en") {
                return "en";
            } else if lang.contains("zh") {
                return "zh";
            }
        }
    }
    // Default to English
    "en"
}

/// Read language from config file
/// Returns the language from config, or system language if config doesn't exist
pub fn get_language_from_config() -> String {
    let config_dir = match get_config_dir() {
        Ok(dir) => dir,
        Err(_) => return get_system_language().to_string(),
    };

    let config_path = config_dir.join("config.json");

    if !config_path.exists() {
        // Config doesn't exist, create it with system language
        let _ = std::fs::create_dir_all(&config_dir);

        let default_config = serde_json::json!({
            "language": get_system_language()
        });

        if let Ok(json) = serde_json::to_string_pretty(&default_config) {
            let _ = std::fs::write(&config_path, json);
        }
        return get_system_language().to_string();
    }

    // Read existing config
    match std::fs::read_to_string(&config_path) {
        Ok(content) => {
            if let Ok(config) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(lang) = config.get("language").and_then(|v| v.as_str()) {
                    return lang.to_string();
                }
            }
            // If language field doesn't exist, add it
            get_system_language().to_string()
        }
        Err(_) => get_system_language().to_string(),
    }
}

/// Write language to config file
pub fn write_language_to_config(language: &str) -> Result<(), Box<dyn std::error::Error>> {
    let config_dir = get_config_dir()?;

    let config_path = config_dir.join("config.json");

    // Ensure config directory exists
    std::fs::create_dir_all(&config_dir)?;

    // Read existing config or create default
    let mut config = if config_path.exists() {
        let config_content = std::fs::read_to_string(&config_path)?;
        serde_json::from_str(&config_content).unwrap_or(serde_json::json!({}))
    } else {
        serde_json::json!({})
    };

    // Update language
    config["language"] = serde_json::json!(language);

    // Write back
    let json = serde_json::to_string_pretty(&config)?;
    std::fs::write(&config_path, json)?;
    Ok(())
}

// ============================================================================
// Tray Icon
// ============================================================================

use std::sync::Mutex;

/// Global cleanup function for tray quit action
static TRAY_CLEANUP: Mutex<Option<Box<dyn Fn() + Send + Sync>>> = Mutex::new(None);

/// Get localized daemon startup messages
pub fn get_daemon_message(message_key: &str) -> String {
    let language = get_language_from_config();
    match (message_key, language.as_str()) {
        // Ready messages
        ("ready", "en") => "Ready".to_string(),
        ("ready", _) => "就绪".to_string(),

        // Loading messages
        ("starting", "en") => "Starting voice service...".to_string(),
        ("starting", _) => "正在启动语音服务...".to_string(),

        ("initializing", "en") => "Initializing voice service...".to_string(),
        ("initializing", _) => "正在初始化语音服务...".to_string(),

        ("loading_assistant", "en") => "Loading voice assistant...".to_string(),
        ("loading_assistant", _) => "正在加载语音助手...".to_string(),

        ("loading_asr", "en") => "Loading speech recognition model...".to_string(),
        ("loading_asr", _) => "正在加载语音识别模型...".to_string(),

        ("loading_llm", "en") => "Loading language model...".to_string(),
        ("loading_llm", _) => "正在加载语言模型...".to_string(),

        ("loading_tts", "en") => "Loading text-to-speech model...".to_string(),
        ("loading_tts", _) => "正在加载语音合成模型...".to_string(),

        ("service_ready", "en") => "Voice service ready".to_string(),
        ("service_ready", _) => "语音服务已就绪".to_string(),

        ("init_success", "en") => "Initialization successful".to_string(),
        ("init_success", _) => "初始化成功".to_string(),

        ("loading", "en") => "Loading...".to_string(),
        ("loading", _) => "正在加载...".to_string(),

        // Error messages
        ("startup_failed", "en") => "Startup failed".to_string(),
        ("startup_failed", _) => "启动失败".to_string(),

        ("config_dir_error", "en") => "Cannot get config directory".to_string(),
        ("config_dir_error", _) => "无法获取配置目录".to_string(),

        ("stdin_error", "en") => "Cannot get process input stream".to_string(),
        ("stdin_error", _) => "无法获取进程输入流".to_string(),

        ("stdout_error", "en") => "Cannot get process output stream".to_string(),
        ("stdout_error", _) => "无法获取进程输出流".to_string(),

        ("stderr_error", "en") => "Cannot get process error stream".to_string(),
        ("stderr_error", _) => "无法获取进程错误流".to_string(),

        ("daemon_exited", "en") => "Voice service exited unexpectedly".to_string(),
        ("daemon_exited", _) => "语音服务意外退出".to_string(),

        ("read_error", "en") => "Failed to read output".to_string(),
        ("read_error", _) => "读取输出失败".to_string(),

        ("timeout", "en") => "Voice service startup timeout. If downloading models, please wait 3 minutes and restart".to_string(),
        ("timeout", _) => "语音服务启动超时。如果是首次启动需要下载模型，请等待3分钟后重启应用".to_string(),

        ("resource_limits_failed", "en") => "Failed to set resource limits, continuing...".to_string(),
        ("resource_limits_failed", _) => "资源限制设置失败，继续启动...".to_string(),

        // Default fallback
        _ => message_key.to_string(),
    }
}

/// Get localized tray menu texts
fn get_tray_menu_texts(language: &str) -> (&'static str, &'static str, &'static str, &'static str) {
    match language {
        "en" => (
            "Show Window",
            "Hide Window",
            "Quit",
            "Speekium"
        ),
        _ => (
            "显示窗口",
            "隐藏窗口",
            "退出",
            "Speekium"
        ),
    }
}

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
    // Read language from config (creates config with system language if not exists)
    let language = get_language_from_config();
    let (show_text, hide_text, quit_text, tooltip_text) = get_tray_menu_texts(&language);

    // Store cleanup function globally
    *TRAY_CLEANUP.lock().unwrap() = Some(Box::new(move || {
        cleanup_fn();
    }));

    // Build menu with localized texts
    let menu = MenuBuilder::new(app)
        .item(&MenuItemBuilder::new(show_text).id("show").build(app)?)
        .item(&MenuItemBuilder::new(hide_text).id("hide").build(app)?)
        .separator()
        .item(&MenuItemBuilder::new(quit_text).id("quit").build(app)?)
        .build()?;

    // Load tray icon (template icon for macOS menu bar)
    let icon_bytes = include_bytes!("../icons/tray-template.png");
    let icon_image = image::load_from_memory(icon_bytes)
        .expect("Failed to load tray icon");
    let rgba = icon_image.to_rgba8();
    let (width, height) = rgba.dimensions();
    let tray_icon = Image::new_owned(rgba.into_raw(), width, height);

    // Create tray icon with explicit ID for later updates
    let _tray = TrayIconBuilder::with_id("main")
        .menu(&menu)
        .icon(tray_icon)
        .icon_as_template(true)
        .tooltip(tooltip_text)
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
                // Use global cleanup function
                if let Some(cleanup) = TRAY_CLEANUP.lock().unwrap().as_ref() {
                    cleanup();
                }
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

/// Update the tray menu with new language
/// This can be called when the user changes the language setting
pub fn update_tray_menu(app: &tauri::AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // Read current language from config
    let language = get_language_from_config();
    let (show_text, hide_text, quit_text, tooltip_text) = get_tray_menu_texts(&language);

    eprintln!("Updating tray menu with language: {}", language);

    // Build new menu with localized texts
    let menu = MenuBuilder::new(app)
        .item(&MenuItemBuilder::new(show_text).id("show").build(app)?)
        .item(&MenuItemBuilder::new(hide_text).id("hide").build(app)?)
        .separator()
        .item(&MenuItemBuilder::new(quit_text).id("quit").build(app)?)
        .build()?;

    // Get the tray by its ID and update menu
    if let Some(tray) = app.tray_by_id("main") {
        eprintln!("Found tray, updating menu");
        tray.set_menu(Some(menu))?;
        tray.set_tooltip(Some(tooltip_text))?;
        eprintln!("Tray menu updated successfully");
    } else {
        eprintln!("WARNING: Tray with ID 'main' not found!");
    }

    Ok(())
}
