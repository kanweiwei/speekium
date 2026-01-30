//! Socket-based IPC Client for Daemon Communication
//!
//! This module implements the SocketDaemonClient which communicates with the
//! Python daemon using Unix Domain Sockets (macOS/Linux) or Named Pipes (Windows).
//! The communication protocol is JSON-RPC 2.0.

use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::PathBuf;
use std::time::Duration;

#[cfg(unix)]
use std::os::unix::net::UnixStream;

#[cfg(windows)]
use std::fs::File;

// ============================================================================
// JSON-RPC 2.0 Types
// ============================================================================

/// JSON-RPC 2.0 Request
#[derive(Debug, serde::Serialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: serde_json::Value,
}

/// JSON-RPC 2.0 Response
#[derive(Debug, serde::Deserialize)]
#[allow(dead_code)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: u64,
    result: Option<serde_json::Value>,
    error: Option<JsonRpcError>,
}

/// JSON-RPC 2.0 Error
#[derive(Debug, serde::Deserialize)]
#[allow(dead_code)]
struct JsonRpcError {
    code: i32,
    message: String,
    data: Option<serde_json::Value>,
}

/// JSON-RPC 2.0 Error Codes
#[allow(dead_code)]
mod jsonrpc_error_codes {
    pub const PARSE_ERROR: i32 = -32700;
    pub const INVALID_REQUEST: i32 = -32600;
    pub const METHOD_NOT_FOUND: i32 = -32601;
    pub const INVALID_PARAMS: i32 = -32602;
    pub const INTERNAL_ERROR: i32 = -32603;
}

// ============================================================================
// SocketDaemonClient
// ============================================================================

/// Socket-based daemon client using JSON-RPC 2.0 protocol
pub struct SocketDaemonClient {
    socket_path: PathBuf,
    #[cfg(unix)]
    reader: Option<BufReader<UnixStream>>,
    #[cfg(unix)]
    writer: Option<BufWriter<UnixStream>>,
    #[cfg(windows)]
    reader: Option<BufReader<File>>,
    #[cfg(windows)]
    writer: Option<BufWriter<File>>,
    request_id: u64,
}

impl SocketDaemonClient {
    /// Create a new SocketDaemonClient
    ///
    /// # Arguments
    ///
    /// * `socket_path` - Path to the Unix socket or Named Pipe
    pub fn new(socket_path: PathBuf) -> Self {
        SocketDaemonClient {
            socket_path,
            #[cfg(unix)]
            reader: None,
            #[cfg(unix)]
            writer: None,
            #[cfg(windows)]
            reader: None,
            #[cfg(windows)]
            writer: None,
            request_id: 0,
        }
    }

    /// Get the default socket path for the current platform
    pub fn default_socket_path() -> PathBuf {
        #[cfg(unix)]
        {
            PathBuf::from("/tmp/speekium-daemon.sock")
        }

        #[cfg(windows)]
        {
            PathBuf::from(r"\\.\pipe\speekium-daemon")
        }
    }

    /// Get the default notification socket path for the current platform
    ///
    /// This is a separate socket where Python daemon connects as client
    /// and Rust listens as server for receiving async notifications
    /// (PTT events, download progress, etc.)
    pub fn default_notification_socket_path() -> PathBuf {
        #[cfg(unix)]
        {
            PathBuf::from("/tmp/speekium-notif.sock")
        }

        #[cfg(windows)]
        {
            PathBuf::from(r"\\.\pipe\speekium-notif")
        }
    }

    /// Connect to the daemon socket
    ///
    /// This will attempt to connect to the Unix socket or Named Pipe.
    /// Returns an error if the connection fails.
    pub fn connect(&mut self) -> Result<(), String> {
        #[cfg(unix)]
        {
            self.connect_unix()
        }

        #[cfg(windows)]
        {
            self.connect_windows()
        }
    }

