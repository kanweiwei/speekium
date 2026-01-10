import React from 'react';
import { Mic, MessageSquare, Bot, Moon, Sun, Monitor } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useTheme, Theme } from '../hooks/useTheme';

interface StatusBarProps {
  mode: string;
  messageCount: number;
  llmBackend: string;
}

export function StatusBar({ mode, messageCount, llmBackend }: StatusBarProps) {
  const { theme, setTheme } = useTheme();

  const modeIcon = mode === 'push_to_talk' ? <Mic className="w-4 h-4" /> : <MessageSquare className="w-4 h-4" />;
  const modeText = mode === 'push_to_talk' ? '按键录音' : '自由对话';

  const getThemeIcon = () => {
    switch (theme) {
      case 'light':
        return <Sun className="w-4 h-4" />;
      case 'dark':
        return <Moon className="w-4 h-4" />;
      default:
        return <Monitor className="w-4 h-4" />;
    }
  };

  const cycleTheme = () => {
    const themes: Theme[] = ['light', 'dark', 'system'];
    const currentIndex = themes.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themes.length;
    setTheme(themes[nextIndex]);
  };

  return (
    <div className="h-16 px-6 border-b border-border bg-background flex items-center justify-between">
      {/* Left: Status indicators */}
      <div className="flex items-center gap-4">
        <Badge variant="secondary" className="gap-2">
          {modeIcon}
          <span>{modeText}</span>
        </Badge>

        <Badge variant="outline" className="gap-2">
          <MessageSquare className="w-4 h-4" />
          <span>{messageCount} 条对话</span>
        </Badge>

        <Badge variant="outline" className="gap-2">
          <Bot className="w-4 h-4" />
          <span>{llmBackend}</span>
        </Badge>
      </div>

      {/* Right: Theme toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={cycleTheme}
        title={`当前主题: ${theme === 'light' ? '浅色' : theme === 'dark' ? '深色' : '跟随系统'}`}
      >
        {getThemeIcon()}
      </Button>
    </div>
  );
}
