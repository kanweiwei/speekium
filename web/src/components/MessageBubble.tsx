import React from 'react';
import { Message } from '../types';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className="text-2xl flex-shrink-0">
        {isUser ? '👤' : '🤖'}
      </div>
      <Card className={`max-w-[80%] ${isUser ? 'bg-primary text-primary-foreground' : 'bg-card text-card-foreground'}`}>
        <CardContent>
          <p className="whitespace-pre-wrap break-words leading-relaxed">
            {message.content}
          </p>
          {message.language && (
            <p className="text-xs pt-0 opacity-60">
              语言: {message.language}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
