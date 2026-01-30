// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Event listener traits and implementations

use crate::event::Event;
use std::fmt;

/// Trait for objects that can handle events
pub trait EventListener: Send + Sync {
    /// Handle an event
    fn on_event(&self, event: &Event);

    /// Get the listener's name (for debugging)
    fn name(&self) -> &str {
        std::any::type_name::<Self>()
    }

    /// Check if this listener is interested in the event
    fn is_interested(&self, event: &Event) -> bool {
        true // By default, listen to all events
    }
}

/// Function-based event listener
pub struct FnListener<F>
where
    F: Fn(&Event) + Send + Sync,
{
    name: String,
    callback: F,
    filter: Option<EventFilter>,
}

impl<F> FnListener<F>
where
    F: Fn(&Event) + Send + Sync,
{
    /// Create a new function-based listener
    pub fn new(name: impl Into<String>, callback: F) -> Self {
        Self {
            name: name.into(),
            callback,
            filter: None,
        }
    }

    /// Set a filter for this listener
    pub fn with_filter(mut self, filter: EventFilter) -> Self {
        self.filter = Some(filter);
        self
    }
}

impl<F> EventListener for FnListener<F>
where
    F: Fn(&Event) + Send + Sync,
{
    fn on_event(&self, event: &Event) {
        (self.callback)(event);
    }

    fn name(&self) -> &str {
        &self.name
    }

    fn is_interested(&self, event: &Event) -> bool {
        match &self.filter {
            Some(filter) => filter.matches(event),
            None => true,
        }
    }
}

/// Filter for events
pub enum EventFilter {
    /// Listen to all events
    All,
    /// Listen to events of a specific category
    Category(EventCategory),
    /// Listen to events matching a predicate
    Predicate(Box<dyn Fn(&Event) -> bool + Send + Sync>),
}

impl Clone for EventFilter {
    fn clone(&self) -> Self {
        match self {
            Self::All => Self::All,
            Self::Category(cat) => Self::Category(*cat),
            // Predicate filters cannot be cloned
            // This is a limitation - users should recreate the filter
            Self::Predicate(_) => Self::All,
        }
    }
}

impl EventFilter {
    /// Check if an event matches this filter
    pub fn matches(&self, event: &Event) -> bool {
        match self {
            Self::All => true,
            Self::Category(category) => event.category() == *category,
            Self::Predicate(predicate) => predicate(event),
        }
    }
}

impl fmt::Display for EventFilter {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::All => write!(f, "All"),
            Self::Category(cat) => write!(f, "Category({:?})", cat),
            Self::Predicate(_) => write!(f, "Predicate(...)"),
        }
    }
}

impl fmt::Debug for EventFilter {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self)
    }
}

// Re-export EventCategory from shared types
use shared_types::events::EventCategory;

#[cfg(test)]
mod tests {
    use super::*;
    use shared_types::{RecordingMode, StopReason};
    use std::sync::Arc;
    use tokio::sync::RwLock;

    #[test]
    fn test_fn_listener() {
        let counter = Arc::new(RwLock::new(0));
        let counter_clone = counter.clone();
        let listener = FnListener::new("test_listener", move |_event| {
            let rt = tokio::runtime::Handle::try_current();
            if let Ok(handle) = rt {
                let c = counter_clone.clone();
                handle.spawn(async move {
                    *c.write().await += 1;
                });
            }
        });

        let event = Event::recording_started(RecordingMode::PushToTalk);
        listener.on_event(&event);

        // Give time for async task to complete
        std::thread::sleep(std::time::Duration::from_millis(100));
        let final_count = *counter.read().unwrap();
        assert_eq!(final_count, 1);
    }

    #[test]
    fn test_category_filter() {
        let filter = EventFilter::Category(EventCategory::Recording);
        let recording_event = Event::recording_started(RecordingMode::Continuous);
        let config_event = Event::config_changed("test".to_string(), serde_json::json!(null));

        assert!(filter.matches(&recording_event));
        assert!(!filter.matches(&config_event));
    }

    #[test]
    fn test_predicate_filter() {
        let filter = EventFilter::Predicate(Box::new(|event| {
            matches!(
                event,
                Event::RecordingStopped { .. }
            )
        }));

        let stop_event = Event::recording_stopped(StopReason::UserStopped);
        let start_event = Event::recording_started(RecordingMode::PushToTalk);

        assert!(filter.matches(&stop_event));
        assert!(!filter.matches(&start_event));
    }
}
