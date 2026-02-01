/**
 * useEventListener Hook
 *
 * Generic hook for listening to backend events via Tauri.
 * Uses shared-types for type-safe event handling.
 *
 * @example
 * ```tsx
 * // Listen to all events
 * const { events, isConnected } = useEventListener();
 *
 * // Listen to specific event
 * const unsub = useEventListenerSubscription('recording-started', (event) => {
 *   console.log('Recording started:', event.mode);
 * });
 * ```
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import {
  Event,
  EventCategory,
  RecordingMode,
  DaemonStatus,
  HealthStatus,
  ModelType,
  ProgressStage,
  PttState,
  type AppStateSnapshot,
  type ChatMessage,
  type ErrorInfo,
  type ProcessingStage,
  type RecordingStartedEvent,
  type RecordingProgressEvent,
  type ProcessingStartedEvent,
  type ProcessingProgressEvent,
  type ProcessingCompletedEvent,
  type ProcessingFailedEvent,
  type DaemonStatusChangedEvent,
  type DaemonHealthChangedEvent,
  type DaemonConnectedEvent,
  type DaemonDisconnectedEvent,
  type ModelProgressEvent,
  type ChatMessageAddedEvent,
  type ChatHistoryClearedEvent,
  type ErrorOccurredEvent,
  type ErrorClearedEvent,
  type PttStateChangedEvent,
  type PttKeyPressedEvent,
  type PttKeyReleasedEvent,
} from '@speekium/shared-types';

/**
 * Event listener callback type
 */
export type EventCallback<T = Event> = (event: T) => void;

/**
 * Event filter options
 */
export interface EventFilterOptions {
  /** Filter by event category */
  category?: EventCategory;
  /** Filter by event type (e.g., 'recording-started') */
  type?: string;
}

/**
 * Hook return value
 */
export interface UseEventListenerReturn {
  /** All received events (circular buffer) */
  events: Event[];
  /** Current app state snapshot (latest state-changed event) */
  appState: AppStateSnapshot | null;
  /** Whether event listener is connected */
  isConnected: boolean;
  /** Number of events received */
  eventCount: number;
  /** Clear event history */
  clearHistory: () => void;
  /** Get events by category */
  getEventsByCategory: (category: EventCategory) => Event[];
  /** Get events by type */
  getEventsByType: (type: string) => Event[];
}

/**
 * Maximum events to keep in memory (circular buffer)
 */
const MAX_EVENTS = 100;

/**
 * Hook for listening to all backend events
 */
export function useEventListener(options?: EventFilterOptions): UseEventListenerReturn {
  const [events, setEvents] = useState<Event[]>([]);
  const [appState, setAppState] = useState<AppStateSnapshot | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const unlistenFnsRef = useRef<Set<UnlistenFn>>(new Set());
  const eventBufferRef = useRef<Event[]>([]);

  /**
   * Add event to circular buffer
   */
  const addEvent = useCallback((event: Event) => {
    setEvents(() => {
      const newBuffer = [...eventBufferRef.current, event];
      if (newBuffer.length > MAX_EVENTS) {
        newBuffer.shift();
      }
      eventBufferRef.current = newBuffer;
      return newBuffer;
    });

    // Update app state snapshot
    if (event.type === 'state-changed') {
      const stateEvent = event as Extract<Event, { type: 'state-changed' }>;
      setAppState(stateEvent.data.new);
    }
  }, []);

  /**
   * Clear event history
   */
  const clearHistory = useCallback(() => {
    setEvents([]);
    eventBufferRef.current = [];
  }, []);

  /**
   * Get events by category
   */
  const getEventsByCategory = useCallback((category: EventCategory) => {
    return events.filter(event => {
      const eventCat = mapEventToCategory(event.type);
      return eventCat === category;
    });
  }, [events]);

  /**
   * Get events by type
   */
  const getEventsByType = useCallback((type: string) => {
    return events.filter(event => event.type === type);
  }, [events]);

  /**
   * Setup event listeners
   */
  useEffect(() => {
    const setupListeners = async () => {
      try {
        // Listen to all events through event bus
        const unlisten = await listen<Event>('event-bus', (event) => {
          // Apply filters if provided
          if (options?.category) {
            const eventCat = mapEventToCategory(event.payload.type);
            if (eventCat !== options.category) return;
          }
          if (options?.type && event.payload.type !== options.type) return;

          addEvent(event.payload);
        });

        unlistenFnsRef.current.add(unlisten);
        setIsConnected(true);

        console.log('[useEventListener] Connected to event bus');
      } catch (error) {
        console.error('[useEventListener] Failed to connect:', error);
        setIsConnected(false);
      }
    };

    setupListeners();

    return () => {
      unlistenFnsRef.current.forEach(unlisten => unlisten());
      unlistenFnsRef.current.clear();
    };
  }, [addEvent, options]);

  return {
    events,
    appState,
    isConnected,
    eventCount: events.length,
    clearHistory,
    getEventsByCategory,
    getEventsByType,
  };
}

