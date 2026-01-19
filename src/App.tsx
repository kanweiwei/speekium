import React from 'react';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/core';
import { useTauriAPI } from './useTauriAPI';
import { Settings } from './Settings';
import { HistoryDrawer } from './components/HistoryDrawer';
import { NewSessionDialog } from './components/NewSessionDialog';
import { ThemeToggle } from './components/ThemeToggle';
import { ModeStatusBadge } from './components/ModeStatusBadge';
import { SystemToast } from './components/SystemToast';
import type { ToastType } from './components/SystemToast';
import { CollapsibleInput } from './components/CollapsibleInput';
import { historyAPI } from './useTauriAPI';
import { useWorkMode } from './contexts/WorkModeContext';
import type { WorkModeChangeEvent } from './types/workMode';
import { SettingsProvider } from './contexts/SettingsContext';
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
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from './types/workMode';
import { parseHotkeyDisplay } from '@/utils/hotkeyParser';
import type { HotkeyConfig } from '@/types/hotkey';
import { SpeekiumIcon } from './components/SpeekiumIcon';

// Empty state component
function EmptyState({
  onPromptClick,
  pushToTalkHotkey
}: {
  onPromptClick: (prompt: string) => void;
  pushToTalkHotkey?: HotkeyConfig;
}) {
  const { t } = useTranslation();

  // Parse hotkey configuration for display
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

// Loading screen component shown during daemon initialization
function LoadingScreen({
  message,
  status,
  downloadProgress,
  modelLoadingStages
}: {
  message: string;
  status: 'loading' | 'error';
  downloadProgress?: {
    show: boolean;
    model: string;
    percent: number;
    speed: string;
    totalSize: string;
    eventType: 'started' | 'progress' | 'completed';
  };
  modelLoadingStages?: {
    vad: 'pending' | 'loading' | 'loaded';
    asr: 'pending' | 'loading' | 'loaded';
  };
}) {
  const { t } = useTranslation();

  // Determine visual display state based on message content
  // Even if status is 'error', show loading style if message indicates loading is in progress
  const displayStatus = React.useMemo(() => {
    const loadingKeywords = ['loading', '加载', 'starting', '启动', 'initializing', '初始化', 'waiting', '等待'];
    const messageLower = (message || '').toLowerCase();
    const isLoadingMessage = loadingKeywords.some(keyword => messageLower.includes(keyword));
    return isLoadingMessage ? 'loading' : status;
  }, [message, status]);

  const handleRetry = () => {
    // Reload the app to retry daemon initialization
    window.location.reload();
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-background relative overflow-hidden">
      {/* Animated gradient mesh background */}
      {displayStatus === 'loading' && (
        <>
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {/* Layer 1 - Slow blue gradient */}
            <div
              className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-blue-500/8 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '8s', animationDelay: '0s' }}
            />
            {/* Layer 2 - Purple gradient, offset timing */}
            <div
              className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-purple-500/8 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '10s', animationDelay: '2s' }}
            />
            {/* Layer 3 - Small accent */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '12s', animationDelay: '4s' }}
            />
          </div>

          {/* Subtle grid overlay */}
          <div
            className="absolute inset-0 opacity-[0.02]"
            style={{
              backgroundImage: `
                linear-gradient(to right, currentColor 1px, transparent 1px),
                linear-gradient(to bottom, currentColor 1px, transparent 1px)
              `,
              backgroundSize: '60px 60px'
            }}
          />
        </>
      )}

      {/* Content container */}
      <div className="relative z-10 flex flex-col items-center">
        {/* Logo with animated sound wave rings */}
        <div className="relative mb-10">
          {/* Outer glow */}
          <div className={cn(
            "absolute -inset-8 rounded-full bg-gradient-to-br opacity-20 blur-2xl -z-10 transition-all duration-500",
            displayStatus === 'loading'
              ? "from-blue-500 via-purple-500 to-cyan-500 animate-pulse"
              : "from-destructive to-destructive/50"
          )}
          style={displayStatus === 'loading' ? { animationDuration: '3s' } : {}}
          />

          {/* Animated wave rings - only when loading */}
          {displayStatus === 'loading' && (
            <>
              {/* Ring 1 */}
              <div
                className="absolute inset-0 rounded-full border border-blue-500/30 animate-wave-ring"
                style={{ animationDelay: '0s' }}
              />
              {/* Ring 2 */}
              <div
                className="absolute inset-0 rounded-full border border-purple-500/25 animate-wave-ring"
                style={{ animationDelay: '0.8s' }}
              />
              {/* Ring 3 */}
              <div
                className="absolute inset-0 rounded-full border border-cyan-500/20 animate-wave-ring"
                style={{ animationDelay: '1.6s' }}
              />
            </>
          )}

          {/* Logo container */}
          <div className={cn(
            "w-28 h-28 transition-all duration-500 relative",
            displayStatus === 'loading' && "animate-logo-glow",
            displayStatus === 'error' && "opacity-50 scale-90"
          )}>
            <img
              src="/logo.svg"
              alt="Speekium"
              className="w-full h-full drop-shadow-2xl"
            />
          </div>
        </div>

        {/* Title with subtle gradient */}
        <h1 className={cn(
          "text-3xl font-semibold mb-8 tracking-tight transition-all duration-300",
          displayStatus === 'loading' ? "animate-fade-in" : "opacity-60"
        )}>
          <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent dark:from-blue-400 dark:via-purple-400 dark:to-cyan-400">
            {t('app.title')}
          </span>
        </h1>

        {/* Rhythmic loading dots - only when loading */}
        {displayStatus === 'loading' && (
          <div className="flex items-center gap-2 mb-6">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="w-1.5 h-6 rounded-full bg-gradient-to-t from-blue-500 to-purple-500 animate-dot-wave"
                style={{
                  animationDelay: `${i * 0.1}s`,
                  height: `${12 + Math.sin(i * 0.8) * 8}px`
                }}
              />
            ))}
          </div>
        )}

        {/* Status message */}
        <div className={cn(
          "flex items-center gap-3 px-5 py-3 rounded-2xl transition-all duration-300 backdrop-blur-sm",
          displayStatus === 'error'
            ? "bg-destructive/10 border border-destructive/30 text-destructive"
            : "bg-muted/50 border border-border/30 text-muted-foreground"
        )}>
          {displayStatus === 'loading' ? (
            <div className="relative">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
              <div className="absolute inset-0 w-5 h-5 rounded-full border-2 border-transparent border-t-purple-500/50 animate-spin" style={{ animationDuration: '1.5s' }} />
            </div>
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span className="text-sm font-medium">{message || t('app.loading.startingService')}</span>
        </div>

        {/* Model loading stages */}
        {modelLoadingStages && displayStatus === 'loading' && (
          <div className="mt-4 w-72 animate-fade-in">
            <div className="bg-muted/80 border border-border/50 rounded-xl p-4 backdrop-blur-sm">
              <div className="text-xs text-muted-foreground mb-3">{t('app.loading.loadingModels')}</div>
              <div className="space-y-2">
                {[
                  { key: 'vad', label: t('app.loading.vad'), desc: t('app.loading.vadDesc') },
                  { key: 'asr', label: t('app.loading.asr'), desc: t('app.loading.asrDesc') },
                ].map((model) => {
                  const stage = modelLoadingStages[model.key as keyof typeof modelLoadingStages];
                  const isLoading = stage === 'loading';
                  const isLoaded = stage === 'loaded';
                  const isPending = stage === 'pending';

                  return (
                    <div key={model.key} className="flex items-center gap-2 text-sm">
                      {isLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
                      ) : isLoaded ? (
                        <div className="w-3.5 h-3.5 rounded-full bg-green-500 flex items-center justify-center">
                          <span className="text-white text-[8px]">✓</span>
                        </div>
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-muted-foreground/30" />
                      )}
                      <span className={cn(
                        "flex-1",
                        isPending && "text-muted-foreground/50",
                        isLoaded && "text-foreground"
                      )}>
                        {model.label}
                      </span>
                      <span className={cn(
                        "text-xs text-muted-foreground",
                        isPending && "opacity-50"
                      )}>
                        {model.desc}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Download progress card */}
        {downloadProgress?.show && (
          <div className="mt-4 w-72 animate-fade-in">
            <div className="bg-muted/80 border border-border/50 rounded-xl p-4 backdrop-blur-sm">
              {/* Model name */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-sm font-medium">{downloadProgress.model}</span>
              </div>

              {/* Progress bar */}
              <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${downloadProgress.percent}%` }}
                />
              </div>

              {/* Progress info */}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{downloadProgress.percent}%</span>
                {downloadProgress.speed && (
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500/60" />
                    {downloadProgress.speed}
                  </span>
                )}
                {downloadProgress.totalSize && (
                  <span>{downloadProgress.totalSize}</span>
                )}
              </div>

              {/* Completed state */}
              {downloadProgress.eventType === 'completed' && (
                <div className="mt-2 text-xs text-green-500 flex items-center gap-1">
                  <span>✓</span>
                  <span>{t('app.loading.downloadComplete')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* First launch hint */}
        {displayStatus === 'loading' && !downloadProgress?.show && (
          <p className="text-sm text-muted-foreground/60 mt-6 animate-fade-in-delayed flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500/60 animate-pulse" />
            {t('app.loading.firstLaunchHint')}
          </p>
        )}

        {/* Retry button for error state */}
        {displayStatus === 'error' && (
          <Button
            variant="outline"
            size="sm"
            className="mt-6 gap-2"
            onClick={handleRetry}
          >
            <RefreshCw className="w-4 h-4" />
            {t('app.loading.retry')}
          </Button>
        )}
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

  // Daemon initialization status
  const [daemonStatus, setDaemonStatus] = React.useState<'loading' | 'ready' | 'error'>('loading');
  const [loadingMessage, setLoadingMessage] = React.useState<string>('');

  // Download progress state
  const [downloadProgress, setDownloadProgress] = React.useState<{
    show: boolean;
    model: string;
    percent: number;
    speed: string;
    totalSize: string;
    eventType: 'started' | 'progress' | 'completed';
  }>({
    show: false,
    model: '',
    percent: 0,
    speed: '',
    totalSize: '',
    eventType: 'started',
  });

  // Model loading stage state (VAD and ASR only - LLM is API-based, doesn't download)
  const [modelLoadingStages, setModelLoadingStages] = React.useState<{
    vad: 'pending' | 'loading' | 'loaded';
    asr: 'pending' | 'loading' | 'loaded';
  }>({
    vad: 'pending',
    asr: 'pending',
  });

  // Toast state - 支持多种 Toast 类型
  const [toast, setToast] = React.useState<{
    show: boolean;
    type: ToastType;
    workMode: WorkMode;
    message?: string;
    duration?: number;
  }>({
    show: false,
    type: 'custom',
    workMode: 'conversation',
  });

  const [recordMode, setRecordMode] = React.useState<'push-to-talk' | 'continuous'>(() => {
    const saved = localStorage.getItem('recordMode');
    return (saved === 'continuous' || saved === 'push-to-talk') ? saved : 'push-to-talk';
  });

  const {
    isRecording,
    isProcessing,
    messages,
    config,
    startRecording,
    forceStopRecording,
    chatGenerator,
    clearHistory,
    generateTTS,
    addMessage,
    updateLastAssistantMessage,
    setDaemonReady,
  } = useTauriAPI();

  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);
  const [isNewSessionDialogOpen, setIsNewSessionDialogOpen] = React.useState(false);
  const [showModeBadges, setShowModeBadges] = React.useState(() => {
    const saved = localStorage.getItem('showModeBadges');
    return saved !== 'false'; // Default to true
  });
  const [currentSessionId, setCurrentSessionId] = React.useState<string | null>(null);
  const [currentSessionTitle, setCurrentSessionTitle] = React.useState<string | null>(null);
  const currentSessionIdRef = React.useRef<string | null>(null);
  const pttAssistantResponseRef = React.useRef<string>('');
  const pttAssistantAddedRef = React.useRef<boolean>(false);
  const isRecordingRef = React.useRef(isRecording);
  const isProcessingRef = React.useRef(isProcessing);
  const isSpeakingRef = React.useRef(isSpeaking);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const recordModeRef = React.useRef(recordMode); // Track current mode for immediate access

  React.useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  React.useEffect(() => {
    isProcessingRef.current = isProcessing;
  }, [isProcessing]);

  React.useEffect(() => {
    isSpeakingRef.current = isSpeaking;
  }, [isSpeaking]);

  React.useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
    // Persist session ID to localStorage
    if (currentSessionId) {
      localStorage.setItem('speekium_current_session_id', currentSessionId);
    } else {
      localStorage.removeItem('speekium_current_session_id');
    }
  }, [currentSessionId]);

  // Sync recording mode with backend on initial mount
  // Mode changes via Alt+2 shortcut are delivered via events
  React.useEffect(() => {
    if (daemonStatus !== 'ready') {
      return;
    }

    // Initial sync - get current mode from backend
    const syncInitialMode = async () => {
      try {
        const currentMode = await invoke<string>('get_recording_mode');
        if (currentMode === 'push-to-talk' || currentMode === 'continuous') {
          setRecordMode(currentMode);
        }
      } catch (error) {
        console.error('[App] Failed to get initial recording mode:', error);
      }
    };

    syncInitialMode();
  }, [daemonStatus]);

  // Sync recordMode to ref for immediate access in async operations
  React.useEffect(() => {
    recordModeRef.current = recordMode;

    // Notify Rust backend about mode change when changed from Settings UI
    // (Alt+2 shortcut changes are handled via event listener)
    const notifyModeChange = async () => {
      if (daemonStatus !== 'ready') {
        return;
      }

      try {
        await invoke('set_recording_mode', { mode: recordMode });
      } catch (error) {
        console.error('Failed to set recording mode:', error);
      }
    };

    notifyModeChange();
  }, [recordMode, daemonStatus]);

  // Listen for daemon status events
  React.useEffect(() => {
    const setupDaemonListener = async () => {
      const unlisten = await listen<{ status: string; message: string }>('daemon-status', (event) => {
        const { status, message } = event.payload;
        if (status === 'ready') {
          setDaemonStatus('ready');
          // Enable health check only after daemon is ready
          setDaemonReady(true);
        } else if (status === 'error') {
          setDaemonStatus('error');
          setLoadingMessage(message);
        } else {
          setLoadingMessage(message);
        }
      });

      return unlisten;
    };

    const unlistenPromise = setupDaemonListener();

    // After setting up the listener, check daemon health to trigger status event
    // This is important when page is refreshed - daemon may already be running
    // and won't emit the ready event again automatically
    unlistenPromise.then(() => {
      invoke('daemon_health').catch((error) => {
        console.error('[App] Failed to check daemon health:', error);
        // If health check fails, set error status
        setDaemonStatus('error');
        setLoadingMessage(String(error));
      });
    });

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

  // Listen for download progress events
  React.useEffect(() => {
    const setupDownloadListener = async () => {
      const unlisten = await listen<{
        event_type: string;
        model: string;
        percent?: number;
        speed?: string;
        total_size?: string;
      }>('download-progress', (event) => {
        const { event_type, model, percent, speed, total_size } = event.payload;

        if (event_type === 'started') {
          setDownloadProgress({
            show: true,
            model,
            percent: 0,
            speed: '',
            totalSize: total_size || '',
            eventType: 'started',
          });
        } else if (event_type === 'progress') {
          setDownloadProgress(prev => ({
            show: true,
            model,
            percent: percent || 0,
            speed: speed || '',
            totalSize: total_size || prev.totalSize,
            eventType: 'progress',
          }));
        } else if (event_type === 'completed') {
          setDownloadProgress(prev => ({
            show: true,
            model,
            percent: 100,
            speed: prev.speed,
            totalSize: prev.totalSize,
            eventType: 'completed',
          }));
          // Hide the completed notification after 2 seconds
          setTimeout(() => {
            setDownloadProgress(prev => ({ ...prev, show: false }));
          }, 2000);
        }
      });

      return unlisten;
    };

    const unlistenPromise = setupDownloadListener();

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

  // Listen for model loading stage events
  React.useEffect(() => {
    const setupModelLoadingListener = async () => {
      const unlisten = await listen<{
        stage: string;
        status: string;
        message: string;
      }>('model-loading', (event) => {
        const { stage, status } = event.payload;

        setModelLoadingStages(prev => {
          const updated = { ...prev };
          if (stage === 'vad') {
            updated.vad = status === 'loading' ? 'loading' : 'loaded';
          } else if (stage === 'asr') {
            updated.asr = status === 'loading' ? 'loading' : 'loaded';
          } else if (stage === 'complete') {
            // All models loaded
            updated.vad = 'loaded';
            updated.asr = 'loaded';
          }
          return updated;
        });
      });

      return unlisten;
    };

    const unlistenPromise = setupModelLoadingListener();

    return () => {
      unlistenPromise.then(unlisten => unlisten());
    };
  }, []);

  // Restore last session from localStorage
  React.useEffect(() => {
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
        if (workMode === 'text-input') {
          // Text input mode: call type_text_command to input text to focused field and log to session history

          // First log to session history and database
          addMessage('user', userText);

          // Save to database (non-blocking, don't await)
          (async () => {
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
          })();

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

          // Save to database (non-blocking, don't await)
          (async () => {
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
          })();
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

        // Save assistant message to database (non-blocking, don't await)
        if (finalResponse && currentSessionIdRef.current) {
          (async () => {
            try {
              if (currentSessionIdRef.current) {
                await historyAPI.addSessionMessage(currentSessionIdRef.current, 'assistant', finalResponse);
              }
            } catch (error) {
              console.error('Failed to save assistant message:', error);
            }
          })();
        }

        pttAssistantResponseRef.current = '';
        pttAssistantAddedRef.current = false;
      });

      // Note: ptt-audio-chunk events are handled by Python daemon playback
      // Frontend does NOT play audio to avoid duplication

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
  }, [addMessage, updateLastAssistantMessage, workMode, t]);

  React.useEffect(() => {
    localStorage.setItem('recordMode', recordMode);
    if (recordMode === 'push-to-talk') {
      setError(null);
    }
  }, [recordMode]);

  // Continuous listening mode
  React.useEffect(() => {
    // Only start continuous listening after daemon is ready
    if (daemonStatus !== 'ready') {
      return;
    }

    let isContinuousMode = recordMode === 'continuous';
    let shouldKeepListening = true;
    let abortController = new AbortController();
    let hasShownStartToast = false;  // Track if we've shown the start toast

    const continuousListen = async () => {
      // Show toast when continuous listening starts
      if (!hasShownStartToast && isContinuousMode) {
        setToast({
          show: true,
          type: 'custom',
          workMode,
          message: '🎤 自动监听已启动',
          duration: 2000,
        });
        // Auto-hide toast after 2 seconds
        setTimeout(() => {
          setToast(prev => ({ ...prev, show: false }));
        }, 2000);
        hasShownStartToast = true;
      }

      while (isContinuousMode && shouldKeepListening && !abortController.signal.aborted) {
        // Check if mode has changed (use ref for immediate access)
        if (recordModeRef.current !== 'continuous') {
          console.log('Mode changed to push-to-talk, stopping continuous listening');
          break;
        }

        if (isRecordingRef.current || isProcessingRef.current || isSpeakingRef.current) {
          await new Promise(resolve => setTimeout(resolve, 500));
          continue;
        }

        try {
          // 🔧 Bug fix #2: Determine autoChat based on workMode
          // - conversation mode: auto chat with LLM + TTS
          // - text-input mode: only transcribe and input text, no LLM
          const shouldAutoChat = workMode === 'conversation';
          // 🔧 Bug fix #3: Pass workMode to startRecording so it can call type_text_command
          const result = await startRecording('continuous', 'auto', shouldAutoChat, shouldAutoChat && autoTTS, workMode);

          // Check again after recording completes
          if (recordModeRef.current !== 'continuous') {
            console.log('Mode changed during recording, stopping continuous listening');
            break;
          }

          if (!result.success) {
            // Check if error is due to mode change (recording cancelled)
            if (result.error?.includes('Recording cancelled') || result.error?.includes('Recording mode changed')) {
              console.log('Recording cancelled due to mode change, stopping continuous listening');
              break;
            }
            // Check if error is due to streaming in progress - just wait and retry
            if (result.error?.includes('streaming in progress')) {
              console.log('Recording blocked by streaming, waiting...');
              await new Promise(resolve => setTimeout(resolve, 1000));
              continue;
            }
            // Check if error is "No audio recorded" - this is normal in continuous mode when no speech detected
            // Just wait briefly and retry, don't show error
            if (result.error?.includes('No audio recorded')) {
              console.log('No speech detected, continuing to listen...');
              await new Promise(resolve => setTimeout(resolve, 1000));
              continue;
            }
            // For other errors, show error and wait longer before retry
            setError(result.error || t('app.errors.listenFailed'));
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        } catch (error) {
          if (abortController.signal.aborted) break;
          // Check mode on error too
          if (recordModeRef.current !== 'continuous') {
            console.log('Mode changed, stopping continuous listening (error path)');
            break;
          }
        }

        await new Promise(resolve => setTimeout(resolve, 500));
      }
      console.log('Continuous listening loop ended');
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
  }, [recordMode, daemonStatus, workMode]); // Add workMode dependency for toast

  // 监听 Rust 发送的系统事件，显示 Toast 通知
  React.useEffect(() => {
    const unlisteners: Promise<() => void>[] = [];

    // 监听通用 show-toast 事件
    unlisteners.push(
      (async () => {
        const unlisten = await listen<string>('show-toast', (event) => {
          console.log('[Toast] Received show-toast event:', event.payload);
          setToast({
            show: true,
            type: 'custom',
            workMode,
            message: event.payload,
            duration: 2000,
          });
        });
        return unlisten;
      })()
    );

    // 监听工作模式变化（通过轮询检测）
    // 注意：快捷键不再使用事件，而是通过配置轮询来检测变化
    unlisteners.push(
      (async () => {
        const unlisten = await listen<WorkModeChangeEvent>('work-mode-change', (event) => {
          console.log('[Toast] Received work-mode-change event:', event.payload);
          // Mode status is now shown in header, no toast needed
        });
        return unlisten;
      })()
    );

    // 监听录音模式切换事件 (Alt+2 快捷键)
    unlisteners.push(
      (async () => {
        const unlisten = await listen<string>('recording-mode-changed', async (event) => {
          const newMode = event.payload as 'push-to-talk' | 'continuous';
          console.log('[App] Received recording-mode-changed event:', newMode);

          // 同步更新 recordMode state
          setRecordMode(newMode);

          // Update daemon and handle PTT shortcut registration
          try {
            await invoke('update_recording_mode', { mode: newMode });
          } catch (error) {
            console.error('[App] Failed to update recording mode:', error);
          }

          // Save to localStorage
          localStorage.setItem('recordMode', newMode);
        });
        return unlisten;
      })()
    );

    // Cleanup
    return () => {
      Promise.all(unlisteners).then(cleanupFns => {
        cleanupFns.forEach(fn => fn());
      });
    };
  }, [workMode, setWorkMode]);

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

  // Show loading screen while daemon is initializing
  if (daemonStatus !== 'ready') {
    return (
      <SettingsProvider>
        <LoadingScreen
          message={loadingMessage}
          status={daemonStatus}
          downloadProgress={downloadProgress}
          modelLoadingStages={modelLoadingStages}
        />
      </SettingsProvider>
    );
  }

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

        <div className="flex items-center gap-3">
          <h1 className={cn(
            "text-lg font-semibold max-w-[300px] truncate",
            currentSessionTitle ? "text-foreground" : "text-foreground"
          )}>
            {currentSessionTitle || 'Speekium'}
          </h1>

          {/* 模式状态标签 */}
          {showModeBadges && (
            <ModeStatusBadge
              workMode={workMode}
              recordMode={recordMode}
              onWorkModeClick={() => {
                const newMode = workMode === 'conversation' ? 'text-input' : 'conversation';
                setWorkMode(newMode, 'hotkey');
              }}
              onRecordModeClick={async () => {
                const newMode = recordMode === 'push-to-talk' ? 'continuous' : 'push-to-talk';
                setRecordMode(newMode);
                try {
                  await invoke('update_recording_mode', { mode: newMode });
                } catch (error) {
                  console.error('[App] Failed to update recording mode:', error);
                }
                localStorage.setItem('recordMode', newMode);
              }}
            />
          )}
        </div>

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
              <EmptyState
                onPromptClick={handlePromptClick}
                pushToTalkHotkey={config?.push_to_talk_hotkey}
              />
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
        }}
        onClearHistory={handleClearHistory}
        showModeBadges={showModeBadges}
        onToggleModeBadges={(value) => {
          setShowModeBadges(value);
          localStorage.setItem('showModeBadges', value.toString());
        }}
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

      {/* Toast 通知 - P2-8: 使用 SystemToast 支持多种类型 */}
      {toast.show && (
        <SystemToast
          type={toast.type}
          workMode={toast.workMode}
          message={toast.message}
          duration={toast.duration}
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
