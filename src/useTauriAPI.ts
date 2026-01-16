/**
 * Speekium Tauri API Integration
 * ✅ 正确架构：使用 Tauri invoke 调用 Rust 后端
 * ❌ 旧架构：fetch HTTP API (已废弃)
 */

import { useState, useEffect, useCallback } from 'react';
import { invoke, convertFileSrc } from '@tauri-apps/api/core';

// ============================================================================
// Type Definitions
// ============================================================================

interface ConfigResult {
  success: boolean;
  config?: Record<string, any>;
  error?: string;
}

interface RecordingResult {
  success: boolean;
  text?: string;
  language?: string;
  error?: string;
}

interface ChatResult {
  success: boolean;
  content?: string;
  error?: string;
}

interface TTSResult {
  success: boolean;
  audio_path?: string;
  error?: string;
}

interface HealthResult {
  success: boolean;
  status?: string;
  command_count?: number;
  models_loaded?: Record<string, boolean>;
  error?: string;
}

// History types
interface Session {
  id: string;
  title: string;
  is_favorite?: boolean;
  created_at: number;
  updated_at: number;
}

interface HistoryMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
}

interface PaginatedResult<T> {
  items: T[];
  total: number;
  has_more: boolean;
}

// ============================================================================
// Main Hook
// ============================================================================