/**
 * Hook for subscribing to a specific event type
 */
export function useEventListenerSubscription<T = Event>(
  eventType: string,
  callback: EventCallback<T>,
  deps: React.DependencyList = []
): UnlistenFn | null {
  const unlistenRef = useRef<UnlistenFn | null>(null);

  useEffect(() => {
    let isMounted = true;

    const setupListener = async () => {
      try {
        const unlisten = await listen<T>(eventType, (event) => {
          if (isMounted) {
            callback(event.payload);
          }
        });

        if (isMounted) {
          unlistenRef.current = unlisten;
        }
      } catch (error) {
        console.error(`[useEventListenerSubscription] Failed to listen to ${eventType}:`, error);
      }
    };

    setupListener();

    return () => {
      isMounted = false;
      if (unlistenRef.current) {
        unlistenRef.current();
        unlistenRef.current = null;
      }
    };
  }, [eventType, callback, ...deps]);

  return unlistenRef.current;
}

/**
 * Map event type to category
 */
function mapEventToCategory(eventType: string): EventCategory {
  if (eventType.startsWith('state-')) return EventCategory.State;
  if (eventType.startsWith('recording-')) return EventCategory.Recording;
  if (eventType.startsWith('processing-')) return EventCategory.Processing;
  if (eventType.includes('config') || eventType.includes('mode')) return EventCategory.Config;
  if (eventType.startsWith('daemon-')) return EventCategory.Daemon;
  if (eventType.startsWith('model-')) return EventCategory.Model;
  if (eventType.startsWith('chat-')) return EventCategory.Chat;
  if (eventType.startsWith('audio-')) return EventCategory.Audio;
  if (eventType.startsWith('ptt-')) return EventCategory.Ptt;
  if (eventType.startsWith('error-')) return EventCategory.Error;
  if (eventType.includes('theme') || eventType.includes('language')) return EventCategory.Ui;
  return EventCategory.State;
}

// ============================================================================
// Specific Event Hooks
// ============================================================================

/**
 * Hook for recording state events
 */
export function useRecordingEvents() {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingMode, setRecordingMode] = useState<RecordingMode>(RecordingMode.PushToTalk);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);

  useEventListenerSubscription<RecordingStartedEvent>('recording-started', (event) => {
    setIsRecording(true);
    setRecordingMode(event.data.mode);
  });

  useEventListenerSubscription('recording-stopped', () => {
    setIsRecording(false);
  });

  useEventListenerSubscription<RecordingProgressEvent>('recording-progress', (event) => {
    setRecordingDuration(event.data.duration);
    setAudioLevel(event.data.audio_level);
  });

  return {
    isRecording,
    recordingMode,
    recordingDuration,
    audioLevel,
  };
}

/**
 * Hook for processing state events
 */
