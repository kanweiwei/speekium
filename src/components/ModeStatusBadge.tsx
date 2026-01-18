import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import { MessageCircle, Type, Mic, Waves } from 'lucide-react';
import type { WorkMode } from '@/types/workMode';

interface ModeStatusBadgeProps {
  workMode: WorkMode;
  recordMode: 'push-to-talk' | 'continuous';
  onWorkModeClick?: () => void;
  onRecordModeClick?: () => void;
  className?: string;
}

export function ModeStatusBadge({
  workMode,
  recordMode,
  onWorkModeClick,
  onRecordModeClick,
  className,
}: ModeStatusBadgeProps) {
  const { t } = useTranslation();

  const workModeConfig = {
    conversation: {
      label: t('modeStatus.workMode.conversation'),
      icon: MessageCircle,
      colorClass: 'text-blue-500 dark:text-blue-400',
      bgClass: 'bg-blue-500/10 dark:bg-blue-400/10',
      borderClass: 'border-blue-500/20 dark:border-blue-400/20',
    },
    'text-input': {
      label: t('modeStatus.workMode.text'),
      icon: Type,
      colorClass: 'text-green-500 dark:text-green-400',
      bgClass: 'bg-green-500/10 dark:bg-green-400/10',
      borderClass: 'border-green-500/20 dark:border-green-400/20',
    },
  };

  const recordModeConfig = {
    'push-to-talk': {
      label: t('modeStatus.recordMode.pushToTalk'),
      icon: Mic,
      colorClass: 'text-purple-500 dark:text-purple-400',
      bgClass: 'bg-purple-500/10 dark:bg-purple-400/10',
      borderClass: 'border-purple-500/20 dark:border-purple-400/20',
    },
    continuous: {
      label: t('modeStatus.recordMode.continuous'),
      icon: Waves,
      colorClass: 'text-cyan-500 dark:text-cyan-400',
      bgClass: 'bg-cyan-500/10 dark:bg-cyan-400/10',
      borderClass: 'border-cyan-500/20 dark:border-cyan-400/20',
    },
  };

  const currentWorkMode = workModeConfig[workMode];
  const currentRecordMode = recordModeConfig[recordMode];
  const WorkModeIcon = currentWorkMode.icon;
  const RecordModeIcon = currentRecordMode.icon;

  return (
    <div className={cn('flex items-center gap-1.5', className)}>
      {/* 工作模式标签 */}
      <button
        onClick={onWorkModeClick}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all duration-200',
          'hover:scale-105 active:scale-[0.98]',
          currentWorkMode.bgClass,
          currentWorkMode.borderClass,
          currentWorkMode.colorClass,
          'border',
          onWorkModeClick && 'cursor-pointer hover:shadow-sm',
        )}
        aria-label={t('modeStatus.switchWorkMode')}
      >
        <WorkModeIcon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{currentWorkMode.label}</span>
      </button>

      {/* 录音模式标签 */}
      <button
        onClick={onRecordModeClick}
        className={cn(
          'flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-all duration-200',
          'hover:scale-105 active:scale-[0.98]',
          currentRecordMode.bgClass,
          currentRecordMode.borderClass,
          currentRecordMode.colorClass,
          'border',
          onRecordModeClick && 'cursor-pointer hover:shadow-sm',
        )}
        aria-label={t('modeStatus.switchRecordMode')}
      >
        <RecordModeIcon className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">{currentRecordMode.label}</span>
      </button>
    </div>
  );
}
