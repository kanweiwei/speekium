import React from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';
import { useTauriAPI } from './useTauriAPI';
import { Settings } from './Settings';
import { HistoryDrawer } from './components/HistoryDrawer';
import { NewSessionDialog } from './components/NewSessionDialog';
import { ThemeToggle } from './components/ThemeToggle';
import { WorkModeToast } from './components/WorkModeToast';
import { CollapsibleInput } from './components/CollapsibleInput';
import { historyAPI } from './useTauriAPI';
import { useWorkMode } from './contexts/WorkModeContext';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import { Button } from '@/components/ui/button';
import {
  Mic,
  Settings as SettingsIcon,
  Play,
  Sparkles,
  Zap,
  MessageSquare,
  AlertCircle,
  X,
  Wand2,
  Clock,
  PenSquare,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from './types/workMode';
import { parseHotkeyDisplay } from '@/utils/hotkeyParser';

// Empty state component
function EmptyState({ onPromptClick }: { onPromptClick: (prompt: string) => void }) {
  const { t } = useTranslation();
  const { config } = useSettings();

  // Parse hotkey configuration for display
  const keyParts = parseHotkeyDisplay(config?.push_to_talk_hotkey);

  const examplePrompts = [
    { icon: Sparkles, text: t('app.emptyState.prompts.introduce'), gradient: "from-blue-500 to-purple-500" },
    { icon: MessageSquare, text: t('app.emptyState.prompts.weather'), gradient: "from-purple-500 to-pink-500" },
    { icon: Zap, text: t('app.emptyState.prompts.joke'), gradient: "from-pink-500 to-orange-500" },
    { icon: Wand2, text: t('app.emptyState.prompts.book'), gradient: "from-orange-500 to-yellow-500" },
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

function App() {
  const { t } = useTranslation();
  const { workMode, setWorkMode } = useWorkMode();
  const [textInput, setTextInput] = React.useState<string>('');
  const [autoTTS, setAutoTTS] = React.useState<boolean>(true);
  const [isSpeaking, setIsSpeaking] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = React.useState(false);
  const [isStreaming, setIsStreaming] = React.useState<boolean>(false);
  const [isWaitingForLLM, setIsWaitingForLLM] = React.useState<boolean>(false);

  // Work Mode Toast state
  const [toast, setToast] = React.useState<{
    show: boolean;
    mode: WorkMode;
    message?: string;
  }>({
    show: false,
    mode: 'conversation',
  });

  const [recordMode, setRecordMode] = React.useState<'push-to-talk' | 'continuous'>(() => {
    const saved = localStorage.getItem('recordMode');
    return (saved === 'continuous' || saved === 'push-to-talk') ? saved : 'push-to-talk';
  });

  const {
    isRecording,
    isProcessing,
    messages,
    startRecording,
    forceStopRecording,
    chatGenerator,
    clearHistory,
    loadConfig,
    generateTTS,
    addMessage,
    updateLastAssistantMessage,
  } = useTauriAPI();

  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);
  const [isNewSessionDialogOpen, setIsNewSessionDialogOpen] = React.useState(false);
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null);
  const [currentSessionTitle, setCurrentSessionTitle] = React.useState<string | null>(null);
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
    // Persist session ID to localStorage
    if (currentSessionId) {
      localStorage.setItem('speekium_current_session_id', currentSessionId);
    } else {
      localStorage.removeItem('speekium_current_session_id');
    }
  }, [currentSessionId]);

  React.useEffect(() => {
    loadConfig();

    // Restore last session from localStorage
    const restoreSession = async () => {
      const savedSessionId = localStorage.getItem('speekium_current_session_id');
      if (savedSessionId) {
        try {
          const session = await historyAPI.getSession(savedSessionId);
          setCurrentSessionId(session.id);
          setCurrentSessionTitle(session.title);

          // Load session messages
          const messagesResult = await historyAPI.getSessionMessages(savedSessionId, 1, 1000);
          messagesResult.items.forEach(msg => {
            // Skip system messages
            if (msg.role === 'user' || msg.role === 'assistant') {
              addMessage(msg.role, msg.content);
            }
          });
        } catch (error) {
          console.error('Failed to restore session:', error);
          // If restore fails, clear the invalid session ID
          localStorage.removeItem('speekium_current_session_id');
        }
      }
    };

    restoreSession();
  }, []);

  // Auto scroll to bottom when messages change
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Listen for PTT events
  React.useEffect(() => {
    const setupListeners = async () => {
      const unlistenUserMessage = await listen<string>('ptt-user-message', async (event) => {
        const userText = event.payload;

        // Determine behavior based on work mode
        if (workMode === 'text') {
          // Text input mode: call type_text_command to input text to focused field and log to session history

          // First log to session history and database
          addMessage('user', userText);

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
              setCurrentSessionTitle(title);
            }
            await historyAPI.addSessionMessage(sessionId, 'user', userText);
          } catch (error) {
            console.error('Failed to save user message:', error);
          }

          // Then call type_text_command to paste text to focused field
          try {
            await invoke<string>('type_text_command', { text: userText });
          } catch (error) {
            console.error('[PTT] 文字输入失败:', error);
            setError(`文字输入失败: ${error}`);
            setTimeout(() => setError(null), 3000);
          }
        } else {
          // Conversation mode: display user message and wait for LLM response
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
              setCurrentSessionTitle(title);
            }
            await historyAPI.addSessionMessage(sessionId, 'user', userText);
          } catch (error) {
            console.error('Failed to save user message:', error);
          }
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
        setError(`${t('app.errors.pttError')}: ${event.payload}`);
      });

      return () => {
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
  }, [addMessage, updateLastAssistantMessage, workMode]);

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
            setError(result.error || t('app.errors.listenFailed'));
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

  // New session
  const handleNewSession = async (customTitle?: string | null) => {
    // Clear current message list
    clearHistory();
    // Reset session ID
    setCurrentSessionId(null);
    currentSessionIdRef.current = null;
    // Clear error state
    setError(null);
    // Reset session title
    setCurrentSessionTitle(customTitle || null);

    // If custom title provided, create session immediately
    if (customTitle) {
      try {
        const session = await historyAPI.createSession(customTitle);
        setCurrentSessionId(session.id);
        currentSessionIdRef.current = session.id;
      } catch (error) {
        console.error('Failed to create session:', error);
      }
    }
  };

  const handleSendText = async (text?: string) => {
    const message = text?.trim() || textInput.trim();
    if (!message || isProcessing) return;

    const userMessage = message;
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
        setCurrentSessionTitle(title);
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
            setError(`${t('app.errors.ttsFailed')}: ${ttsResult.error}`);
          }
        } catch (ttsError) {
          setError(`${t('app.errors.ttsError')}: ${ttsError}`);
        } finally {
          setIsSpeaking(false);
        }
      }
    } catch (chatError) {
      setError(`${t('app.errors.chatFailed')}: ${chatError}`);
    }
  };

  // Handle quick prompt card click
  const handlePromptClick = async (prompt: string) => {
    await handleSendText(prompt);
  };

  return (
    <SettingsProvider>
      <div className="flex flex-col h-screen bg-background text-foreground">
      {/* 顶栏 */}
      <header className="h-14 border-b border-border/50 bg-background/80 backdrop-blur-xl flex items-center justify-between px-4 sticky top-0 z-40">
        {/* 左侧按钮组 */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setIsHistoryOpen(!isHistoryOpen)}
          >
            <Clock className="w-4 h-4 mr-2" />
            {t('app.header.history')}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all duration-200 active:scale-[0.98]"
            onClick={() => setIsNewSessionDialogOpen(true)}
            disabled={isProcessing}
            aria-label={t('app.header.newSession')}
          >
            <PenSquare className="w-4 h-4 mr-2" />
            {t('app.header.newSession')}
          </Button>
        </div>

        <h1 className={cn(
          "text-lg font-semibold max-w-[300px] truncate",
          currentSessionTitle ? "text-foreground" : "text-foreground"
        )}>
          {currentSessionTitle || 'Speekium'}
        </h1>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setIsSettingsOpen(true)}
          >
            <SettingsIcon className="w-4 h-4 mr-2" />
            {t('app.header.settings')}
          </Button>
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-hidden relative">
        {/* 消息区域 */}
        <div className="h-full overflow-y-auto px-4">
          {/* 错误提示 */}
          {error && (
            <div className="max-w-[680px] mx-auto mt-4">
              <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/30 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
                <span className="flex-1 text-sm text-destructive">{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="text-destructive hover:text-destructive/80 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {/* 空状态或消息列表 */}
          <div className="max-w-[680px] mx-auto py-4">
            {messages.length === 0 ? (
              <EmptyState onPromptClick={handlePromptClick} />
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
                            : "bg-muted text-foreground border border-border/50 rounded-tl-sm"
                        )}
                      >
                        {isVoice && (
                          <div className="flex items-center gap-1.5 mb-1.5 opacity-70">
                            <Mic className="h-3 w-3" />
                            <span className="text-xs">{t('app.messages.voiceLabel')}</span>
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
                            className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                            onClick={() => {
                              if (!isSpeaking) {
                                setIsSpeaking(true);
                                generateTTS(message.content)
                                  .catch(err => setError(`${t('app.errors.ttsFailed')}: ${err}`))
                                  .finally(() => setIsSpeaking(false));
                              }
                            }}
                          >
                            <Play className="w-3 h-3" />
                            <span>{isSpeaking ? t('app.messages.playing') : t('app.messages.play')}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Loading indicator - shown while waiting for LLM response */}
                {(isProcessing || isWaitingForLLM) && (
                  <div className="flex gap-3 animate-in slide-in-from-bottom-4 duration-300">
                    <div className="bg-muted border border-border/50 rounded-2xl rounded-tl-sm px-4 py-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 底部输入区 - 使用可折叠输入框 */}
      <CollapsibleInput
        value={textInput}
        onChange={setTextInput}
        onSend={handleSendText}
        isProcessing={isProcessing}
      />

      {/* 设置弹窗 */}
      <Settings
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        autoTTS={autoTTS}
        onAutoTTSChange={setAutoTTS}
        recordMode={recordMode}
        onRecordModeChange={setRecordMode}
        workMode={workMode}
        onWorkModeChange={(mode) => {
          setWorkMode(mode, 'settings');
          // Show toast notification
          setToast({
            show: true,
            mode,
          });
        }}
        onClearHistory={handleClearHistory}
      />

      {/* 历史抽屉 */}
      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onNewSession={() => {
          setIsHistoryOpen(false);
          setIsNewSessionDialogOpen(true);
        }}
      />

      {/* 工作模式 Toast */}
      {toast.show && (
        <WorkModeToast
          mode={toast.mode}
          message={toast.message}
          onClose={() => setToast(prev => ({ ...prev, show: false }))}
        />
      )}

      {/* 新建会话弹窗 */}
      <NewSessionDialog
        isOpen={isNewSessionDialogOpen}
        onClose={() => setIsNewSessionDialogOpen(false)}
        onCreate={handleNewSession}
      />
      </div>
    </SettingsProvider>
  );
}

export default App;
