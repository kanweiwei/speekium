import React from 'react';
import { usePywebview } from '../hooks/usePywebview';
import { Button } from '@/components/ui/button';

interface Props {
  onStartRecording: () => void;
  onClearHistory: () => void;
  isRecording: boolean;
  isProcessing: boolean;
}

export function ControlPanel({ onStartRecording, onClearHistory, isRecording, isProcessing }: Props) {
  return (
    <div className="border-t bg-background px-6 py-4">
      <div className="flex items-center justify-center gap-4">
        <Button
          onClick={onStartRecording}
          disabled={isRecording || isProcessing}
          size="lg"
          className="min-w-[200px]"
        >
          {isRecording ? '🔴 录音中...' : '🎤 开始录音'}
        </Button>
        
        <Button
          onClick={onClearHistory}
          disabled={isProcessing}
          variant="outline"
          size="lg"
        >
          🗑️ 清空对话
        </Button>
      </div>
      
      <p className="text-center text-xs text-muted-foreground mt-3">
        说 "清空对话" 或 "clear history" 也可以清除历史
      </p>
    </div>
  );
}
