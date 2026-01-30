// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

//! Type-safe event bus for asynchronous event handling

use super::listener::EventListener;
use super::Event;
use std::sync::Arc;
use tokio::sync::{broadcast, RwLock};
use uuid::Uuid;

/// Channel capacity for the event bus
const CHANNEL_CAPACITY: usize = 1000;

/// The EventBus manages event distribution to subscribers
///
/// # Design Principles
/// 1. **Type Safety**: All events are strongly typed via the Event enum
/// 2. **Unidirectional Flow**: Events flow from publisher → subscribers only
/// 3. **Async Distribution**: Event publishing doesn't block subscribers
/// 4. **No Deadlocks**: Uses broadcast channels to avoid lock contention
#[derive(Clone)]
pub struct EventBus {
    /// Sender for publishing events
    sender: broadcast::Sender<Event>,
    /// Registered listeners (for synchronous direct calls)
    listeners: Arc<RwLock<Vec<ListenerEntry>>>,
    /// Event history (for debugging and replay)
    history: Arc<RwLock<Vec<HistoryEntry>>>,
    /// Configuration
    config: Arc<RwLock<EventBusConfig>>,
}

/// Configuration for the EventBus
#[derive(Debug, Clone)]
pub struct EventBusConfig {
    /// Maximum number of events to keep in history
    pub max_history_size: usize,
    /// Whether to log all events
    pub log_events: bool,
    /// Whether to enable event replay for new subscribers
    pub enable_replay: bool,
}

impl Default for EventBusConfig {
    fn default() -> Self {
        Self {
            max_history_size: 1000,
            log_events: false,
            enable_replay: false,
        }
    }
}

/// A listener entry with metadata
struct ListenerEntry {
    /// Unique ID for this listener
    id: Uuid,
    /// The listener itself (boxed trait object)
    listener: Box<dyn EventListener>,
    /// Whether this listener is active
    active: bool,
}

impl ListenerEntry {
    fn new(listener: Box<dyn EventListener>) -> Self {
        Self {
            id: Uuid::new_v4(),
            listener,
            active: true,
        }
    }
}

/// Entry in event history
#[derive(Debug, Clone)]
pub struct HistoryEntry {
    /// The event
    pub event: Event,
    /// Timestamp
    pub timestamp: i64,
    /// Source of the event (optional)
    pub source: Option<String>,
}

/// Subscription handle that auto-unsubscribes when dropped
pub struct EventSubscription {
    _unsubscribe: broadcast::Receiver<Event>,
    listener_id: Option<Uuid>,
    event_bus: Option<EventBus>,
}

impl EventSubscription {
    /// Create a new subscription that doesn't auto-unsubscribe
    pub fn without_unsubscribe(receiver: broadcast::Receiver<Event>) -> Self {
        Self {
            _unsubscribe: receiver,
            listener_id: None,
            event_bus: None,
        }
    }

    /// Manually unsubscribe
    pub async fn unsubscribe(mut self) {
        if let (Some(id), Some(bus)) = (self.listener_id.take(), self.event_bus.take()) {
            bus.remove_listener(id).await;
        }
    }

    /// Create a subscription that auto-unsubscribes on drop
    fn new_with_auto_unsubscribe(
        receiver: broadcast::Receiver<Event>,
        listener_id: Uuid,
        event_bus: EventBus,
    ) -> Self {
        Self {
            _unsubscribe: receiver,
            listener_id: Some(listener_id),
            event_bus: Some(event_bus),
        }
    }
}

impl Drop for EventSubscription {
    fn drop(&mut self) {
        // Note: We can't use async here, so actual removal is lazy
        // The listener is marked inactive and cleaned up later
        if let (Some(id), Some(bus)) = (self.listener_id.take(), self.event_bus.take()) {
            let rt = tokio::runtime::Handle::try_current();
            if let Ok(handle) = rt {
                let bus_clone = bus.clone();
                handle.spawn(async move {
                    bus_clone.remove_listener(id).await;
                });
            }
        }
    }
}

