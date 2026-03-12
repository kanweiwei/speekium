import { Mic, MessageSquare, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from '../types/workMode';
import type { HotkeyConfig } from '../types/hotkey';

interface HotkeyStatusPanelProps {
  pushToTalkHotkey?: HotkeyConfig;
  workMode?: WorkMode;
  recordMode?: 'push-to-talk' | 'continuous';
  language?: string;
  className?: string;
}

/**
 * HotkeyStatusPanel - 快捷键状态面板
 * 
 * 桌面端常驻显示当前快捷键状态
 * 参考设计：
 * ┌─────────────────┐
 * │ 🎤 PTT: Alt+3   │
 * │ 🔄 模式: 对话   │
 * │ 🌍 语言: 中文   │
 * └─────────────────┘
 */
export function HotkeyStatusPanel({
  pushToTalkHotkey,
  workMode = 'conversation',
  recordMode = 'push-to-talk',
  language = 'zh',
  className
}: HotkeyStatusPanelProps) {
  const { t, i18n } = useTranslation();

  // 格式化快捷键显示
  const formatHotkey = (hotkey?: HotkeyConfig) => {
    if (!hotkey) return 'Alt+3';
    
    const modifierMap: Record<string, string> = {
      'CmdOrCtrl': 'Ctrl',
      'Alt': 'Alt',
      'Shift': 'Shift',
      'Meta': '⌘',
    };
    
    const modifiers = hotkey.modifiers?.map(m => modifierMap[m] || m) || [];
    const key = hotkey.key?.toUpperCase() || '';
    return [...modifiers, key].join('+');
  };

  // 获取语言显示名称
  const getLanguageName = (lang?: string) => {
    const langMap: Record<string, string> = {
      'zh': '中文',
      'en': 'English',
      'ja': '日本語',
    };
    return langMap[lang || i18n.language] || '中文';
  };

  // 获取模式显示名称
  const getModeName = (mode: WorkMode) => {
    return mode === 'conversation' ? t('modes.conversation') : t('modes.textInput');
  };

  // 获取录音模式显示名称
  const getRecordModeName = (mode: 'push-to-talk' | 'continuous') => {
    return mode === 'push-to-talk' ? t('modeStatus.recordMode.ptt') : t('modeStatus.recordMode.continuous');
  };

  return (
    <div
      className={cn(
        "flex flex-col gap-1.5 px-3 py-2 rounded-lg",
        "bg-background/80 backdrop-blur-sm border border-border/50",
        "text-xs text-muted-foreground",
        className
      )}
    >
      {/* PTT 快捷键 */}
      <div className="flex items-center gap-2">
        <Mic className="w-3.5 h-3.5 text-blue-500" />
        <span className="text-muted-foreground">PTT:</span>
        <span className="font-medium text-foreground">{formatHotkey(pushToTalkHotkey)}</span>
      </div>

      {/* 工作模式 */}
      <div className="flex items-center gap-2">
        <MessageSquare className="w-3.5 h-3.5 text-purple-500" />
        <span className="text-muted-foreground">{t('modes.label')}:</span>
        <span className="font-medium text-foreground">{getModeName(workMode)}</span>
      </div>

      {/* 录音模式 */}
      <div className="flex items-center gap-2">
        <span className="w-3.5 h-3.5 flex items-center justify-center text-orange-500">🔄</span>
        <span className="text-muted-foreground">{t('modeStatus.recordMode.label')}:</span>
        <span className="font-medium text-foreground">{getRecordModeName(recordMode)}</span>
      </div>

      {/* 语言 */}
      <div className="flex items-center gap-2">
        <Globe className="w-3.5 h-3.5 text-green-500" />
        <span className="text-muted-foreground">{t('settings.fields.language')}:</span>
        <span className="font-medium text-foreground">{getLanguageName(language)}</span>
      </div>
    </div>
  );
}
