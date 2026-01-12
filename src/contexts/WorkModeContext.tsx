/**
 * 工作模式 Context Provider
 * Work Mode Context Provider
 *
 * 管理工作模式的全局状态，提供模式切换和持久化功能
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import type { WorkMode, WorkModeConfig, WorkModeChangeEvent } from '@/types/workMode';
import {
  DEFAULT_WORK_MODE,
  WORK_MODE_STORAGE_KEY,
} from '@/types/workMode';

/**
 * WorkModeContext 接口定义
 */
interface WorkModeContextValue {
  /** 当前工作模式 */
  workMode: WorkMode;
  /** 设置工作模式 */
  setWorkMode: (mode: WorkMode, source?: WorkModeChangeEvent['source']) => void;
  /** 切换到对话模式 */
  switchToConversation: () => void;
  /** 切换到文字输入模式 */
  switchToText: () => void;
  /** 是否是对话模式 */
  isConversationMode: boolean;
  /** 是否是文字输入模式 */
  isTextInputMode: boolean;
}

/**
 * 创建 Context
 */
const WorkModeContext = createContext<WorkModeContextValue | undefined>(undefined);

/**
 * WorkModeProvider 组件
 *
 * 提供工作模式的全局状态管理
 */
export function WorkModeProvider({ children }: { children: React.ReactNode }) {
  const [workMode, setWorkModeState] = useState<WorkMode>(() => {
    // 从 localStorage 读取保存的模式，如果没有则使用默认值
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
      if (saved === 'conversation' || saved === 'text') {
        return saved;
      }
    }
    return DEFAULT_WORK_MODE;
  });

  /**
   * 从 localStorage 和配置文件加载工作模式
   */
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // 首先从 localStorage 读取（快速加载）
    const saved = localStorage.getItem(WORK_MODE_STORAGE_KEY);
    if (saved === 'conversation' || saved === 'text') {
      setWorkModeState(saved);
    }

    // 然后从配置文件同步（确保与后端一致）
    const syncFromConfig = async () => {
      try {
        const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');
        const configWorkMode = result?.config?.work_mode;
        if (configWorkMode === 'conversation' || configWorkMode === 'text') {
          setWorkModeState(configWorkMode);
          localStorage.setItem(WORK_MODE_STORAGE_KEY, configWorkMode);
        }
      } catch (error) {
        console.error('[WorkMode] 从配置文件加载失败:', error);
      }
    };

    syncFromConfig();
  }, []);

  /**
   * 设置工作模式并持久化到 localStorage 和配置文件
   */
  const setWorkMode = useCallback(async (mode: WorkMode, source: WorkModeChangeEvent['source'] = 'settings') => {
    // 更新状态
    setWorkModeState(mode);

    // 持久化到 localStorage
    if (typeof window !== 'undefined') {
      localStorage.setItem(WORK_MODE_STORAGE_KEY, mode);
    }

    // 保存到配置文件（Python daemon 从这里读取）
    try {
      // 先加载完整配置
      const result = await invoke<{ success: boolean; config?: Record<string, any> }>('load_config');

      if (result.success && result.config) {
        // 更新 work_mode 字段
        const updatedConfig = {
          ...result.config,
          work_mode: mode,
        };

        // 保存完整配置并检查返回值
        const saveResult = await invoke<{ success: boolean; error?: string }>('save_config', {
          config: updatedConfig,
        });

        if (saveResult.success) {
          // 配置保存成功
        } else {
          console.error(`[WorkMode] ❌ 保存配置失败: ${saveResult.error}`);
        }
      } else {
        console.error('[WorkMode] 加载配置失败:', result);
      }
    } catch (error) {
      console.error('[WorkMode] 保存配置失败:', error);
    }
  }, [workMode]);

  /**
   * 切换到对话模式
   */
  const switchToConversation = useCallback(() => {
    setWorkMode('conversation', 'api');
  }, [setWorkMode]);

  /**
   * 切换到文字输入模式
   */
  const switchToText = useCallback(() => {
    setWorkMode('text', 'api');
  }, [setWorkMode]);

  /**
   * 计算属性：是否是对话模式
   */
  const isConversationMode = workMode === 'conversation';

  /**
   * 计算属性：是否是文字输入模式
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
 * 用于在组件中访问工作模式状态和方法
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
