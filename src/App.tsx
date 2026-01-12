import React from 'react';
import { listen } from '@tauri-apps/api/event';
import { useTauriAPI } from './useTauriAPI';
import { Settings } from './Settings';
import { HistoryDrawer } from './components/HistoryDrawer';
import { historyAPI } from './useTauriAPI';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Mic,
  Send,
  Settings as SettingsIcon,
  Clock,
  Play,
  Sparkles,
  Zap,
  MessageSquare,
  Wand2,
  Loader2,
  AlertCircle,
  X,
  PenSquare,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Empty state component
function EmptyState() {
  const examplePrompts = [
    { icon: Sparkles, text: "介绍一下自己", gradient: "from-blue-500 to-purple-500" },
    { icon: MessageSquare, text: "今天天气怎么样？", gradient: "from-purple-500 to-pink-500" },
    { icon: Zap, text: "讲个笑话", gradient: "from-pink-500 to-orange-500" },
    { icon: Wand2, text: "推荐一本书", gradient: "from-orange-500 to-yellow-500" },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full px-4">
      {/* 品牌图标 */}
      <div className="relative mb-8">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <Mic className="w-10 h-10 text-white" />
        </div>
        <div className="absolute -inset-1 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 opacity-20 blur-xl" />
      </div>

      {/* 标题 */}
      <h2 className="text-2xl font-semibold text-zinc-200 mb-2">开始对话</h2>
      <p className="text-zinc-400 mb-8">输入消息或使用语音助手</p>

      {/* 快捷键提示 */}
      <div className="flex items-center gap-2 mb-8 px-4 py-2 rounded-full bg-[#1C1C1F] border border-zinc-800/50">
        <Mic className="w-4 h-4 text-zinc-400" />
        <span className="text-sm text-zinc-400">按住</span>
        <kbd className="px-2 py-1 rounded bg-[#141416] text-zinc-300 text-xs font-mono border border-zinc-800">⌘ Cmd</kbd>
        <span className="text-sm text-zinc-400">+</span>
        <kbd className="px-2 py-1 rounded bg-[#141416] text-zinc-300 text-xs font-mono border border-zinc-800">⌥ Alt</kbd>
        <span className="text-sm text-zinc-400">说话</span>
      </div>

      {/* 示例提示卡片 */}
      <div className="grid grid-cols-2 gap-3 w-full max-w-md">
        {examplePrompts.map((prompt, idx) => {
          const Icon = prompt.icon;
          return (
            <button
              key={idx}
              className="group p-4 rounded-xl bg-[#1C1C1F] border border-zinc-800/50 hover:border-zinc-700 transition-all hover:scale-[1.02] text-left"
            >
              <div className={cn(
                "w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center mb-3",
                prompt.gradient
              )}>
                <Icon className="w-4 h-4 text-white" />
              </div>
              <p className="text-sm text-zinc-300 group-hover:text-zinc-200">{prompt.text}</p>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// PTT 状态覆盖层组件
function PTTOverlay({ state }: { state: 'idle' | 'recording' | 'processing' | 'error' }) {
  if (state === 'idle' || state === 'error') return null;

  return (
    <div className="absolute inset-0 flex items-center justify-center bg-[#0A0A0B]/80 backdrop-blur-sm z-50">
      {state === 'recording' && (
        <div className="flex flex-col items-center">
          {/* 声波动画 */}
          <div className="relative">
            <div className="w-32 h-32 rounded-full bg-red-500/20 flex items-center justify-center">
              <div className="w-24 h-24 rounded-full bg-red-500/40 flex items-center justify-center animate-pulse">
                <div className="w-16 h-16 rounded-full bg-red-500 flex items-center justify-center">
                  <Mic className="w-8 h-8 text-white" />
                </div>
              </div>
            </div>
            {/* 脉冲扩散动画 */}
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="absolute inset-0 rounded-full border-2 border-red-500 animate-ping"
                style={{
                  animationDelay: `${i * 0.3}s`,
                  animationDuration: '1.5s',
                }}
              />
            ))}
          </div>
          <p className="mt-6 text-lg font-medium text-red-400">录音中...</p>
          <p className="mt-2 text-sm text-zinc-400">松开停止录音</p>
        </div>
      )}

      {state === 'processing' && (
        <div className="flex flex-col items-center">
          {/* 处理动画 */}
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-amber-500/20 flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-amber-500/40 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
              </div>
            </div>
            <div className="absolute inset-0 rounded-full border-2 border-amber-500/50 animate-pulse" />
          </div>
          <p className="mt-6 text-lg font-medium text-amber-400">思考中...</p>
          <p className="mt-2 text-sm text-zinc-400">正在处理您的消息</p>
        </div>
      )}
    </div>
  );
}

function App() {
  const [textInput, setTextInput] = React.useState<string>('');
  const [autoTTS, setAutoTTS] = React.useState<boolean>(true);
  const [isSpeaking, setIsSpeaking] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);
  const [pttState, setPttState] = React.useState<'idle' | 'recording' | 'processing' | 'error'>('idle');
  const [isHistoryOpen, setIsHistoryOpen] = React.useState(false);
  const [isStreaming, setIsStreaming] = React.useState<boolean>(false);
  const [isWaitingForLLM, setIsWaitingForLLM] = React.useState<boolean>(false);

  const [recordMode, setRecordMode] = React.useState<'push-to-talk' | 'continuous'>(() => {
    const saved = localStorage.getItem('recordMode');
    return (saved === 'continuous' || saved === 'push-to-talk') ? saved : 'push-to-talk';
  });

  const {
    isRecording,
    isProcessing,
    config,
    messages,
    startRecording,
    forceStopRecording,
    chatGenerator,
    clearHistory,
    loadConfig,
    saveConfig,
    generateTTS,
    addMessage,
    updateLastAssistantMessage,
  } = useTauriAPI();

  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null);
  const currentSessionIdRef = React.useRef<string | null>(null);
  const pttAssistantResponseRef = React.useRef<string>('');
  const pttAssistantAddedRef = React.useRef<boolean>(false);
  const isRecordingRef = React.useRef(isRecording);
  const isProcessingRef = React.useRef(isProcessing);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  React.useEffect(() => {
    isProcessingRef.current = isProcessing;
  }, [isProcessing]);

  React.useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  React.useEffect(() => {
    loadConfig();
  }, []);

  // Auto scroll to bottom when messages change
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen for PTT events
  React.useEffect(() => {
    const setupListeners = async () => {
      const unlistenState = await listen<string>('ptt-state', (event) => {
        const state = event.payload as 'idle' | 'recording' | 'processing' | 'error';
        setPttState(state);
        if (state === 'recording') {
          setError(null);
        }
      });

      const unlistenUserMessage = await listen<string>('ptt-user-message', async (event) => {
        const userText = event.payload;
        addMessage('user', userText);
        pttAssistantResponseRef.current = '';
        pttAssistantAddedRef.current = false;
        setIsWaitingForLLM(true);  // Start waiting for LLM response

        // Save to database
        try {
          let sessionId = currentSessionIdRef.current;
          if (!sessionId) {
            // Create new session with first message as title
            const title = userText.slice(0, 30) + (userText.length > 30 ? '...' : '');
            const session = await historyAPI.createSession(title);
            sessionId = session.id;
            setCurrentSessionId(sessionId);
            currentSessionIdRef.current = sessionId;
          }
          await historyAPI.addSessionMessage(sessionId, 'user', userText);
        } catch (error) {
          console.error('Failed to save user message:', error);
        }
      });

      const unlistenAssistantChunk = await listen<string>('ptt-assistant-chunk', (event) => {
        setIsWaitingForLLM(false);  // LLM started responding, stop waiting
        setIsStreaming(true);
        pttAssistantResponseRef.current += event.payload;
        if (!pttAssistantAddedRef.current) {
          addMessage('assistant', pttAssistantResponseRef.current);
          pttAssistantAddedRef.current = true;
        } else {
          updateLastAssistantMessage(pttAssistantResponseRef.current);
        }
      });

      const unlistenAssistantDone = await listen<string>('ptt-assistant-done', async (event) => {
        setIsWaitingForLLM(false);  // Ensure waiting state is reset
        setIsStreaming(false);
        const finalResponse = event.payload || pttAssistantResponseRef.current;
        if (event.payload) {
          updateLastAssistantMessage(event.payload);
        }

        // Save assistant message to database
        if (finalResponse && currentSessionIdRef.current) {
          try {
            await historyAPI.addSessionMessage(currentSessionIdRef.current, 'assistant', finalResponse);
          } catch (error) {
            console.error('Failed to save assistant message:', error);
          }
        }

        pttAssistantResponseRef.current = '';
        pttAssistantAddedRef.current = false;
      });

      const unlistenError = await listen<string>('ptt-error', (event) => {
        setIsWaitingForLLM(false);  // Reset waiting state on error
        setIsStreaming(false);
        setError(`PTT 错误: ${event.payload}`);
      });

      return () => {
        unlistenState();
        unlistenUserMessage();
        unlistenAssistantChunk();
        unlistenAssistantDone();
        unlistenError();
      };
    };

    const cleanup = setupListeners();
    return () => {
      cleanup.then(fn => fn());
    };
  }, [addMessage, updateLastAssistantMessage]);

  React.useEffect(() => {
    localStorage.setItem('recordMode', recordMode);
    if (recordMode === 'push-to-talk') {
      setError(null);
    }
  }, [recordMode]);

  // Continuous listening mode
  React.useEffect(() => {
    let isContinuousMode = recordMode === 'continuous';
    let shouldKeepListening = true;
    let abortController = new AbortController();

    const continuousListen = async () => {
      while (isContinuousMode && shouldKeepListening && !abortController.signal.aborted) {
        if (isRecordingRef.current || isProcessingRef.current) {
          await new Promise(resolve => setTimeout(resolve, 500));
          continue;
        }

        try {
          const result = await startRecording('continuous', 'auto', true, autoTTS);
          if (!result.success) {
            setError(result.error || '监听失败');
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        } catch (error) {
          if (abortController.signal.aborted) break;
        }

        await new Promise(resolve => setTimeout(resolve, 500));
      }
    };

    if (recordMode === 'continuous') {
      continuousListen();
    } else {
      shouldKeepListening = false;
      abortController.abort();
      setError(null);
    }

    return () => {
      shouldKeepListening = false;
      isContinuousMode = false;
      abortController.abort();
      if (recordMode !== 'continuous') {
        forceStopRecording();
        setError(null);
      }
    };
  }, [recordMode]);

  const handleClearHistory = () => {
    clearHistory();
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
  };

  // 新建会话
  const handleNewSession = () => {
    // 清空当前消息列表
    clearHistory();
    // 重置会话 ID
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
    // 清空错误状态
    setError(null);
  };

  const handleSendText = async () => {
    if (!textInput.trim() || isProcessing) return;

    const userMessage = textInput.trim();
    setTextInput('');
    setError(null);

    // Add user message to chat list
    addMessage('user', userMessage);

    // Save user message to database
    let sessionId = currentSessionIdRef.current;
    try {
      if (!sessionId) {
        const title = userMessage.slice(0, 30) + (userMessage.length > 30 ? '...' : '');
        const session = await historyAPI.createSession(title);
        sessionId = session.id;
        setCurrentSessionId(sessionId);
        currentSessionIdRef.current = sessionId;
      }
      await historyAPI.addSessionMessage(sessionId, 'user', userMessage);
    } catch (error) {
      console.error('Failed to save user message:', error);
    }

    try {
      const result = await chatGenerator(userMessage);

      // Save assistant message to database
      if (result && result.success && result.content && sessionId) {
        try {
          await historyAPI.addSessionMessage(sessionId, 'assistant', result.content);
        } catch (error) {
          console.error('Failed to save assistant message:', error);
        }
      }

      if (autoTTS && result && result.success && result.content) {
        setIsSpeaking(true);
        try {
          const ttsResult = await generateTTS(result.content);
          if (!ttsResult.success) {
            setError(`TTS 失败: ${ttsResult.error}`);
          }
        } catch (ttsError) {
          setError(`TTS 错误: ${ttsError}`);
        } finally {
          setIsSpeaking(false);
        }
      }
    } catch (error) {
      setError(`对话失败: ${error}`);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  return (
    <div className="flex flex-col h-screen bg-[#0A0A0B] text-zinc-200">
      {/* 顶栏 */}
      <header className="h-14 border-b border-zinc-800/50 bg-[#141416]/80 backdrop-blur-xl flex items-center justify-between px-4 sticky top-0 z-40">
        {/* 左侧按钮组 */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
          >
            <Clock className="w-4 h-4 mr-2" />
            历史
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 transition-all duration-200 active:scale-[0.98]"
            onClick={handleNewSession}
            disabled={isProcessing}
            aria-label="新建会话"
          >
            <PenSquare className="w-4 h-4 mr-2" />
            新建
          </Button>
        </div>

        <h1 className="text-lg font-semibold text-zinc-200">Speekium</h1>

        <Button
          variant="ghost"
          size="sm"
          className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          onClick={() => setIsSettingsOpen(true)}
        >
          <SettingsIcon className="w-4 h-4 mr-2" />
          设置
        </Button>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-hidden relative">
        {/* 消息区域 */}
        <div className="h-full overflow-y-auto px-4">
          {/* 错误提示 */}
          {error && (
            <div className="max-w-[680px] mx-auto mt-4">
              <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <span className="flex-1 text-sm text-red-400">{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-red-400 hover:text-red-300 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {/* 空状态或消息列表 */}
          <div className="max-w-[680px] mx-auto py-4">
            {messages.length === 0 ? (
              <EmptyState />
            ) : (
              <div className="space-y-4">
                {messages.map((message, index) => {
                  const isUser = message.role === 'user';
                  const isVoice = message.content.startsWith('🎤');
                  const isLastAssistantMessage = !isUser && index === messages.length - 1;
                  const showStreamingCursor = isStreaming && isLastAssistantMessage;

                  return (
                    <div
                      key={index}
                      className={cn(
                        "flex gap-3 animate-in slide-in-from-bottom-4 duration-300",
                        isUser ? "justify-end" : "justify-start"
                      )}
                    >
                      <div
                        className={cn(
                          "max-w-[85%] rounded-2xl px-4 py-3 transition-all",
                          isUser
                            ? "bg-blue-600 text-white rounded-tr-sm"
                            : "bg-[#1C1C1F] text-zinc-200 border border-zinc-800/50 rounded-tl-sm"
                        )}
                      >
                        {isVoice && (
                          <div className="flex items-center gap-1.5 mb-1.5 opacity-70">
                            <Mic className="h-3 w-3" />
                            <span className="text-xs">语音消息</span>
                          </div>
                        )}
                        <p className="text-sm whitespace-pre-wrap leading-relaxed">
                          {message.content.replace(/^🎤\s*/, '')}
                          {showStreamingCursor && (
                            <span
                              className="inline-block w-[2px] h-[1.1em] bg-blue-500 ml-0.5 align-middle rounded-sm animate-cursor-blink"
                              aria-hidden="true"
                            />
                          )}
                        </p>

                        {/* AI 消息播放按钮 */}
                        {!isUser && (
                          <button
                            className="mt-2 flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
                            onClick={() => {
                              if (!isSpeaking) {
                                setIsSpeaking(true);
                                generateTTS(message.content)
                                  .catch(err => setError(`TTS 失败: ${err}`))
                                  .finally(() => setIsSpeaking(false));
                              }
                            }}
                          >
                            <Play className="w-3 h-3" />
                            <span>{isSpeaking ? '播放中...' : '播放'}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Loading indicator - shown while waiting for LLM response */}
                {(isProcessing || isWaitingForLLM) && (
                  <div className="flex gap-3 animate-in slide-in-from-bottom-4 duration-300">
                    <div className="bg-[#1C1C1F] border border-zinc-800/50 rounded-2xl rounded-tl-sm px-4 py-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* PTT 覆盖层 */}
        <PTTOverlay state={pttState} />
      </div>

      {/* 底部输入区 */}
      <div className="border-t border-zinc-800/50 bg-[#141416] px-4 py-4">
        <div className="max-w-[680px] mx-auto">
          {/* 输入框和发送按钮 */}
          <div className="flex items-center gap-3 mb-3">
            <Input
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入消息..."
              disabled={isProcessing}
              className="flex-1 bg-[#1C1C1F] border-zinc-800/50 text-zinc-200 placeholder:text-zinc-500 focus-visible:ring-blue-500"
            />
            <Button
              onClick={handleSendText}
              disabled={!textInput.trim() || isProcessing}
              className="bg-blue-600 hover:bg-blue-700 text-white disabled:bg-zinc-800 disabled:text-zinc-500"
            >
              {isProcessing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>

          {/* PTT 提示 */}
          <div className="flex items-center justify-center gap-2 text-xs text-zinc-500">
            <Mic className="w-3 h-3" />
            <span>按住 <kbd className="px-1.5 py-0.5 rounded bg-[#1C1C1F] text-zinc-400 font-mono border border-zinc-800">⌘+⌥</kbd> 说话</span>
          </div>
        </div>
      </div>

      {/* 设置弹窗 */}
      <Settings
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        config={config}
        onSave={saveConfig}
        autoTTS={autoTTS}
        onAutoTTSChange={setAutoTTS}
        recordMode={recordMode}
        onRecordModeChange={setRecordMode}
        onClearHistory={handleClearHistory}
      />

      {/* 历史抽屉 */}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
      />
    </div>
  );
}

export default App;
