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
        // Wait for socket to be available (max 30 seconds)
        let max_attempts = 300; // 30 seconds * 10 attempts per second
        let mut attempts = 0;

        loop {
            match UnixStream::connect(&self.socket_path) {
                Ok(stream) => {
                    stream.set_nonblocking(false)
                        .map_err(|e| format!("Failed to set blocking mode: {}", e))?;
                    stream.set_read_timeout(Some(Duration::from_secs(30)))
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
                        return Err(format!("Socket not available after 30 seconds: {}", e));
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

        // Wait for pipe to be available (max 30 seconds)
        let max_attempts = 300;
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
                        return Err(format!("Named pipe not available after 30 seconds: {}", e));
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
                    obj.get("success")
                        .and_then(|v| v.as_bool())
                        .unwrap_or(false)
                } else {
                    false
                }
            }
            Err(_) => false,
        }
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
