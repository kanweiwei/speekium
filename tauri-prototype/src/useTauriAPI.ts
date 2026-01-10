/**
 * Speekium Tauri API Integration
 * ✅ 正确架构：使用 Tauri invoke 调用 Rust 后端
 * ❌ 旧架构：fetch HTTP API (已废弃)
 */

import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

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

  // 加载配置和健康检查
  useEffect(() => {
    loadConfig();
    checkDaemonHealth();

    // 定期健康检查（每30秒）
    const healthInterval = setInterval(() => {
      checkDaemonHealth();
    }, 30000);

    return () => clearInterval(healthInterval);
  }, []);

  // 音频队列播放器
  useEffect(() => {
    if (audioQueue.length === 0 || isPlayingQueue) {
      return;
    }

    const playNext = async () => {
      setIsPlayingQueue(true);
      setIsSpeaking(true);

      const audioItem = audioQueue[0];
      console.log(`[Audio Queue] Playing: ${audioItem.text.substring(0, 30)}...`);

      try {
        const audio = new Audio(`file://${audioItem.path}`);

        await new Promise<void>((resolve, reject) => {
          audio.onended = () => {
            console.log('[Audio Queue] Finished playing');
            resolve();
          };
          audio.onerror = (error) => {
            console.error('[Audio Queue] Playback error:', error);
            reject(error);
          };
          audio.play().catch(reject);
        });

        // 移除已播放的音频
        setAudioQueue(prev => prev.slice(1));
      } catch (error) {
        console.error('[Audio Queue] Error:', error);
        // 出错也要移除，避免卡住
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

  const startRecording = async (mode: string = 'push-to-talk', duration?: number) => {
    setIsRecording(true);
    try {
      console.log(`[Recording] Starting: mode=${mode}, duration=${duration}`);

      const result = await invoke<RecordingResult>('record_audio', {
        mode,
        duration: duration || 3.0
      });

      if (result.success && result.text) {
        console.log(`[Recording] Success: "${result.text}" (${result.language})`);

        // 添加用户消息
        setMessages(prev => [...prev, {
          role: 'user',
          content: result.text!
        }]);

        // 自动调用 LLM
        await chatGenerator(result.text!, result.language);
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

  const chatGenerator = async (text: string, language: string = 'auto', useStreaming: boolean = true, useTTS: boolean = false) => {
    setIsProcessing(true);

    try {
      console.log(`[Chat] Sending: "${text}" (streaming: ${useStreaming}, TTS: ${useTTS})`);

      if (useTTS && useStreaming) {
        // TTS 流式模式
        return await chatTTSStream(text);
      }

      if (!useStreaming) {
        // 非流式模式
        const result = await invoke<ChatResult>('chat_llm', { text });

        if (result.success && result.content) {
          console.log(`[Chat] Response: "${result.content}"`);

          // 添加 LLM 响应
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

      // 流式模式
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

      // 监听流式事件
      const { listen } = await import('@tauri-apps/api/event');

      const unlistenChunk = await listen<string>('chat-chunk', (event) => {
        const chunk = event.payload;
        fullResponse += chunk;

        console.log(`[Chat] Chunk received: "${chunk}"`);

        // 实时更新 UI
        setMessages(prev => {
          if (!assistantMessageAdded) {
            // 第一次，添加新消息
            assistantMessageAdded = true;
            return [...prev, {
              role: 'assistant',
              content: fullResponse
            }];
          } else {
            // 更新最后一条消息
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: fullResponse
            };
            return newMessages;
          }
        });
      });

      const unlistenDone = await listen('chat-done', () => {
        console.log('[Chat] Stream done');
        unlistenChunk();
        unlistenDone();
        unlistenError();

        resolve({
          success: true,
          content: fullResponse
        });
      });

      const unlistenError = await listen<string>('chat-error', (event) => {
        console.error('[Chat] Stream error:', event.payload);
        unlistenChunk();
        unlistenDone();
        unlistenError();

        reject(new Error(event.payload));
      });

      // 调用 Rust 命令开始流式响应
      try {
        await invoke('chat_llm_stream', { text });
      } catch (error) {
        unlistenChunk();
        unlistenDone();
        unlistenError();
        reject(error);
      }
    });
  };

  const chatTTSStream = async (text: string) => {
    return new Promise<ChatResult>(async (resolve, reject) => {
      let fullResponse = '';
      let assistantMessageAdded = false;

      // 监听流式事件
      const { listen } = await import('@tauri-apps/api/event');

      const unlistenTextChunk = await listen<string>('tts-text-chunk', (event) => {
        const chunk = event.payload;
        fullResponse += chunk;

        console.log(`[TTS] Text chunk: "${chunk}"`);

        // 实时更新 UI
        setMessages(prev => {
          if (!assistantMessageAdded) {
            assistantMessageAdded = true;
            return [...prev, {
              role: 'assistant',
              content: fullResponse
            }];
          } else {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: fullResponse
            };
            return newMessages;
          }
        });
      });

      const unlistenAudioChunk = await listen<{ audio_path: string; text: string }>('tts-audio-chunk', (event) => {
        const { audio_path, text: audioText } = event.payload;
        console.log(`[TTS] Audio chunk: "${audioText.substring(0, 30)}..." -> ${audio_path}`);

        // 添加到音频队列
        setAudioQueue(prev => [...prev, { path: audio_path, text: audioText }]);
      });

      const unlistenDone = await listen('tts-done', () => {
        console.log('[TTS] Stream done');
        unlistenTextChunk();
        unlistenAudioChunk();
        unlistenDone();
        unlistenError();

        resolve({
          success: true,
          content: fullResponse
        });
      });

      const unlistenError = await listen<string>('tts-error', (event) => {
        console.error('[TTS] Stream error:', event.payload);
        unlistenTextChunk();
        unlistenAudioChunk();
        unlistenDone();
        unlistenError();

        reject(new Error(event.payload));
      });

      // 调用 Rust 命令开始 TTS 流式响应
      try {
        await invoke('chat_tts_stream', { text, autoPlay: true });
      } catch (error) {
        unlistenTextChunk();
        unlistenAudioChunk();
        unlistenDone();
        unlistenError();
        reject(error);
      }
    });
  };

  const generateTTS = async (text: string) => {
    try {
      console.log(`[TTS] Generating: "${text}"`);
      setIsSpeaking(true);

      const result = await invoke<TTSResult>('generate_tts', { text });

      if (result.success && result.audio_path) {
        console.log(`[TTS] Success: ${result.audio_path}`);
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
      const audio = new Audio(`file://${audioPath}`);
      audio.onended = () => setIsSpeaking(false);
      audio.onerror = () => setIsSpeaking(false);
      await audio.play();
    } catch (error) {
      console.error('[Audio] Playback failed:', error);
      setIsSpeaking(false);
    }
  };

  const clearHistory = () => {
    setMessages([]);
    console.log('[History] Cleared');
  };

  const checkDaemonHealth = async () => {
    try {
      const result = await invoke<HealthResult>('daemon_health');
      setDaemonHealth(result);

      if (result.success) {
        console.log('[Daemon] Healthy - Commands:', result.command_count);
      } else {
        console.warn('[Daemon] Health check failed:', result.error);
      }
    } catch (error) {
      console.error('[Daemon] Health check error:', error);
      setDaemonHealth({
        success: false,
        error: String(error)
      });
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
    chatGenerator,
    clearHistory,
    loadConfig,
    generateTTS,
    playAudio,
    checkDaemonHealth,
  };
}