impl EventBus {
    /// Create a new EventBus
    pub fn new() -> Self {
        let (sender, _) = broadcast::channel(CHANNEL_CAPACITY);
        Self {
            sender,
            listeners: Arc::new(RwLock::new(Vec::new())),
            history: Arc::new(RwLock::new(Vec::new())),
            config: Arc::new(RwLock::new(EventBusConfig::default())),
        }
    }

    /// Create a new EventBus with custom configuration
    pub fn with_config(config: EventBusConfig) -> Self {
        let (sender, _) = broadcast::channel(CHANNEL_CAPACITY);
        Self {
            sender,
            listeners: Arc::new(RwLock::new(Vec::new())),
            history: Arc::new(RwLock::new(Vec::new())),
            config: Arc::new(RwLock::new(config)),
        }
    }

    /// Publish an event to all subscribers
    ///
    /// Returns the number of subscribers that received the event
    pub async fn publish(&self, event: Event) -> usize {
        // Add to history
        self.add_to_history(event.clone(), None).await;

        // Get config
        let config = self.config.read().await;
        if config.log_events {
            eprintln!("[EventBus] Publishing: {:?}", event);
        }

        // Send to channel subscribers
        let receiver_count = self.sender.send(event.clone()).unwrap_or(0);

        // Also notify direct listeners
        let listeners = self.listeners.read().await;
        for entry in listeners.iter() {
            if entry.active && entry.listener.is_interested(&event) {
                entry.listener.on_event(&event);
            }
        }

        receiver_count
    }

    /// Publish an event with a source identifier
    pub async fn publish_with_source(&self, event: Event, source: impl Into<String>) -> usize {
        let source = source.into();
        self.add_to_history(event.clone(), Some(source)).await;
        self.publish(event).await
    }

    /// Subscribe to all events
    ///
    /// Returns a receiver that can be used to listen for events
    pub fn subscribe(&self) -> broadcast::Receiver<Event> {
        self.sender.subscribe()
    }

    /// Subscribe with a filter function
    pub fn subscribe_filtered<F>(&self, filter: F) -> FilteredSubscription
    where
        F: Fn(&Event) -> bool + Send + Sync + 'static,
    {
        let rx = self.sender.subscribe();
        FilteredSubscription::new(rx, filter)
    }

    /// Add a direct listener (will be called synchronously)
    pub async fn add_listener(&self, listener: Box<dyn EventListener>) -> EventSubscription {
        let entry = ListenerEntry::new(listener);
        let id = entry.id;

        let mut listeners = self.listeners.write().await;
        listeners.push(entry);

        // Create a subscription that will clean up on drop
        let rx = self.sender.subscribe();
        EventSubscription::new_with_auto_unsubscribe(rx, id, self.clone())
    }

    /// Remove a listener by ID
    pub async fn remove_listener(&self, id: Uuid) {
        let mut listeners = self.listeners.write().await;
        listeners.retain(|entry| entry.id != id);
    }

    /// Get event history
    pub async fn get_history(&self) -> Vec<HistoryEntry> {
        self.history.read().await.clone()
    }

    /// Clear event history
    pub async fn clear_history(&self) {
        self.history.write().await.clear();
    }

    /// Get current configuration
    pub async fn get_config(&self) -> EventBusConfig {
        self.config.read().await.clone()
    }

    /// Update configuration
    pub async fn update_config<F>(&self, updater: F)
    where
        F: FnOnce(&mut EventBusConfig),
    {
        let mut config = self.config.write().await;
        updater(&mut config);
    }

    /// Get the number of active listeners
    pub async fn listener_count(&self) -> usize {
        self.listeners.read().await.iter().filter(|l| l.active).count()
    }

