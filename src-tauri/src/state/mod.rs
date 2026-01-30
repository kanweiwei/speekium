// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Application state management
//!
//! This module provides the unified state manager for the application.
//! It integrates with the event system to provide reactive state updates.

mod app_state;

pub use app_state::{NewAppState, AppStateData, RecordingStateData, ProcessingStateData};

// Legacy compatibility: Re-export Database from database module
pub use crate::database::Database;

// Legacy compatibility: The old simple AppState struct
// This is used by app.rs and will be phased out
pub struct AppState {
    pub db: Database,
}

// Re-export the new AppState with a different name to avoid conflicts
pub use NewAppState as UnifiedAppState;
