import React from 'react';
import {
  Sparkles,
  MessageSquare,
  Zap,
  Wand2,
  Mic,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import { parseHotkeyDisplay } from '@/utils/hotkeyParser';
import type { HotkeyConfig } from '@/types/hotkey';
import { SpeekiumIcon } from './SpeekiumIcon';

interface EmptyStateProps {
  onPromptClick: (prompt: string) => void;
  pushToTalkHotkey?: HotkeyConfig;
}

export function EmptyState({
  onPromptClick,
  pushToTalkHotkey,
}: EmptyStateProps) {
  const { t } = useTranslation();

  const keyParts = parseHotkeyDisplay(pushToTalkHotkey);

  const examplePrompts = [
    { icon: Sparkles, text: t('app.emptyState.prompts.introduce'), gradient: "from-blue-500 to-purple-500" },
    { icon: MessageSquare, text: t('app.emptyState.prompts.weather'), gradient: "from-purple-500 to-pink-500" },
    { icon: Zap, text: t('app.emptyState.prompts.joke'), gradient: "from-pink-500 to-orange-500" },
    { icon: Wand2, text: t('app.emptyState.prompts.book'), gradient: "from-orange-500 to-yellow-500" },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      {/* Brand icon */}
      <div className="relative mb-8">
        <SpeekiumIcon size={80} className="drop-shadow-lg shadow-blue-500/20" />
        <div className="absolute -inset-1 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 opacity-20 blur-xl" />
      </div>

      {/* 标题 */}
      <h2 className="text-2xl font-semibold text-foreground mb-2">{t('app.emptyState.title')}</h2>
      <p className="text-muted-foreground mb-8">{t('app.emptyState.description')}</p>

      {/* 快捷键提示 */}
      <div className="flex items-center gap-2 mb-8 px-4 py-2 rounded-full bg-muted border border-border/50">
        <Mic className="w-4 h-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">{t('app.emptyState.shortcutHint')}</span>
        {keyParts.map((key, index) => (
          <React.Fragment key={index}>
            {index > 0 && <span className="text-sm text-muted-foreground">+</span>}
            <kbd className="px-2 py-1 rounded bg-background text-foreground text-xs font-mono border border-border">{key}</kbd>
          </React.Fragment>
        ))}
        <span className="text-sm text-muted-foreground">{t('app.emptyState.shortcutAction')}</span>
      </div>

      {/* 示例提示卡片 */}
      <div className="grid grid-cols-2 gap-3 w-full max-w-md">
        {examplePrompts.map((prompt, idx) => {
          const Icon = prompt.icon;
          return (
            <button
              key={idx}
              onClick={() => onPromptClick(prompt.text)}
              className="group p-4 rounded-xl bg-muted border border-border/50 hover:border-border transition-all hover:scale-[1.02] text-left cursor-pointer"
            >
              <div className={cn(
                "w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center mb-3",
                prompt.gradient
              )}>
                <Icon className="w-4 h-4 text-white" />
              </div>
              <p className="text-sm text-muted-foreground group-hover:text-foreground">{prompt.text}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
