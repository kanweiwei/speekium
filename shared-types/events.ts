// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

/**
 * Event definitions for the event bus system
 */

import {
  EventCategory,
  type RecordingMode,
  type WorkMode,
  type DaemonStatus,
  type HealthStatus,
  type ProcessingStage,
  type ModelType,
  type ProgressStage,
  type PttState,
} from './enums';
import type {
  AppStateSnapshot,
  ProcessingResult,
  ChatMessage,
  AudioLevel,
  ErrorInfo,
} from './interfaces';

// ===== Event Types =====

/**
 * Base event interface
 */
export interface BaseEvent {
  type: string;
}

// State events

export interface StateChangedEvent extends BaseEvent {
  type: 'state-changed';
  data: {
    old: AppStateSnapshot | null;
    new: AppStateSnapshot;
  };
}

// Recording events

export interface RecordingStartedEvent extends BaseEvent {
  type: 'recording-started';
  data: {
    mode: RecordingMode;
  };
}

export interface RecordingStoppedEvent extends BaseEvent {
  type: 'recording-stopped';
  data: {
    reason: 'user' | 'silence' | 'timeout' | 'error';
  };
}

export interface RecordingProgressEvent extends BaseEvent {
  type: 'recording-progress';
  data: {
    duration: number;
    audio_level: number;
  };
}

// Processing events

export interface ProcessingStartedEvent extends BaseEvent {
  type: 'processing-started';
  data: {
    stage: ProcessingStage;
  };
}

export interface ProcessingProgressEvent extends BaseEvent {
  type: 'processing-progress';
  data: {
    stage: ProcessingStage;
    progress: number;
    message: string;
  };
}

export interface ProcessingCompletedEvent extends BaseEvent {
  type: 'processing-completed';
  data: {
    stage: ProcessingStage;
    result: ProcessingResult;
  };
}

export interface ProcessingFailedEvent extends BaseEvent {
  type: 'processing-failed';
  data: {
    stage: ProcessingStage;
    error: string;
  };
}

// Config events

export interface ConfigChangedEvent extends BaseEvent {
  type: 'config-changed';
  data: {
    key: string;
    value: unknown;
  };
}

export interface WorkModeChangedEvent extends BaseEvent {
  type: 'work-mode-changed';
  data: {
    old: WorkMode;
    new: WorkMode;
  };
}

export interface RecordingModeChangedEvent extends BaseEvent {
  type: 'recording-mode-changed';
  data: {
    old: RecordingMode;
    new: RecordingMode;
  };
}

// Daemon events

export interface DaemonStatusChangedEvent extends BaseEvent {
  type: 'daemon-status-changed';
  data: {
    status: DaemonStatus;
  };
}

export interface DaemonHealthChangedEvent extends BaseEvent {
  type: 'daemon-health-changed';
  data: {
    health: HealthStatus;
  };
}

export interface DaemonConnectedEvent extends BaseEvent {
  type: 'daemon-connected';
}

export interface DaemonDisconnectedEvent extends BaseEvent {
  type: 'daemon-disconnected';
}

// Model events

export interface ModelProgressEvent extends BaseEvent {
  type: 'model-progress';
  data: {
    model: ModelType;
    stage: ProgressStage;
    progress: number;
    message: string;
  };
}

export interface ModelLoadedEvent extends BaseEvent {
  type: 'model-loaded';
  data: {
    model: ModelType;
  };
}

export interface ModelLoadFailedEvent extends BaseEvent {
  type: 'model-load-failed';
  data: {
    model: ModelType;
    error: string;
  };
}

// Chat events

export interface ChatMessageAddedEvent extends BaseEvent {
  type: 'chat-message-added';
  data: {
    message: ChatMessage;
  };
}

export interface ChatHistoryClearedEvent extends BaseEvent {
  type: 'chat-history-cleared';
}

export interface ChatStreamStartedEvent extends BaseEvent {
  type: 'chat-stream-started';
}

export interface ChatStreamEndedEvent extends BaseEvent {
  type: 'chat-stream-ended';
}

// Audio events

export interface AudioLevelChangedEvent extends BaseEvent {
  type: 'audio-level-changed';
  data: {
    level: AudioLevel;
  };
}

export interface AudioPlaybackStartedEvent extends BaseEvent {
  type: 'audio-playback-started';
}

export interface AudioPlaybackStoppedEvent extends BaseEvent {
  type: 'audio-playback-stopped';
}

export interface AudioPlaybackProgressEvent extends BaseEvent {
  type: 'audio-playback-progress';
  data: {
    position: number;
    duration: number;
  };
}

// PTT events

