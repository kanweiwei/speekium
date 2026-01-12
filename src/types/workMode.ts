/**
 * 工作模式类型定义
 * Work Mode Type Definitions
 */

/**
 * 工作模式枚举
 * - conversation: 对话模式 (语音 → AI 对话 → TTS 播放)
 * - text: 文字输入模式 (语音 → 直接输入文字到焦点框)
 */
export type WorkMode = 'conversation' | 'text';

/**
 * 工作模式配置接口
 */
export interface WorkModeConfig {
  /** 当前工作模式 */
  currentMode: WorkMode;
  /** 最后修改时间戳 */
  lastModified: number;
}

/**
 * 工作模式切换事件接口
 */
export interface WorkModeChangeEvent {
  /** 新的工作模式 */
  mode: WorkMode;
  /** 事件时间戳 */
  timestamp: number;
  /** 事件来源 */
  source: 'settings' | 'tray' | 'hotkey' | 'api';
}

/**
 * 工作模式显示信息接口
 */
export interface WorkModeDisplayInfo {
  /** 模式标识 */
  mode: WorkMode;
  /** 显示名称 */
  label: string;
  /** 描述信息 */
  description: string;
  /** 图标名称 (Lucide React) */
  icon: 'MessageCircle' | 'Type';
  /** 主题颜色 */
  color: 'blue' | 'green';
}

/**
 * 工作模式元数据映射
 */
export const WORK_MODE_INFO: Record<WorkMode, WorkModeDisplayInfo> = {
  conversation: {
    mode: 'conversation',
    label: 'Conversation Mode',
    description: 'Voice → AI conversation → Text-to-Speech',
    icon: 'MessageCircle',
    color: 'blue',
  },
  text: {
    mode: 'text',
    label: 'Text Input Mode',
    description: 'Voice → Direct text input to focused field',
    icon: 'Type',
    color: 'green',
  },
};

/**
 * 默认工作模式配置
 */
export const DEFAULT_WORK_MODE: WorkMode = 'conversation';

/**
 * LocalStorage 键名
 */
export const WORK_MODE_STORAGE_KEY = 'speekium-work-mode';
