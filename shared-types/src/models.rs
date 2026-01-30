// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Data models shared across the application

use serde::{Deserialize, Serialize};

/// Recording mode - how the user triggers recording
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RecordingMode {
    /// User holds a key to record, releases to stop
    PushToTalk,
    /// Continuous listening with VAD (Voice Activity Detection)
    Continuous,
}

impl Default for RecordingMode {
    fn default() -> Self {
        Self::PushToTalk
    }
}

/// Work mode - how the user interacts with the assistant
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum WorkMode {
    /// Voice conversation mode
    Conversation,
    /// Text input mode
    TextInput,
}

impl Default for WorkMode {
    fn default() -> Self {
        Self::Conversation
    }
}

/// Application status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AppStatus {
    /// Idle, waiting for user input
    Idle,
    /// Listening for voice input
    Listening,
    /// Recording audio
    Recording,
    /// Processing speech to text
    AsrProcessing,
    /// Processing LLM request
    LlmProcessing,
    /// Processing text to speech
    TtsProcessing,
    /// Playing audio response
    Playing,
    /// Error state
    Error,
}

/// Daemon status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DaemonStatus {
    /// Daemon is starting
    Starting,
    /// Daemon is ready and running
    Ready,
    /// Daemon is busy processing
    Busy,
    /// Daemon has stopped
    Stopped,
    /// Daemon encountered an error
    Error,
}

/// Health status of a component
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HealthStatus {
    /// Component is healthy
    Healthy,
    /// Component is degraded
    Degraded,
    /// Component is unhealthy
    Unhealthy,
    /// Component status unknown
    Unknown,
}

/// Recording state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecordingState {
    /// Whether currently recording
    pub is_recording: bool,
    /// Whether audio is being processed
    pub is_processing: bool,
    /// Current audio level in dB
    pub audio_level_db: f32,
    /// Recording duration in seconds
    pub duration_seconds: f64,
}

impl Default for RecordingState {
    fn default() -> Self {
        Self {
            is_recording: false,
            is_processing: false,
            audio_level_db: 0.0,
            duration_seconds: 0.0,
        }
    }
}

/// Processing stage
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProcessingStage {
    /// No processing
    Idle,
    /// Connecting to daemon
    Connecting,
    /// Recording audio
    Recording,
    /// ASR processing
    AsrProcessing,
    /// LLM processing
    LlmProcessing,
    /// TTS processing
    TtsProcessing,
    /// Playing audio
    Playing,
}

/// Processing state
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingState {
    /// Current processing stage
    pub stage: ProcessingStage,
    /// Progress from 0.0 to 1.0
    pub progress: f32,
    /// Human-readable status message
    pub message: String,
}

impl Default for ProcessingState {
    fn default() -> Self {
        Self {
            stage: ProcessingStage::Idle,
            progress: 0.0,
            message: String::new(),
        }
    }
}

/// Processing result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingResult {
    /// Whether processing was successful
    pub success: bool,
    /// Result message or data
    pub data: String,
    /// Optional error message
    pub error: Option<String>,
}

/// Reason for stopping recording
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum StopReason {
    /// User manually stopped
    UserStopped,
    /// Voice activity detected (for continuous mode)
    SilenceDetected,
    /// Maximum duration reached
    MaxDurationReached,
    /// Error occurred
    Error(String),
}

/// Model type for progress tracking
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ModelType {
    /// ASR model
    Asr,
    /// LLM model
    Llm,
    /// TTS model
    Tts,
    /// VAD model
    Vad,
}

/// Progress stage for model loading
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ProgressStage {
    /// Starting to load
    Downloading,
    /// Verifying checksum
    Verifying,
    /// Loading into memory
    Loading,
    /// Model ready
    Ready,
    /// Loading failed
    Failed,
}

/// Model progress info
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelProgress {
    /// Model type
    pub model: ModelType,
    /// Current stage
    pub stage: ProgressStage,
    /// Progress from 0.0 to 1.0
    pub progress: f32,
    /// Progress message
    pub message: String,
}

/// User configuration (subset shared across platforms)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserConfig {
    /// Work mode
    pub work_mode: WorkMode,
    /// Recording mode
    pub recording_mode: RecordingMode,
    /// Language code (e.g., "zh", "en")
    pub language: String,
    /// Input language
    pub input_language: String,
    /// Output language
    pub output_language: String,
}

impl Default for UserConfig {
    fn default() -> Self {
        Self {
            work_mode: WorkMode::default(),
            recording_mode: RecordingMode::default(),
            language: "zh".to_string(),
            input_language: "zh".to_string(),
            output_language: "zh".to_string(),
        }
    }
}

/// Chat message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    /// Message role
    pub role: MessageRole,
    /// Message content
    pub content: String,
    /// Message timestamp
    pub timestamp: i64,
}

/// Message role
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MessageRole {
    /// User message
    User,
    /// Assistant message
    Assistant,
    /// System message
    System,
}

/// Audio level data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioLevel {
    /// Audio level in dB
    pub level_db: f32,
    /// Whether the level is clipping
    pub is_clipping: bool,
}

/// PTT (Push-to-Talk) state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PttState {
    /// PTT is idle
    Idle,
    /// PTT key is pressed
    Pressed,
    /// PTT is recording
    Recording,
    /// PTT is processing
    Processing,
}

/// Statistics data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Statistics {
    /// Total recordings
    pub total_recordings: u64,
    /// Total recording time in seconds
    pub total_recording_time: f64,
    /// Total messages sent
    pub total_messages: u64,
    /// Total responses received
    pub total_responses: u64,
}

impl Default for Statistics {
    fn default() -> Self {
        Self {
            total_recordings: 0,
            total_recording_time: 0.0,
            total_messages: 0,
            total_responses: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_recording_mode_serialization() {
        let mode = RecordingMode::PushToTalk;
        let json = serde_json::to_string(&mode).unwrap();
        assert_eq!(json, "\"push-to-talk\"");

        let deserialized: RecordingMode = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized, RecordingMode::PushToTalk);
    }

    #[test]
    fn test_work_mode_serialization() {
        let mode = WorkMode::TextInput;
        let json = serde_json::to_string(&mode).unwrap();
        assert_eq!(json, "\"text-input\"");

        let deserialized: WorkMode = serde_json::from_str(&json).unwrap();
        assert_eq!(deserialized, WorkMode::TextInput);
    }

    #[test]
    fn test_recording_state_default() {
        let state = RecordingState::default();
        assert!(!state.is_recording);
        assert!(!state.is_processing);
        assert_eq!(state.audio_level_db, 0.0);
        assert_eq!(state.duration_seconds, 0.0);
    }

    #[test]
    fn test_user_config_default() {
        let config = UserConfig::default();
        assert_eq!(config.work_mode, WorkMode::Conversation);
        assert_eq!(config.recording_mode, RecordingMode::PushToTalk);
        assert_eq!(config.language, "zh");
    }
}
