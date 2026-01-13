/**
 * Settings Context Provider
 *
 * Manages global settings state with auto-save functionality
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { invoke } from '@tauri-apps/api/core';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

interface SettingsContextValue {
  /** Current configuration */
  config: Record<string, any> | null;
  /** Current save status */
  saveStatus: SaveStatus;
  /** Last save error message */
  saveError: string | null;
  /** Update a single config value and auto-save */
  updateConfig: (key: string, value: any) => void;
  /** Update multiple config values and auto-save */
  updateConfigBatch: (updates: Record<string, any>) => void;
  /** Manually save current config */
  saveConfig: () => Promise<void>;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

/**
 * Debounced save function
 */
const createDebouncedSave = (
  onSave: (config: Record<string, any>) => Promise<void>,
  onStatusChange: (status: SaveStatus, error?: string) => void
) => {
  let timeoutId: NodeJS.Timeout | null = null;

  return (config: Record<string, any>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(async () => {
      onStatusChange('saving');
      try {
        await onSave(config);
        onStatusChange('saved');

        // Reset to idle after 2 seconds
        setTimeout(() => {
          onStatusChange('idle');
        }, 2000);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Save failed';
        onStatusChange('error', errorMessage);
        console.error('[Settings] Auto-save failed:', error);
      }
    }, 500); // 500ms debounce
  };
};

/**
 * SettingsProvider component
 *
 * Provides global state management for settings with auto-save
 */
export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);

  // Load config on mount
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');
        if (result.success && result.config) {
          setConfig(result.config);
        }
      } catch (error) {
        console.error('[Settings] Failed to load config:', error);
      }
    };

    loadConfig();
  }, []);

  // Create debounced save function
  const debouncedSave = useMemo(() => {
    const saveFunction = async (newConfig: Record<string, any>) => {
      const result = await invoke<{ success: boolean; error?: string }>('save_config', {
        config: newConfig,
      });

      if (!result.success) {
        throw new Error(result.error || 'Save failed');
      }
    };

    return createDebouncedSave(saveFunction, setSaveError);
  }, []);

  /**
   * Update a single config value
   */
  const updateConfig = useCallback((key: string, value: any) => {
    setConfig(prev => {
      if (!prev) return prev;

      const newConfig = {
        ...prev,
        [key]: value,
      };

      // Trigger auto-save
      debouncedSave(newConfig);

      return newConfig;
    });
  }, [debouncedSave]);

  /**
   * Update multiple config values at once
   */
  const updateConfigBatch = useCallback((updates: Record<string, any>) => {
    setConfig(prev => {
      if (!prev) return prev;

      const newConfig = {
        ...prev,
        ...updates,
      };

      // Trigger auto-save
      debouncedSave(newConfig);

      return newConfig;
    });
  }, [debouncedSave]);

  /**
   * Manually save current config
   */
  const saveConfig = useCallback(async () => {
    if (!config) {
      throw new Error('No config to save');
    }

    setSaveStatus('saving');
    setSaveError(null);

    try {
      const result = await invoke<{ success: boolean; error?: string }>('save_config', {
        config: config,
      });

      if (result.success) {
        setSaveStatus('saved');
        setTimeout(() => setSaveStatus('idle'), 2000);
      } else {
        throw new Error(result.error || 'Save failed');
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Save failed';
      setSaveStatus('error');
      setSaveError(errorMessage);
      console.error('[Settings] Manual save failed:', error);
      throw error;
    }
  }, [config]);

  const contextValue: SettingsContextValue = {
    config,
    saveStatus,
    saveError,
    updateConfig,
    updateConfigBatch,
    saveConfig,
  };

  return (
    <SettingsContext.Provider value={contextValue}>
      {children}
    </SettingsContext.Provider>
  );
}

/**
 * useSettings Hook
 *
 * Used to access settings state and methods in components
 *
 * @example
 * ```tsx
 * const { config, updateConfig, saveStatus } = useSettings();
 * ```
 */
export const useSettings = (): SettingsContextValue => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within SettingsProvider');
  }
  return context;
};
