use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{TrayIconBuilder, TrayIconEvent},
    webview::WebviewWindowBuilder,
    Emitter, Manager, Runtime, State,
};
use std::process::{Command, Stdio, Child, ChildStdin, ChildStdout, ChildStderr};
use std::io::{BufReader, BufWriter, Write, BufRead};
use std::sync::{Mutex, atomic::{AtomicBool, Ordering}};
use serde::{Deserialize, Serialize};

mod database;
use database::{Database, Session, Message, PaginatedResult};

// ============================================================================
// Data Structures
// ============================================================================

#[derive(Serialize, Deserialize, Debug)]
struct RecordResult {
    success: bool,
    text: Option<String>,
    language: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ChatResult {
    success: bool,
    content: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct TTSResult {
    success: bool,
    audio_path: Option<String>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct ConfigResult {
    success: bool,
    config: Option<serde_json::Value>,
    error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct HealthResult {
    success: bool,
    status: Option<String>,
    command_count: Option<u32>,
    models_loaded: Option<serde_json::Value>,
    error: Option<String>,
}

// ============================================================================
// Python Daemon Manager
// ============================================================================

struct PythonDaemon {
    process: Child,
    stdin: BufWriter<ChildStdin>,
    stdout: BufReader<ChildStdout>,
}

impl PythonDaemon {
    fn new() -> Result<Self, String> {
        println!("🚀 启动 Python 守护进程...");

        let mut child = Command::new("python3")
            .arg("../worker_daemon.py")
            .arg("daemon")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())  // Capture stderr for PTT events
            .spawn()
            .map_err(|e| format!("Failed to start daemon: {}", e))?;

        let stdin = BufWriter::new(
            child.stdin.take().ok_or("Failed to get stdin")?
        );
        let mut stdout = BufReader::new(
            child.stdout.take().ok_or("Failed to get stdout")?
        );
        let stderr = BufReader::new(
            child.stderr.take().ok_or("Failed to get stderr")?
        );

        // Store stderr in global variable for PTT event reader
        {
            let mut ptt_stderr = PTT_STDERR.lock().unwrap();
            *ptt_stderr = Some(stderr);
        }

        // Wait for daemon initialization - read stdout until "ready" event
        // Daemon takes ~7s to load models, set 15s timeout
        use std::time::{Duration, Instant};
        let start = Instant::now();
        let timeout = Duration::from_secs(15);
        let mut initialized = false;

        println!("⏳ 等待守护进程初始化...");

        while start.elapsed() < timeout {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon exited unexpectedly
                    println!("❌ 守护进程在初始化期间退出");
                    return Err("Daemon exited during initialization".to_string());
                }
                Ok(_) => {
                    // Parse JSON log events
                    if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(event_type) = event.get("event").and_then(|v| v.as_str()) {
                            println!("📋 守护进程事件: {}", event_type);

                            // Check if this is the "ready" daemon_success event (last init event)
                            if event_type == "daemon_success" {
                                if let Some(message) = event.get("message").and_then(|v| v.as_str()) {
                                    if message.contains("就绪") || message.contains("ready") {
                                        initialized = true;
                                        println!("✨ 守护进程初始化完成");
                                        break;
                                    }
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    println!("❌ 读取守护进程输出失败: {}", e);
                    return Err(format!("Failed to read daemon output: {}", e));
                }
            }
        }

        if !initialized {
            println!("❌ 守护进程初始化超时 (15 秒)");
            return Err("Daemon initialization timeout (15 seconds)".to_string());
        }

        println!("✅ Python 守护进程已启动");

        Ok(PythonDaemon {
            process: child,
            stdin,
            stdout,
        })
    }

    fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
        // Build request
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        println!("📤 发送命令: {}", command);

        // Send to stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        println!("⏳ 等待响应...");

        // Read response from stdout, skip log events
        // Daemon log events have "event" field, command responses have "success" field
        loop {
            let mut line = String::new();
            self.stdout.read_line(&mut line)
                .map_err(|e| {
                    println!("❌ 读取响应失败: {}", e);
                    format!("Failed to read response: {}", e)
                })?;

            // Parse JSON
            let result: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| {
                    println!("❌ JSON 解析失败: {} | 原始内容: {}", e, line);
                    format!("Failed to parse JSON: {}", e)
                })?;

            // Check if this is a log event (has "event" field)
            if result.get("event").is_some() {
                println!("📋 跳过日志事件: {}", result.get("event").unwrap().as_str().unwrap_or("unknown"));
                continue;  // Skip log, continue reading next line
            }

            // This is a command response (has "success" field or other response fields)
            println!("📥 收到命令响应: {}", line.trim());
            return Ok(result);
        }
    }

    fn health_check(&mut self) -> bool {
        println!("🏥 执行健康检查...");
        match self.send_command("health", serde_json::json!({})) {
            Ok(result) => {
                println!("✅ 健康检查响应: {:?}", result);
                if let Some(obj) = result.as_object() {
                    let success = obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                    println!("🔍 success 字段: {}", success);
                    return success;
                }
                println!("⚠️ 响应不是对象");
                false
            }
            Err(e) => {
                println!("❌ 健康检查失败: {}", e);
                false
            }
        }
    }
}

// Global daemon instance
static DAEMON: Mutex<Option<PythonDaemon>> = Mutex::new(None);

// PTT stderr reader handle
static PTT_STDERR: Mutex<Option<BufReader<ChildStderr>>> = Mutex::new(None);

// Streaming operation flag - prevent health checks from interfering
static STREAMING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

fn ensure_daemon_running() -> Result<(), String> {
    let mut daemon = DAEMON.lock().unwrap();

    // If daemon exists, check health first
    if let Some(ref mut d) = *daemon {
        // Skip health check during streaming
        if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
            println!("⏸️ 流式操作进行中，跳过 ensure_daemon 健康检查");
            return Ok(());
        }

        if d.health_check() {
            return Ok(());  // Healthy, return directly
        }

        // Unhealthy, terminate and restart
        println!("⚠️ 守护进程不健康，正在重启...");
        let _ = d.process.kill();
    }

    // Start new daemon
    *daemon = Some(PythonDaemon::new()?);

    Ok(())
}

fn call_daemon(command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    ensure_daemon_running()?;

    let mut daemon = DAEMON.lock().unwrap();
    let daemon = daemon.as_mut().ok_or("Daemon not available")?;

    daemon.send_command(command, args)
}

/// Start PTT (Push-to-Talk) event reader
/// Listen to Python daemon stderr in background thread, parse PTT events and forward to frontend
fn start_ptt_reader<R: Runtime>(app_handle: tauri::AppHandle<R>) {
    std::thread::spawn(move || {
        println!("🎧 PTT 事件读取器启动");

        loop {
            // Get stderr reader
            let line = {
                let mut ptt_stderr = PTT_STDERR.lock().unwrap();
                if let Some(ref mut stderr) = *ptt_stderr {
                    let mut line = String::new();
                    match stderr.read_line(&mut line) {
                        Ok(0) => {
                            println!("🔚 PTT: stderr EOF - 守护进程可能已退出");
                            break;
                        }
                        Ok(_) => Some(line),
                        Err(e) => {
                            println!("❌ PTT: 读取 stderr 失败: {}", e);
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
                        println!("🎤 PTT 事件: {}", ptt_event);

                        // Get main window and floating window
                        let main_window = app_handle.get_webview_window("main");
                        let overlay_window = app_handle.get_webview_window("ptt-overlay");

                        // Send state to floating window and control visibility
                        if let Some(ref overlay) = overlay_window {
                            match ptt_event {
                                "recording" => {
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
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
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
                                        let _ = overlay.hide();
                                    }
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-chunk", content);
                                    }
                                }
                                "assistant_done" => {
                                    // LLM response complete - ensure overlay is hidden
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
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
                                    let _ = window.emit("ptt-state", "error");
                                    if let Some(error) = event.get("error").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-error", error);
                                    }
                                }
                                _ => {
                                    println!("⚠️ PTT: 未知事件类型: {}", ptt_event);
                                }
                            }
                        }
                    }
                } else {
                    // Not a PTT event JSON, output as regular log
                    println!("📋 daemon stderr: {}", line);
                }
            }
        }

        println!("🛑 PTT 事件读取器退出");
    });
}

