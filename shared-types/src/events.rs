// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Event definitions for the event bus system

use serde::{Deserialize, Serialize};
use crate::models::*;

/// Application event - all events flow through the EventBus
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "data")]
pub enum Event {
    /// State changed event
    StateChanged {
        old: Option<AppStateSnapshot>,
        new: AppStateSnapshot,
    },

    /// Recording events
    RecordingStarted { mode: RecordingMode },
    RecordingStopped { reason: StopReason },
    RecordingProgress { duration: f64, audio_level: f32 },

    /// Processing events
    ProcessingStarted { stage: ProcessingStage },
    ProcessingProgress { stage: ProcessingStage, progress: f32, message: String },
    ProcessingCompleted { stage: ProcessingStage, result: ProcessingResult },
    ProcessingFailed { stage: ProcessingStage, error: String },

    /// Configuration events
    ConfigChanged { key: String, value: serde_json::Value },
    WorkModeChanged { old: WorkMode, new: WorkMode },
    RecordingModeChanged { old: RecordingMode, new: RecordingMode },

    /// Daemon events
    DaemonStatusChanged { status: DaemonStatus },
    DaemonHealthChanged { health: HealthStatus },
    DaemonConnected,
    DaemonDisconnected,

    /// Model loading events
    ModelProgress { model: ModelType, stage: ProgressStage, progress: f32, message: String },
    ModelLoaded { model: ModelType },
    ModelLoadFailed { model: ModelType, error: String },

    /// Chat events
    ChatMessageAdded { message: ChatMessage },
    ChatHistoryCleared,

    /// Audio events
    AudioLevelChanged { level: AudioLevel },
    AudioPlaybackStarted,
    AudioPlaybackStopped,
    AudioPlaybackProgress { position: f64, duration: f64 },

    /// PTT events
    PttStateChanged { old: PttState, new: PttState },
    PttKeyPressed,
    PttKeyReleased,

    /// UI events
    ThemeChanged { theme: String },
    LanguageChanged { language: String },

    /// Error events
    ErrorOccurred { error: ErrorInfo },
    ErrorCleared { error_id: String },
}

/// Application state snapshot for state change events
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppStateSnapshot {
    /// Timestamp of the snapshot
    pub timestamp: i64,
    /// Current app status
    pub app_status: AppStatus,
    /// Current recording state
    pub recording_state: RecordingState,
    /// Current processing state
    pub processing_state: ProcessingState,
    /// Current work mode
    pub work_mode: WorkMode,
    /// Current recording mode
    pub recording_mode: RecordingMode,
    /// Daemon status
    pub daemon_status: DaemonStatus,
    /// Whether daemon is connected
    pub daemon_connected: bool,
}

/// Error information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorInfo {
    /// Unique error ID
    pub id: String,
    /// Error category
    pub category: ErrorCategory,
    /// Error message
    pub message: String,
    /// Additional context
    pub context: Option<String>,
    /// Timestamp
    pub timestamp: i64,
}

/// Error category
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ErrorCategory {
    /// Configuration error
    Config,
    /// Network error
    Network,
    /// Audio device error
    Audio,
    /// Model loading error
    Model,
    /// Daemon communication error
    Daemon,
    /// File I/O error
    Io,
    /// Generic error
    Generic,
}

impl Event {
    /// Create a state changed event
    pub fn state_changed(old: Option<AppStateSnapshot>, new: AppStateSnapshot) -> Self {
        Self::StateChanged { old, new }
    }

    /// Create a recording started event
    pub fn recording_started(mode: RecordingMode) -> Self {
        Self::RecordingStarted { mode }
    }

    /// Create a recording stopped event
    pub fn recording_stopped(reason: StopReason) -> Self {
        Self::RecordingStopped { reason }
    }

    /// Create a recording progress event
    pub fn recording_progress(duration: f64, audio_level: f32) -> Self {
        Self::RecordingProgress { duration, audio_level }
    }

    /// Create a processing started event
    pub fn processing_started(stage: ProcessingStage) -> Self {
        Self::ProcessingStarted { stage }
    }

    /// Create a processing progress event
    pub fn processing_progress(stage: ProcessingStage, progress: f32, message: String) -> Self {
        Self::ProcessingProgress { stage, progress, message }
    }

    /// Create a processing completed event
    pub fn processing_completed(stage: ProcessingStage, result: ProcessingResult) -> Self {
        Self::ProcessingCompleted { stage, result }
    }

    /// Create a processing failed event
    pub fn processing_failed(stage: ProcessingStage, error: String) -> Self {
        Self::ProcessingFailed { stage, error }
    }

    /// Create a config changed event
    pub fn config_changed(key: String, value: serde_json::Value) -> Self {
        Self::ConfigChanged { key, value }
    }

    /// Create a work mode changed event
    pub fn work_mode_changed(old: WorkMode, new: WorkMode) -> Self {
        Self::WorkModeChanged { old, new }
    }

    /// Create a recording mode changed event
    pub fn recording_mode_changed(old: RecordingMode, new: RecordingMode) -> Self {
        Self::RecordingModeChanged { old, new }
    }

