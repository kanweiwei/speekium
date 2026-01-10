import React from 'react';
import './App.css';

// 导入 Tauri API hook
import { useTauriAPI } from './useTauriAPI';

function App() {
  const [status, setStatus] = React.useState<string>('就绪');
  const [textInput, setTextInput] = React.useState<string>('');
  const [autoTTS, setAutoTTS] = React.useState<boolean>(true);
  const [isSpeaking, setIsSpeaking] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);
  const [recordMode, setRecordMode] = React.useState<'push-to-talk' | 'continuous'>('push-to-talk');

  // 使用 Tauri API hook
  const {
    isRecording,
    isProcessing,
    config,
    messages,
    startRecording,
    chatGenerator,
    clearHistory,
    loadConfig,
    generateTTS
  } = useTauriAPI();

  React.useEffect(() => {
    loadConfig();
  }, []);

  // 开始录音
  const handleStartRecording = async () => {
    if (isRecording || isProcessing) {
      return;
    }

    if (recordMode === 'push-to-talk') {
      setStatus('录音中... 请说话');
    } else {
      setStatus('等待语音... 请开始说话');
    }

    setError(null);
    const result = await startRecording(recordMode, 'auto');

    if (!result.success) {
      setError(result.error || '录音失败');
    }

    setStatus('就绪');
  };

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
      // 调用 LLM
      const chunks = await chatGenerator(userMessage);

      // 自动播放 TTS（如果启用）
      if (autoTTS && chunks && chunks.length > 0) {
        const lastChunk = chunks[chunks.length - 1];
        if (lastChunk.content) {
          setStatus('播放语音...');
          setIsSpeaking(true);
          try {
            const result = await generateTTS(lastChunk.content);
            if (!result.success) {
              setError(`TTS 失败: ${result.error}`);
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
            {isRecording && <span className="badge recording">录音中</span>}
            {isProcessing && <span className="badge processing">处理中</span>}
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
            <button
              onClick={handleStartRecording}
              disabled={isRecording || isProcessing}
              className={`btn-record ${isRecording ? 'recording' : ''}`}
            >
              {isRecording ? '🔴 停止' : '🎤 录音'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
