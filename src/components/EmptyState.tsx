import React, { useState } from 'react';
import {
  Sparkles,
  MessageSquare,
  Zap,
  Wand2,
  Mic,
  ChevronRight,
  Check,
  Settings,
  Volume2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import { parseHotkeyDisplay } from '@/utils/hotkeyParser';
import type { HotkeyConfig } from '@/types/hotkey';
import { SpeekiumIcon } from './SpeekiumIcon';
import { Button } from '@/components/ui/button';

interface EmptyStateProps {
  onPromptClick: (prompt: string) => void;
  pushToTalkHotkey?: HotkeyConfig;
  isFirstLaunch?: boolean;
  onComplete?: () => void;
}

// 引导步骤
type GuideStep = 'welcome' | 'hotkey' | 'llm' | 'complete';

interface GuideStepInfo {
  key: GuideStep;
  titleKey: string;
  descKey: string;
}

const GUIDE_STEPS: GuideStepInfo[] = [
  { key: 'welcome', titleKey: 'app.guide.welcome.title', descKey: 'app.guide.welcome.desc' },
  { key: 'hotkey', titleKey: 'app.guide.hotkey.title', descKey: 'app.guide.hotkey.desc' },
  { key: 'llm', titleKey: 'app.guide.llm.title', descKey: 'app.guide.llm.desc' },
  { key: 'complete', titleKey: 'app.guide.complete.title', descKey: 'app.guide.complete.desc' },
];

export function EmptyState({
  onPromptClick,
  pushToTalkHotkey,
  isFirstLaunch = false,
  onComplete,
}: EmptyStateProps) {
  const { t } = useTranslation();
  const [guideStep, setGuideStep] = useState<GuideStep>('welcome');
  const [guideCompleted, setGuideCompleted] = useState(!isFirstLaunch);

  const keyParts = parseHotkeyDisplay(pushToTalkHotkey);

  const examplePrompts = [
    { icon: Sparkles, text: t('app.emptyState.prompts.introduce'), gradient: "from-blue-500 to-purple-500" },
    { icon: MessageSquare, text: t('app.emptyState.prompts.weather'), gradient: "from-purple-500 to-pink-500" },
    { icon: Zap, text: t('app.emptyState.prompts.joke'), gradient: "from-pink-500 to-orange-500" },
    { icon: Wand2, text: t('app.emptyState.prompts.book'), gradient: "from-orange-500 to-yellow-500" },
  ];

  const handleNext = () => {
    const currentIndex = GUIDE_STEPS.findIndex(s => s.key === guideStep);
    if (currentIndex < GUIDE_STEPS.length - 1) {
      setGuideStep(GUIDE_STEPS[currentIndex + 1].key);
    } else {
      setGuideCompleted(true);
      onComplete?.();
    }
  };

  const handleSkip = () => {
    setGuideCompleted(true);
    onComplete?.();
  };

  // 引导模式
  if (!guideCompleted && isFirstLaunch) {
    const currentStepInfo = GUIDE_STEPS.find(s => s.key === guideStep)!;
    const currentIndex = GUIDE_STEPS.findIndex(s => s.key === guideStep);

    return (
      <div className="flex flex-col items-center justify-center h-full px-4">
        {/* 进度指示器 */}
        <div className="flex items-center gap-2 mb-8">
          {GUIDE_STEPS.map((step, idx) => (
            <div
              key={step.key}
              className={cn(
                "w-2 h-2 rounded-full transition-all",
                idx <= currentIndex ? "bg-primary" : "bg-muted"
              )}
            />
          ))}
        </div>

        {/* 图标 */}
        <div className="relative mb-6">
          <SpeekiumIcon size={64} className="drop-shadow-lg shadow-blue-500/20" />
        </div>

        {/* 标题 */}
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          {t(currentStepInfo.titleKey)}
        </h2>
        <p className="text-muted-foreground mb-8 text-center max-w-sm">
          {t(currentStepInfo.descKey)}
        </p>

        {/* 步骤相关内容 */}
        {guideStep === 'welcome' && (
          <div className="text-center mb-8">
            <div className="grid grid-cols-2 gap-4 max-w-sm">
              <div className="p-4 rounded-xl bg-muted border border-border/50 text-center">
                <Mic className="w-6 h-6 mx-auto mb-2 text-primary" />
                <p className="text-sm">{t('app.guide.welcome.feature1')}</p>
              </div>
              <div className="p-4 rounded-xl bg-muted border border-border/50 text-center">
                <Volume2 className="w-6 h-6 mx-auto mb-2 text-primary" />
                <p className="text-sm">{t('app.guide.welcome.feature2')}</p>
              </div>
            </div>
          </div>
        )}

        {guideStep === 'hotkey' && (
          <div className="mb-8">
            <div className="flex items-center gap-2 px-4 py-3 rounded-full bg-muted border border-border/50">
              <Mic className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{t('app.emptyState.shortcutHint')}</span>
              {keyParts.map((key, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <span className="text-sm text-muted-foreground">+</span>}
                  <kbd className="px-2 py-1 rounded bg-background text-foreground text-xs font-mono border border-border">{key}</kbd>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}

        {guideStep === 'llm' && (
          <div className="mb-8">
            <div className="grid grid-cols-2 gap-4 max-w-sm">
              <button
                onClick={handleNext}
                className="p-4 rounded-xl bg-muted border border-border/50 hover:border-primary transition-all text-left"
              >
                <Sparkles className="w-6 h-6 mb-2 text-primary" />
                <p className="text-sm font-medium">{t('app.guide.llm.local')}</p>
                <p className="text-xs text-muted-foreground">{t('app.guide.llm.localDesc')}</p>
              </button>
              <button
                onClick={handleNext}
                className="p-4 rounded-xl bg-muted border border-border/50 hover:border-primary transition-all text-left"
              >
                <Settings className="w-6 h-6 mb-2 text-primary" />
                <p className="text-sm font-medium">{t('app.guide.llm.api')}</p>
                <p className="text-xs text-muted-foreground">{t('app.guide.llm.apiDesc')}</p>
              </button>
            </div>
          </div>
        )}

        {guideStep === 'complete' && (
          <div className="text-center mb-8">
            <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center mx-auto mb-4">
              <Check className="w-8 h-8 text-green-500" />
            </div>
            <p className="text-muted-foreground">{t('app.guide.complete.tip')}</p>
          </div>
        )}

        {/* 按钮 */}
        <div className="flex gap-3">
          {guideStep !== 'llm' && (
            <Button variant="outline" onClick={handleSkip}>
              {t('app.guide.skip')}
            </Button>
          )}
          <Button onClick={handleNext}>
            {guideStep === 'complete' ? t('app.guide.start') : t('app.guide.next')}
            {guideStep !== 'complete' && <ChevronRight className="w-4 h-4 ml-1" />}
          </Button>
        </div>
      </div>
    );
  }

  // 正常空状态
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