// ============================================================================
// App State (for Database)
// ============================================================================

pub struct AppState {
    pub db: Database,
}

// ============================================================================
// Text Input Commands (macOS)
// ============================================================================

#[cfg(target_os = "macos")]
fn char_to_key_code(ch: char) -> Option<u16> {
    // macOS virtual key codes
    // Reference: https://cdecl.org/wiki/Virtual_Key_Codes
    match ch {
        // Letters (A-Z) - all map to same key code, shift determines case
        'a'..='z' | 'A'..='Z' => Some(0),  // kVK_ANSI_A

        // Numbers (0-9)
        '0' => Some(29),  // kVK_ANSI_0
        '1'..='9' => Some(((ch as u8) - (b'1') + 18) as u16),  // kVK_ANSI_1 through kVK_ANSI_9

        // Special characters
        ' ' => Some(49),   // kVK_Space
        '\n' | '\r' => Some(36),  // kVK_Return
        '\t' => Some(48),  // kVK_Tab
        '.' => Some(47),   // kVK_ANSI_Period
        ',' => Some(43),   // kVK_ANSI_Comma
        '?' => Some(44),   // kVK_ANSI_Slash (with shift)
        '!' => Some(18),   // kVK_ANSI_1 (with shift)
        '@' => Some(19),   // kVK_ANSI_2 (with shift)
        '#' => Some(20),   // kVK_ANSI_3 (with shift)
        '$' => Some(21),   // kVK_ANSI_4 (with shift)
        '%' => Some(23),   // kVK_ANSI_5 (with shift)
        '^' => Some(22),   // kVK_ANSI_6 (with shift)
        '&' => Some(26),   // kVK_ANSI_7 (with shift)
        '*' => Some(28),   // kVK_ANSI_8 (with shift)
        '(' => Some(25),   // kVK_ANSI_9 (with shift)
        ')' => Some(29),   // kVK_ANSI_0 (with shift)
        '-' => Some(27),   // kVK_ANSI_Minus
        '_' => Some(27),   // kVK_ANSI_Minus (with shift)
        '=' => Some(24),   // kVK_ANSI_Equal
        '+' => Some(24),   // kVK_ANSI_Equal (with shift)
        '[' => Some(33),   // kVK_ANSI_LeftBracket
        ']' => Some(30),   // kVK_ANSI_RightBracket
        '{' => Some(33),   // kVK_ANSI_LeftBracket (with shift)
        '}' => Some(30),   // kVK_ANSI_RightBracket (with shift)
        '\\' => Some(42),  // kVK_ANSI_Backslash
        '|' => Some(42),   // kVK_ANSI_Backslash (with shift)
        ';' => Some(41),   // kVK_ANSI_Semicolon
        ':' => Some(41),   // kVK_ANSI_Semicolon (with shift)
        '\'' => Some(39),  // kVK_ANSI_Quote
        '"' => Some(39),   // kVK_ANSI_Quote (with shift)
        '`' => Some(50),   // kVK_ANSI_Grave
        '~' => Some(50),   // kVK_ANSI_Grave (with shift)
        '/' => Some(44),   // kVK_ANSI_Slash
        '<' => Some(43),   // kVK_ANSI_Comma (with shift)
        '>' => Some(47),   // kVK_ANSI_Period (with shift)

        _ => None,  // Unsupported character
    }
}