export function useTauriAPI() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [daemonHealth, setDaemonHealth] = useState<HealthResult | null>(null);
  const [audioQueue, setAudioQueue] = useState<Array<{ path: string; text: string }>>([]);
  const [isPlayingQueue, setIsPlayingQueue] = useState(false);
  const [daemonReady, setDaemonReady] = useState(false);

  // Load config and start periodic health check only after daemon is ready
  useEffect(() => {
    // Only load config after daemon is ready
    if (!daemonReady) {
      return;
    }

    // Initial config load when daemon becomes ready
    loadConfig();

    // Initial health check when daemon becomes ready
    checkDaemonHealth();

    // Periodic health check (every 30s)
    const healthInterval = setInterval(() => {
      checkDaemonHealth();
    }, 30000);

    return () => clearInterval(healthInterval);
  }, [daemonReady]);

  // Audio queue player
  useEffect(() => {
    if (audioQueue.length === 0 || isPlayingQueue) {
      return;
    }

    const playNext = async () => {
      setIsPlayingQueue(true);
      setIsSpeaking(true);

      const audioItem = audioQueue[0];

      try {
        const audio = new Audio(`file://${audioItem.path}`);

        await new Promise<void>((resolve, reject) => {
          audio.onended = () => {
            resolve();
          };
          audio.onerror = (error) => {
            console.error('[Audio Queue] Playback error:', error);
            reject(error);
          };
          audio.play().catch(reject);
        });

        // Remove played audio
        setAudioQueue(prev => prev.slice(1));
      } catch (error) {
        console.error('[Audio Queue] Error:', error);
        // Remove on error to avoid getting stuck
        setAudioQueue(prev => prev.slice(1));
      } finally {
        setIsPlayingQueue(false);
        if (audioQueue.length <= 1) {
          setIsSpeaking(false);
        }
      }
    };

    playNext();
  }, [audioQueue, isPlayingQueue]);

  // ============================================================================
  // API Functions
  // ============================================================================

  const loadConfig = async () => {
    try {
      const result = await invoke<ConfigResult>('load_config');
      if (result.success && result.config) {
        setConfig(result.config);
      } else {
        console.error('[Config] Load failed:', result.error);
      }
    } catch (error) {
      console.error('[Config] Invoke failed:', error);
    }
  };

  const saveConfig = async (newConfig: Record<string, any>) => {
    try {
      const result = await invoke<{ success: boolean; error?: string }>('save_config', { config: newConfig });
      if (result.success) {
        setConfig(newConfig);
      } else {
        console.error('[Config] Save failed:', result.error);
        throw new Error(result.error || 'Save failed');
      }
    } catch (error) {
      console.error('[Config] Save invoke failed:', error);
      throw error;
    }
  };

  const startRecording = async (
    mode: string = 'push-to-talk',
    duration?: number | string,
    autoChat: boolean = true,
    useTTS: boolean = false,
    workMode?: 'conversation' | 'text-input'  // 🔧 Added workMode parameter
  ) => {
    setIsRecording(true);
    try {

      // Convert duration to string (Rust requires String type)
      const durationStr = duration === undefined ? 'auto' : String(duration);

      const result = await invoke<RecordingResult>('record_audio', {
        mode,
        duration: durationStr
      });

      if (result.success && result.text) {

        // 🔧 Bug fix: Handle text-input mode by calling type_text_command
        if (workMode === 'text-input') {
          try {
            await invoke<string>('type_text_command', { text: result.text! });
            console.log('[Recording] Text input completed:', result.text!.slice(0, 30) + '...');
          } catch (error) {
            console.error('[Recording] Text input failed:', error);
            throw error;
          }
        } else {
          // Conversation mode: add message and optionally call LLM
          setMessages(prev => [...prev, {
            role: 'user',
            content: result.text!
          }]);

          // Auto call LLM (if enabled)
          if (autoChat) {
            await chatGenerator(result.text!, result.language, true, useTTS);
          }
        }
      } else {
        console.error('[Recording] Failed:', result.error);
        throw new Error(result.error || 'Recording failed');
      }

      return result;
    } catch (error) {
      console.error('[Recording] Error:', error);
      return { success: false, error: String(error) };
    } finally {
      setIsRecording(false);
    }
  };

  const forceStopRecording = () => {
    setIsRecording(false);
    setIsProcessing(false);
  };

  const chatGenerator = async (text: string, _language: string = 'auto', useStreaming: boolean = true, useTTS: boolean = false) => {
    setIsProcessing(true);

    try {

      if (useTTS && useStreaming) {
        // TTS streaming mode
        return await chatTTSStream(text);
      }

      if (!useStreaming) {
        // Non-streaming mode
        const result = await invoke<ChatResult>('chat_llm', { text });

        if (result.success && result.content) {

          // Add LLM response
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: result.content!
          }]);
        } else {
          console.error('[Chat] Failed:', result.error);
          throw new Error(result.error || 'Chat failed');
        }

        return result;
      }

      // Streaming mode
      return await chatStream(text);

    } catch (error) {
      console.error('[Chat] Error:', error);
      return { success: false, error: String(error) };
    } finally {
      setIsProcessing(false);
    }
  };

  const chatStream = async (text: string) => {
    return new Promise<ChatResult>(async (resolve, reject) => {
      let fullResponse = '';
      let assistantMessageAdded = false;

      // Track unlisten functions safely
      let unlistenChunk: (() => void) | null = null;
      let unlistenDone: (() => void) | null = null;
      let unlistenError: (() => void) | null = null;

      // Listen for streaming events
      const { listen } = await import('@tauri-apps/api/event');

      try {
        unlistenChunk = await listen<string>('chat-chunk', (event) => {
          const chunk = event.payload;
          fullResponse += chunk;


          // Real-time UI update
          setMessages(prev => {
            if (!assistantMessageAdded) {
              // First time, add new message
              assistantMessageAdded = true;
              return [...prev, {
                role: 'assistant',
                content: fullResponse
              }];
            } else {
              // Update last assistant message
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;

              // Check if last message is assistant
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = {
                  role: 'assistant',
                  content: fullResponse
                };
                return newMessages;
              } else {
                // If last message is not assistant, add new message
                return [...prev, {
                  role: 'assistant',
                  content: fullResponse
                }];
              }
            }
          });
        });

        unlistenDone = await listen('chat-done', () => {
          // Safely unlisten all
          unlistenChunk?.();
          unlistenDone?.();
          unlistenError?.();

          resolve({
            success: true,
            content: fullResponse
          });
        });

        unlistenError = await listen<string>('chat-error', (event) => {
          console.error('[Chat] Stream error:', event.payload);
          // Safely unlisten all
          unlistenChunk?.();
          unlistenDone?.();
          unlistenError?.();

          reject(new Error(event.payload));
        });

        // Call Rust command to start streaming response
        await invoke('chat_llm_stream', { text });
      } catch (error) {
        // Safely unlisten all (only if they were set up)
        unlistenChunk?.();
        unlistenDone?.();
        unlistenError?.();
        reject(error);
      }
    });
  };

  const chatTTSStream = async (text: string) => {
    return new Promise<ChatResult>(async (resolve, reject) => {
      let fullResponse = '';
      let assistantMessageAdded = false;

      // Track unlisten functions safely
      let unlistenTextChunk: (() => void) | null = null;
      let unlistenAudioChunk: (() => void) | null = null;
      let unlistenDone: (() => void) | null = null;
      let unlistenError: (() => void) | null = null;

      // Listen for streaming events
      const { listen } = await import('@tauri-apps/api/event');

      try {
        unlistenTextChunk = await listen<string>('tts-text-chunk', (event) => {
          const chunk = event.payload;
          fullResponse += chunk;


          // Real-time UI update
          setMessages(prev => {
            if (!assistantMessageAdded) {
              assistantMessageAdded = true;
              return [...prev, {
                role: 'assistant',
                content: fullResponse
              }];
            } else {
              // Update last assistant message
              const newMessages = [...prev];
              const lastIndex = newMessages.length - 1;

              // Check if last message is assistant
              if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant') {
                newMessages[lastIndex] = {
                  role: 'assistant',
                  content: fullResponse
                };
                return newMessages;
              } else {
                // If last message is not assistant, add new message
                return [...prev, {
                  role: 'assistant',
                  content: fullResponse
                }];
              }
            }
          });
        });

        unlistenAudioChunk = await listen<{ audio_path: string; text: string }>('tts-audio-chunk', (event) => {
          const { audio_path, text: audioText } = event.payload;

          // Add to audio queue
          setAudioQueue(prev => [...prev, { path: audio_path, text: audioText }]);
        });

        unlistenDone = await listen('tts-done', () => {
          // Safely unlisten all
          unlistenTextChunk?.();
          unlistenAudioChunk?.();
          unlistenDone?.();
          unlistenError?.();

          resolve({
            success: true,
            content: fullResponse
          });
        });

        unlistenError = await listen<string>('tts-error', (event) => {
          console.error('[TTS] Stream error:', event.payload);
          // Safely unlisten all
          unlistenTextChunk?.();
          unlistenAudioChunk?.();
          unlistenDone?.();
          unlistenError?.();

          reject(new Error(event.payload));
        });

        // Call Rust command to start TTS streaming response
        await invoke('chat_tts_stream', { text, autoPlay: true });
      } catch (error) {
        // Safely unlisten all (only if they were set up)
        unlistenTextChunk?.();
        unlistenAudioChunk?.();
        unlistenDone?.();
        unlistenError?.();
        reject(error);
      }
    });
  };

  const generateTTS = async (text: string) => {
    try {
      setIsSpeaking(true);

      const result = await invoke<TTSResult>('generate_tts', { text });

      if (result.success && result.audio_path) {
        await playAudio(result.audio_path);
      } else {
        console.error('[TTS] Failed:', result.error);
        setIsSpeaking(false);
        throw new Error(result.error || 'TTS failed');
      }

      return result;
    } catch (error) {
      console.error('[TTS] Error:', error);
      setIsSpeaking(false);
      return { success: false, error: String(error) };
    }
  };

  const playAudio = async (audioPath: string) => {
    try {
      // Use Tauri convertFileSrc to convert local file path to accessible URL
      const audioUrl = convertFileSrc(audioPath);
      const audio = new Audio(audioUrl);
      audio.onended = () => setIsSpeaking(false);
      audio.onerror = (e) => {
        console.error('[Audio] Playback error:', e);
        setIsSpeaking(false);
      };
      await audio.play();
    } catch (error) {
      console.error('[Audio] Playback failed:', error);
      setIsSpeaking(false);
    }
  };

  const clearHistory = () => {
    setMessages([]);
  };

  const addMessage = useCallback((role: 'user' | 'assistant', content: string) => {
    setMessages(prev => [...prev, { role, content }]);
  }, []);

  const updateLastAssistantMessage = useCallback((content: string) => {
    setMessages(prev => {
      const newMessages = [...prev];
      // Find and update last assistant message
      for (let i = newMessages.length - 1; i >= 0; i--) {
        if (newMessages[i].role === 'assistant') {
          newMessages[i] = { ...newMessages[i], content };
          return newMessages;
        }
      }
      // If no assistant message, add new one
      return [...prev, { role: 'assistant', content }];
    });
  }, []);

  const checkDaemonHealth = async () => {
    try {
      const result = await invoke<HealthResult>('daemon_health');
      setDaemonHealth(result);

      if (result.success) {
        return result; // ✅ 返回结果
      } else {
        console.warn('[Daemon] Health check failed:', result.error);
        return result; // ✅ 返回结果（即使失败）
      }
    } catch (error) {
      console.error('[Daemon] Health check error:', error);
      const errorResult = {
        success: false,
        error: String(error)
      };
      setDaemonHealth(errorResult);
      return errorResult; // ✅ 返回错误结果
    }
  };

  // ============================================================================
  // History API
  // ============================================================================

  const listSessions = async (page: number = 1, pageSize: number = 20, filterFavorite?: boolean) => {
    try {
      const result = await invoke<PaginatedResult<Session>>('db_list_sessions', {
        page,
        pageSize,
        filterFavorite,
      });
      return result;
    } catch (error) {
      console.error('[History] List sessions failed:', error);
      throw error;
    }
  };

  const getSession = async (sessionId: string) => {
    try {
      const result = await invoke<Session>('db_get_session', { sessionId });
      return result;
    } catch (error) {
      console.error('[History] Get session failed:', error);
      throw error;
    }
  };

  const createSession = async (title: string) => {
    try {
      const result = await invoke<Session>('db_create_session', { title });
      return result;
    } catch (error) {
      console.error('[History] Create session failed:', error);
      throw error;
    }
  };

  const deleteSession = async (sessionId: string) => {
    try {
      await invoke('db_delete_session', { sessionId });
    } catch (error) {
      console.error('[History] Delete session failed:', error);
      throw error;
    }
  };

  const getSessionMessages = async (sessionId: string, page: number = 1, pageSize: number = 100) => {
    try {
      const result = await invoke<PaginatedResult<HistoryMessage>>('db_get_messages', {
        sessionId,
        page,
        pageSize,
      });
      return result;
    } catch (error) {
      console.error('[History] Get messages failed:', error);
      throw error;
    }
  };

  const addSessionMessage = async (sessionId: string, role: string, content: string) => {
    try {
      const result = await invoke<HistoryMessage>('db_add_message', {
        sessionId,
        role,
        content,
      });
      return result;
    } catch (error) {
      console.error('[History] Add message failed:', error);
      throw error;
    }
  };

  // ============================================================================
  // Return
  // ============================================================================

  return {
    isRecording,
    isProcessing,
    isSpeaking,
    config,
    messages,
    daemonHealth,
    audioQueue,
    startRecording,
    forceStopRecording,
    chatGenerator,
    clearHistory,
    loadConfig,
    saveConfig,
    generateTTS,
    playAudio,
    checkDaemonHealth,
    setDaemonReady,
    addMessage,
    updateLastAssistantMessage,
    // History API
    listSessions,
    getSession,
    createSession,
    deleteSession,
    getSessionMessages,
    addSessionMessage,
  };
}

