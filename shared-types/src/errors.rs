// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Error types shared across the application

use serde::{Deserialize, Serialize};

/// Shared error type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SharedError {
    /// Error kind
    pub kind: ErrorKind,
    /// Human-readable error message
    pub message: String,
    /// Optional error code
    pub code: Option<String>,
    /// Source of the error
    pub source: ErrorSource,
}

/// Error kind
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorKind {
    /// Invalid input
    InvalidInput,
    /// Not found
    NotFound,
    /// Permission denied
    PermissionDenied,
    /// Network error
    Network,
    /// Timeout
    Timeout,
    /// Serialization/deserialization error
    Serialization,
    /// Audio device error
    AudioDevice,
    /// Model loading error
    ModelLoad,
    /// Configuration error
    Configuration,
    /// Daemon communication error
    DaemonCommunication,
    /// Internal error
    Internal,
}

/// Source of the error
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ErrorSource {
    /// Frontend
    Frontend,
    /// Rust backend
    RustBackend,
    /// Python daemon
    PythonDaemon,
    /// External service
    External,
    /// Unknown source
    Unknown,
}

impl SharedError {
    /// Create a new error
    pub fn new(kind: ErrorKind, message: impl Into<String>, source: ErrorSource) -> Self {
        Self {
            kind,
            message: message.into(),
            code: None,
            source,
        }
    }

    /// Create an invalid input error
    pub fn invalid_input(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::InvalidInput, message, ErrorSource::Unknown)
    }

    /// Create a not found error
    pub fn not_found(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::NotFound, message, ErrorSource::Unknown)
    }

    /// Create a network error
    pub fn network(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::Network, message, ErrorSource::Unknown)
    }

    /// Create a timeout error
    pub fn timeout(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::Timeout, message, ErrorSource::Unknown)
    }

    /// Create a serialization error
    pub fn serialization(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::Serialization, message, ErrorSource::Unknown)
    }

    /// Create an audio device error
    pub fn audio_device(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::AudioDevice, message, ErrorSource::Unknown)
    }

    /// Create a model load error
    pub fn model_load(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::ModelLoad, message, ErrorSource::Unknown)
    }

    /// Create a configuration error
    pub fn configuration(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::Configuration, message, ErrorSource::Unknown)
    }

    /// Create a daemon communication error
    pub fn daemon_communication(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::DaemonCommunication, message, ErrorSource::Unknown)
    }

    /// Create an internal error
    pub fn internal(message: impl Into<String>) -> Self {
        Self::new(ErrorKind::Internal, message, ErrorSource::Unknown)
    }

    /// Add an error code
    pub fn with_code(mut self, code: impl Into<String>) -> Self {
        self.code = Some(code.into());
        self
    }

    /// Set the error source
    pub fn with_source(mut self, source: ErrorSource) -> Self {
        self.source = source;
        self
    }
}

impl std::fmt::Display for SharedError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "[{:?}] {}", self.kind, self.message)
    }
}

impl std::error::Error for SharedError {}

/// Convert from std::io::Error
impl From<std::io::Error> for SharedError {
    fn from(err: std::io::Error) -> Self {
        let kind = match err.kind() {
            std::io::ErrorKind::NotFound => ErrorKind::NotFound,
            std::io::ErrorKind::PermissionDenied => ErrorKind::PermissionDenied,
            std::io::ErrorKind::TimedOut => ErrorKind::Timeout,
            std::io::ErrorKind::ConnectionReset
            | std::io::ErrorKind::ConnectionAborted
            | std::io::ErrorKind::NotConnected => ErrorKind::Network,
            _ => ErrorKind::Internal,
        };
        Self::new(kind, err.to_string(), ErrorSource::Unknown)
    }
}

/// Convert from serde_json::Error
impl From<serde_json::Error> for SharedError {
    fn from(err: serde_json::Error) -> Self {
        Self::serialization(err.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_creation() {
        let error = SharedError::invalid_input("Invalid parameter");
        assert_eq!(error.kind, ErrorKind::InvalidInput);
        assert_eq!(error.message, "Invalid parameter");
        assert_eq!(error.source, ErrorSource::Unknown);
    }

    #[test]
    fn test_error_with_code() {
        let error = SharedError::not_found("Config file")
            .with_code("CONF_404")
            .with_source(ErrorSource::PythonDaemon);
        assert_eq!(error.code, Some("CONF_404".to_string()));
        assert_eq!(error.source, ErrorSource::PythonDaemon);
    }

    #[test]
    fn test_error_serialization() {
        let error = SharedError::network("Connection failed");
        let json = serde_json::to_string(&error).unwrap();
        let deserialized: SharedError = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized.kind, ErrorKind::Network);
        assert_eq!(deserialized.message, "Connection failed");
    }
}