#[cfg(target_os = "macos")]
fn type_text(text: &str) -> Result<(), String> {
    use cocoa::appkit::NSPasteboard;
    use cocoa::base::{id, nil};
    use cocoa::foundation::NSString as CFString;
    use core_graphics::event::{CGEvent, CGEventTapLocation, CGEventFlags};
    use core_graphics::event_source::{CGEventSource, CGEventSourceStateID};
    use objc::{msg_send, sel, sel_impl, class};

    println!("⌨️  使用剪贴板输入文字: {}", text);

    // 1. Save current clipboard content
    let pasteboard: id = unsafe { msg_send![class!(NSPasteboard), generalPasteboard] };

    // Use NSPasteboardTypeString constant
    let pasteboard_type = unsafe { CFString::alloc(nil).init_str("public.utf8-plain-text") };
    let old_content: id = unsafe { msg_send![pasteboard, stringForType: pasteboard_type] };

    println!("📋 已保存旧剪贴板内容");

    // Define clipboard restoration function
    let restore_clipboard = || -> Result<(), String> {
        if old_content != nil {
            unsafe {
                let _: () = msg_send![pasteboard, clearContents];
                let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
                let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
                let success: bool = msg_send![pasteboard, setString: old_content forType: pasteboard_type];

                if !success {
                    eprintln!("⚠️  警告：剪贴板恢复失败，用户数据可能丢失");
                    return Err("Failed to restore clipboard".to_string());
                }
            }
            println!("🔄 已恢复原剪贴板内容");
        }
        Ok(())
    };

    // 2. Set new content to clipboard
    let ns_string = unsafe { CFString::alloc(nil).init_str(text) };

    unsafe {
        let _: () = msg_send![pasteboard, clearContents];
        let types: id = msg_send![class!(NSArray), arrayWithObject: pasteboard_type];
        let _: () = msg_send![pasteboard, declareTypes: types owner: nil];
        let success: bool = msg_send![pasteboard, setString: ns_string forType: pasteboard_type];

        if !success {
            println!("⚠️  剪贴板设置失败");
            // Attempt to restore clipboard
            let _ = restore_clipboard();
            return Err("Failed to set clipboard content".to_string());
        }
    }

    println!("✅ 已设置新剪贴板内容");

    // 3. Create event source
    let event_source = CGEventSource::new(CGEventSourceStateID::HIDSystemState)
        .map_err(|e| format!("Failed to create event source: {:?}", e))?;

    // 4. Simulate Cmd+V keypress
    // Cmd key code is 55 (kVK_Command)
    let cmd_key_code: u16 = 55;
    // V key code is 9 (kVK_ANSI_V)
    let v_key_code: u16 = 9;

    // Press Cmd
    let cmd_down = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, true)
        .map_err(|e| format!("Failed to create Cmd key down event: {:?}", e))?;
    cmd_down.set_flags(CGEventFlags::CGEventFlagCommand);
    cmd_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 Cmd");

    // Press V (with Cmd flag)
    let v_down = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, true)
        .map_err(|e| format!("Failed to create V key down event: {:?}", e))?;
    v_down.set_flags(CGEventFlags::CGEventFlagCommand);
    v_down.post(CGEventTapLocation::Session);
    println!("⌨️  按下 V");

    // Release V
    let v_up = CGEvent::new_keyboard_event(event_source.clone(), v_key_code, false)
        .map_err(|e| format!("Failed to create V key up event: {:?}", e))?;
    v_up.set_flags(CGEventFlags::CGEventFlagCommand);
    v_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 V");

    // Release Cmd
    let cmd_up = CGEvent::new_keyboard_event(event_source.clone(), cmd_key_code, false)
        .map_err(|e| format!("Failed to create Cmd key up event: {:?}", e))?;
    cmd_up.post(CGEventTapLocation::Session);
    println!("⌨️  释放 Cmd");

    // Wait for paste to complete
    std::thread::sleep(std::time::Duration::from_millis(50));

    // 5. Restore original clipboard content
    restore_clipboard()?;

    println!("⌨️  文字输入完成");
    Ok(())
}

