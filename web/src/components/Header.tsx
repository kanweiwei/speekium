import React from 'react';
import { usePywebview } from '../hooks/usePywebview';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface Props {
  onOpenSettings: () => void;
}

export function Header({ onOpenSettings }: Props) {
  const { isRecording, isProcessing, historyCount } = usePywebview();

  return (
    <header className="border-b bg-primary px-6 py-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2 text-primary-foreground">
          <span>🎙️</span>
          <span>Speekium</span>
        </h1>
        
        <div className="flex items-center gap-3">
          {isRecording && (
            <Badge variant="default" className="animate-pulse">
              🔴 录音中
            </Badge>
          )}
          {isProcessing && (
            <Badge variant="secondary">
              ⏳ 处理中
            </Badge>
          )}
          <span className="text-sm text-primary-foreground/80">
            对话: {historyCount} 轮
          </span>
          
          <Button variant="ghost" size="icon" onClick={onOpenSettings} className="text-primary-foreground hover:bg-white/20">
            ⚙️
          </Button>
        </div>
      </div>
    </header>
  );
}
