// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Event system for type-safe, asynchronous event handling
//!
//! The EventBus provides a publish/subscribe mechanism for communication
//! between different parts of the application.

mod bus;
mod listener;

pub use bus::{EventBus, EventSubscription, HistoryEntry};
pub use listener::{EventListener, EventFilter};

// Re-export shared types
pub use shared_types::events::{Event, EventCategory};

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_event_creation() {
        let event = Event::recording_started(shared_types::RecordingMode::PushToTalk);
        assert!(event.is_recording_event());
        assert_eq!(event.category(), EventCategory::Recording);
    }
}