export interface PttStateChangedEvent extends BaseEvent {
  type: 'ptt-state-changed';
  data: {
    old: PttState;
    new: PttState;
  };
}

export interface PttKeyPressedEvent extends BaseEvent {
  type: 'ptt-key-pressed';
}

export interface PttKeyReleasedEvent extends BaseEvent {
  type: 'ptt-key-released';
}

// UI events

export interface ThemeChangedEvent extends BaseEvent {
  type: 'theme-changed';
  data: {
    theme: string;
  };
}

export interface LanguageChangedEvent extends BaseEvent {
  type: 'language-changed';
  data: {
    language: string;
  };
}

// Error events

export interface ErrorOccurredEvent extends BaseEvent {
  type: 'error-occurred';
  data: {
    error: ErrorInfo;
  };
}

export interface ErrorClearedEvent extends BaseEvent {
  type: 'error-cleared';
  data: {
    error_id: string;
  };
}

// ===== Union Type =====

/**
 * All event types as a union
 */
export type Event =
  | StateChangedEvent
  | RecordingStartedEvent
  | RecordingStoppedEvent
  | RecordingProgressEvent
  | ProcessingStartedEvent
  | ProcessingProgressEvent
  | ProcessingCompletedEvent
  | ProcessingFailedEvent
  | ConfigChangedEvent
  | WorkModeChangedEvent
  | RecordingModeChangedEvent
  | DaemonStatusChangedEvent
  | DaemonHealthChangedEvent
  | DaemonConnectedEvent
  | DaemonDisconnectedEvent
  | ModelProgressEvent
  | ModelLoadedEvent
  | ModelLoadFailedEvent
  | ChatMessageAddedEvent
  | ChatHistoryClearedEvent
  | ChatStreamStartedEvent
  | ChatStreamEndedEvent
  | AudioLevelChangedEvent
  | AudioPlaybackStartedEvent
  | AudioPlaybackStoppedEvent
  | AudioPlaybackProgressEvent
  | PttStateChangedEvent
  | PttKeyPressedEvent
  | PttKeyReleasedEvent
  | ThemeChangedEvent
  | LanguageChangedEvent
  | ErrorOccurredEvent
  | ErrorClearedEvent;

// ===== Type Guards =====

/**
 * Get event category from event type
 */
export function getEventCategory(eventType: string): EventCategory {
  const categoryMap: Record<string, EventCategory> = {
    'state-changed': EventCategory.State,
    'recording-started': EventCategory.Recording,
    'recording-stopped': EventCategory.Recording,
    'recording-progress': EventCategory.Recording,
    'processing-started': EventCategory.Processing,
    'processing-progress': EventCategory.Processing,
    'processing-completed': EventCategory.Processing,
    'processing-failed': EventCategory.Processing,
    'config-changed': EventCategory.Config,
    'work-mode-changed': EventCategory.Config,
    'recording-mode-changed': EventCategory.Config,
    'daemon-status-changed': EventCategory.Daemon,
    'daemon-health-changed': EventCategory.Daemon,
    'daemon-connected': EventCategory.Daemon,
    'daemon-disconnected': EventCategory.Daemon,
    'model-progress': EventCategory.Model,
    'model-loaded': EventCategory.Model,
    'model-load-failed': EventCategory.Model,
    'chat-message-added': EventCategory.Chat,
    'chat-history-cleared': EventCategory.Chat,
    'chat-stream-started': EventCategory.Chat,
    'chat-stream-ended': EventCategory.Chat,
    'audio-level-changed': EventCategory.Audio,
    'audio-playback-started': EventCategory.Audio,
    'audio-playback-stopped': EventCategory.Audio,
    'audio-playback-progress': EventCategory.Audio,
    'ptt-state-changed': EventCategory.Ptt,
    'ptt-key-pressed': EventCategory.Ptt,
    'ptt-key-released': EventCategory.Ptt,
    'theme-changed': EventCategory.Ui,
    'language-changed': EventCategory.Ui,
    'error-occurred': EventCategory.Error,
    'error-cleared': EventCategory.Error,
  };
  return categoryMap[eventType] ?? EventCategory.State;
}

/**
 * Type guard for state changed events
 */
export function isStateChangedEvent(event: Event): event is StateChangedEvent {
  return event.type === 'state-changed';
}

/**
 * Type guard for recording events
 */
export function isRecordingEvent(event: Event): boolean {
  return event.type.startsWith('recording-');
}

/**
 * Type guard for processing events
 */
export function isProcessingEvent(event: Event): boolean {
  return event.type.startsWith('processing-');
}

/**
 * Type guard for error events
 */
export function isErrorEvent(event: Event): event is ErrorOccurredEvent | ErrorClearedEvent {
  return event.type.startsWith('error-');
}
