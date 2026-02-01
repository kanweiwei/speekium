/**
 * useAppState Hook
 *
 * Provides application state using shared-types and the event system.
 * Replaces polling with event-driven state updates.
 *
 * @example
 * ```tsx
 * const { appState, status, recordingState, isIdle, isRecording } = useAppState();
 * ```
 */

import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import {
  AppStatus,
  RecordingMode,
  WorkMode,
  DaemonStatus,
  type AppStateSnapshot,
  type RecordingState,
  type ProcessingState,
  type UserConfig,
  type ChatMessage,
  type AudioLevel,
  type Statistics,
  type WorkModeChangedEvent,
  type RecordingModeChangedEvent,
  type AudioLevelChangedEvent,
  type ChatMessageAddedEvent,
  type ChatHistoryClearedEvent,
  type ThemeChangedEvent,
  type LanguageChangedEvent,
  type ErrorOccurredEvent,
  type ErrorClearedEvent,
  type ChatStreamStartedEvent,
  type ChatStreamEndedEvent,
} from '@speekium/shared-types';
import { useEventListenerSubscription } from './useEventListener';

/**
 * Hook return value
 */
export interface UseAppStateReturn {
  /** Full app state snapshot */
  appState: AppStateSnapshot | null;
  /** Current app status */
  status: AppStatus;
  /** Current recording state */
  recordingState: RecordingState | null;
  /** Current processing state */
  processingState: ProcessingState | null;
  /** Current work mode */
  workMode: WorkMode;
  /** Current recording mode */
  recordingMode: RecordingMode;
  /** Daemon status */
  daemonStatus: DaemonStatus;
  /** Whether daemon is connected */
  daemonConnected: boolean;
  /** User configuration */
  config: UserConfig | null;
  /** Chat messages */
  messages: ChatMessage[];
  /** Current audio level */
  audioLevel: AudioLevel | null;
  /** Statistics */
  statistics: Statistics | null;

  // Computed properties
  /** Whether app is idle */
  isIdle: boolean;
  /** Whether app is listening */
  isListening: boolean;
  /** Whether app is recording */
  isRecording: boolean;
  /** Whether app is processing (ASR, LLM, or TTS) */
  isProcessing: boolean;
  /** Whether app is playing audio */
  isPlaying: boolean;
  /** Whether app is in error state */
  isError: boolean;
  /** Whether daemon is ready */
  isDaemonReady: boolean;

  // Actions
  /** Refresh app state from backend */
  refresh: () => Promise<void>;
  /** Set work mode */
  setWorkMode: (mode: WorkMode) => Promise<void>;
  /** Set recording mode */
  setRecordingMode: (mode: RecordingMode) => Promise<void>;
}

/**
 * Default recording state
 */
const DEFAULT_RECORDING_STATE: RecordingState = {
  is_recording: false,
  is_processing: false,
  audio_level_db: -Infinity,
  duration_seconds: 0,
};

/**
 * Default processing state
 */
const DEFAULT_PROCESSING_STATE: ProcessingState = {
  current_stage: null,
  stage_progress: 0,
  stage_message: '',
};

/**
 * Default audio level
 */
const DEFAULT_AUDIO_LEVEL: AudioLevel = {
  rms: 0,
  peak: 0,
  db: -Infinity,
};

/**
 * Hook for accessing application state
 */
export function useAppState(): UseAppStateReturn {
  const [appState, setAppState] = useState<AppStateSnapshot | null>(null);
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [audioLevel, setAudioLevel] = useState<AudioLevel>(DEFAULT_AUDIO_LEVEL);
  const [statistics] = useState<Statistics | null>(null);

  /**
   * Refresh state from backend
   */
  const refresh = useCallback(async () => {
    try {
      const state = await invoke<AppStateSnapshot>('get_app_state');
      setAppState(state);
    } catch (error) {
      console.error('[useAppState] Failed to refresh state:', error);
    }
  }, []);

  /**
   * Refresh config from backend
   */
  const refreshConfig = useCallback(async () => {
    try {
      const cfg = await invoke<UserConfig>('get_config');
      setConfig(cfg);
    } catch (error) {
      console.error('[useAppState] Failed to refresh config:', error);
    }
  }, []);

  /**
   * Set work mode
   */
  const setWorkMode = useCallback(async (mode: WorkMode) => {
    try {
      await invoke('set_work_mode', { mode });
    } catch (error) {
      console.error('[useAppState] Failed to set work mode:', error);
      throw error;
    }
  }, []);

  /**
   * Set recording mode
   */
  const setRecordingMode = useCallback(async (mode: RecordingMode) => {
    try {
      await invoke('set_recording_mode', { mode });
    } catch (error) {
      console.error('[useAppState] Failed to set recording mode:', error);
      throw error;
    }
  }, []);

  /**
   * Initial state load
   */
  useEffect(() => {
    refresh();
    refreshConfig();
  }, [refresh, refreshConfig]);

  /**
   * Listen to state change events
   */
  useEventListenerSubscription<AppStateSnapshot>('state-changed', (event) => {
    setAppState(event);
  });

  /**
   * Listen to config change events
   */
  useEventListenerSubscription('config-changed', () => {
    refreshConfig();
  });

  /**
   * Listen to work mode changes
   */
  useEventListenerSubscription<WorkModeChangedEvent>('work-mode-changed', (event) => {
    if (appState) {
      setAppState({
        ...appState,
        work_mode: event.data.new,
      });
    }
  });

  /**
   * Listen to recording mode changes
   */
  useEventListenerSubscription<RecordingModeChangedEvent>('recording-mode-changed', (event) => {
    if (appState) {
      setAppState({
        ...appState,
        recording_mode: event.data.new,
      });
    }
  });

  /**
   * Listen to audio level changes
   */
  useEventListenerSubscription<AudioLevelChangedEvent>('audio-level-changed', (event) => {
    setAudioLevel(event.data.level);
  });

  /**
   * Listen to chat message additions
   */
  useEventListenerSubscription<ChatMessageAddedEvent>('chat-message-added', (event) => {
    setMessages((prev) => [...prev, event.data.message]);
  });

  /**
   * Listen to chat history clear
   */
  useEventListenerSubscription<ChatHistoryClearedEvent>('chat-history-cleared', () => {
    setMessages([]);
  });

  // Extract values from app state
  const status = appState?.app_status ?? AppStatus.Idle;
  const recordingState = appState?.recording_state ?? DEFAULT_RECORDING_STATE;
  const processingState = appState?.processing_state ?? DEFAULT_PROCESSING_STATE;
  const workMode = appState?.work_mode ?? WorkMode.Conversation;
  const recordingMode = appState?.recording_mode ?? RecordingMode.PushToTalk;
  const daemonStatus = appState?.daemon_status ?? DaemonStatus.Starting;
  const daemonConnected = appState?.daemon_connected ?? false;

  // Computed properties
  const isIdle = status === AppStatus.Idle;
  const isListening = status === AppStatus.Listening;
  const isRecording = status === AppStatus.Recording;
  const isProcessing =
    status === AppStatus.AsrProcessing ||
    status === AppStatus.LlmProcessing ||
    status === AppStatus.TtsProcessing;
  const isPlaying = status === AppStatus.Playing;
  const isError = status === AppStatus.Error;
  const isDaemonReady = daemonStatus === DaemonStatus.Ready && daemonConnected;

  return {
    appState,
    status,
    recordingState,
    processingState,
    workMode,
    recordingMode,
    daemonStatus,
    daemonConnected,
    config,
    messages,
    audioLevel,
    statistics,

    // Computed properties
    isIdle,
    isListening,
    isRecording,
    isProcessing,
    isPlaying,
    isError,
    isDaemonReady,

    // Actions
    refresh,
    setWorkMode,
    setRecordingMode,
  };
}