    /// Add an event to history
    async fn add_to_history(&self, event: Event, source: Option<String>) {
        let mut history = self.history.write().await;
        let config = self.config.read().await;

        let entry = HistoryEntry {
            event,
            timestamp: chrono::Utc::now().timestamp(),
            source,
        };

        history.push(entry);

        // Trim history if needed
        if history.len() > config.max_history_size {
            history.remove(0);
        }
    }
}

impl Default for EventBus {
    fn default() -> Self {
        Self::new()
    }
}

/// Filtered subscription that only receives matching events
pub struct FilteredSubscription {
    receiver: broadcast::Receiver<Event>,
    filter: Box<dyn Fn(&Event) -> bool + Send + Sync>,
}

impl FilteredSubscription {
    fn new<F>(receiver: broadcast::Receiver<Event>, filter: F) -> Self
    where
        F: Fn(&Event) -> bool + Send + Sync + 'static,
    {
        Self {
            receiver,
            filter: Box::new(filter),
        }
    }

    /// Receive the next matching event
    pub async fn recv(&mut self) -> Result<Event, broadcast::error::RecvError> {
        loop {
            let event = self.receiver.recv().await?;
            if (self.filter)(&event) {
                return Ok(event);
            }
        }
    }

    /// Try to receive without blocking
    pub fn try_recv(&mut self) -> Result<Event, broadcast::error::TryRecvError> {
        loop {
            let event = self.receiver.try_recv()?;
            if (self.filter)(&event) {
                return Ok(event);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use shared_types::{RecordingMode, StopReason};

    #[tokio::test]
    async fn test_event_bus_publish() {
        let bus = EventBus::new();
        let event = Event::recording_started(RecordingMode::PushToTalk);

        let count = bus.publish(event.clone()).await;
        assert_eq!(count, 0); // No subscribers yet
    }

    #[tokio::test]
    async fn test_event_bus_subscribe() {
        let bus = EventBus::new();
        let mut rx = bus.subscribe();

        let event = Event::recording_started(RecordingMode::Continuous);
        bus.publish(event.clone()).await;

        let received = rx.recv().await.unwrap();
        assert!(received.is_recording_event());
    }

    #[tokio::test]
    async fn test_filtered_subscription() {
        let bus = EventBus::new();
        let mut sub = bus.subscribe_filtered(|e| e.is_recording_event());

        let recording_event = Event::recording_started(RecordingMode::PushToTalk);
        let config_event = Event::config_changed("test".to_string(), serde_json::json!(null));

        bus.publish(config_event).await;
        bus.publish(recording_event.clone()).await;

        let received = sub.recv().await.unwrap();
        assert_eq!(received, recording_event);
    }

    #[tokio::test]
    async fn test_direct_listener() {
        let bus = EventBus::new();
        let mut count = Arc::new(RwLock::new(0));

        let count_clone = count.clone();
        let listener = super::super::listener::FnListener::new("test_listener", move |_event| {
            let rt = tokio::runtime::Handle::try_current();
            if let Ok(handle) = rt {
                let count_clone = count_clone.clone();
                handle.spawn(async move {
                    *count_clone.write().await += 1;
                });
            }
        });

        bus.add_listener(Box::new(listener)).await;

        let event = Event::recording_started(RecordingMode::PushToTalk);
        bus.publish(event).await;

        // Give time for async listener to process
        tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;

        let final_count = *count.read().await;
        assert_eq!(final_count, 1);
    }

    #[tokio::test]
    async fn test_event_history() {
        let bus = EventBus::new();
        let event = Event::recording_stopped(StopReason::UserStopped);

        bus.publish(event.clone()).await;
        let history = bus.get_history().await;

        assert_eq!(history.len(), 1);
        assert!(history[0].event.is_recording_event());
    }

    #[tokio::test]
    async fn test_listener_count() {
        let bus = EventBus::new();
        assert_eq!(bus.listener_count().await, 0);

        let listener = super::super::listener::FnListener::new("test", |_| {});
        bus.add_listener(Box::new(listener)).await;

        assert_eq!(bus.listener_count().await, 1);
    }
}