#[cfg(not(target_os = "macos"))]
fn type_text(_text: &str) -> Result<(), String> {
    Err("Text input is only supported on macOS".to_string())
}

#[tauri::command]
async fn type_text_command(text: String) -> Result<String, String> {
    println!("⌨️  Typing text: {} ({} chars)", text, text.chars().count());

    type_text(&text)?;

    Ok(format!("Typed {} characters", text.chars().count()))
}

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
) -> Result<PaginatedResult<Session>, String> {
    state.db.list_sessions(page, page_size)
}

#[tauri::command]
async fn db_get_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<Session, String> {
    state.db.get_session(&session_id)
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

    println!("🎤 调用守护进程: record {}", args);

    // Send recording start state to all windows (unified state sync)
    emit_ptt_state(&app_handle, "recording");

    let result = call_daemon("record", args);

    // Send processing state
    emit_ptt_state(&app_handle, "processing");

    // Handle result
    let parsed_result = result.and_then(|r| {
        serde_json::from_value(r)
            .map_err(|e| format!("Failed to parse result: {}", e))
    });

    // Send idle state
    emit_ptt_state(&app_handle, "idle");

    parsed_result
}

/// Send PTT state to all windows
fn emit_ptt_state(app_handle: &tauri::AppHandle, state: &str) {
    // Send to main window
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // Send to floating window
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // Control floating window visibility
        match state {
            "recording" | "processing" => {
                // Recalculate position before showing (in case screen config changed)
                match calculate_overlay_position(app_handle) {
                    Ok((x, y)) => {
                        if let Err(e) = overlay.set_position(tauri::Position::Logical(tauri::LogicalPosition { x, y })) {
                            eprintln!("❌ Failed to set PTT overlay position: {}", e);
                        }
                    }
                    Err(e) => {
                        eprintln!("❌ Failed to calculate PTT overlay position: {}, showing anyway", e);
                    }
                }
                let _ = overlay.show();
            }
            "idle" | "error" => {
                let _ = overlay.hide();
            }
            _ => {}
        }
    }
}

