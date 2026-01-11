import React from 'react';
import './App.css';

// 导入 Tauri API hook
import { useTauriAPI } from './useTauriAPI';
import { listen } from '@tauri-apps/api/event';

function App() {
  const [status, setStatus] = React.useState<string>('就绪');
  const [textInput, setTextInput] = React.useState<string>('');
  const [autoTTS, setAutoTTS] = React.useState<boolean>(true);
  const [isSpeaking, setIsSpeaking] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);
  const [pttState, setPttState] = React.useState<'idle' | 'recording' | 'processing' | 'error'>('idle');

  // Load recording mode from localStorage with fallback to 'push-to-talk'
  const [recordMode, setRecordMode] = React.useState<'push-to-talk' | 'continuous'>(() => {
    const saved = localStorage.getItem('recordMode');
    return (saved === 'continuous' || saved === 'push-to-talk') ? saved : 'push-to-talk';
  });

  // 使用 Tauri API hook
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
    generateTTS,
    addMessage,
    updateLastAssistantMessage,
  } = useTauriAPI();

  // PTT 流式响应的临时累积
  const pttAssistantResponseRef = React.useRef<string>('');
  const pttAssistantAddedRef = React.useRef<boolean>(false);

  React.useEffect(() => {
    loadConfig();
  }, []);

  // Listen for PTT (Push-to-Talk) events from Tauri
  React.useEffect(() => {
    const setupListeners = async () => {
      const unlistenState = await listen<string>('ptt-state', (event) => {
        console.log('[App] PTT state:', event.payload);
        const state = event.payload as 'idle' | 'recording' | 'processing' | 'error';
        setPttState(state);

        // Update status based on PTT state
        switch (state) {
          case 'recording':
            setStatus('🎤 PTT 录音中... (松开停止)');
            setError(null);
            break;
          case 'processing':
            setStatus('🔄 处理中...');
            break;
          case 'idle':
            setStatus('就绪');
            break;
          case 'error':
            setStatus('就绪');
            break;
        }
      });

      // 用户语音识别结果
      const unlistenUserMessage = await listen<string>('ptt-user-message', (event) => {
        console.log('[App] PTT user message:', event.payload);
        addMessage('user', event.payload);
        // 重置 assistant 响应累积
        pttAssistantResponseRef.current = '';
        pttAssistantAddedRef.current = false;
      });

      // LLM 流式响应片段
      const unlistenAssistantChunk = await listen<string>('ptt-assistant-chunk', (event) => {
        console.log('[App] PTT assistant chunk:', event.payload);
        pttAssistantResponseRef.current += event.payload;

        if (!pttAssistantAddedRef.current) {
          // 第一个 chunk，添加新的 assistant 消息
          addMessage('assistant', pttAssistantResponseRef.current);
          pttAssistantAddedRef.current = true;
        } else {
          // 后续 chunk，更新已有的 assistant 消息
          updateLastAssistantMessage(pttAssistantResponseRef.current);
        }
      });

      // LLM 响应完成
      const unlistenAssistantDone = await listen<string>('ptt-assistant-done', (event) => {
        console.log('[App] PTT assistant done:', event.payload);
        // 确保最终内容正确
        if (event.payload) {
          updateLastAssistantMessage(event.payload);
        }
        pttAssistantResponseRef.current = '';
        pttAssistantAddedRef.current = false;
      });

      const unlistenError = await listen<string>('ptt-error', (event) => {
        console.error('[App] PTT error:', event.payload);
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

  // Save recording mode to localStorage when it changes
  // Also reset status when switching modes
  React.useEffect(() => {
    localStorage.setItem('recordMode', recordMode);
    console.log('[App] Recording mode saved:', recordMode);

    // Reset status and errors when switching modes
    if (recordMode === 'push-to-talk') {
      setStatus('就绪');
      setError(null);
    }
  }, [recordMode]);

  // Continuous listening mode: auto-start listening when mode is 'continuous'
  React.useEffect(() => {
    let isContinuousMode = recordMode === 'continuous';
    let shouldKeepListening = true;
    let abortController = new AbortController();

    const continuousListen = async () => {
      while (isContinuousMode && shouldKeepListening && !abortController.signal.aborted) {
        if (isRecording || isProcessing) {
          // Wait if already recording or processing
          await new Promise(resolve => setTimeout(resolve, 500));
          continue;
        }

        console.log('[App] Continuous mode: Starting VAD listening...');
        setStatus('持续监听中... 请说话');

        try {
          const result = await startRecording('continuous', 'auto', true, autoTTS);

          if (!result.success) {
            console.error('[App] Continuous listening failed:', result.error);
            setError(result.error || '监听失败');
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        } catch (error) {
          console.error('[App] Continuous listening error:', error);
          if (abortController.signal.aborted) {
            break; // Exit loop if aborted
          }
        }

        // Small delay before next listening cycle
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      console.log('[App] Continuous listening loop ended');
    };

    if (recordMode === 'continuous') {
      console.log('[App] Entering continuous listening mode');
      continuousListen();
    } else {
      console.log('[App] Exiting continuous listening mode');
      shouldKeepListening = false;
      abortController.abort();
      setStatus('就绪');
      setError(null);
    }

    // Cleanup function
    return () => {
      console.log('[App] Cleaning up continuous listening mode');
      shouldKeepListening = false;
      isContinuousMode = false;
      abortController.abort();
      if (recordMode !== 'continuous') {
        // Force stop any ongoing recording when switching to push-to-talk mode
        forceStopRecording();
        setStatus('就绪');
        setError(null);
      }
    };
  // Note: Only depend on recordMode to avoid re-running on isRecording/isProcessing changes
  // The continuous loop checks isRecording/isProcessing internally
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordMode]);

  // 清空历史
  const handleClearHistory = () => {
    clearHistory();
    setStatus('历史已清空');
  };

  // 测试 TTS
  const handleTestTTS = async () => {
    setStatus('测试 TTS...');
    const result = await generateTTS('你好，我是语音助手');
    if (result.success) {
      setStatus('TTS 播放成功');
    } else {
      setStatus(`TTS 失败: ${result.error}`);
    }
  };

  // 发送文本消息
  const handleSendText = async () => {
    if (!textInput.trim() || isProcessing) return;

    const userMessage = textInput.trim();
    setTextInput('');
    setStatus('思考中...');
    setError(null);

    try {
      // 调用 LLM (chatGenerator 返回 ChatResult 类型)
      const result = await chatGenerator(userMessage);

      // 自动播放 TTS（如果启用）
      if (autoTTS && result && result.success && result.content) {
        setStatus('播放语音...');
        setIsSpeaking(true);
        try {
          const ttsResult = await generateTTS(result.content);
          if (!ttsResult.success) {
            setError(`TTS 失败: ${ttsResult.error}`);
            setStatus('就绪');
          } else {
            setStatus('就绪');
          }
        } catch (ttsError) {
          setError(`TTS 错误: ${ttsError}`);
          setStatus('就绪');
        } finally {
          setIsSpeaking(false);
        }
      } else {
        setStatus('就绪');
      }
    } catch (error) {
      setError(`对话失败: ${error}`);
      setStatus('就绪');
    }
  };

  // 处理回车键发送
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <h1>🎤 Speekium</h1>
          <p className="subtitle">Tauri 桌面应用</p>
          <p className="version">v0.1.0</p>
        </div>

        <div className="sidebar-section">
          <h2>配置</h2>
          {config ? (
            <div className="config-info">
              <div className="config-item">
                <span className="label">LLM 后端:</span>
                <span className="value">{config.llm_backend}</span>
              </div>
              <div className="config-item">
                <span className="label">Ollama 模型:</span>
                <span className="value">{config.ollama_model}</span>
              </div>
              <div className="config-item">
                <span className="label">TTS 后端:</span>
                <span className="value">{config.tts_backend}</span>
              </div>
              <div className="config-item">
                <span className="label">VAD 阈值:</span>
                <span className="value">{config.vad_threshold}</span>
              </div>
              <div className="config-item">
                <span className="label">最大历史:</span>
                <span className="value">{config.max_history}</span>
              </div>
            </div>
          ) : (
            <div className="config-info loading">加载中...</div>
          )}
        </div>

        <div className="sidebar-section">
          <h2>设置</h2>
          <label className="toggle-setting">
            <input
              type="checkbox"
              checked={autoTTS}
              onChange={(e) => setAutoTTS(e.target.checked)}
            />
            <span>自动语音播放</span>
          </label>

          <div className="setting-group" style={{ marginTop: '15px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontSize: '14px' }}>录音模式:</label>
            <select
              value={recordMode}
              onChange={(e) => setRecordMode(e.target.value as 'push-to-talk' | 'continuous')}
              style={{
                width: '100%',
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid #444',
                background: '#2a2a2a',
                color: '#fff',
                fontSize: '14px'
              }}
            >
              <option value="push-to-talk">按键录音 (推荐)</option>
              <option value="continuous">自动检测</option>
            </select>
            <div style={{ fontSize: '12px', color: '#888', marginTop: '5px' }}>
              {recordMode === 'push-to-talk' ?
                '✓ 点击后立即录音，3秒后自动停止' :
                '⏱ 等待检测到语音后开始录音'
              }
            </div>
          </div>
        </div>

        <div className="sidebar-section">
          <h2>操作</h2>
          <button
            onClick={handleClearHistory}
            disabled={messages.length === 0}
            className="btn-secondary"
          >
            清空历史
          </button>
          <button
            onClick={handleTestTTS}
            disabled={isProcessing || isSpeaking}
            className="btn-secondary"
            style={{ marginTop: '10px' }}
          >
            🔊 测试 TTS
          </button>
        </div>
      </div>

      <div className="main-content">
        <div className="status-bar">
          <span className="status-text">状态: {status}</span>
          <div className="status-indicators">
            {pttState === 'recording' && <span className="badge recording">PTT 录音</span>}
            {pttState === 'processing' && <span className="badge processing">PTT 处理</span>}
            {isRecording && pttState === 'idle' && <span className="badge recording">录音中</span>}
            {isProcessing && pttState === 'idle' && <span className="badge processing">处理中</span>}
            {isSpeaking && <span className="badge speaking">播放中</span>}
          </div>
        </div>

        <div className="chat-container">
          {error && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{error}</span>
              <button
                className="error-close"
                onClick={() => setError(null)}
              >
                ✕
              </button>
            </div>
          )}

          <div className="messages">
            {messages.length === 0 ? (
              <div className="empty-state">
                <p>💬 输入消息或使用语音开始对话</p>
                <p className="hint">🎤 按住 <kbd>Cmd+Alt</kbd> 说话，松开结束</p>
                <p className="hint">支持文本输入和语音录音</p>
                {autoTTS && <p className="hint">✅ 自动语音播放已启用</p>}
              </div>
            ) : (
              messages.map((message, index) => (
                <div
                  key={index}
                  className={`message ${message.role}`}
                >
                  <div className="message-content">
                    <div className="message-role">
                      {message.role === 'user' ? '👤 用户' : '🤖 助手'}
                    </div>
                    <div className="message-text">{message.content}</div>
                  </div>
                </div>
              ))
            )}

            {isProcessing && (
              <div className="message assistant">
                <div className="message-content">
                  <div className="message-role">🤖 助手</div>
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="control-bar">
          <div className="input-group">
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入消息或使用语音..."
              disabled={isProcessing}
              className="text-input"
            />
            <button
              onClick={handleSendText}
              disabled={!textInput.trim() || isProcessing}
              className="btn-send"
            >
              发送
            </button>
            <div className={`ptt-status ${pttState}`}>
              <div className="ptt-indicator"></div>
              <span className="ptt-label">
                {pttState === 'recording' ? '录音中...' :
                 pttState === 'processing' ? '处理中...' :
                 'Cmd+Alt 说话'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