    /// Create a PTT state changed event
    pub fn ptt_state_changed(old: PttState, new: PttState) -> Self {
        Self::PttStateChanged { old, new }
    }

    /// Create a daemon status changed event
    pub fn daemon_status_changed(status: DaemonStatus) -> Self {
        Self::DaemonStatusChanged { status }
    }

    /// Create a model progress event
    pub fn model_progress(model: ModelType, stage: ProgressStage, progress: f32, message: String) -> Self {
        Self::ModelProgress { model, stage, progress, message }
    }

    /// Create a chat message added event
    pub fn chat_message_added(message: ChatMessage) -> Self {
        Self::ChatMessageAdded { message }
    }

    /// Create an error occurred event
    pub fn error_occurred(error: ErrorInfo) -> Self {
        Self::ErrorOccurred { error }
    }

    /// Check if this is a state event
    pub fn is_state_event(&self) -> bool {
        matches!(self, Self::StateChanged { .. })
    }

    /// Check if this is a recording event
    pub fn is_recording_event(&self) -> bool {
        matches!(
            self,
            Self::RecordingStarted { .. } | Self::RecordingStopped { .. } | Self::RecordingProgress { .. }
        )
    }

    /// Check if this is a processing event
    pub fn is_processing_event(&self) -> bool {
        matches!(
            self,
            Self::ProcessingStarted { .. }
                | Self::ProcessingProgress { .. }
                | Self::ProcessingCompleted { .. }
                | Self::ProcessingFailed { .. }
        )
    }

    /// Check if this is an error event
    pub fn is_error_event(&self) -> bool {
        matches!(self, Self::ErrorOccurred { .. })
    }

    /// Get event category for filtering
    pub fn category(&self) -> EventCategory {
        match self {
            Self::StateChanged { .. } => EventCategory::State,
            Self::RecordingStarted { .. } | Self::RecordingStopped { .. } | Self::RecordingProgress { .. } => {
                EventCategory::Recording
            }
            Self::ProcessingStarted { .. }
            | Self::ProcessingProgress { .. }
            | Self::ProcessingCompleted { .. }
            | Self::ProcessingFailed { .. } => EventCategory::Processing,
            Self::ConfigChanged { .. }
            | Self::WorkModeChanged { .. }
            | Self::RecordingModeChanged { .. } => EventCategory::Config,
            Self::DaemonStatusChanged { .. }
            | Self::DaemonHealthChanged { .. }
            | Self::DaemonConnected
            | Self::DaemonDisconnected => EventCategory::Daemon,
            Self::ModelProgress { .. } | Self::ModelLoaded { .. } | Self::ModelLoadFailed { .. } => {
                EventCategory::Model
            }
            Self::ChatMessageAdded { .. } | Self::ChatHistoryCleared => EventCategory::Chat,
            Self::AudioLevelChanged { .. }
            | Self::AudioPlaybackStarted
            | Self::AudioPlaybackStopped
            | Self::AudioPlaybackProgress { .. } => EventCategory::Audio,
            Self::PttStateChanged { .. } | Self::PttKeyPressed | Self::PttKeyReleased => EventCategory::Ptt,
            Self::ThemeChanged { .. } | Self::LanguageChanged { .. } => EventCategory::Ui,
            Self::ErrorOccurred { .. } | Self::ErrorCleared { .. } => EventCategory::Error,
        }
    }
}

/// Event category for filtering
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EventCategory {
    /// State events
    State,
    /// Recording events
    Recording,
    /// Processing events
    Processing,
    /// Configuration events
    Config,
    /// Daemon events
    Daemon,
    /// Model events
    Model,
    /// Chat events
    Chat,
    /// Audio events
    Audio,
    /// PTT events
    Ptt,
    /// UI events
    Ui,
    /// Error events
    Error,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_recording_started() {
        let event = Event::recording_started(RecordingMode::PushToTalk);
        assert!(event.is_recording_event());
        assert_eq!(event.category(), EventCategory::Recording);
    }

    #[test]
    fn test_event_processing_progress() {
        let event = Event::processing_progress(ProcessingStage::AsrProcessing, 0.5, "Processing".to_string());
        assert!(event.is_processing_event());
        assert_eq!(event.category(), EventCategory::Processing);
    }

    #[test]
    fn test_event_serialization() {
        let event = Event::recording_started(RecordingMode::Continuous);
        let json = serde_json::to_string(&event).unwrap();
        let deserialized: Event = serde_json::from_str(&json).unwrap();
        assert!(deserialized.is_recording_event());
    }

    #[test]
    fn test_event_category_filtering() {
        let state_event = Event::StateChanged {
            old: None,
            new: AppStateSnapshot {
                timestamp: 0,
                app_status: AppStatus::Idle,
                recording_state: RecordingState::default(),
                processing_state: ProcessingState::default(),
                work_mode: WorkMode::Conversation,
                recording_mode: RecordingMode::PushToTalk,
                daemon_status: DaemonStatus::Stopped,
                daemon_connected: false,
            },
        };
        assert_eq!(state_event.category(), EventCategory::State);
        assert!(state_event.is_state_event());
    }
}
