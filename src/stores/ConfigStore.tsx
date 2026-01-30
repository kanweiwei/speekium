/**
 * ConfigStore - 单一配置管理源
 *
 * 作为整个应用的配置管理核心，提供:
 * - 统一的配置状态管理
 * - 防抖保存机制
 * - 变更检测 (避免无效保存)
 * - 事件订阅系统
 * - 类型安全的配置操作
 *
 * @module stores/ConfigStore
 */

import { invoke } from '@tauri-apps/api/core';
import type { WorkMode } from '@/types/workMode';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * 配置保存状态
 */
export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

/**
 * 配置状态接口
 */
export interface ConfigStoreState {
  /** 当前配置对象 */
  config: Record<string, any> | null;
  /** 加载状态 */
  loading: boolean;
  /** 保存状态 */
  saveStatus: SaveStatus;
  /** 错误信息 */
  error: string | null;
  /** 上次保存的配置 (用于变更检测) */
  lastSaved: Record<string, any> | null;
  /** 是否有待保存的更改 */
  hasPendingChanges: boolean;
}

/**
 * 配置监听器类型
 */
export type ConfigListener = (state: ConfigStoreState) => void;

/**
 * 取消订阅函数类型
 */
export type Unsubscribe = () => void;

/**
 * 配置存储操作接口
 */
export interface ConfigStoreAPI {
  // 状态查询
  getState: () => ConfigStoreState;
  getConfig: () => Record<string, any> | null;
  getWorkMode: () => WorkMode;
  isLoading: () => boolean;
  hasError: () => boolean;
  hasPendingChanges: () => boolean;

  // 配置操作
  loadConfig: () => Promise<void>;
  reloadConfig: () => Promise<void>;
  saveConfig: (immediate?: boolean) => Promise<void>;
  updateConfig: (updates: Record<string, any>) => void;
  setWorkMode: (mode: WorkMode) => Promise<void>;

  // 订阅管理
  subscribe: (listener: ConfigListener) => Unsubscribe;

  // 状态重置
  reset: () => void;
}

// ============================================================================
// Constants
// ============================================================================

/** 默认防抖延迟 (毫秒) */
const DEFAULT_DEBOUNCE_MS = 500;

/** LocalStorage 工作模式键 */
const WORK_MODE_STORAGE_KEY = 'speekium-work-mode';

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * 深度比较两个对象是否相等
 * 用于检测配置是否真正发生变化
 */
function deepEqual(a: any, b: any): boolean {
  if (a === b) return true;
  if (a == null || b == null) return false;
  if (typeof a !== typeof b) return false;

  if (typeof a !== 'object') return false;

  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }

  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;

  for (const key of keysA) {
    if (!keysB.includes(key)) return false;
    if (!deepEqual(a[key], b[key])) return false;
  }
  return true;
}

// ============================================================================
// ConfigStore Implementation
// ============================================================================

/**
 * ConfigStore 内部状态
 */
let state: ConfigStoreState = {
  config: null,
  loading: false,
  saveStatus: 'idle' as SaveStatus,
  error: null,
  lastSaved: null,
  hasPendingChanges: false,
};

/**
 * 监听器集合
 */
const listeners: Set<ConfigListener> = new Set();

/**
 * 防抖保存定时器
 */
let saveTimeout: NodeJS.Timeout | null = null;

/**
 * 正在保存标志 (防止并发保存)
 */
let isSaving = false;

/**
 * 通知所有监听器
 */
function notifyListeners(): void {
  listeners.forEach(listener => {
    try {
      listener({ ...state });
    } catch (error) {
      console.error('[ConfigStore] Listener error:', error);
    }
  });
}

/**
 * 更新状态并通知监听器
 */
function setState(partial: Partial<ConfigStoreState>): void {
  const prevState = { ...state };
  state = { ...state, ...partial };

  // 检测是否有待保存的更改
  if (partial.config || partial.lastSaved !== undefined) {
    state.hasPendingChanges = !deepEqual(state.config, state.lastSaved);
  }

  // 只有状态真正变化时才通知
  if (!deepEqual(prevState, state)) {
    notifyListeners();
  }
}

/**
 * 执行保存操作 (内部实现)
 */
