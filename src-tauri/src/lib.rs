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
            .stderr(Stdio::piped())  // 捕获 stderr 用于 PTT 事件
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

        // 存储 stderr 到全局变量，供 PTT 事件读取器使用
        {
            let mut ptt_stderr = PTT_STDERR.lock().unwrap();
            *ptt_stderr = Some(stderr);
        }

        // 等待守护进程初始化完成 - 读取 stdout 直到看到带 "就绪" 消息的事件
        // 守护进程加载模型需要约 7 秒，设置 15 秒超时
        use std::time::{Duration, Instant};
        let start = Instant::now();
        let timeout = Duration::from_secs(15);
        let mut initialized = false;

        println!("⏳ 等待守护进程初始化...");

        while start.elapsed() < timeout {
            let mut line = String::new();
            match stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - 守护进程意外退出
                    println!("❌ 守护进程在初始化期间退出");
                    return Err("Daemon exited during initialization".to_string());
                }
                Ok(_) => {
                    // 解析 JSON 日志事件
                    if let Ok(event) = serde_json::from_str::<serde_json::Value>(&line) {
                        if let Some(event_type) = event.get("event").and_then(|v| v.as_str()) {
                            println!("📋 守护进程事件: {}", event_type);

                            // 检查是否是带"就绪"消息的 daemon_success 事件（最后一个初始化事件）
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
        // 构造请求
        let request = serde_json::json!({
            "command": command,
            "args": args
        });

        println!("📤 发送命令: {}", command);

        // 发送到 stdin
        writeln!(self.stdin, "{}", request.to_string())
            .map_err(|e| format!("Failed to write command: {}", e))?;

        self.stdin.flush()
            .map_err(|e| format!("Failed to flush stdin: {}", e))?;

        println!("⏳ 等待响应...");

        // 从 stdout 读取响应，跳过日志事件
        // 守护进程的日志事件有 "event" 字段，命令响应有 "success" 字段
        loop {
            let mut line = String::new();
            self.stdout.read_line(&mut line)
                .map_err(|e| {
                    println!("❌ 读取响应失败: {}", e);
                    format!("Failed to read response: {}", e)
                })?;

            // 解析 JSON
            let result: serde_json::Value = serde_json::from_str(&line)
                .map_err(|e| {
                    println!("❌ JSON 解析失败: {} | 原始内容: {}", e, line);
                    format!("Failed to parse JSON: {}", e)
                })?;

            // 检查是否是日志事件（有 "event" 字段）
            if result.get("event").is_some() {
                println!("📋 跳过日志事件: {}", result.get("event").unwrap().as_str().unwrap_or("unknown"));
                continue;  // 跳过日志，继续读取下一行
            }

            // 这是命令响应（有 "success" 字段或其他响应字段）
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

// 全局守护进程实例
static DAEMON: Mutex<Option<PythonDaemon>> = Mutex::new(None);

// PTT stderr reader handle
static PTT_STDERR: Mutex<Option<BufReader<ChildStderr>>> = Mutex::new(None);

// 流式操作标志 - 防止健康检查干扰流式操作
static STREAMING_IN_PROGRESS: AtomicBool = AtomicBool::new(false);

fn ensure_daemon_running() -> Result<(), String> {
    let mut daemon = DAEMON.lock().unwrap();

    // 如果守护进程已存在，先检查健康状态
    if let Some(ref mut d) = *daemon {
        // 流式操作期间跳过健康检查
        if STREAMING_IN_PROGRESS.load(Ordering::SeqCst) {
            println!("⏸️ 流式操作进行中，跳过 ensure_daemon 健康检查");
            return Ok(());
        }

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

/// 启动 PTT (Push-to-Talk) 事件读取器
/// 在后台线程中监听 Python daemon 的 stderr，解析 PTT 事件并转发到前端
fn start_ptt_reader<R: Runtime>(app_handle: tauri::AppHandle<R>) {
    std::thread::spawn(move || {
        println!("🎧 PTT 事件读取器启动");

        loop {
            // 获取 stderr 读取器
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
                    // stderr 尚未就绪，等待一下
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

                // 尝试解析为 JSON PTT 事件
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(line) {
                    if let Some(ptt_event) = event.get("ptt_event").and_then(|v| v.as_str()) {
                        println!("🎤 PTT 事件: {}", ptt_event);

                        // 获取主窗口和浮动窗口
                        let main_window = app_handle.get_webview_window("main");
                        let overlay_window = app_handle.get_webview_window("ptt-overlay");

                        // 发送状态到浮动窗口并控制显示/隐藏
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

                        // 发送完整事件到主窗口
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
                                    // 用户语音识别结果 - 隐藏覆盖层，显示消息
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
                                    // LLM 流式响应片段 - 确保覆盖层已隐藏
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        let _ = overlay.hide();
                                    }
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-chunk", content);
                                    }
                                }
                                "assistant_done" => {
                                    // LLM 响应完成 - 确保覆盖层已隐藏
                                    let _ = window.emit("ptt-state", "idle");
                                    if let Some(ref overlay) = overlay_window {
                                        let _ = overlay.hide();
                                    }
                                    if let Some(content) = event.get("content").and_then(|v| v.as_str()) {
                                        let _ = window.emit("ptt-assistant-done", content);
                                    }
                                }
                                "audio_chunk" => {
                                    // TTS 音频片段
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
                    // 不是 PTT 事件 JSON，作为普通日志输出
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
    // 处理 duration 参数：支持数字字符串、"auto" 或空值
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

    // 发送录音开始状态到所有窗口（统一状态同步）
    emit_ptt_state(&app_handle, "recording");

    let result = call_daemon("record", args);

    // 发送处理中状态
    emit_ptt_state(&app_handle, "processing");

    // 处理结果
    let parsed_result = result.and_then(|r| {
        serde_json::from_value(r)
            .map_err(|e| format!("Failed to parse result: {}", e))
    });

    // 发送空闲状态
    emit_ptt_state(&app_handle, "idle");

    parsed_result
}

/// 发送 PTT 状态到所有窗口
fn emit_ptt_state(app_handle: &tauri::AppHandle, state: &str) {
    // 发送到主窗口
    if let Some(main_window) = app_handle.get_webview_window("main") {
        let _ = main_window.emit("ptt-state", state);
    }
    // 发送到浮动窗口
    if let Some(overlay) = app_handle.get_webview_window("ptt-overlay") {
        let _ = overlay.emit("ptt-state", state);
        // 控制浮动窗口显示/隐藏
        match state {
            "recording" | "processing" => {
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

    // 设置流式操作标志
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // 在单独的线程中处理流式响应
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

        // 发送流式命令
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

        // 循环读取流式输出
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - 守护进程可能崩溃
                    let _ = window.emit("chat-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(_) => {
                    // 解析 JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        // 跳过日志事件（有 "event" 字段）
                        if chunk.get("event").is_some() {
                            continue;
                        }

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
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // 错误
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

    // 设置流式操作标志
    STREAMING_IN_PROGRESS.store(true, Ordering::SeqCst);

    // 在单独的线程中处理流式响应
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

        // 发送流式命令
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

        // 循环读取流式输出
        loop {
            let mut line = String::new();
            match daemon.stdout.read_line(&mut line) {
                Ok(0) => {
                    // EOF - 守护进程可能崩溃
                    println!("❌ TTS 流式线程：读到 EOF");
                    let _ = window.emit("tts-error", "Daemon connection lost");
                    STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                    break;
                }
                Ok(n) => {
                    println!("📥 TTS 流式线程：读到 {} 字节: {}", n, line.trim());

                    // 解析 JSON
                    if let Ok(chunk) = serde_json::from_str::<serde_json::Value>(&line) {
                        println!("✅ TTS 流式线程：JSON 解析成功: {:?}", chunk);

                        // 跳过日志事件（有 "event" 字段）
                        if chunk.get("event").is_some() {
                            println!("⏭️ TTS 流式线程：跳过日志事件");
                            continue;
                        }

                        let chunk_type = chunk.get("type").and_then(|v| v.as_str()).unwrap_or("");
                        println!("🔍 TTS 流式线程：chunk_type = {}", chunk_type);

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
                                STREAMING_IN_PROGRESS.store(false, Ordering::SeqCst);
                                break;
                            }
                            "error" => {
                                // 错误
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
    println!("💾 调用守护进程: save_config");

    let args = serde_json::json!({
        "config": config
    });

    call_daemon("save_config", args)
}

#[tauri::command]
async fn daemon_health() -> Result<HealthResult, String> {
    // 检查是否有流式操作正在进行
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

// ============================================================================
// Global Shortcuts
// ============================================================================

fn register_shortcuts<R: Runtime>(app: &tauri::AppHandle<R>) -> tauri::Result<()> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

    // 注册显示/隐藏窗口快捷键: Command+Shift+Space
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

    // PTT 快捷键现在由 Python daemon 的 HotkeyManager 处理 (支持 Cmd+Alt)
    // 不再需要在 Tauri 中注册

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
// PTT Overlay Window
// ============================================================================

fn create_ptt_overlay<R: Runtime>(app: &tauri::AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    // 获取主显示器信息
    let monitor = app.primary_monitor()?.ok_or("No primary monitor found")?;
    let screen_size = monitor.size();
    let scale_factor = monitor.scale_factor();

    // 窗口尺寸（精简设计）
    let window_width: u32 = 140;
    let window_height: u32 = 50;

    // 计算底部居中位置
    let x = ((screen_size.width as f64 / scale_factor) / 2.0 - (window_width as f64 / 2.0)) as i32;
    let y = ((screen_size.height as f64 / scale_factor) - (window_height as f64) - 60.0) as i32; // 距离底部 60px

    // 创建 PTT 浮动窗口（透明窗口）
    let _overlay = WebviewWindowBuilder::new(
        app,
        "ptt-overlay",
        tauri::WebviewUrl::App("ptt-overlay.html".into())
    )
    .title("PTT Status")
    .inner_size(window_width as f64, window_height as f64)
    .position(x as f64, y as f64)
    .always_on_top(true)
    .decorations(false)
    .resizable(false)
    .skip_taskbar(true)
    .focused(false)
    .visible(false)
    .transparent(true)
    .shadow(false)  // 禁用窗口阴影，有助于透明效果
    .build()?;

    println!("✅ PTT 浮动窗口已创建 ({}x{} @ {}, {})", window_width, window_height, x, y);

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
            // 初始化数据库
            let db_path = database::get_database_path(app.handle())
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to get database path: {}", e)))?;

            let db = Database::new(db_path)
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to initialize database: {}", e)))?;

            app.manage(AppState { db });
            println!("✅ 数据库已初始化");

            // 创建托盘图标
            create_tray(app.handle())?;

            // 注册快捷键
            register_shortcuts(app.handle())?;

            // 启动守护进程
            ensure_daemon_running()
                .map_err(|e| tauri::Error::Anyhow(anyhow::anyhow!("Failed to start daemon: {}", e)))?;

            // 启动 PTT 事件读取器 (监听 Python daemon 的 stderr)
            start_ptt_reader(app.handle().clone());

            // 创建 PTT 浮动状态窗口
            if let Err(e) = create_ptt_overlay(app.handle()) {
                println!("⚠️ 创建 PTT 浮动窗口失败: {}", e);
            }

            println!("✅ Speekium 应用已启动 (守护进程模式)");
            println!("🎤 PTT 快捷键: Cmd+Alt (按住说话，松开结束)");

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // 阻止窗口关闭，改为隐藏
                api.prevent_close();
                window.hide().unwrap();
            }
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            match event {
                tauri::RunEvent::Reopen { .. } => {
                    // macOS: 点击 dock 图标时显示主窗口
                    if let Some(window) = app_handle.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                tauri::RunEvent::ExitRequested { .. } => {
                    // 应用退出时清理守护进程
                    cleanup_daemon();
                }
                _ => {}
            }
        });
}