#[tauri::command]
async fn chat_llm(text: String) -> Result<ChatResult, String> {
    let args = serde_json::json!({
        "text": text
    });

    println!("💬 调用守护进程: chat");

    let result = call_daemon("chat", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn chat_llm_stream(
    window: tauri::Window,
    text: String
) -> Result<(), String> {
    println!("💬 调用守护进程: chat_stream");

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
                                println!("⚠️ Unknown chunk type: {}", chunk_type);
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
    println!("💬🔊 调用守护进程: chat_tts_stream");

    // Set streaming operation flag
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // Handle streaming response in separate thread
    std::thread::spawn(move || {
        println!("🧵 TTS 流式线程启动");
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                println!("❌ TTS 流式线程：守护进程不可用");
                let _ = window.emit("tts-error", "Daemon not available");
                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                return;
            }
        };

        println!("🔒 TTS 流式线程：已获取守护进程锁");

        // Send streaming command
        let request = serde_json::json!({
            "command": "chat_tts_stream",
            "args": {
                "text": text.clone(),
                "auto_play": auto_play.unwrap_or(true)
            }
        });

        println!("📤 TTS 流式线程：发送命令 - {}", text);

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            println!("❌ TTS 流式线程：写入失败 - {}", e);
            let _ = window.emit("tts-error", format!("Write error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            println!("❌ TTS 流式线程：刷新失败 - {}", e);
            let _ = window.emit("tts-error", format!("Flush error: {}", e));
            STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
            return;
        }

        println!("✅ TTS 流式线程：命令已发送，开始读取响应...");

        // Loop to read streaming output
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - daemon may have crashed
                    println!("❌ TTS 流式线程：读到 EOF");
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(n) => {
                    println!("📥 TTS 流式线程：读到 {} 字节: {}", n, line.trim());

                    // Parse JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        println!("✅ TTS 流式线程：JSON 解析成功: {:?}", chunk);

                        // Skip log events (have "event" field)
                        if chunk.get("event").is_some() {
                            println!("⏭️ TTS 流式线程：跳过日志事件");
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");
                        println!("🔍 TTS 流式线程：chunk_type = {}", chunk_type);

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
                                println!("⚠️ TTS 流式线程：Unknown chunk type: {}", chunk_type);
                            }
                        }
                    } else {
                        println!("❌ TTS 流式线程：JSON 解析失败，原始内容: {}", line.trim());
                    }
                }
                Err(e) => {
                    println!("❌ TTS 流式线程：读取错误: {}", e);
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

    println!("🔊 调用守护进程: tts");

    let result = call_daemon("tts", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn load_config() -> Result<ConfigResult, String> {
    println!("⚙️ 调用守护进程: config");

    let result = call_daemon("config", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn save_config(config: serde_json::Value) -> Result<serde_json::Value, String> {
    println!("💾 调用守护进程: save_config, work_mode = {}", config.get("work_mode").and_then(|v| v.as_str()).unwrap_or("MISSING"));

    // Pass config directly, do not re-wrap
    // Frontend already passed { config: updatedConfig }
    // Pass config directly as parameter to Python daemon
    call_daemon("save_config", config)
}

#[tauri::command]
async fn daemon_health() -> Result<HealthResult, String> {
    // Check if there is an ongoing streaming operation
    if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
        println!("⏸️ 流式操作进行中，跳过健康检查");
        return Ok(HealthResult {
            success: true,
            status: Some("streaming".to_string()),
            command_count: None,
            models_loaded: None,
            error: None,
        });
    }

    println!("🏥 守护进程健康检查");

    let result = call_daemon("health", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

#[tauri::command]
async fn test_ollama_connection(base_url: String, model: String) -> Result<serde_json::Value, String> {
    println!("🔗 测试 Ollama 连接: {} ({})", base_url, model);

    // Use reqwest to test Ollama connection directly
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    // Test 1: Check if Ollama service is running
    let tags_url = format!("{}/api/tags", base_url);
    let response = client
        .get(&tags_url)
        .send()
        .await;

    match response {
        Ok(resp) => {
            if resp.status().is_success() {
                println!("✅ Ollama 服务运行正常");

                // Test 2: Check if specified model exists
                let models = resp.json::<serde_json::Value>()
                    .await
                    .map_err(|e| format!("Failed to parse models list: {}", e))?;

                if let Some(models_array) = models.get("models").and_then(|m| m.as_array()) {
                    let model_exists = models_array.iter().any(|m| {
                        m.get("name")
                            .and_then(|n| n.as_str())
                            .map(|n| n.starts_with(&model) || n == model)
                            .unwrap_or(false)
                    });

                    if model_exists {
                        println!("✅ 模型 {} 已安装", model);
                        return Ok(serde_json::json!({
                            "success": true,
                            "message": format!("连接成功，模型 {} 已安装", model)
                        }));
                    } else {
                        println!("⚠️ 模型 {} 未找到", model);
                        return Ok(serde_json::json!({
                            "success": false,
                            "error": format!("模型 {} 未安装，请先运行: ollama pull {}", model, model)
                        }));
                    }
                } else {
                    return Ok(serde_json::json!({
                        "success": false,
                        "error": "无法解析模型列表"
                    }));
                }
            } else {
                println!("❌ Ollama 服务返回错误: {}", resp.status());
                return Ok(serde_json::json!({
                    "success": false,
                    "error": format!("Ollama 服务返回错误状态: {}", resp.status())
                }));
            }
        }
        Err(e) => {
            println!("❌ 连接 Ollama 失败: {}", e);
            return Ok(serde_json::json!({
                "success": false,
                "error": format!("无法连接到 Ollama 服务: {}", e)
            }));
        }
    }
}

// ============================================================================
// Global Shortcuts
// ============================================================================

fn register_shortcuts<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

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

    // PTT shortcut is now handled by Python daemon's HotkeyManager (supports Cmd+Alt)
    // No longer need to register in Tauri

    println!("✅ 全局快捷键已注册:");
    println!("   • Command+Shift+Space - 显示/隐藏窗口");
    println!("   • Command+Alt (Python pynput) - Push-to-Talk (按住说话)");

    Ok(())
}

// ============================================================================
// Tray Icon
// ============================================================================

fn create_tray<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
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
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            "hide" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.hide();
                }
            }
            "quit" => {
                // Clean up daemon
                cleanup_daemon();
                app.exit(0);
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { .. } = event {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}

// ============================================================================
// Cleanup
// ============================================================================

fn cleanup_daemon() {
    println!("🧹 清理守护进程...");

    let mut daemon = DAEMON.lock().unwrap();
    if let Some(mut d) = daemon.take() {
        // Send exit command
        let _ = d.send_command("exit", serde_json::json!({}));

        // Wait for process to exit
        let _ = d.process.wait();

        println!("✅ 守护进程已关闭");
    }
}

// ============================================================================
// PTT Overlay Window
// ============================================================================

// PTT Overlay window constants
const OVERLAY_WIDTH: f64 = 140.0;
const OVERLAY_HEIGHT: f64 = 50.0;
const BOTTOM_MARGIN: f64 = 60.0;

/// Calculate PTT overlay window position based on current screen size
fn calculate_overlay_position<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(f64, f64), Box<dyn std::error::Error>> {
    let monitor = app.primary_monitor()?.ok_or_else(|| Box::<dyn std::error::Error>::from("No primary monitor found"))?;
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
        eprintln!("⚠️ Warning: Calculated PTT overlay position may exceed screen bounds");
    }

    Ok((x, y))
}

fn create_ptt_overlay<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    // Calculate initial position
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
    .shadow(false)  // Disable window shadow for better transparency
    .build()?;

    println!("✅ PTT 浮动窗口已创建 ({}x{} @ {}, {})", OVERLAY_WIDTH, OVERLAY_HEIGHT, x, y);

    Ok(())
}

// ============================================================================
// Main Entry Point
// ============================================================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            greet,
            record_audio,
            chat_llm,
            chat_llm_stream,
            chat_tts_stream,
            generate_tts,
            load_config,
            save_config,
            daemon_health,
            test_ollama_connection,
            type_text_command,
            // Database commands
            db_create_session,
            db_list_sessions,
            db_get_session,
            db_update_session,
            db_delete_session,
            db_add_message,
            db_get_messages,
            db_delete_message
        ])
        .setup(|app| {
            // Initialize database
            let db_path = database::get_database_path(app.handle())
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to get database path: {}", e)))?;

            let db = Database::new(db_path)
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to initialize database: {}", e)))?;

            app.manage(AppState { db });
            println!("✅ 数据库已初始化");

            // Create tray icon
            create_tray(app.handle())?;

            // Register shortcuts
            register_shortcuts(app.handle())?;

            // Start daemon
            ensure_daemon_running()
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to start daemon: {}", e)))?;

            // Start PTT event reader (listen to Python daemon stderr)
            start_ptt_reader(app.handle().clone());

            // Create PTT floating state window
            if let Err(e) = create_ptt_overlay(app.handle()) {
                println!("⚠️ 创建 PTT 浮动窗口失败: {}", e);
            }

            println!("✅ Speekium 应用已启动 (守护进程模式)");
            println!("🎤 PTT 快捷键: Cmd+Alt (按住说话，松开结束)");

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
            match event {
                tauri::RunEvent::Reopen { .. } => {
                    // macOS: Show main window when dock icon is clicked
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                tauri::RunEvent::ExitRequested { .. } => {
                    // Clean up daemon on app exit
                    cleanup_daemon();
                }
                _ => {}
            }
        });
}
