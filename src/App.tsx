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
  Settings as SettingsIcon,
  AlertCircle,
  X,
  Clock,
  PenSquare,
  Bell,
  Mic,
} from 'lucide-react';
import { isPermissionGranted, requestPermission, sendNotification } from '@tauri-apps/plugin-notification';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import type { WorkMode } from './types/workMode';
import { EmptyState } from './components/EmptyState';
import { LoadingScreen } from './components/LoadingScreen';
import { ChatBubble, LoadingIndicator } from './components/ChatBubble';
import { HotkeyStatusPanel } from './components/HotkeyStatusPanel';
import { MiniModeBubble } from './components/MiniModeBubble';
import { ConversationTemplates } from './components/ConversationTemplates';
import { ClipboardHistory, addToClipboardHistory } from './components/ClipboardHistory';
import { NotificationCenter } from './components/NotificationCenter';
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
    interruptTTS,
  } = useTauriAPI();

  const [isSettingsOpen, setIsSettingsOpen] = React.useState(false);
  const [isNewSessionDialogOpen, setIsNewSessionDialogOpen] = React.useState(false);
  const [isMiniMode, setIsMiniMode] = React.useState(false);
  
  // Mini mode settings
  const [miniModeSettings, setMiniModeSettings] = React.useState(() => {
    const saved = localStorage.getItem('miniModeSettings');
    return saved ? JSON.parse(saved) : {
      position: { x: 20, y: 200 },
      opacity: 100,
      color: 'purple'
    };
  });

  // Save mini mode settings when changed
  React.useEffect(() => {
    localStorage.setItem('miniModeSettings', JSON.stringify(miniModeSettings));
  }, [miniModeSettings]);

  const updateMiniModeSettings = (updates: { position?: { x: number; y: number }; opacity?: number; color?: string }) => {
    setMiniModeSettings((prev: { position: { x: number; y: number }; opacity: number; color: string }) => ({ ...prev, ...updates }));
  };
  const [showTemplates, setShowTemplates] = React.useState(false);
  const [showClipboardHistory, setShowClipboardHistory] = React.useState(false);
  const [showNotificationCenter, setShowNotificationCenter] = React.useState(false);
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

  // Listen for Escape key to interrupt TTS
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape key to interrupt TTS
      if (e.key === 'Escape' && isSpeaking) {
        console.log('[App] Escape pressed - interrupting TTS');
        interruptTTS();
        setIsSpeaking(false);
      }
      
      // Ctrl+Alt+M to toggle mini mode
      if (e.ctrlKey && e.altKey && e.key === 'm') {
        console.log('[App] Ctrl+Alt+M pressed - toggling mini mode');
        setIsMiniMode(prev => !prev);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isSpeaking, interruptTTS]);

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
            // 同时复制到剪贴板
            try {
              await navigator.clipboard.writeText(userText);
              addToClipboardHistory(userText); // 保存到历史
              console.log('[PTT] 已复制到剪贴板');
            } catch (clipErr) {
              console.warn('[PTT] 剪贴板复制失败:', clipErr);
            }
            
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

    // 在打字模式下，不调用 LLM，只发送消息后直接返回
    if (workMode === 'text-input') {
      // 只添加用户消息， 不调用 LLM
      return;
    }

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
        
        // 发送系统通知
        try {
          let hasPermission = await isPermissionGranted();
          if (!hasPermission) {
            const permission = await requestPermission();
            hasPermission = permission === 'granted';
          }
          if (hasPermission) {
            sendNotification({
              title: 'Speekium',
              body: 'AI 正在回复...',
            });
          }
        } catch (notifyError) {
          console.warn('[Notification] Failed to send:', notifyError);
        }
        
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

  // Handle template selection
  const handleTemplateSelect = (_prompt: string) => {
    setShowTemplates(false);
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
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setShowTemplates(true)}
          >
            <PenSquare className="w-4 h-4 mr-2" />
            {t('app.templates.button') || '模板'}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setShowClipboardHistory(true)}
          >
            <PenSquare className="w-4 h-4 mr-2" />
            剪贴板
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setShowNotificationCenter(true)}
          >
            <Bell className="w-4 h-4 mr-2" />
            通知
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
            className={cn(
              "text-muted-foreground hover:text-foreground hover:bg-muted/50",
              isMiniMode && "text-violet-500 bg-violet-500/10"
            )}
            onClick={() => setIsMiniMode(!isMiniMode)}
            title="Ctrl+Alt+M 切换迷你模式"
          >
            <Mic className="w-4 h-4" />
          </Button>
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
        {/* 迷你模式悬浮球 - 固定在右侧 */}
        {isMiniMode && (
          <MiniModeBubble
            isRecording={isRecording}
            isProcessing={isProcessing}
            isSpeaking={isSpeaking}
            workMode={workMode}
            settings={miniModeSettings}
            onSettingsChange={updateMiniModeSettings}
            onClick={() => setIsMiniMode(false)}
          />
        )}

        {/* 快捷键状态面板 */}
        {!isMiniMode && (
        <div className="max-w-[680px] mx-auto pt-4 px-4">
          <HotkeyStatusPanel
            pushToTalkHotkey={config?.push_to_talk_hotkey}
            workMode={workMode}
            recordMode={recordMode}
          />
        </div>
        )}

        {/* 消息区域 */}
        {!isMiniMode && (
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
                  const isLastAssistantMessage = !isUser && index === messages.length - 1;
                  const showStreaming = isStreaming && isLastAssistantMessage;
                  
                  // 连续相同角色消息隐藏头像
                  const prevMessage = messages[index - 1];
                  const hideAvatar = prevMessage && prevMessage.role === message.role;

                  return (
                    <ChatBubble
                      key={index}
                      message={message}
                      index={index}
                      isStreaming={showStreaming}
                      isSpeaking={isSpeaking}
                      hideAvatar={hideAvatar}
                      onPlayTTS={!isUser ? (content) => {
                        if (!isSpeaking) {
                          setIsSpeaking(true);
                          generateTTS(content)
                            .catch(err => setError(`${t('app.errors.ttsFailed')}: ${err}`))
                            .finally(() => setIsSpeaking(false));
                        }
                      } : undefined}
                    />
                  );
                })}

                {/* Loading indicator - shown while waiting for LLM response */}
                {(isProcessing || isWaitingForLLM) && (
                  <LoadingIndicator />
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>
        )}
      </div>

      {/* 底部输入区 - 使用可折叠输入框 */}
      {!isMiniMode && (
      <CollapsibleInput
        value={textInput}
        onChange={setTextInput}
        onSend={handleSendText}
        isProcessing={isProcessing}
        isRecording={isRecording}
        isSpeaking={isSpeaking}
      />
      )}

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
        miniModeSettings={miniModeSettings}
        onMiniModeSettingsChange={updateMiniModeSettings}
      />

      {/* 对话模板弹窗 */}
      {showTemplates && (
        <ConversationTemplates
          onSelectTemplate={handleTemplateSelect}
          onClose={() => setShowTemplates(false)}
        />
      )}

      {/* 剪贴板历史弹窗 */}
      {showClipboardHistory && (
        <ClipboardHistory
          onSelect={(_content) => {
            setShowClipboardHistory(false);
          }}
          onClose={() => setShowClipboardHistory(false)}
        />
      )}

      {/* 通知中心弹窗 */}
      {showNotificationCenter && (
        <NotificationCenter
          isOpen={showNotificationCenter}
          onClose={() => setShowNotificationCenter(false)}
        />
      )}

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