    /// Connect to Unix Domain Socket (macOS/Linux)
    #[cfg(unix)]
    fn connect_unix(&mut self) -> Result<(), String> {
        // Wait for socket to be available (max 150 seconds to match server timeout)
        let max_attempts = 1500; // 150 seconds * 10 attempts per second
        let mut attempts = 0;

        loop {
            match UnixStream::connect(&self.socket_path) {
                Ok(stream) => {
                    stream.set_nonblocking(false)
                        .map_err(|e| format!("Failed to set blocking mode: {}", e))?;
                    // Set timeout to 150s to match server timeout
                    // PTT operations (ASR + LLM + TTS) can take 60s+ in some cases
                    stream.set_read_timeout(Some(Duration::from_secs(150)))
                        .map_err(|e| format!("Failed to set read timeout: {}", e))?;

                    // Create reader and writer
                    let reader = BufReader::new(stream.try_clone()
                        .map_err(|e| format!("Failed to clone stream: {}", e))?);
                    let writer = BufWriter::new(stream);

                    self.reader = Some(reader);
                    self.writer = Some(writer);
                    return Ok(());
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound || e.kind() == std::io::ErrorKind::ConnectionRefused => {
                    // Socket doesn't exist yet, wait and retry
                    attempts += 1;
                    if attempts >= max_attempts {
                        return Err(format!("Socket not available after 150 seconds: {}. Possible causes: 1) Daemon still initializing 2) Model downloading 3) System resources exhausted", e));
                    }
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                Err(e) => {
                    return Err(format!("Failed to connect to socket: {}", e));
                }
            }
        }
    }

    /// Connect to Named Pipe (Windows)
    #[cfg(windows)]
    fn connect_windows(&mut self) -> Result<(), String> {
        use std::fs::OpenOptions;
        use std::os::windows::fs::OpenOptionsExt;

        // Wait for pipe to be available (max 150 seconds to match server timeout)
        let max_attempts = 1500;
        let mut attempts = 0;

        loop {
            // Convert path to Windows-compatible format
            let path_str = self.socket_path.to_string_lossy().to_string();

            // Try to open the named pipe
            match OpenOptions::new()
                .read(true)
                .write(true)
                .custom_flags(winapi::um::winnt::FILE_FLAG_OVERLAPPED)
                .open(&path_str)
            {
                Ok(file) => {
                    // Create reader and writer
                    let reader = BufReader::new(file.try_clone()
                        .map_err(|e| format!("Failed to clone file: {}", e))?);
                    let writer = BufWriter::new(file);

                    self.reader = Some(reader);
                    self.writer = Some(writer);
                    return Ok(());
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                    // Pipe doesn't exist yet, wait and retry
                    attempts += 1;
                    if attempts >= max_attempts {
                        return Err(format!("Named pipe not available after 150 seconds: {}. Possible causes: 1) Daemon still initializing 2) Model downloading 3) System resources exhausted", e));
                    }
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                Err(e) => {
                    return Err(format!("Failed to connect to named pipe: {}", e));
                }
            }
        }
    }

    /// Check if client is connected to the daemon
    pub fn is_connected(&self) -> bool {
        #[cfg(unix)]
        {
            self.reader.is_some() && self.writer.is_some()
        }
        #[cfg(windows)]
        {
            self.reader.is_some() && self.writer.is_some()
        }
    }

    /// Send a JSON-RPC request and wait for response
    ///
    /// # Arguments
    ///
    /// * `method` - RPC method name
    /// * `params` - Method parameters
    ///
    /// # Returns
    ///
    /// Result containing the response value or an error message
    #[cfg(unix)]
    pub fn send_request(&mut self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
        // Ensure connected
        if !self.is_connected() {
            self.connect()?;
        }

        // Increment request ID
        self.request_id += 1;
        let id = self.request_id;

        // Build JSON-RPC request
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        };

        // Serialize request
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize request: {}", e))?;

        // Only log for interesting methods, not for frequent health checks
        if method != "health" {
            println!("[Speekium] → {}", method);
        }

        // Send request
        if let Some(ref mut writer) = self.writer {
            writeln!(writer, "{}", request_json)
                .map_err(|e| format!("Failed to write request: {}", e))?;
            writer.flush()
                .map_err(|e| format!("Failed to flush writer: {}", e))?;
        } else {
            return Err("Writer not available".to_string());
        }

        // Don't log "waiting" - it's noise

        // Read response
        if let Some(ref mut reader) = self.reader {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(bytes_read) => {
                    if bytes_read == 0 {
                        eprintln!("[Speekium] ⚠️ Connection closed by daemon");
                        // Clear connection state to force reconnect on next request
                        return Err("Connection closed by server (0 bytes read)".to_string());
                    }
                    // Don't log bytes - not useful for users
                }
                Err(e) => {
                    eprintln!("[Speekium] ⚠️ Read error: {}", e);
                    return Err(format!("Failed to read response: {}", e));
                }
            }

            // Parse JSON-RPC response
            let response: JsonRpcResponse = serde_json::from_str(&line)
                .map_err(|e| format!("Failed to parse response: {}", e))?;

            // Check for RPC error
            if let Some(error) = response.error {
                return Err(format!("RPC error (code {}): {}", error.code, error.message));
            }

            // Return result
            response.result.ok_or_else(|| "No result in response".to_string())
        } else {
            Err("Reader not available".to_string())
        }
    }

    /// Send a JSON-RPC request and wait for response (Windows version)
    #[cfg(windows)]
    pub fn send_request(&mut self, method: &str, params: serde_json::Value) -> Result<serde_json::Value, String> {
        // Ensure connected
        if !self.is_connected() {
            self.connect()?;
        }

        // Increment request ID
        self.request_id += 1;
        let id = self.request_id;

        // Build JSON-RPC request
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        };

        // Serialize request
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize request: {}", e))?;

        // Send request
        if let Some(ref mut writer) = self.writer {
            writeln!(writer, "{}", request_json)
                .map_err(|e| format!("Failed to write request: {}", e))?;
            writer.flush()
                .map_err(|e| format!("Failed to flush writer: {}", e))?;
        } else {
            return Err("Writer not available".to_string());
        }

        // Read response
        if let Some(ref mut reader) = self.reader {
            let mut line = String::new();
            reader.read_line(&mut line)
                .map_err(|e| format!("Failed to read response: {}", e))?;

            // Parse JSON-RPC response
            let response: JsonRpcResponse = serde_json::from_str(&line)
                .map_err(|e| format!("Failed to parse response: {}", e))?;

            // Check for RPC error
            if let Some(error) = response.error {
                return Err(format!("RPC error (code {}): {}", error.code, error.message));
            }

            // Return result
            response.result.ok_or_else(|| "No result in response".to_string())
        } else {
            Err("Reader not available".to_string())
        }
    }