export function useProcessingEvents() {
  const [currentStage, setCurrentStage] = useState<ProcessingStage | null>(null);
  const [stageProgress, setStageProgress] = useState(0);
  const [stageMessage, setStageMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  useEventListenerSubscription<ProcessingStartedEvent>('processing-started', (event) => {
    setCurrentStage(event.data.stage);
    setIsProcessing(true);
  });

  useEventListenerSubscription<ProcessingProgressEvent>('processing-progress', (event) => {
    setCurrentStage(event.data.stage);
    setStageProgress(event.data.progress);
    setStageMessage(event.data.message);
  });

  useEventListenerSubscription<ProcessingCompletedEvent>('processing-completed', () => {
    setIsProcessing(false);
    setStageProgress(100);
  });

  useEventListenerSubscription<ProcessingFailedEvent>('processing-failed', () => {
    setIsProcessing(false);
    setStageProgress(0);
  });

  return {
    currentStage,
    stageProgress,
    stageMessage,
    isProcessing,
  };
}

/**
 * Hook for daemon state events
 */
export function useDaemonEvents() {
  const [daemonStatus, setDaemonStatus] = useState<DaemonStatus>(DaemonStatus.Starting);
  const [daemonHealth, setDaemonHealth] = useState<HealthStatus>(HealthStatus.Unknown);
  const [isConnected, setIsConnected] = useState(false);

  useEventListenerSubscription<DaemonStatusChangedEvent>('daemon-status-changed', (event) => {
    setDaemonStatus(event.data.status);
  });

  useEventListenerSubscription<DaemonHealthChangedEvent>('daemon-health-changed', (event) => {
    setDaemonHealth(event.data.health);
  });

  useEventListenerSubscription<DaemonConnectedEvent>('daemon-connected', () => {
    setIsConnected(true);
  });

  useEventListenerSubscription<DaemonDisconnectedEvent>('daemon-disconnected', () => {
    setIsConnected(false);
  });

  return {
    daemonStatus,
    daemonHealth,
    isConnected,
  };
}

/**
 * Hook for model loading events
 */
export function useModelEvents() {
  const [modelProgress, setModelProgress] = useState<Record<ModelType, {
    stage: ProgressStage;
    progress: number;
    message: string;
  }>>({} as any);

  useEventListenerSubscription<ModelProgressEvent>('model-progress', (event) => {
    setModelProgress((prev) => ({
      ...prev,
      [event.data.model]: {
        stage: event.data.stage,
        progress: event.data.progress,
        message: event.data.message,
      },
    }));
  });

  const getModelProgress = (model: ModelType) => modelProgress[model];

  return {
    getModelProgress,
    allProgress: modelProgress,
  };
}

/**
 * Hook for chat events
 */
export function useChatEvents() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEventListenerSubscription<ChatMessageAddedEvent>('chat-message-added', (event) => {
    setMessages((prev) => [...prev, event.data.message]);
  });

  useEventListenerSubscription<ChatHistoryClearedEvent>('chat-history-cleared', () => {
    setMessages([]);
  });

  return {
    messages,
    addMessage: (message: ChatMessage) => setMessages((prev) => [...prev, message]),
    clearMessages: () => setMessages([]),
  };
}

/**
 * Hook for error events
 */
export function useErrorEvents() {
  const [errors, setErrors] = useState<ErrorInfo[]>([]);

  useEventListenerSubscription<ErrorOccurredEvent>('error-occurred', (event) => {
    setErrors((prev) => [...prev, event.data.error]);
  });

  useEventListenerSubscription<ErrorClearedEvent>('error-cleared', (event) => {
    setErrors((prev) => prev.filter((e) => e.id !== event.data.error_id));
  });

  return {
    errors,
    clearError: (errorId: string) => {
      setErrors((prev) => prev.filter((e) => e.id !== errorId));
    },
    clearAllErrors: () => setErrors([]),
  };
}

/**
 * Hook for PTT (Push-to-Talk) events
 */
export function usePttEvents() {
  const [pttState, setPttState] = useState<PttState>(PttState.Idle);

  useEventListenerSubscription<PttStateChangedEvent>('ptt-state-changed', (event) => {
    setPttState(event.data.new);
  });

  useEventListenerSubscription<PttKeyPressedEvent>('ptt-key-pressed', () => {
    setPttState(PttState.Pressed);
  });

  useEventListenerSubscription<PttKeyReleasedEvent>('ptt-key-released', () => {
    setPttState(PttState.Idle);
  });

  return {
    pttState,
    isPressed: pttState === PttState.Pressed,
    isLocked: pttState === PttState.Locked,
  };
}
