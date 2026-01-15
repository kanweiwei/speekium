/**
 * SystemToast 组件
 * 系统通知组件 - P2-8
 *
 * 支持多种通知类型：
 * - 工作模式切换
 * - 录音模式切换
 * - 操作停止
 * - 错误提示
 * - 自定义消息
 */

import { useEffect, useState } from 'react';
import {
  MessageCircle,
  Type,
  Mic,
  StopCircle,
  AlertCircle,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useTranslation } from '@/i18n';
import { cn } from '@/lib/utils';
import type { WorkMode } from '@/types/workMode';

export type ToastType =
  | 'work-mode-conversation'
  | 'work-mode-text-input'
  | 'recording-mode-push-to-talk'
  | 'recording-mode-continuous'
  | 'operation-stopped'
  | 'error'
  | 'custom';

interface SystemToastProps {
  /** Toast 类型 */
  type: ToastType;
  /** 自定义消息 (优先使用) */
  message?: string;
  /** 工作模式 (用于 work-mode 类型) */
  workMode?: WorkMode;
  /** 显示时长 (毫秒)，0 表示不自动关闭 */
  duration?: number;
  /** 关闭回调 */
  onClose?: () => void;
}

/**
 * Toast 类型配置
 */
interface ToastConfig {
  icon: LucideIcon;
  text: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}

/**
 * SystemToast 组件
 *
 * @example
 * ```tsx
 * <SystemToast
 *   type="work-mode-conversation"
 *   workMode="conversation"
 *   duration={1500}
 *   onClose={() => setShowToast(false)}
 * />
 * ```
 */
export function SystemToast({
  type,
  message,
  workMode = 'conversation',
  duration = 2000,
  onClose,
}: SystemToastProps) {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    // duration = 0 表示不自动关闭
    if (duration === 0) return;

    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => {
        onClose?.();
      }, 150);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  /**
   * 获取 Toast 配置 - P2-8: 支持多种类型
   */
  const getToastConfig = (): ToastConfig => {
    // 工作模式 - 对话模式
    if (type === 'work-mode-conversation' || (type === 'custom' && workMode === 'conversation' && !message)) {
      return {
        icon: MessageCircle,
        text: message || t('settings.workModes.conversation') || 'Conversation Mode',
        bgColor: 'bg-blue-50 dark:bg-blue-950/50',
        textColor: 'text-blue-700 dark:text-blue-300',
        borderColor: 'border-blue-200 dark:border-blue-800',
      };
    }

    // 工作模式 - 文字输入模式
    if (type === 'work-mode-text-input' || (type === 'custom' && workMode === 'text-input' && !message)) {
      return {
        icon: Type,
        text: message || t('settings.workModes.text') || 'Text Input Mode',
        bgColor: 'bg-green-50 dark:bg-green-950/50',
        textColor: 'text-green-700 dark:text-green-300',
        borderColor: 'border-green-200 dark:border-green-800',
      };
    }

    // 录音模式 - 按键录音
    if (type === 'recording-mode-push-to-talk') {
      return {
        icon: Mic,
        text: message || '已切换到按键录音模式',
        bgColor: 'bg-purple-50 dark:bg-purple-950/50',
        textColor: 'text-purple-700 dark:text-purple-300',
        borderColor: 'border-purple-200 dark:border-purple-800',
      };
    }

    // 录音模式 - 自动检测
    if (type === 'recording-mode-continuous') {
      return {
        icon: Mic,
        text: message || '已切换到自动检测模式',
        bgColor: 'bg-cyan-50 dark:bg-cyan-950/50',
        textColor: 'text-cyan-700 dark:text-cyan-300',
        borderColor: 'border-cyan-200 dark:border-cyan-800',
      };
    }

    // 操作停止
    if (type === 'operation-stopped') {
      return {
        icon: StopCircle,
        text: message || '已停止当前操作',
        bgColor: 'bg-gray-50 dark:bg-gray-950/50',
        textColor: 'text-gray-700 dark:text-gray-300',
        borderColor: 'border-gray-200 dark:border-gray-800',
      };
    }

    // 错误提示
    if (type === 'error') {
      return {
        icon: AlertCircle,
        text: message || '操作失败',
        bgColor: 'bg-red-50 dark:bg-red-950/50',
        textColor: 'text-red-700 dark:text-red-300',
        borderColor: 'border-red-200 dark:border-red-800',
      };
    }

    // 自定义消息 (默认使用工作模式的样式)
    return {
      icon: workMode === 'conversation' ? MessageCircle : Type,
      text: message || 'Notification',
      bgColor: workMode === 'conversation'
        ? 'bg-blue-50 dark:bg-blue-950/50'
        : 'bg-green-50 dark:bg-green-950/50',
      textColor: workMode === 'conversation'
        ? 'text-blue-700 dark:text-blue-300'
        : 'text-green-700 dark:text-green-300',
      borderColor: workMode === 'conversation'
        ? 'border-blue-200 dark:border-blue-800'
        : 'border-green-200 dark:border-green-800',
    };
  };

  const config = getToastConfig();
  const Icon = config.icon;

  if (!isVisible) return null;

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        // 定位
        "fixed top-6 left-1/2 -translate-x-1/2 z-[9999]",

        // 尺寸
        "min-w-[200px] max-w-[400px] w-auto",

        // 背景
        config.bgColor,

        // 边框和阴影
        "border rounded-lg shadow-lg",
        config.borderColor,

        // 内边距和布局
        "px-4 py-3 flex items-center gap-2.5",

        // 动画
        "animate-in fade-in slide-in-from-top-2",
        "duration-150 ease-out",
        "[&_svg]:h-4 [&_svg]:w-4"
      )}
    >
      {/* 图标 */}
      <Icon className={cn("flex-shrink-0", config.textColor)} aria-hidden="true" />

      {/* 文本 */}
      <p className={cn("text-sm font-medium flex-1", config.textColor)}>
        {config.text}
      </p>

      {/* 关闭按钮 */}
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onClose?.(), 150);
        }}
        className="flex-shrink-0 text-muted-foreground hover:text-foreground
                   transition-colors rounded p-0.5 -mr-1 -my-0.5"
        aria-label="Close"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
