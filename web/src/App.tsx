import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { StatusBar } from './components/StatusBar';
import { ChatHistory } from './components/ChatHistory';
import { SettingsPanel } from './components/SettingsPanel';
import { usePywebview } from './hooks/usePywebview';
import { Message } from './types';

// 辅助函数：将base64转换为Blob
function base64ToBlob(base64: string, mimeType: string): Blob {
  const byteCharacters = atob(base64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: mimeType });
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentResponse, setCurrentResponse] = useState('');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const { isProcessing, isRecording, api } = usePywebview();

  // 状态栏数据
  const [mode, setMode] = useState('continuous');
  const [llmBackend, setLlmBackend] = useState('Ollama');

  // 加载初始状态
  useEffect(() => {
    if (!api) return;

    const loadStatus = async () => {
      try {
        const config = await api.get_config();
        setLlmBackend(config.llm_backend === 'ollama' ? 'Ollama' : 'Claude');

        const modeStatus = await api.get_mode();
        setMode(modeStatus.mode);
      } catch (error) {
        console.error('加载状态失败:', error);
      }
    };

    loadStatus();
  }, [api]);

  const handleStartRecording = async () => {
    if (!api) return;

    try {
      const result = await api.start_recording();

      if (result.success && result.text) {
        const userMsg: Message = {
          id: Date.now().toString(),
          role: 'user',
          content: result.text,
          timestamp: new Date(),
          language: result.language
        };
        setMessages(prev => [...prev, userMsg]);

        let responseText = '';
        const language = result.language || 'zh';

        // 获取所有响应块
        const chunks = await api.chat_generator(result.text, language);

        // 迭代处理每个块
        for (const chunk of chunks) {
          if (chunk.type === 'partial') {
            responseText += chunk.content;
            setCurrentResponse(responseText);
          } else if (chunk.type === 'complete') {
            const aiMsg: Message = {
              id: (Date.now() + 1).toString(),
              role: 'assistant',
              content: responseText,
              timestamp: new Date()
            };
            setMessages(prev => [...prev, aiMsg]);

            // 播放TTS音频
            if (chunk.audio && chunk.audioFormat) {
              try {
                const audioBlob = base64ToBlob(chunk.audio, chunk.audioFormat);
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);

                audio.onended = () => {
                  URL.revokeObjectURL(audioUrl);
                };

                await audio.play();
              } catch (error) {
                console.error('音频播放失败:', error);
              }
            }
          } else if (chunk.type === 'error') {
            console.error('LLM错误:', chunk.content);
            alert(`生成失败: ${chunk.content}`);
          }
        }

        setCurrentResponse('');
      }
    } catch (error) {
      console.error('录音失败:', error);
      alert(`录音失败: ${error}`);
    }
  };

  const handleClearHistory = async () => {
    if (!api) return;
    await api.clear_history();
    setMessages([]);
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Left Sidebar */}
      <Sidebar onOpenSettings={() => setIsSettingsOpen(true)} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Status Bar */}
        <StatusBar
          mode={mode}
          messageCount={messages.length}
          llmBackend={llmBackend}
        />

        {/* Chat History */}
        <ChatHistory messages={messages} />

        {/* Current Response (Streaming) */}
        {currentResponse && (
          <div className="px-6 pb-6">
            <div className="bg-card rounded-2xl rounded-tl-md p-4 shadow-md max-w-[80%] border border-border">
              <p className="whitespace-pre-wrap break-words">
                {currentResponse}
                <span className="animate-pulse">|</span>
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Settings Panel */}
      <SettingsPanel
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        api={api}
      />
    </div>
  );
}

export default App;