// Export types for use in components
export type { Session, HistoryMessage, PaginatedResult };

// ============================================================================
// Standalone History API (can be used outside of hook)
// ============================================================================

export const historyAPI = {
  listSessions: async (page: number = 1, pageSize: number = 20, filterFavorite?: boolean) => {
    console.log('[historyAPI] listSessions called with:', { page, pageSize, filterFavorite });
    const params: Record<string, any> = { page, pageSize };
    if (filterFavorite !== undefined) {
      params.filterFavorite = filterFavorite;
    }
    console.log('[historyAPI] Invoking with params:', params);
    const result = await invoke<PaginatedResult<Session>>('db_list_sessions', params);
    console.log('[historyAPI] Invoke result:', result);
    return result;
  },

  getSession: async (sessionId: string) => {
    const result = await invoke<Session>('db_get_session', { sessionId });
    return result;
  },

  toggleFavorite: async (sessionId: string) => {
    console.log('[historyAPI] toggleFavorite called with sessionId:', sessionId);
    try {
      const result = await invoke<boolean>('db_toggle_favorite', { sessionId });
      console.log('[historyAPI] toggleFavorite result:', result);
      return result;
    } catch (error) {
      console.error('[historyAPI] toggleFavorite error:', error);
      throw error;
    }
  },

  createSession: async (title: string) => {
    const result = await invoke<Session>('db_create_session', { title });
    return result;
  },

  deleteSession: async (sessionId: string) => {
    await invoke('db_delete_session', { sessionId });
  },

  getSessionMessages: async (sessionId: string, page: number = 1, pageSize: number = 100) => {
    const result = await invoke<PaginatedResult<HistoryMessage>>('db_get_messages', {
      sessionId,
      page,
      pageSize,
    });
    return result;
  },

  addSessionMessage: async (sessionId: string, role: string, content: string) => {
    const result = await invoke<HistoryMessage>('db_add_message', {
      sessionId,
      role,
      content,
    });
    return result;
  },
};
