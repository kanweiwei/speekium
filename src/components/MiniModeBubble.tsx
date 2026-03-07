import { Mic, MicOff, Loader2, GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from '../types/workMode';
import { useState, useRef, useEffect } from 'react';

interface MiniModeSettings {
  position: { x: number; y: number };
  opacity: number;
  color: string;
}

interface MiniModeBubbleProps {
  isRecording?: boolean;
  isProcessing?: boolean;
  isSpeaking?: boolean;
  workMode?: WorkMode;
  onClick?: () => void;
  settings?: MiniModeSettings;
  onSettingsChange?: (settings: Partial<MiniModeSettings>) => void;
}

// Color options
const COLOR_OPTIONS = [
  { id: 'purple', gradient: 'from-violet-500 to-indigo-600', shadow: 'rgba(139, 92, 246, 0.4)' },
  { id: 'blue', gradient: 'from-blue-500 to-cyan-600', shadow: 'rgba(59, 130, 246, 0.4)' },
  { id: 'green', gradient: 'from-green-500 to-emerald-600', shadow: 'rgba(34, 197, 94, 0.4)' },
  { id: 'gray', gradient: 'from-gray-500 to-slate-600', shadow: 'rgba(100, 116, 139, 0.4)' },
];

function getColorStyle(colorId: string) {
  const color = COLOR_OPTIONS.find(c => c.id === colorId) || COLOR_OPTIONS[0];
  return color;
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
  settings = { position: { x: 20, y: 200 }, opacity: 100, color: 'purple' },
  onSettingsChange
}: MiniModeBubbleProps) {
  const { t } = useTranslation();
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const bubbleRef = useRef<HTMLDivElement>(null);

  const colorStyle = getColorStyle(settings.color);
  const opacity = settings.opacity / 100;

  // Handle drag start
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    if (bubbleRef.current) {
      const rect = bubbleRef.current.getBoundingClientRect();
      setDragOffset({
        x: e.clientX - rect.left - rect.width / 2,
        y: e.clientY - rect.top - rect.height / 2
      });
    }
  };

  // Handle drag move
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (onSettingsChange) {
        onSettingsChange({
          position: {
            x: Math.max(0, Math.min(window.innerWidth - 80, e.clientX - dragOffset.x)),
            y: Math.max(0, Math.min(window.innerHeight - 120, e.clientY - dragOffset.y))
          }
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, dragOffset, onSettingsChange]);

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
    <div 
      className={cn("flex flex-col items-center fixed z-50", isDragging && "cursor-grabbing")}
      style={{ 
        left: settings.position.x, 
        top: settings.position.y,
        opacity 
      }}
      ref={bubbleRef}
    >
      {/* 拖拽手柄 */}
      <button
        onMouseDown={handleDragStart}
        className="absolute -top-6 left-1/2 -translate-x-1/2 p-1 rounded bg-background/80 hover:bg-background text-muted-foreground cursor-grab"
        title="拖拽移动"
      >
        <GripVertical className="w-3 h-3" />
      </button>
      
      {/* 悬浮球主体 */}
      <button
        onClick={onClick}
        className={cn(
          "relative w-16 h-16 rounded-full flex items-center justify-center",
          "bg-gradient-to-br shadow-lg",
          colorStyle.gradient,
          "transition-all duration-300 hover:scale-105 active:scale-95",
          "border-2 border-white/20",
          isRecording && "animate-pulse-red"
        )}
        style={isRecording ? {
          boxShadow: '0 0 20px rgba(239, 68, 68, 0.5)'
        } : {
          boxShadow: `0 4px 20px ${colorStyle.shadow}`
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
