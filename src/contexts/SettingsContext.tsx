/**
 * Settings Context Provider
 *
 * Manages global settings state using ConfigStore as single source of truth.
 * Simplified to pure UI layer - all persistence handled by ConfigStore.
 *
 * Architecture Changes:
 * - Uses ConfigStore for all config operations
 * - Removed independent debounced save (handled by ConfigStore)
 * - Subscribes to ConfigStore for reactive updates
 * - Simplified to UI state management only
 */

import React, { createContext, useContext, useCallback, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { HotkeyConfig } from '../types/hotkey';
import { configStore, type SaveStatus } from '@/stores/ConfigStore';

interface SettingsContextValue {
  /** Current configuration */
  config: Record<string, any> | null;
  /** Current save status */
  saveStatus: SaveStatus;
  /** Last save error message */
  saveError: string | null;
  /** Whether config is currently loading */
  loading: boolean;
  /** Update a single config value (auto-save via ConfigStore) */
  updateConfig: (key: string, value: any) => void;
  /** Update multiple config values (auto-save via ConfigStore) */
  updateConfigBatch: (updates: Record<string, any>) => void;
  /** Manually save current config */
  saveConfig: () => Promise<void>;
  /** Update hotkey configuration (auto-save via ConfigStore) */
  updateHotkey: (hotkey: HotkeyConfig) => void;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

/**
 * SettingsProvider component
 *
 * Provides global state management for settings using ConfigStore
 */
export function SettingsProvider({ children }: { children: React.ReactNode }) {
  // Local state for UI updates (synced with ConfigStore via subscription)
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Subscribe to ConfigStore for state updates
  useEffect(() => {
    const unsubscribe = configStore.subscribe((state) => {
      setConfig(state.config ? { ...state.config } : null);
      setSaveStatus(state.saveStatus);
      setSaveError(state.error);
      setLoading(state.loading);
    });

    return unsubscribe;
  }, []);

  // Ensure hotkey default value
  useEffect(() => {
    if (config && !config.push_to_talk_hotkey) {
      configStore.updateConfig({
        push_to_talk_hotkey: {
          modifiers: ['Alt'],
          key: 'Digit3',
          displayName: '⌥3',
        },
      });
    }
  }, [config]);

  /**
   * Update a single config value
   */
  const updateConfig = useCallback((key: string, value: any) => {
    configStore.updateConfig({ [key]: value });
  }, []);

  /**
   * Update multiple config values at once
   */
  const updateConfigBatch = useCallback((updates: Record<string, any>) => {
    configStore.updateConfig(updates);
  }, []);

  /**
   * Manually save current config
   */
  const saveConfig = useCallback(async () => {
    await configStore.saveConfig(true); // immediate save
  }, []);

  /**
   * Update hotkey configuration
   * Special handling: also update backend hotkey immediately
   */
  const updateHotkey = useCallback((hotkey: HotkeyConfig) => {
    // Update config via ConfigStore
    configStore.updateConfig({ push_to_talk_hotkey: hotkey });

    // Also update hotkey in backend immediately (for PTT)
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
  }, []);

  const contextValue: SettingsContextValue = {
    config,
    saveStatus,
    saveError,
    loading,
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