/**
 * Hook for accessing recording state
 */
export function useRecordingState() {
  const { appState, recordingState, isRecording, isListening } = useAppState();

  return {
    recordingState,
    isRecording,
    isListening,
    audioLevel: recordingState?.audio_level_db ?? -Infinity,
    duration: recordingState?.duration_seconds ?? 0,
    isProcessing: recordingState?.is_processing ?? false,
    recordingMode: appState?.recording_mode ?? RecordingMode.PushToTalk,
  };
}

/**
 * Hook for accessing processing state
 */
export function useProcessingState() {
  const { processingState, isProcessing } = useAppState();

  return {
    processingState,
    isProcessing,
    currentStage: processingState?.current_stage ?? null,
    stageProgress: processingState?.stage_progress ?? 0,
    stageMessage: processingState?.stage_message ?? '',
  };
}

/**
 * Hook for accessing daemon state
 */
export function useDaemonState() {
  const { daemonStatus, daemonConnected, isDaemonReady } = useAppState();

  return {
    daemonStatus,
    daemonConnected,
    isDaemonReady,
  };
}

/**
 * Hook for accessing chat state
 */
export function useChatState() {
  const { messages } = useAppState();
  const [isStreaming, setIsStreaming] = useState(false);

  useEventListenerSubscription<ChatStreamStartedEvent>('chat-stream-started', () => {
    setIsStreaming(true);
  });

  useEventListenerSubscription<ChatStreamEndedEvent>('chat-stream-ended', () => {
    setIsStreaming(false);
  });

  return {
    messages,
    isStreaming,
    messageCount: messages.length,
  };
}

/**
 * Hook for accessing UI state (theme, language)
 */
export function useUIState() {
  const [theme, setTheme] = useState<string>('system');
  const [language, setLanguage] = useState<string>('en');

  useEventListenerSubscription<ThemeChangedEvent>('theme-changed', (event) => {
    setTheme(event.data.theme);
  });

  useEventListenerSubscription<LanguageChangedEvent>('language-changed', (event) => {
    setLanguage(event.data.language);
  });

  return {
    theme,
    language,
    setTheme: async (newTheme: string) => {
      try {
        await invoke('set_theme', { theme: newTheme });
      } catch (error) {
        console.error('[useUIState] Failed to set theme:', error);
      }
    },
    setLanguage: async (newLanguage: string) => {
      try {
        await invoke('set_language', { language: newLanguage });
      } catch (error) {
        console.error('[useUIState] Failed to set language:', error);
      }
    },
  };
}

/**
 * Hook for accessing error state
 */
export function useErrorState() {
  const [errors, setErrors] = useState<Array<{
    id: string;
    message: string;
    timestamp: number;
    recoverable: boolean;
  }>>([]);

  useEventListenerSubscription<ErrorOccurredEvent>('error-occurred', (event) => {
    setErrors((prev) => [...prev, event.data.error]);
  });

  useEventListenerSubscription<ErrorClearedEvent>('error-cleared', (event) => {
    setErrors((prev) => prev.filter((e) => e.id !== event.data.error_id));
  });

  const clearError = useCallback(async (errorId: string) => {
    try {
      await invoke('clear_error', { errorId });
    } catch (error) {
      console.error('[useErrorState] Failed to clear error:', error);
    }
  }, []);

  const clearAllErrors = useCallback(async () => {
    for (const error of errors) {
      await clearError(error.id);
    }
  }, [errors, clearError]);

  return {
    errors,
    hasErrors: errors.length > 0,
    clearError,
    clearAllErrors,
  };
}
