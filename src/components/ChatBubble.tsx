import { Mic, Play } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: number;
}

interface ChatBubbleProps {
  message: Message;
  index?: number;
  isStreaming?: boolean;
  isSpeaking?: boolean;
  onPlayTTS?: (content: string) => void;
  showTime?: boolean;
}

/**
 * ChatBubble - 对话气泡组件
 * 
 * 设计规范：
 * | 元素 | 用户消息 | AI 消息 |
 * |------|---------|---------|
 * | 对齐 | 靠右 | 靠左 |
 * | 背景 | 渐变蓝 (#3b82f6 → #2563eb) | 深灰 (#21262d) |
 * | 圆角 | 右上角直角 | 左上角直角 |
 * | 头像 | 蓝底用户图标 | 紫底机器人 |
 */
export function ChatBubble({ 
  message, 
  index: _index, 
  isStreaming = false, 
  isSpeaking = false,
  onPlayTTS,
  showTime = true 
}: ChatBubbleProps) {
  const { t } = useTranslation();
  const isUser = message.role === 'user';
  const isVoice = message.content.startsWith('🎤');
  const content = message.content.replace(/^🎤\s*/, '');
  
  // 判断是否需要显示头像（连续相同角色消息则隐藏）
  // 这个逻辑在父组件处理更合适，这里只负责渲染
  
  // 格式化时间
  const formatTime = (timestamp?: number) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  return (
    <div
      className={cn(
        "flex gap-3 animate-in slide-in-from-bottom-4 duration-300",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* AI 头像 - 仅在非用户时显示 */}
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center shadow-lg">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="white" fillOpacity="0.9"/>
            <path d="M8 11h8M8 15h8" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
      )}

      {/* 气泡内容区域 */}
      <div className={cn("max-w-[75%] group", isUser && "order-1")}>
        {/* 气泡 */}
        <div
          className={cn(
            "relative px-4 py-3 transition-all duration-200",
            isUser
              ? "bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-2xl rounded-tr-sm shadow-lg shadow-blue-500/20"
              : "bg-[#21262d] text-gray-100 border border-gray-700/50 rounded-2xl rounded-tl-sm"
          )}
        >
          {/* 语音输入标识 */}
          {isVoice && (
            <div className="flex items-center gap-1.5 mb-1.5 opacity-70">
              <Mic className="h-3 w-3" />
              <span className="text-xs">{t('app.messages.voiceLabel')}</span>
            </div>
          )}
          
          {/* 消息内容 */}
          <p className="text-sm whitespace-pre-wrap leading-relaxed">
            {content}
            {/* 流式输出光标 */}
            {isStreaming && (
              <span
                className="inline-block w-[2px] h-[1.1em] bg-white/50 ml-0.5 align-middle rounded-sm animate-cursor-blink"
                aria-hidden="true"
              />
            )}
          </p>

          {/* AI 消息播放按钮 */}
          {!isUser && onPlayTTS && (
            <button
              className={cn(
                "mt-2 flex items-center gap-1.5 text-xs transition-all duration-200",
                isSpeaking 
                  ? "text-purple-400" 
                  : "text-gray-400 hover:text-gray-200 opacity-0 group-hover:opacity-100"
              )}
              onClick={() => !isSpeaking && onPlayTTS(content)}
            >
              <Play className={cn("w-3 h-3", isSpeaking && "animate-pulse")} />
              <span>{isSpeaking ? t('app.messages.playing') : t('app.messages.play')}</span>
            </button>
          )}
        </div>

        {/* 时间戳 - 气泡下方 */}
        {showTime && (
          <p className={cn(
            "text-[11px] text-gray-400/60 mt-1.5",
            isUser ? "text-right" : "text-left"
          )}>
            {formatTime(message.timestamp)}
          </p>
        )}
      </div>

      {/* 用户头像 - 仅在用户时显示 */}
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center shadow-lg">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <circle cx="12" cy="7" r="4" stroke="white" strokeWidth="2"/>
          </svg>
        </div>
      )}
    </div>
  );
}

/**
 * LoadingIndicator - 加载动画组件
 */
export function LoadingIndicator() {
  return (
    <div className="flex gap-3 animate-in slide-in-from-bottom-4 duration-300">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="white" fillOpacity="0.9"/>
          <path d="M8 11h8M8 15h8" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </div>
      <div className="bg-[#21262d] border border-gray-700/50 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="flex gap-1">
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  );
}
