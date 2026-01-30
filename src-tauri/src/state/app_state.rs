// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Unified application state manager
//!
//! This module provides a centralized state management system that:
//! 1. Replaces scattered global static variables
//! 2. Integrates with the event system for reactive updates
//! 3. Provides thread-safe access to all application state
//! 4. Maintains a history of state changes for debugging

use crate::event::{EventBus, Event};
use shared_types::{
    RecordingMode, WorkMode, AppStatus, DaemonStatus, HealthStatus,
    RecordingState, ProcessingState, ProcessingStage, PttState,
};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Maximum number of state snapshots to keep in history
const MAX_STATE_HISTORY: usize = 100;

/// Unified application state manager
///
/// # Design Principles
/// 1. **Single Source of Truth**: All application state in one place
/// 2. **Immutable Updates**: State changes create new snapshots
/// 3. **Event Integration**: State changes emit events for subscribers
/// 4. **Thread Safety**: All operations are thread-safe via RwLock
/// 5. **Observable**: State changes can be subscribed to via EventBus
///
/// # Migration Path
/// This is the new unified state manager. Legacy global static variables
/// in `daemon::state` module will be gradually migrated here.
pub struct NewAppState {
    /// Inner state data
    inner: RwLock<AppStateData>,
    /// Event bus for emitting state change events
    event_bus: Arc<EventBus>,
    /// State history (for debugging and replay)
    history: Arc<RwLock<Vec<StateSnapshot>>>,
}

/// Core application state data
///
/// This struct contains all the state that was previously scattered
/// across 13 global static variables.
#[derive(Debug, Clone)]
pub struct AppStateData {
    // === Daemon Related ===
    /// Daemon connection status
    pub daemon_status: DaemonStatus,
    /// Daemon health status
    pub daemon_health: HealthStatus,
    /// Whether daemon is ready to accept commands
    pub daemon_ready: bool,

    // === Recording Related ===
    /// Current recording state
    pub recording_state: RecordingStateData,
    /// Current recording mode
    pub recording_mode: RecordingMode,

    // === Processing Related ===
    /// Current processing state
    pub processing_state: ProcessingStateData,

    // === Application Status ===
    /// Current application status
    pub app_status: AppStatus,

    // === Work Mode ===
    /// Current work mode
    pub work_mode: WorkMode,

    // === PTT Related ===
    /// PTT state
    pub ptt_state: PttState,
    /// Whether PTT is currently processing
    pub ptt_processing: bool,
    /// Whether PTT key is currently pressed
    pub ptt_key_pressed: bool,
    /// Current PTT shortcut (e.g., "Cmd+Shift+R")
    pub ptt_shortcut: Option<String>,

    // === Streaming ===
    /// Whether a streaming operation is in progress
    pub streaming_in_progress: bool,

    // === Recording Control ===
    /// Whether recording was aborted
    pub recording_aborted: bool,
}

impl Default for AppStateData {
    fn default() -> Self {
        Self {
            daemon_status: DaemonStatus::Stopped,
            daemon_health: HealthStatus::Unknown,
            daemon_ready: false,
            recording_state: RecordingStateData::default(),
            recording_mode: RecordingMode::PushToTalk,
            processing_state: ProcessingStateData::default(),
            app_status: AppStatus::Idle,
            work_mode: WorkMode::Conversation,
            ptt_state: PttState::Idle,
            ptt_processing: false,
            ptt_key_pressed: false,
            ptt_shortcut: None,
            streaming_in_progress: false,
            recording_aborted: false,
        }
    }
}

/// Recording state data
#[derive(Debug, Clone)]
pub struct RecordingStateData {
    /// Whether currently recording
    pub is_recording: bool,
    /// Whether audio is being processed
    pub is_processing: bool,
    /// Current audio level in dB
    pub audio_level_db: f32,
    /// Recording duration in seconds
    pub duration_seconds: f64,
}

impl Default for RecordingStateData {
    fn default() -> Self {
        Self {
            is_recording: false,
            is_processing: false,
            audio_level_db: 0.0,
            duration_seconds: 0.0,
        }
    }
}

/// Processing state data
#[derive(Debug, Clone)]
pub struct ProcessingStateData {
    /// Current processing stage
    pub stage: ProcessingStage,
    /// Progress from 0.0 to 1.0
    pub progress: f32,
    /// Human-readable status message
    pub message: String,
}

