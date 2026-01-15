/**
 * Settings Context Provider
 *
 * Manages global settings state with auto-save functionality
 */

import React, { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { HotkeyConfig } from '../types/hotkey';

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
  /** Update hotkey configuration and auto-save */
  updateHotkey: (hotkey: HotkeyConfig) => void;
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
  const [daemonReady, setDaemonReady] = useState(false);

  // Load config on mount (only after daemon is ready)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');
        if (result.success && result.config) {
          // Ensure push_to_talk_hotkey has default value if not present
          const configWithDefaults = {
            ...result.config,
            push_to_talk_hotkey: result.config.push_to_talk_hotkey || {
              modifiers: ['CmdOrCtrl'],
              key: 'Digit1',
              displayName: '⌘1',
            },
          };
          setConfig(configWithDefaults);
        }
      } catch (error) {
        // Silently ignore errors during daemon initialization
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (!errorMessage.includes('语音服务正在启动中')) {
          console.error('[Settings] Failed to load config:', error);
        }
      }
    };

    // Only load config after daemon is ready
    if (daemonReady) {
      loadConfig();
    }
  }, [daemonReady]);

  // Listen for daemon status events
  useEffect(() => {
    const unlistenPromise = listen<{ status: string; message: string }>('daemon-status', (event) => {
      if (event.payload.status === 'ready') {
        setDaemonReady(true);
      }
    });

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
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

  /**
   * Update hotkey configuration
   */
  const updateHotkey = useCallback(async (hotkey: HotkeyConfig) => {
    setConfig(prev => {
      if (!prev) return prev;

      const newConfig = {
        ...prev,
        push_to_talk_hotkey: hotkey,
      };

      // Trigger auto-save
      debouncedSave(newConfig);

      // Also update hotkey in backend immediately
      invoke('update_hotkey', { hotkeyConfig: hotkey })
        .then((result: unknown) => {
          const res = result as { success: boolean; error?: string };
          if (!res.success) {
            console.error('[Settings] Failed to update hotkey:', res.error);
          }
        })
        .catch((error) => {
          console.error('[Settings] Failed to update hotkey:', error);
        });

      return newConfig;
    });
  }, [debouncedSave]);

  const contextValue: SettingsContextValue = {
    config,
    saveStatus,
    saveError,
    updateConfig,
    updateConfigBatch,
    saveConfig,
    updateHotkey,
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
