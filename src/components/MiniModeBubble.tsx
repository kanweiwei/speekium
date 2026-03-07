import { Mic, MicOff, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from '../types/workMode';

interface MiniModeBubbleProps {
  isRecording?: boolean;
  isProcessing?: boolean;
  isSpeaking?: boolean;
  workMode?: WorkMode;
  onClick?: () => void;
  className?: string;
}

/**
 * MiniModeBubble - 迷你模式悬浮球
 * 
 * 设计规范：
 * - 直径：64px，圆形
 * - 位置：屏幕右侧边缘居中（可拖拽）
 * - 背景：渐变紫 (#8b5cf6 → #6366f1)
 * - 录音中：红色脉冲动画
 */
export function MiniModeBubble({
  isRecording = false,
  isProcessing = false,
  isSpeaking = false,
  workMode = 'conversation',
  onClick,
  className
}: MiniModeBubbleProps) {
  const { t } = useTranslation();

  // 确定显示状态
  const getStatus = () => {
    if (isRecording) return t('app.status.recording');
    if (isProcessing || isSpeaking) return t('app.status.processing');
    return t('app.status.online');
  };

  // 确定状态颜色
  const getStatusColor = () => {
    if (isRecording) return 'text-red-500';
    if (isProcessing || isSpeaking) return 'text-yellow-500';
    return 'text-green-500';
  };

  // 获取模式文字
  const getModeText = () => {
    return workMode === 'conversation' 
      ? t('app.modes.conversation') 
      : t('app.modes.textInput');
  };

  return (
    <div className={cn("flex flex-col items-center", className)}>
      {/* 悬浮球主体 */}
      <button
        onClick={onClick}
        className={cn(
          "relative w-16 h-16 rounded-full flex items-center justify-center",
          "bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg",
          "transition-all duration-300 hover:scale-105 active:scale-95",
          "border-2 border-white/20",
          isRecording && "animate-pulse-red"
        )}
        style={isRecording ? {
          boxShadow: '0 0 20px rgba(239, 68, 68, 0.5)'
        } : {
          boxShadow: '0 4px 20px rgba(139, 92, 246, 0.4)'
        }}
      >
        {/* 录音中红色脉冲 */}
        {isRecording && (
          <span className="absolute inset-0 rounded-full animate-ping bg-red-500/50" />
        )}

        {/* 图标 */}
        <div className="relative z-10">
          {isRecording ? (
            <MicOff className="w-7 h-7 text-white animate-pulse" />
          ) : isProcessing || isSpeaking ? (
            <Loader2 className="w-7 h-7 text-white animate-spin" />
          ) : (
            <Mic className="w-7 h-7 text-white" />
          )}
        </div>
      </button>

      {/* 状态文字 */}
      <div className="mt-2 flex flex-col items-center">
        <span className={cn("text-xs font-medium", getStatusColor())}>
          {getStatus()}
        </span>
        <span className="text-[10px] text-muted-foreground">
          · {getModeText()}
        </span>
      </div>
    </div>
  );
}
