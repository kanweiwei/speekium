/**
 * Work Mode Context Provider
 *
 * Manages global state for work mode, provides mode switching and persistence functionality
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { WorkMode, WorkModeChangeEvent } from '@/types/workMode';
import {
  DEFAULT_WORK_MODE,
  WORK_MODE_STORAGE_KEY,
} from '@/types/workMode';

/**
 * WorkModeContext interface definition
 */
interface WorkModeContextValue {
  /** Current work mode */
  workMode: WorkMode;
  /** Set work mode (persist to backend) */
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
 * Provides global state management for work mode
 */
export function WorkModeProvider({ children }: { children: React.ReactNode }) {
  const [workMode, setWorkModeState] = useState<WorkMode>(() => {
    // Read saved mode from localStorage, use default value if not exists
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
      if (saved === 'conversation' || saved === 'text-input') {
        return saved;
      }
    }
    return DEFAULT_WORK_MODE;
  });

  /**
   * Load work mode from localStorage and config file
   * Also poll for changes from backend (e.g., hotkey shortcuts)
   */
  useEffect(() => {
    if (typeof window === 'undefined') return;

    let lastKnownMode: WorkMode | null = null;

    // First read from localStorage (fast loading)
    const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
    if (saved === 'conversation' || saved === 'text-input') {
      setWorkModeState(saved);
      lastKnownMode = saved;
    }

    // Sync from config file and poll for changes
    const syncFromConfig = async () => {
      try {
        // Use lightweight get_work_mode command (reads from Rust state, no daemon call)
        const currentMode = await invoke<string>('get_work_mode');

        if (currentMode === 'conversation' || currentMode === 'text-input') {
          // Only update if mode changed (avoid unnecessary re-renders)
          if (currentMode !== lastKnownMode) {
            console.log('[WorkMode] Mode changed (detected via polling):', currentMode);
            setWorkModeState(currentMode);
            localStorage.setItem(WORK_MODE_STORAGE_KEY, currentMode);
            lastKnownMode = currentMode;

            // Save to config file (persist the change)
            try {
              const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');
              if (result.success && result.config) {
                const updatedConfig = {
                  ...result.config,
                  work_mode: currentMode,
                };
                await invoke<{ success: boolean; error?: string }>('save_config', {
                  config: updatedConfig,
                });
              }
            } catch (saveError) {
              console.error('[WorkMode] Failed to save config after detecting change:', saveError);
            }
          }
        }
      } catch (error) {
        console.error('[WorkMode] Failed to get work mode:', error);
      }
    };

    // Initial sync
    syncFromConfig();

    // Poll every 500ms for config changes (lightweight operation)
    const intervalId = setInterval(syncFromConfig, 500);

    return () => {
      clearInterval(intervalId);
    };
  }, []);

  /**
   * Set work mode and persist to localStorage and config file
   */
  const setWorkMode = useCallback(async (mode: WorkMode, _source: WorkModeChangeEvent['source'] = 'settings') => {
    // Update state
    setWorkModeState(mode);

    // Persist to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
    }

    // CRITICAL: Update backend WORK_MODE state immediately
    // This ensures PTT shortcut and other backend features use the correct mode
    try {
      await invoke('set_work_mode', { mode });
      console.log('[WorkMode] Backend state updated to:', mode);
    } catch (error) {
      console.error('[WorkMode] Failed to update backend state:', error);
    }

    // Save to config file (Python daemon reads from here)
    try {
      // First load complete configuration
      const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');

      if (result.success && result.config) {
        // Update work_mode field
        const updatedConfig = {
          ...result.config,
          work_mode: mode,
        };

        // Save complete configuration and check return value
        const saveResult = await invoke<{ success: boolean; error?: string }>('save_config', {
          config: updatedConfig,
        });

        if (saveResult.success) {
          // Configuration saved successfully
        } else {
          console.error(`[WorkMode] Failed to save configuration: ${saveResult.error}`);
        }
      } else {
        console.error('[WorkMode] Failed to load configuration:', result);
      }
    } catch (error) {
      console.error('[WorkMode] Failed to save configuration:', error);
    }
  }, [workMode]);

  /**
   * Set work mode locally without calling backend
   * Used when the backend has already saved the config (e.g., hotkey events)
   */
  const setWorkModeLocal = useCallback((mode: WorkMode) => {
    // Update state
    setWorkModeState(mode);

    // Persist to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
    }
    // Note: No backend call - backend already saved the config
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
