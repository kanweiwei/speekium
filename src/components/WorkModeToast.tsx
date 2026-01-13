/**
 * WorkModeToast 组件
 * 工作模式切换通知组件
 *
 * 屏幕中央顶部显示，简洁风格
 */

import { useEffect, useState } from 'react';
import { MessageCircle, Type, X } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { cn } from '@/lib/utils';
import type { WorkMode } from '@/types/workMode';

interface WorkModeToastProps {
  /** 工作模式 */
  mode: WorkMode;
  /** 自定义消息 */
  message?: string;
  /** 显示时长 (毫秒) */
  duration?: number;
  /** 关闭回调 */
  onClose?: () => void;
}

/**
 * WorkModeToast 组件 - 简洁版
 *
 * @example
 * ```tsx
 * <WorkModeToast
 *   mode="conversation"
 *   duration={1500}
 *   onClose={() => setShowToast(false)}
 * />
 * ```
 */
export function WorkModeToast({
  mode,
  message,
  duration = 1500,
  onClose,
}: WorkModeToastProps) {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(() => {
        onClose?.();
      }, 150);
    }, duration);

    return () => clearTimeout(timer);
  }, [duration, onClose]);

  /**
   * 获取 Toast 配置
   */
  const getToastConfig = () => {
    // 对话模式
    if (mode === 'conversation') {
      return {
        icon: MessageCircle,
        text: message || t('settings.workModes.conversation') || 'Conversation Mode',
        bgColor: 'bg-blue-50 dark:bg-blue-950/50',
        textColor: 'text-blue-700 dark:text-blue-300',
        borderColor: 'border-blue-200 dark:border-blue-800',
      };
    }

    // 文字输入模式
    return {
      icon: Type,
      text: message || t('settings.workModes.text') || 'Text Input Mode',
      bgColor: 'bg-green-50 dark:bg-green-950/50',
      textColor: 'text-green-700 dark:text-green-300',
      borderColor: 'border-green-200 dark:border-green-800',
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
        "min-w-[200px] max-w-[300px] w-auto",

        // 背景
        config.bgColor,

        // 边框和阴影
        "border rounded-lg shadow-lg",
        config.borderColor,

        // 内边距和布局
        "px-4 py-2 flex items-center gap-2",

        // 动画
        "animate-in fade-in slide-in-from-top-2",
        "duration-150 ease-out",
        "[&_svg]:h-4 [&_svg]:w-4"
      )}
    >
      {/* 图标 */}
      <Icon className={cn("flex-shrink-0", config.textColor)} aria-hidden="true" />

      {/* 文本 */}
      <p className={cn("text-sm font-medium", config.textColor)}>
        {config.text}
      </p>

      {/* 关闭按钮 */}
      <button
        onClick={() => {
          setIsVisible(false);
          setTimeout(() => onClose?.(), 150);
        }}
        className="flex-shrink-0 text-muted-foreground hover:text-foreground
                   transition-colors rounded p-0.5 -mr-1 -my-0.5 ml-auto"
        aria-label="Close"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