impl Default for ProcessingStateData {
    fn default() -> Self {
        Self {
            stage: ProcessingStage::Idle,
            progress: 0.0,
            message: String::new(),
        }
    }
}

/// A snapshot of the application state at a point in time
#[derive(Debug, Clone)]
pub struct StateSnapshot {
    /// Timestamp of the snapshot
    pub timestamp: i64,
    /// The state data
    pub data: AppStateData,
    /// Optional description of what caused the change
    pub reason: String,
}

impl NewAppState {
    /// Create a new AppState with default values
    pub fn new(event_bus: Arc<EventBus>) -> Self {
        Self {
            inner: RwLock::new(AppStateData::default()),
            event_bus,
            history: Arc::new(RwLock::new(Vec::new())),
        }
    }

    /// Get a read-only snapshot of the current state
    pub async fn get_state(&self) -> AppStateData {
        self.inner.read().await.clone()
    }

    /// Get a specific field using a selector function
    pub async fn read_state<F, R>(&self, selector: F) -> R
    where
        F: FnOnce(&AppStateData) -> R,
    {
        let state = self.inner.read().await;
        selector(&state)
    }

    /// Update state with a transformation function
    ///
    /// This will:
    /// 1. Apply the transformation to the state
    /// 2. Create a snapshot of the new state
    /// 3. Emit a StateChanged event
    /// 4. Add the snapshot to history
    pub async fn update_state<F>(&self, f: F) -> AppStateData
    where
        F: FnOnce(&mut AppStateData),
    {
        let mut state = self.inner.write().await;
        let old = state.clone();
        f(&mut state);
        let new = state.clone();

        // Emit state change event
        let snapshot_old = shared_types::events::AppStateSnapshot {
            timestamp: chrono::Utc::now().timestamp(),
            app_status: old.app_status,
            recording_state: shared_types::RecordingState {
                is_recording: old.recording_state.is_recording,
                is_processing: old.recording_state.is_processing,
                audio_level_db: old.recording_state.audio_level_db,
                duration_seconds: old.recording_state.duration_seconds,
            },
            processing_state: shared_types::ProcessingState {
                stage: old.processing_state.stage,
                progress: old.processing_state.progress,
                message: old.processing_state.message.clone(),
            },
            work_mode: old.work_mode,
            recording_mode: old.recording_mode,
            daemon_status: old.daemon_status,
            daemon_connected: old.daemon_ready,
        };

        let snapshot_new = shared_types::events::AppStateSnapshot {
            timestamp: chrono::Utc::now().timestamp(),
            app_status: new.app_status,
            recording_state: shared_types::RecordingState {
                is_recording: new.recording_state.is_recording,
                is_processing: new.recording_state.is_processing,
                audio_level_db: new.recording_state.audio_level_db,
                duration_seconds: new.recording_state.duration_seconds,
            },
            processing_state: shared_types::ProcessingState {
                stage: new.processing_state.stage,
                progress: new.processing_state.progress,
                message: new.processing_state.message.clone(),
            },
            work_mode: new.work_mode,
            recording_mode: new.recording_mode,
            daemon_status: new.daemon_status,
            daemon_connected: new.daemon_ready,
        };

        let event = Event::state_changed(Some(snapshot_old), snapshot_new);
        drop(state); // Release lock before publishing

        // Publish event (async, non-blocking)
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });

        // Add to history
        self.add_to_history(new.clone(), "update_state").await;

        new
    }

    /// Update daemon status
    pub async fn set_daemon_status(&self, status: DaemonStatus) {
        self.update_state(|s| s.daemon_status = status).await;
    }

    /// Update daemon health
    pub async fn set_daemon_health(&self, health: HealthStatus) {
        self.update_state(|s| s.daemon_health = health).await;
    }

    /// Update daemon ready flag
    pub async fn set_daemon_ready(&self, ready: bool) {
        self.update_state(|s| s.daemon_ready = ready).await;

        // Emit specific daemon status event
        let event = if ready {
            Event::DaemonConnected
        } else {
            Event::DaemonDisconnected
        };
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Update recording state
    pub async fn update_recording<F>(&self, f: F)
    where
        F: FnOnce(&mut RecordingStateData),
    {
        self.update_state(|s| f(&mut s.recording_state)).await;
    }

    /// Start recording
    pub async fn start_recording(&self, mode: RecordingMode) {
        self.update_state(|s| {
            s.recording_mode = mode;
            s.recording_state.is_recording = true;
            s.recording_state.duration_seconds = 0.0;
            s.app_status = AppStatus::Recording;
        }).await;

        // Emit recording started event
        let event = Event::recording_started(mode);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Stop recording
    pub async fn stop_recording(&self, reason: shared_types::StopReason) {
        self.update_state(|s| {
            s.recording_state.is_recording = false;
            s.app_status = AppStatus::Idle;
        }).await;

        // Emit recording stopped event
        let event = Event::recording_stopped(reason);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Update recording progress
    pub async fn set_recording_progress(&self, duration: f64, audio_level: f32) {
        self.update_state(|s| {
            s.recording_state.duration_seconds = duration;
            s.recording_state.audio_level_db = audio_level;
        }).await;

        // Emit progress event
        let event = Event::recording_progress(duration, audio_level);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Update processing state
    pub async fn set_processing_state(&self, stage: ProcessingStage, progress: f32, message: String) {
        self.update_state(|s| {
            s.processing_state.stage = stage;
            s.processing_state.progress = progress;
            s.processing_state.message = message.clone();

            // Update app_status based on stage
            s.app_status = match stage {
                ProcessingStage::Idle => AppStatus::Idle,
                ProcessingStage::Recording => AppStatus::Recording,
                ProcessingStage::AsrProcessing => AppStatus::AsrProcessing,
                ProcessingStage::LlmProcessing => AppStatus::LlmProcessing,
                ProcessingStage::TtsProcessing => AppStatus::TtsProcessing,
                ProcessingStage::Playing => AppStatus::Playing,
                _ => AppStatus::Idle,
            };
        }).await;

        // Emit processing progress event
        let event = Event::processing_progress(stage, progress, message);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Set work mode
    pub async fn set_work_mode(&self, mode: WorkMode) {
        let old = self.read_state(|s| s.work_mode).await;
        self.update_state(|s| s.work_mode = mode).await;

        // Emit work mode changed event
        let event = Event::work_mode_changed(old, mode);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Set recording mode
    pub async fn set_recording_mode(&self, mode: RecordingMode) {
        let old = self.read_state(|s| s.recording_mode).await;
        self.update_state(|s| s.recording_mode = mode).await;

        // Emit recording mode changed event
        let event = Event::recording_mode_changed(old, mode);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Update PTT state
    pub async fn set_ptt_state(&self, state: PttState) {
        let old = self.read_state(|s| s.ptt_state).await;
        self.update_state(|s| s.ptt_state = state).await;

        // Emit PTT state changed event
        let event = Event::ptt_state_changed(old, state);
        let event_bus = self.event_bus.clone();
        tokio::spawn(async move {
            event_bus.publish(event).await;
        });
    }

    /// Get the event bus
    pub fn event_bus(&self) -> &Arc<EventBus> {
        &self.event_bus
    }

    /// Get state history
    pub async fn get_history(&self) -> Vec<StateSnapshot> {
        self.history.read().await.clone()
    }

    /// Clear state history
    pub async fn clear_history(&self) {
        self.history.write().await.clear();
    }

    /// Convert state data to a snapshot
    fn to_snapshot(&self, data: AppStateData, reason: String) -> crate::event::HistoryEntry {
        crate::event::HistoryEntry {
            event: Event::StateChanged {
                old: None,
                new: shared_types::events::AppStateSnapshot {
                    timestamp: chrono::Utc::now().timestamp(),
                    app_status: data.app_status,
                    recording_state: shared_types::RecordingState {
                        is_recording: data.recording_state.is_recording,
                        is_processing: data.recording_state.is_processing,
                        audio_level_db: data.recording_state.audio_level_db,
                        duration_seconds: data.recording_state.duration_seconds,
                    },
                    processing_state: shared_types::ProcessingState {
                        stage: data.processing_state.stage,
                        progress: data.processing_state.progress,
                        message: data.processing_state.message,
                    },
                    work_mode: data.work_mode,
                    recording_mode: data.recording_mode,
                    daemon_status: data.daemon_status,
                    daemon_connected: data.daemon_ready,
                },
            },
            timestamp: chrono::Utc::now().timestamp(),
            source: Some(reason),
        }
    }

    /// Add a state snapshot to history
    async fn add_to_history(&self, data: AppStateData, reason: &str) {
        let mut history = self.history.write().await;
        history.push(StateSnapshot {
            timestamp: chrono::Utc::now().timestamp(),
            data,
            reason: reason.to_string(),
        });

        // Trim history if needed
        if history.len() > MAX_STATE_HISTORY {
            history.remove(0);
        }
    }

    // === Legacy compatibility methods ===
    // These methods provide compatibility with existing code that uses
    // global static variables. They will be removed once migration is complete.

    /// Check if daemon is ready (legacy compatibility)
    pub async fn is_daemon_ready(&self) -> bool {
        self.read_state(|s| s.daemon_ready).await
    }

    /// Check if currently recording (legacy compatibility)
    pub async fn is_recording(&self) -> bool {
        self.read_state(|s| s.recording_state.is_recording).await
    }

    /// Check if PTT is processing (legacy compatibility)
    pub async fn is_ptt_processing(&self) -> bool {
        self.read_state(|s| s.ptt_processing).await
    }

    /// Get recording mode (legacy compatibility)
    pub async fn get_recording_mode(&self) -> RecordingMode {
        self.read_state(|s| s.recording_mode).await
    }

    /// Get work mode (legacy compatibility)
    pub async fn get_work_mode(&self) -> WorkMode {
        self.read_state(|s| s.work_mode).await
    }

    /// Get app status (legacy compatibility)
    pub async fn get_app_status(&self) -> AppStatus {
        self.read_state(|s| s.app_status).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_app_state_creation() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus);

        let data = state.get_state().await;
        assert_eq!(data.app_status, AppStatus::Idle);
        assert_eq!(data.recording_mode, RecordingMode::PushToTalk);
        assert_eq!(data.work_mode, WorkMode::Conversation);
        assert!(!data.daemon_ready);
        assert!(!data.recording_state.is_recording);
    }

    #[tokio::test]
    async fn test_set_daemon_ready() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus.clone());

        state.set_daemon_ready(true).await;
        assert!(state.is_daemon_ready().await);

        // Verify event was emitted
        let mut rx = event_bus.subscribe();
        let event = rx.recv().await.unwrap();
        assert!(matches!(event, Event::DaemonConnected));
    }

    #[tokio::test]
    async fn test_start_stop_recording() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus.clone());

        state.start_recording(RecordingMode::Continuous).await;
        assert!(state.is_recording().await);
        assert_eq!(state.get_app_status().await, AppStatus::Recording);

        state.stop_recording(shared_types::StopReason::UserStopped).await;
        assert!(!state.is_recording().await);
    }

    #[tokio::test]
    async fn test_set_work_mode() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus.clone());

        state.set_work_mode(WorkMode::TextInput).await;
        assert_eq!(state.get_work_mode().await, WorkMode::TextInput);

        // Verify event was emitted
        let mut rx = event_bus.subscribe();
        let event = rx.recv().await.unwrap();
        assert!(matches!(event, Event::WorkModeChanged { .. }));
    }

    #[tokio::test]
    async fn test_update_recording_progress() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus);

        state.set_recording_progress(5.5, -12.0).await;
        let data = state.get_state().await;
        assert_eq!(data.recording_state.duration_seconds, 5.5);
        assert_eq!(data.recording_state.audio_level_db, -12.0);
    }

    #[tokio::test]
    async fn test_state_history() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus);

        state.set_daemon_ready(true).await;
        state.set_work_mode(WorkMode::TextInput).await;

        let history = state.get_history().await;
        assert!(history.len() >= 2);
    }

    #[tokio::test]
    async fn test_processing_state() {
        let event_bus = Arc::new(EventBus::new());
        let state = NewAppState::new(event_bus);

        state.set_processing_state(
            ProcessingStage::LlmProcessing,
            0.5,
            "Thinking...".to_string(),
        ).await;

        let data = state.get_state().await;
        assert_eq!(data.processing_state.stage, ProcessingStage::LlmProcessing);
        assert_eq!(data.processing_state.progress, 0.5);
        assert_eq!(data.app_status, AppStatus::LlmProcessing);
    }
}
