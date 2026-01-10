use tauri::{
    image::Image,
    menu::{MenuBuilder, MenuItemBuilder},
    tray::{TrayIconBuilder, TrayIconEvent},
    Manager, Runtime,
};
use std::process::{Command, Stdio, Child, ChildStdin, ChildStdout};
use std::io::{BufReader, BufWriter, Write, BufRead};
use std::sync::Mutex;
use serde::{Deserialize, Serialize};

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
            .arg("../../worker_daemon.py")
            .arg("daemon")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())  // 将 stderr 输出到控制台
            .spawn()
            .map_err(|e| format!("Failed to start daemon: {}", e))?;

        let stdin = BufWriter::new(
            child.stdin.take().ok_or("Failed to get stdin")?
        );
        let stdout = BufReader::new(
            child.stdout.take().ok_or("Failed to get stdout")?
        );

        println!("✅ Python 守护进程已启动");

        Ok(PythonDaemon {
            process: child,
            stdin,
            stdout,
        })
    }

    fn send_command(&mut self, command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
        // 构造请求
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        // 发送到 stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        // 从 stdout 读取响应
        let mut line = String::new();
        self.stdout.read_line(&mut line)
            .map_err(|e| format!("Failed to read response: {}", e))?;

        // 解析 JSON
        serde_json::from_str(&line)
            .map_err(|e| format!("Failed to parse JSON: {}", e))
    }

    fn health_check(&mut self) -> bool {
        match self.send_command("health", serde_json::json!({})) {
            Ok(result) => {
                if let Some(obj) = result.as_object() {
                    return obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);
                }
                false
            }
            Err(_) => false
        }
    }
}

// 全局守护进程实例
static DAEMON: Mutex<Option<PythonDaemon>> = Mutex::new(None);

fn ensure_daemon_running() -> Result<(), String> {
    let mut daemon = DAEMON.lock().unwrap();

    // 如果守护进程已存在，先检查健康状态
    if let Some(ref mut d) = *daemon {
        if d.health_check() {
            return Ok(());  // 健康，直接返回
        }

        // 不健康，终止并重启
        println!("⚠️ 守护进程不健康，正在重启...");
        let _ = d.process.kill();
    }

    // 启动新的守护进程
    *daemon = Some(PythonDaemon::new()?);

    Ok(())
}

fn call_daemon(command: &str, args: serde_json::Value) -> Result<serde_json::Value, String> {
    ensure_daemon_running()?;

    let mut daemon = DAEMON.lock().unwrap();
    let daemon = daemon.as_mut().ok_or("Daemon not available")?;

    daemon.send_command(command, args)
}