    /// Send a JSON-RPC notification (no response expected)
    ///
    /// # Arguments
    ///
    /// * `method` - RPC method name
    /// * `params` - Method parameters
    #[cfg(unix)]
    pub fn send_notification(&mut self, method: &str, params: serde_json::Value) -> Result<(), String> {
        // Ensure connected
        if !self.is_connected() {
            self.connect()?;
        }

        // Build JSON-RPC notification (no id field)
        let request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        });

        // Serialize request
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize notification: {}", e))?;

        // Send notification
        if let Some(ref mut writer) = self.writer {
            writeln!(writer, "{}", request_json)
                .map_err(|e| format!("Failed to write notification: {}", e))?;
            writer.flush()
                .map_err(|e| format!("Failed to flush writer: {}", e))?;
            Ok(())
        } else {
            Err("Writer not available".to_string())
        }
    }

    /// Send a JSON-RPC notification (no response expected) - Windows version
    #[cfg(windows)]
    pub fn send_notification(&mut self, method: &str, params: serde_json::Value) -> Result<(), String> {
        // Ensure connected
        if !self.is_connected() {
            self.connect()?;
        }

        // Build JSON-RPC notification (no id field)
        let request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        });

        // Serialize request
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize notification: {}", e))?;

        // Send notification
        if let Some(ref mut writer) = self.writer {
            writeln!(writer, "{}", request_json)
                .map_err(|e| format!("Failed to write notification: {}", e))?;
            writer.flush()
                .map_err(|e| format!("Failed to flush writer: {}", e))?;
            Ok(())
        } else {
            Err("Writer not available".to_string())
        }
    }

    /// Perform a health check on the daemon
    ///
    /// Returns true if the daemon is healthy, false otherwise
    pub fn health_check(&mut self) -> bool {
        match self.send_request("health", serde_json::json!({})) {
            Ok(result) => {
                if let Some(obj) = result.as_object() {
                    let success = obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false);

                    // IMPORTANT: Also check the status field
                    // "initializing" means not ready yet, only "healthy" is truly ready
                    if success {
                        if let Some(status) = obj.get("status").and_then(|v| v.as_str()) {
                            return status == "healthy";
                        }
                    }

                    false
                } else {
                    false
                }
            }
            Err(_) => false,
        }
    }

    /// Check if there's a notification waiting to be read
    ///
    /// This is a non-blocking check for notifications from the daemon.
    /// Returns Some(notification) if one is available, None otherwise.
    ///
    /// Notifications are JSON-RPC messages without an "id" field, used for
    /// asynchronous events like download progress updates.
    #[cfg(unix)]
    pub fn try_read_notification(&mut self) -> Result<Option<serde_json::Value>, String> {
        if !self.is_connected() {
            return Ok(None);
        }

        // Try to read with timeout - if no data, return None
        if let Some(ref mut reader) = self.reader {
            reader.get_mut().set_nonblocking(true)
                .map_err(|e| format!("Failed to set non-blocking: {}", e))?;

            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => {
                    // EOF - connection closed
                    reader.get_mut().set_nonblocking(false)
                        .map_err(|e| format!("Failed to restore blocking: {}", e))?;
                    Err("Connection closed by server".to_string())
                }
                Ok(_) => {
                    reader.get_mut().set_nonblocking(false)
                        .map_err(|e| format!("Failed to restore blocking: {}", e))?;

                    if line.trim().is_empty() {
                        return Ok(None);
                    }

                    // Try to parse as JSON
                    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                        // Check if it's a notification (no "id" field)
                        if value.get("id").is_none() {
                            return Ok(Some(value));
                        }
                    }
                    // Not a notification or invalid JSON
                    Ok(None)
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    reader.get_mut().set_nonblocking(false)
                        .map_err(|e| format!("Failed to restore blocking: {}", e))?;
                    Ok(None)
                }
                Err(e) => {
                    let _ = reader.get_mut().set_nonblocking(false);
                    Err(format!("Failed to read notification: {}", e))
                }
            }
        } else {
            Ok(None)
        }
    }

    /// Windows version of try_read_notification
    #[cfg(windows)]
    pub fn try_read_notification(&mut self) -> Result<Option<serde_json::Value>, String> {
        if !self.is_connected() {
            return Ok(None);
        }

        // Windows named pipes don't support non-blocking mode
        // We'll use a small timeout instead
        if let Some(ref mut reader) = self.reader {
            let original_timeout = reader.get_ref().try_clone()
                .and_then(|s| s.set_read_timeout(Some(Duration::from_millis(10))))
                .ok();

            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => {
                    return Err("Connection closed by server".to_string());
                }
                Ok(_) => {
                    if let Err(_) = reader.get_ref().set_read_timeout(original_timeout) {
                        // Ignore timeout restore error
                    }

                    if line.trim().is_empty() {
                        return Ok(None);
                    }

                    if let Ok(value) = serde_json::from_str::<serde_json::Value>(&line) {
                        // Check if it's a notification (no "id" field)
                        if value.get("id").is_none() {
                            return Ok(Some(value));
                        }
                    }
                    Ok(None)
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock || e.kind() == std::io::ErrorKind::TimedOut => {
                    if let Err(_) = reader.get_ref().set_read_timeout(original_timeout) {
                        // Ignore timeout restore error
                    }
                    Ok(None)
                }
                Err(e) => {
                    let _ = reader.get_ref().set_read_timeout(original_timeout);
                    Err(format!("Failed to read notification: {}", e))
                }
            }
        } else {
            Ok(None)
        }
    }

    /// Read a line from the socket for streaming responses
    ///
    /// This is used for streaming commands like chat_stream and chat_tts_stream
    /// where the daemon sends multiple JSON lines in response.
    #[cfg(unix)]
    pub fn read_stream_line(&mut self) -> Result<String, String> {
        if let Some(ref mut reader) = self.reader {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => Err("Connection closed".to_string()),
                Ok(_) => Ok(line),
                Err(e) => Err(format!("Read error: {}", e)),
            }
        } else {
            Err("Not connected".to_string())
        }
    }

    /// Windows version of read_stream_line
    #[cfg(windows)]
    pub fn read_stream_line(&mut self) -> Result<String, String> {
        if let Some(ref mut reader) = self.reader {
            let mut line = String::new();
            match reader.read_line(&mut line) {
                Ok(0) => Err("Connection closed".to_string()),
                Ok(_) => Ok(line),
                Err(e) => Err(format!("Read error: {}", e)),
            }
        } else {
            Err("Not connected".to_string())
        }
    }

    /// Send a streaming request (for commands that return multiple responses)
    ///
    /// This sends the request but doesn't wait for a response.
    /// The caller should then call read_stream_line() to read each response.
    pub fn send_streaming_request(&mut self, method: &str, params: serde_json::Value) -> Result<(), String> {
        if !self.is_connected() {
            return Err("Not connected".to_string());
        }

        // Increment request ID first to match send_request behavior
        self.request_id += 1;
        let id = self.request_id;

        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        };

        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Failed to serialize request: {}", e))?;

        if let Some(ref mut writer) = self.writer {
            writeln!(writer, "{}", request_json)
                .map_err(|e| format!("Failed to write request: {}", e))?;
            writer.flush()
                .map_err(|e| format!("Failed to flush: {}", e))?;
            Ok(())
        } else {
            Err("Writer not available".to_string())
        }
    }
}