async function performSave(): Promise<{ success: boolean; error?: string }> {
  if (isSaving) {
    console.log('[ConfigStore] Save already in progress, skipping');
    return { success: true }; // 返回成功避免重复错误
  }

  if (!state.config) {
    return { success: false, error: 'No config to save' };
  }

  // 变更检测: 如果配置与上次保存的一致，跳过
  if (deepEqual(state.config, state.lastSaved)) {
    console.log('[ConfigStore] No changes detected, skipping save');
    return { success: true };
  }

  isSaving = true;
  setState({ saveStatus: 'saving' });

  try {
    console.log('[ConfigStore] Saving config...', {
      keys: Object.keys(state.config),
      hasChanges: state.hasPendingChanges,
    });

    const result = await invoke<{ success: boolean; error?: string }>('save_config', {
      config: state.config,
    });

    if (result.success) {
      setState({
        saveStatus: 'saved',
        lastSaved: JSON.parse(JSON.stringify(state.config)), // 深拷贝
        error: null,
      });

      // 2秒后重置保存状态
      setTimeout(() => {
        if (state.saveStatus === 'saved') {
          setState({ saveStatus: 'idle' });
        }
      }, 2000);

      console.log('[ConfigStore] Config saved successfully');
      return { success: true };
    } else {
      const error = result.error || 'Save failed';
      setState({
        saveStatus: 'error',
        error,
      });
      console.error('[ConfigStore] Save failed:', error);
      return { success: false, error };
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    setState({
      saveStatus: 'error',
      error: errorMessage,
    });
    console.error('[ConfigStore] Save error:', error);
    return { success: false, error: errorMessage };
  } finally {
    isSaving = false;
  }
}

/**
 * 防抖保存 (内部实现)
 */
function debouncedSave(): void {
  if (saveTimeout) {
    clearTimeout(saveTimeout);
  }

  saveTimeout = setTimeout(async () => {
    await performSave();
  }, DEFAULT_DEBOUNCE_MS);
}

// ============================================================================
// ConfigStore API
// ============================================================================

/**
 * 获取当前状态快照
 */
function getState(): ConfigStoreState {
  return { ...state };
}

/**
 * 获取当前配置
 */
function getConfig(): Record<string, any> | null {
  return state.config ? { ...state.config } : null;
}

/**
 * 获取当前工作模式
 */
function getWorkMode(): WorkMode {
  const mode = state.config?.work_mode;
  return (mode === 'conversation' || mode === 'text-input') ? mode : 'conversation';
}

/**
 * 是否正在加载
 */
function isLoading(): boolean {
  return state.loading;
}

/**
 * 是否有错误
 */
function hasError(): boolean {
  return state.error !== null;
}

/**
 * 是否有待保存的更改
 */
function hasPendingChanges(): boolean {
  return state.hasPendingChanges;
}

/**
 * 加载配置
 */
async function loadConfig(): Promise<void> {
  if (state.loading) {
    console.log('[ConfigStore] Already loading, skipping');
    return;
  }

  setState({ loading: true, error: null });

  try {
    console.log('[ConfigStore] Loading config...');
    const result = await invoke<{ success: boolean; config?: Record<string, any>; error?: string }>('load_config');

    if (result.success && result.config) {
      setState({
        config: result.config,
        lastSaved: JSON.parse(JSON.stringify(result.config)), // 深拷贝
        loading: false,
        hasPendingChanges: false,
      });
      console.log('[ConfigStore] Config loaded successfully', {
        keys: Object.keys(result.config),
        workMode: result.config.work_mode,
      });
    } else {
      throw new Error(result.error || 'Load failed');
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    setState({
      loading: false,
      error: errorMessage,
    });
    console.error('[ConfigStore] Load error:', error);
    throw error;
  }
}

/**
 * 重新加载配置
 */
async function reloadConfig(): Promise<void> {
  console.log('[ConfigStore] Reloading config...');
  await loadConfig();
}

/**
 * 保存配置
 * @param immediate - 是否立即保存 (跳过防抖)
 */
async function saveConfig(immediate = false): Promise<void> {
  if (immediate) {
    // 取消防抖定时器
    if (saveTimeout) {
      clearTimeout(saveTimeout);
      saveTimeout = null;
    }
    await performSave();
  } else {
    debouncedSave();
  }
}

/**
 * 更新配置 (触发防抖保存)
 * @param updates - 要更新的配置字段
 */
function updateConfig(updates: Record<string, any>): void {
  if (!state.config) {
    console.warn('[ConfigStore] Cannot update: no config loaded');
    return;
  }

  const newConfig = {
    ...state.config,
    ...updates,
  };

  setState({ config: newConfig });

  // 触发防抖保存
  debouncedSave();
}

/**
 * 设置工作模式
 * @param mode - 工作模式
 */
async function setWorkMode(mode: WorkMode): Promise<void> {
  console.log('[ConfigStore] Setting work mode:', mode);

  // 1. 更新配置
  updateConfig({ work_mode: mode });

  // 2. 更新 localStorage (快速加载用)
  if (typeof window !== 'undefined') {
    localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
  }

  // 3. 立即更新后端状态 (PTT 快捷键等需要)
  try {
    await invoke('set_work_mode', { mode });
    console.log('[ConfigStore] Backend WORK_MODE updated to:', mode);
  } catch (error) {
    console.error('[ConfigStore] Failed to update backend WORK_MODE:', error);
  }

  // 4. 触发防抖保存配置
  await saveConfig(true); // 立即保存工作模式变更
}

/**
 * 订阅配置变更
 * @param listener - 监听器函数
 * @returns 取消订阅函数
 */
function subscribe(listener: ConfigListener): Unsubscribe {
  listeners.add(listener);

  // 立即调用一次，提供当前状态
  try {
    listener({ ...state });
  } catch (error) {
    console.error('[ConfigStore] Initial listener error:', error);
  }

  // 返回取消订阅函数
  return () => {
    listeners.delete(listener);
  };
}

/**
 * 重置状态 (用于测试或登出)
 */
function reset(): void {
  // 取消防抖定时器
  if (saveTimeout) {
    clearTimeout(saveTimeout);
    saveTimeout = null;
  }

  state = {
    config: null,
    loading: false,
    saveStatus: 'idle',
    error: null,
    lastSaved: null,
    hasPendingChanges: false,
  };

  notifyListeners();
  console.log('[ConfigStore] State reset');
}

// ============================================================================
// Export Store API
// ============================================================================

/**
 * ConfigStore 单例
 *
 * 使用示例:
 * ```tsx
 * import { configStore } from '@/stores/ConfigStore';
 *
 * // 读取配置
 * const config = configStore.getConfig();
 *
 * // 更新配置 (自动防抖保存)
 * configStore.updateConfig({ theme: 'dark' });
 *
 * // 订阅变更
 * const unsubscribe = configStore.subscribe((state) => {
 *   console.log('Config changed:', state.config);
 * });
 * ```
 */
export const configStore: ConfigStoreAPI = {
  getState,
  getConfig,
  getWorkMode,
  isLoading,
  hasError,
  hasPendingChanges,
  loadConfig,
  reloadConfig,
  saveConfig,
  updateConfig,
  setWorkMode,
  subscribe,
  reset,
};

// ============================================================================
// React Provider Integration
// ============================================================================

import { useEffect, useState, useCallback } from 'react';

/**
 * ConfigStoreProvider 组件
 *
 * 为应用提供 ConfigStore 初始化和上下文
 * 确保配置在应用启动时正确加载
 */
export function ConfigStoreProvider({ children }: { children: React.ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // 标记为已初始化
    // 实际配置加载由 ConfigStoreInitializer 在 main.tsx 中处理
    setIsInitialized(true);

    return () => {
      // 清理: 取消所有待处理的保存
      if (saveTimeout) {
        clearTimeout(saveTimeout);
        saveTimeout = null;
      }
    };
  }, []);

  if (!isInitialized) {
    return null;
  }

  return <>{children}</>;
}

// ============================================================================
// React Hooks Integration
// ============================================================================

/**
 * useConfig Hook - 订问配置存储
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { config, updateConfig, saveStatus } = useConfig();
 *
 *   return (
 *     <button onClick={() => updateConfig({ theme: 'dark' })}>
 *       Set Dark Mode
 *     </button>
 *   );
 * }
 * ```
 */
export function useConfig() {
  const [, forceUpdate] = useState({});

  // 订阅配置变更
  useEffect(() => {
    const unsubscribe = configStore.subscribe(() => {
      // 触发重新渲染
      forceUpdate({});
    });

    return unsubscribe;
  }, []);

  return {
    /** 当前配置 */
    config: configStore.getConfig(),
    /** 当前工作模式 */
    workMode: configStore.getWorkMode(),
    /** 加载状态 */
    loading: configStore.isLoading(),
    /** 保存状态 */
    saveStatus: state.saveStatus,
    /** 错误信息 */
    error: state.error,
    /** 是否有待保存的更改 */
    hasPendingChanges: configStore.hasPendingChanges(),
    /** 更新配置 */
    updateConfig: useCallback(configStore.updateConfig, []),
    /** 设置工作模式 */
    setWorkMode: useCallback(configStore.setWorkMode, []),
    /** 保存配置 */
    saveConfig: useCallback(configStore.saveConfig, []),
    /** 重新加载配置 */
    reloadConfig: useCallback(configStore.reloadConfig, []),
  };
}

/**
 * useConfigValue Hook - 订阅特定配置值
 *
 * @param key - 配置键名
 * @returns [value, setValue] 类似 useState 的返回值
 *
 * @example
 * ```tsx
 * function ThemeToggle() {
 *   const [theme, setTheme] = useConfigValue('theme');
 *
 *   return (
 *     <button onClick={() => setTheme('dark')}>
 *       Current: {theme}
 *     </button>
 *   );
 * }
 * ```
 */
export function useConfigValue<T = any>(key: string): [T | undefined, (value: T) => void] {
  const [value, setValue] = useState<T | undefined>(() => {
    const config = configStore.getConfig();
    return config?.[key];
  });

  useEffect(() => {
    const unsubscribe = configStore.subscribe((state) => {
      const newValue = state.config?.[key];
      if (newValue !== value) {
        setValue(newValue);
      }
    });

    return unsubscribe;
  }, [key]);

  const updateValue = useCallback((newValue: T) => {
    configStore.updateConfig({ [key]: newValue });
  }, [key]);

  return [value, updateValue];
}