// ============================================================================
// Tauri Commands
// ============================================================================

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn record_audio(mode: String, duration: Option<f32>) -> Result<RecordResult, String> {
    let duration_val = duration.unwrap_or(3.0);
    let args = serde_json::json!({
        "mode": mode,
        "duration": duration_val
    });

    println!("🎤 调用守护进程: record {}", args);

    let result = call_daemon("record", args)?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
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

    // 在单独的线程中处理流式响应
    std::thread::spawn(move || {
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                let _ = window.emit("chat-error", "Daemon not available");
                return;
            }
        };

        // 发送流式命令
        let request = serde_json::json!({
            "command": "chat_stream",
            "args": {"text": text}
        });

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            let _ = window.emit("chat-error", format!("Write error: {}", e));
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            let _ = window.emit("chat-error", format!("Flush error: {}", e));
            return;
        }

        // 循环读取流式输出
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - 守护进程可能崩溃
                    let _ = window.emit("chat-error", "Daemon connection lost");
                    break;
                }
                Ok(_) => {
                    // 解析 JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "chunk" => {
                                // 发送文本片段到前端
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-chunk", content);
                                }
                            }
                            "done" => {
                                // 流式响应完成
                                let _ = window.emit("chat-done", ());
                                break;
                            }
                            "error" => {
                                // 错误
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("chat-error", error);
                                }
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

    // 在单独的线程中处理流式响应
    std::thread::spawn(move || {
        let mut daemon = DAEMON.lock().unwrap();
        let daemon = match daemon.as_mut() {
            Some(d) => d,
            None => {
                let _ = window.emit("tts-error", "Daemon not available");
                return;
            }
        };

        // 发送流式命令
        let request = serde_json::json!({
            "command": "chat_tts_stream",
            "args": {
                "text": text,
                "auto_play": auto_play.unwrap_or(true)
            }
        });

        if let Err(e) = writeln!(daemon.stdin, "{}", request.to_string()) {
            let _ = window.emit("tts-error", format!("Write error: {}", e));
            return;
        }

        if let Err(e) = daemon.stdin.flush() {
            let _ = window.emit("tts-error", format!("Flush error: {}", e));
            return;
        }

        // 循环读取流式输出
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - 守护进程可能崩溃
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    break;
                }
                Ok(_) => {
                    // 解析 JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");

                        match chunk_type {
                            "text_chunk" => {
                                // 发送文本片段到前端
                                if let Some(content) = chunk.get("content").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-text-chunk", content);
                                }
                            }
                            "audio_chunk" => {
                                // 发送音频片段到前端
                                if let Some(audio_path) = chunk.get("audio_path").and_then(|v| v.as_str()) {
                                    let text = chunk.get("text").and_then(|v| v.as_str()).unwrap_or("");
                                    let _ = window.emit("tts-audio-chunk", serde_json::json!({
                                        "audio_path": audio_path,
                                        "text": text
                                    }));
                                }
                            }
                            "done" => {
                                // 流式响应完成
                                let _ = window.emit("tts-done", ());
                                break;
                            }
                            "error" => {
                                // 错误
                                if let Some(error) = chunk.get("error").and_then(|v| v.as_str()) {
                                    let _ = window.emit("tts-error", error);
                                }
                                break;
                            }
                            _ => {
                                println!("⚠️ Unknown chunk type: {}", chunk_type);
                            }
                        }
                    }
                }
                Err(e) => {
                    let _ = window.emit("tts-error", format!("Read error: {}", e));
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
async fn daemon_health() -> Result<HealthResult, String> {
    println!("🏥 守护进程健康检查");

    let result = call_daemon("health", serde_json::json!({}))?;

    serde_json::from_value(result)
        .map_err(|e| format!("Failed to parse result: {}", e))
}

// ============================================================================
// Global Shortcuts
// ============================================================================

fn register_shortcuts<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

    // 注册显示/隐藏窗口快捷键: Command+Shift+Space
    let shortcut: Shortcut = "CommandOrControl+Shift+Space".parse().unwrap();

    let app_handle = app.clone();
    app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, _event| {
        if let Some(window) = app_handle.get_webview_window("main") {
            if window.is_visible().unwrap_or(false) {
                let _ = window.hide();
            } else {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    }).map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to register shortcut: {}", e)))?;

    println!("✅ 全局快捷键已注册:");
    println!("   • Command+Shift+Space - 显示/隐藏窗口");

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

    // Load tray icon
    let icon_bytes = include_bytes!("../icons/32x32.png");
    let icon_image = image::load_from_memory(icon_bytes)
        .expect("Failed to load tray icon");
    let rgba = icon_image.to_rgba8();
    let (width, height) = rgba.dimensions();
    let tray_icon = Image::new_owned(rgba.into_raw(), width, height);

    // Create tray icon
    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .icon(tray_icon)
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
                // 清理守护进程
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
        // 发送退出命令
        let _ = d.send_command("exit", serde_json::json!({}));

        // 等待进程退出
        let _ = d.process.wait();

        println!("✅ 守护进程已关闭");
    }
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
            daemon_health
        ])
        .setup(|app| {
            // 创建托盘图标
            create_tray(app.handle())?;

            // 注册快捷键
            register_shortcuts(app.handle())?;

            // 启动守护进程
            ensure_daemon_running()
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to start daemon: {}", e)))?;

            println!("✅ Speekium 应用已启动 (守护进程模式)");

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // 窗口关闭时隐藏而不是退出
                window.hide().unwrap();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                // 应用退出时清理守护进程
                cleanup_daemon();
            }
        });
}
