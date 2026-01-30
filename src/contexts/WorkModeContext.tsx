/**
 * Work Mode Context Provider
 *
 * Manages global state for work mode, provides mode switching and persistence functionality.
 * Now uses ConfigStore as the single source of truth for configuration management.
 *
 * Architecture Changes:
 * - Uses ConfigStore for all config operations (no duplicate saves)
 * - Subscribes to ConfigStore for reactive updates (no polling needed)
 * - Keeps localStorage sync for fast initial loading
 * - Simplified save logic (handled by ConfigStore)
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { listen } from '@tauri-apps/api/event';
import type { WorkMode, WorkModeChangeEvent } from '@/types/workMode';
import {
  DEFAULT_WORK_MODE,
  WORK_MODE_STORAGE_KEY,
} from '@/types/workMode';
import { configStore } from '@/stores/ConfigStore';

/**
 * WorkModeContext interface definition
 */
interface WorkModeContextValue {
  /** Current work mode */
  workMode: WorkMode;
  /** Set work mode (persist to backend via ConfigStore) */
  setWorkMode: (mode: WorkMode, source?: WorkModeChangeEvent['source']) => void;
  /** Set work mode locally only (no backend call, used by hotkey events) */
  setWorkModeLocal: (mode: WorkMode) => void;
  /** Switch to conversation mode */
  switchToConversation: () => void;
  /** Switch to text input mode */
  switchToText: () => void;
  /** Whether it's conversation mode */
  isConversationMode: boolean;
  /** Whether it's text input mode */
  isTextInputMode: boolean;
}

/**
 * Create Context
 */
const WorkModeContext = createContext<WorkModeContextValue | undefined>(undefined);

/**
 * WorkModeProvider component
 *
 * Provides global state management for work mode using ConfigStore
 */
export function WorkModeProvider({ children }: { children: React.ReactNode }) {
  // Initialize state from localStorage (fast loading) or default
  const [workMode, setWorkModeState] = useState<WorkMode>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
      if (saved === 'conversation' || saved === 'text-input') {
        return saved;
      }
    }
    return DEFAULT_WORK_MODE;
  });

  /**
   * Subscribe to ConfigStore for work mode changes
   * This replaces the polling mechanism - we get notified when config changes
   */
  useEffect(() => {
    let lastKnownMode: WorkMode | null = workMode;

    // Subscribe to ConfigStore changes
    const unsubscribe = configStore.subscribe((state) => {
      const newMode = state.config?.work_mode;
      if (newMode === 'conversation' || newMode === 'text-input') {
        // Only update if mode actually changed
        if (newMode !== lastKnownMode) {
          console.log('[WorkMode] Mode changed (via ConfigStore):', newMode);
          setWorkModeState(newMode);
          localStorage.setItem(WORK_MODE_STORAGE_KEY, newMode);
          lastKnownMode = newMode;
        }
      }
    });

    // Also listen for ptt-state events from backend (hotkey shortcuts)
    const unlistenPromise = listen<{ work_mode?: WorkMode }>('ptt-state', (event) => {
      const newMode = event.payload.work_mode;
      if (newMode && newMode !== lastKnownMode) {
        console.log('[WorkMode] Mode changed (via PTT event):', newMode);
        setWorkModeState(newMode);
        localStorage.setItem(WORK_MODE_STORAGE_KEY, newMode);
        lastKnownMode = newMode;
      }
    });

    return () => {
      unsubscribe();
      unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

  /**
   * Set work mode and persist via ConfigStore
   * ConfigStore handles:
   * - Updating config state
   * - Updating localStorage
   * - Updating backend WORK_MODE state
   * - Debounced save to config file
   */
  const setWorkMode = useCallback(async (mode: WorkMode, _source: WorkModeChangeEvent['source'] = 'settings') => {
    // Update local state immediately (optimistic update)
    setWorkModeState(mode);

    // Use ConfigStore for all persistence
    try {
      await configStore.setWorkMode(mode);
      console.log('[WorkMode] Mode set via ConfigStore:', mode);
    } catch (error) {
      console.error('[WorkMode] Failed to set work mode:', error);
      // Revert state on error
      setWorkModeState(configStore.getWorkMode());
    }
  }, []);

  /**
   * Set work mode locally without calling backend
   * Used when the backend has already saved the config (e.g., hotkey events)
   * ConfigStore subscription will sync the state
   */
  const setWorkModeLocal = useCallback((mode: WorkMode) => {
    console.log('[WorkMode] Setting mode locally:', mode);
    setWorkModeState(mode);

    // Persist to localStorage for fast loading
    if (typeof window !== 'undefined') {
      localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
    }
    // Note: No backend call - ConfigStore will sync via subscription
  }, []);

  /**
   * Switch to conversation mode
   */
  const switchToConversation = useCallback(() => {
    setWorkMode('conversation', 'api');
  }, [setWorkMode]);

  /**
   * Switch to text input mode
   */
  const switchToText = useCallback(() => {
    setWorkMode('text-input', 'api');
  }, [setWorkMode]);

  /**
   * Computed property: whether it's conversation mode
   */
  const isConversationMode = workMode === 'conversation';

  /**
   * Computed property: whether it's text input mode
   */
  const isTextInputMode = workMode === 'text-input';

  const contextValue: WorkModeContextValue = {
    workMode,
    setWorkMode,
    setWorkModeLocal,
    switchToConversation,
    switchToText,
    isConversationMode,
    isTextInputMode,
  };

  return (
    <WorkModeContext.Provider value={contextValue}>
      {children}
    </WorkModeContext.Provider>
  );
}

/**
 * useWorkMode Hook
 *
 * Used to access work mode state and methods in components
 *
 * @example
 * ```tsx
 * const { workMode, setWorkMode, isConversationMode } = useWorkMode();
 * ```
 */
export const useWorkMode = (): WorkModeContextValue => {
  const context = useContext(WorkModeContext);
  if (!context) {
    throw new Error('useWorkMode must be used within WorkModeProvider');
  }
  return context;
};
