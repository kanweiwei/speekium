import React, { useRef, useEffect } from 'react';
import { Message } from '../types';
import { MessageBubble } from './MessageBubble';
import { ScrollArea } from '@/components/ui/scroll-area';

interface Props {
  messages: Message[];
}

export function ChatHistory({ messages }: Props) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-6xl mb-6">🎙️</div>
          <h2 className="text-2xl font-semibold mb-2">欢迎使用 Speekium</h2>
          <p className="text-muted-foreground mb-4">
            按住 <kbd className="px-2 py-1 bg-muted rounded text-sm">Cmd+Alt</kbd> 开始录音
          </p>
          <p className="text-sm text-muted-foreground/60">
            支持中文和英文语音输入
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="flex-1 px-6 py-4">
      <div className="space-y-4 max-w-4xl mx-auto">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  );
}