// ============================================================================
// NotificationListener
// ============================================================================

/// Notification listener - Server for receiving async notifications from Python
///
/// This creates a Unix socket server that Python daemon connects to as a client.
/// Async events (PTT events, download progress) are sent through this channel.
pub struct NotificationListener {
    socket_path: PathBuf,
}

impl NotificationListener {
    /// Create a new notification listener
    pub fn new(socket_path: PathBuf) -> Self {
        NotificationListener {
            socket_path,
        }
    }

    /// Create with default notification socket path
    pub fn with_default_path() -> Self {
        Self::new(SocketDaemonClient::default_notification_socket_path())
    }

    /// Start the notification listener (blocking - should be run in a thread)
    ///
    /// Returns a receiver channel that provides notifications as they arrive
    pub fn start(&mut self) -> Result<std::sync::mpsc::Receiver<serde_json::Value>, String> {
        #[cfg(unix)]
        {
            self.start_unix()
        }

        #[cfg(windows)]
        {
            self.start_windows()
        }
    }

    /// Start Unix socket listener (macOS/Linux)
    #[cfg(unix)]
    fn start_unix(&mut self) -> Result<std::sync::mpsc::Receiver<serde_json::Value>, String> {
        use std::os::unix::net::UnixListener;
        use std::sync::mpsc::channel;

        // Clean up old socket file
        let _ = std::fs::remove_file(&self.socket_path);

        // Create Unix socket listener
        let listener = UnixListener::bind(&self.socket_path)
            .map_err(|e| format!("Failed to bind notification socket: {}", e))?;

        // Set permissions
        let _ = std::fs::set_permissions(&self.socket_path, std::os::unix::fs::PermissionsExt::from_mode(0o600));

        // Notification socket ready (debug only)
        // println!("[Speekium] Notification listener: {}", self.socket_path.display());

        // Create channel for sending notifications back to main thread
        let (tx, rx) = channel();

        // Spawn thread to accept connections and read notifications
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                match stream {
                    Ok(stream) => {
                        // Spawn a task for each client connection
                        let tx_clone = tx.clone();
                        std::thread::spawn(move || {
                            let reader = BufReader::new(stream);
                            for line in reader.lines() {
                                match line {
                                    Ok(l) => {
                                        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&l) {
                                            let _ = tx_clone.send(value);
                                        }
                                    }
                                    Err(_) => break,
                                }
                            }
                        });
                    }
                    Err(_e) => {
                        // Silently ignore notification accept errors during shutdown
                    }
                }
            }
        });

        Ok(rx)
    }

    /// Start TCP listener (Windows fallback)
    #[cfg(windows)]
    fn start_windows(&mut self) -> Result<std::sync::mpsc::Receiver<serde_json::Value>, String> {
        use std::net::TcpListener;
        use std::sync::mpsc::channel;

        // Bind to localhost port for notification
        let listener = TcpListener::bind("127.0.0.1:0")
            .map_err(|e| format!("Failed to bind TCP: {}", e))?;

        let addr = listener.local_addr()
            .map_err(|e| format!("Failed to get addr: {}", e))?;

        // Write port to file for Python to discover
        let port_file = std::path::PathBuf::from("/tmp/.speekium-notification-port");
        std::fs::write(&port_file, addr.port().to_string())
            .map_err(|e| format!("Failed to write port file: {}", e))?;

        // println!("[Speekium] Notification listener: {}", addr);

        // Create channel for sending notifications back to main thread
        let (tx, rx) = channel();

        // Spawn thread to accept connections and read notifications
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                match stream {
                    Ok(stream) => {
                        let tx_clone = tx.clone();
                        std::thread::spawn(move || {
                            let reader = BufReader::new(stream);
                            for line in reader.lines() {
                                match line {
                                    Ok(l) => {
                                        if let Ok(value) = serde_json::from_str::<serde_json::Value>(&l) {
                                            let _ = tx_clone.send(value);
                                        }
                                    }
                                    Err(_) => break,
                                }
                            }
                        });
                    }
                    Err(_e) => {
                        // Silently ignore notification accept errors during shutdown
                    }
                }
            }
        });

        Ok(rx)
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_socket_path() {
        let path = SocketDaemonClient::default_socket_path();
        assert!(path.as_os_str().len() > 0);
    }

    #[test]
    fn test_jsonrpc_request_serialization() {
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id: 1,
            method: "test_method".to_string(),
            params: serde_json::json!({"key": "value"}),
        };

        let json = serde_json::to_string(&request).unwrap();
        assert!(json.contains("2.0"));
        assert!(json.contains("test_method"));
    }
}
