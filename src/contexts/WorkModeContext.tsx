/**
 * Work Mode Context Provider
 *
 * Manages global state for work mode, provides mode switching and persistence functionality
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { WorkMode, WorkModeConfig, WorkModeChangeEvent } from '@/types/workMode';
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
  /** Set work mode */
  setWorkMode: (mode: WorkMode, source?: WorkModeChangeEvent['source']) => void;
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
      if (saved === 'conversation' || saved === 'text') {
        return saved;
      }
    }
    return DEFAULT_WORK_MODE;
  });

  /**
   * Load work mode from localStorage and config file
   */
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // First read from localStorage (fast loading)
    const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
    if (saved === 'conversation' || saved === 'text') {
      setWorkModeState(saved);
    }

    // Then sync from config file (ensure consistency with backend)
    const syncFromConfig = async () => {
      try {
        const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');
        const configWorkMode = result?.config?.work_mode;
        if (configWorkMode === 'conversation' || configWorkMode === 'text') {
          setWorkModeState(configWorkMode);
          localStorage.setItem(WORK_MODE_STORAGE_KEY, configWorkMode);
        }
      } catch (error) {
        console.error('[WorkMode] Failed to load from config file:', error);
      }
    };

    syncFromConfig();
  }, []);

  /**
   * Set work mode and persist to localStorage and config file
   */
  const setWorkMode = useCallback(async (mode: WorkMode, source: WorkModeChangeEvent['source'] = 'settings') => {
    // Update state
    setWorkModeState(mode);

    // Persist to localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
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
   * Switch to conversation mode
   */
  const switchToConversation = useCallback(() => {
    setWorkMode('conversation', 'api');
  }, [setWorkMode]);

  /**
   * Switch to text input mode
   */
  const switchToText = useCallback(() => {
    setWorkMode('text', 'api');
  }, [setWorkMode]);

  /**
   * Computed property: whether it's conversation mode
   */
  const isConversationMode = workMode === 'conversation';

  /**
   * Computed property: whether it's text input mode
   */
  const isTextInputMode = workMode === 'text';

  const contextValue: WorkModeContextValue = {
    workMode,
    setWorkMode,
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
