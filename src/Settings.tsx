import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ThemeToggle } from '@/components/ThemeToggle';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import { SaveStatusIndicator } from '@/components/SaveStatusIndicator';
import { HotkeyRecorder } from '@/components/HotkeyRecorder';
import { useSettings } from '@/contexts/SettingsContext';
import {
  Bot,
  Mic,
  Brain,
  Volume2,
  Keyboard,
  Zap,
  Palette,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Loader2,
  Trash2,
  MessageCircle,
  Type,
  RefreshCw,
} from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from '@/i18n';

// Common model lists for each backend
const OPENAI_MODELS = [
  'gpt-4o-mini',
  'gpt-4o',
  'gpt-4-turbo',
  'gpt-3.5-turbo',
];

const OPENROUTER_MODELS = [
  'google/gemini-2.0-flash-exp:free',
  'google/gemini-2.5-flash',
  'anthropic/claude-3.5-sonnet',
  'anthropic/claude-3.5-haiku',
  'openai/gpt-4o-mini',
  'openai/gpt-4o',
];

const OLLAMA_MODELS = [
  'qwen2.5:1.5b',
  'qwen2.5:7b',
  'llama3.1:8b',
  'mistral:7b',
];

const CUSTOM_MODELS = [
  'gpt-3.5-turbo',
  'gpt-4',
  'llama-2-7b',
];

const ZHIPU_MODELS = [
  'glm-4-plus',
  'glm-4',
  'glm-4-flash',
  'glm-4-air',
];

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
  autoTTS?: boolean;
  onAutoTTSChange?: (value: boolean) => void;
  recordMode?: 'push-to-talk' | 'continuous';
  onRecordModeChange?: (value: 'push-to-talk' | 'continuous') => void;
  workMode?: 'conversation' | 'text-input';
  onWorkModeChange?: (value: 'conversation' | 'text-input') => void;
  onClearHistory?: () => void;
}

type SettingsCategory = 'assistant' | 'voice-recognition' | 'ai-model' | 'tts' | 'shortcuts' | 'appearance' | 'advanced';

export function Settings({
  isOpen,
  onClose,
  autoTTS,
  onAutoTTSChange,
  recordMode,
  onRecordModeChange,
  workMode,
  onWorkModeChange,
  onClearHistory,
}: SettingsProps) {
  const { t } = useTranslation();
  const { config, updateConfig, updateHotkey, saveStatus, saveError } = useSettings();
  const [localConfig, setLocalConfig] = React.useState<Record<string, any>>({});
  const [activeCategory, setActiveCategory] = React.useState<SettingsCategory>('assistant');
  const [showApiKey, setShowApiKey] = React.useState(false);
  const [isTestingConnection, setIsTestingConnection] = React.useState(false);
  const [connectionStatus, setConnectionStatus] = React.useState<'idle' | 'success' | 'error'>('idle');
  const [connectionError, setConnectionError] = React.useState<string>('');
  const [isPreviewingTTS, setIsPreviewingTTS] = React.useState(false);
  const [previewAudio, setPreviewAudio] = React.useState<HTMLAudioElement | null>(null);
  const [customModelInput, setCustomModelInput] = React.useState<Record<string, boolean>>({
    openai: false,
    openrouter: false,
    ollama: false,
    custom: false,
    zhipu: false,
  });
  const [ollamaModels, setOllamaModels] = React.useState<string[]>(OLLAMA_MODELS);
  const [isLoadingOllamaModels, setIsLoadingOllamaModels] = React.useState(false);

  React.useEffect(() => {
    if (config) {
      // Config is loaded from backend, contains all llm_providers
      // Simply sync to localConfig
      setLocalConfig({ ...config });
    }
  }, [config]);

  // Sync workMode prop to localConfig (for hotkey-triggered changes)
  React.useEffect(() => {
    if (workMode && localConfig.work_mode !== workMode) {
      setLocalConfig(prev => ({ ...prev, work_mode: workMode }));
    }
  }, [workMode]);

  // Sync recordMode prop to localConfig (for hotkey-triggered changes)
  React.useEffect(() => {
    if (recordMode && localConfig.recording_mode !== recordMode) {
      setLocalConfig(prev => ({ ...prev, recording_mode: recordMode }));
    }
  }, [recordMode]);

  // 清理音频播放器
  React.useEffect(() => {
    return () => {
      if (previewAudio) {
        previewAudio.pause();
        previewAudio.src = '';
      }
    };
  }, [previewAudio]);

  const updateLocalConfig = (key: string, value: any) => {
    setLocalConfig(prev => ({ ...prev, [key]: value }));
    // Trigger auto-save through context
    updateConfig(key, value);
  };

  // Helper: Get current provider config from providers array
  const getCurrentProviderConfig = (config: Record<string, any>) => {
    const providerName = config.llm_provider || 'ollama';
    const providers = config.llm_providers || [];
    const found = providers.find((p: any) => p.name === providerName) || {};
    console.log('[getCurrentProviderConfig]', {
      providerName,
      providersCount: providers.length,
      found,
      allProviders: providers.map((p: any) => ({ name: p.name, hasKey: !!p.api_key, keyLength: p.api_key?.length || 0 }))
    });
    return found;
  };

  // Helper: Update a field in the current provider config using functional update
  const updateProviderConfig = (field: string, value: any) => {
    setLocalConfig(prev => {
      const providerName = prev.llm_provider || 'ollama';
      const providers = [...(prev.llm_providers || [])];
      const providerIndex = providers.findIndex((p: any) => p.name === providerName);

      if (providerIndex >= 0) {
        providers[providerIndex] = { ...providers[providerIndex], [field]: value };
      } else {
        // Provider not found, create new entry
        providers.push({ name: providerName, [field]: value });
      }

      // Update context config as well to trigger save
      updateConfig('llm_providers', providers);

      return { ...prev, llm_providers: providers };
    });
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionStatus('idle');
    setConnectionError('');

    const providerName = localConfig.llm_provider || 'ollama';

    // Find provider config from providers array
    const providers = localConfig.llm_providers || [];
    const providerConfig = providers.find((p: any) => p.name === providerName) || {};

    const base_url = providerConfig.base_url || '';
    const api_key = providerConfig.api_key || '';
    const model = providerConfig.model || '';

    try {
      let result: { success: boolean; message?: string; error?: string };

      // 根据不同的 provider 类型调用不同的测试命令
      if (providerName === 'ollama') {
        result = await invoke<{
          success: boolean;
          message?: string;
          error?: string;
        }>('test_ollama_connection', {
          baseUrl: base_url || 'http://localhost:11434',
          model: model || 'qwen2.5:1.5b'
        });
      } else if (providerName === 'openai') {
        result = await invoke<{
          success: boolean;
          message?: string;
          error?: string;
        }>('test_openai_connection', {
          apiKey: api_key,
          model: model || 'gpt-4o-mini'
        });
      } else if (providerName === 'openrouter') {
        result = await invoke<{
          success: boolean;
          message?: string;
          error?: string;
        }>('test_openrouter_connection', {
          apiKey: api_key,
          model: model || 'google/gemini-2.5-flash'
        });
      } else if (providerName === 'custom') {
        result = await invoke<{
          success: boolean;
          message?: string;
          error?: string;
        }>('test_custom_connection', {
          apiKey: api_key,
          baseUrl: base_url,
          model: model
        });
      } else if (providerName === 'zhipu') {
        result = await invoke<{
          success: boolean;
          message?: string;
          error?: string;
        }>('test_zhipu_connection', {
          apiKey: api_key,
          baseUrl: base_url || 'https://open.bigmodel.cn/api/paas/v4',
          model: model || 'glm-4-flash'
        });
      } else if (providerName === 'claude') {
        // Claude Code CLI 不需要测试连接，直接返回成功
        result = {
          success: true,
          message: 'Claude Code CLI is available locally'
        };
      } else {
        throw new Error(`Unknown provider: ${providerName}`);
      }

      if (result.success) {
        setConnectionStatus('success');
      } else {
        console.error('[Settings] Connection test failed:', result.error);
        setConnectionStatus('error');
        setConnectionError(result.error || t('settings.audio.unknownError'));
      }
    } catch (error) {
      console.error('[Settings] Connection test error:', error);
      setConnectionStatus('error');
      setConnectionError(String(error));
    } finally {
      setIsTestingConnection(false);
      // 3秒后自动重置状态
      setTimeout(() => {
        setConnectionStatus('idle');
        setConnectionError('');
      }, 3000);
    }
  };

  const handlePreviewTTS = async () => {
    // 如果正在播放，则停止
    if (previewAudio && !previewAudio.paused) {
      previewAudio.pause();
      previewAudio.currentTime = 0;
      setIsPreviewingTTS(false);
      return;
    }

    setIsPreviewingTTS(true);
    setConnectionStatus('idle');
    setConnectionError('');

    try {
      // 调用 Rust 后端的 generate_tts 命令
      const result = await invoke<{
        success: boolean;
        audio_path?: string;
        error?: string;
      }>('generate_tts', {
        text: t('settings.tts.previewText')
      });

      if (result.success && result.audio_path) {
        // 使用 convertFileSrc 转换文件路径
        const { convertFileSrc } = await import('@tauri-apps/api/core');
        const audioUrl = convertFileSrc(result.audio_path);

        // 创建并播放音频
        const audio = new Audio(audioUrl);
        let hasStartedPlaying = false;

        audio.onplay = () => {
          hasStartedPlaying = true;
        };

        audio.onended = () => {
          setIsPreviewingTTS(false);
          setConnectionStatus('idle');
          setConnectionError('');
          setPreviewAudio(null);
        };

        audio.onerror = (error) => {
          console.error('[Settings] TTS playback error:', error);
          // 只在音频真的没有播放时才显示错误
          // 如果已经开始播放了，说明可能是播放结束后的误触发
          if (!hasStartedPlaying) {
            setIsPreviewingTTS(false);
            setConnectionStatus('error');
            setConnectionError(t('settings.audio.previewFailed'));
            setPreviewAudio(null);
          } else {
            // 如果已经开始播放，清除加载状态但不显示错误
            setIsPreviewingTTS(false);
          }
        };

        setPreviewAudio(audio);
        await audio.play();
      } else {
        console.error('[Settings] TTS generation failed:', result.error);
        setIsPreviewingTTS(false);
        setConnectionStatus('error');
        setConnectionError(result.error || t('settings.audio.generationFailed'));
        // 3秒后自动重置状态
        setTimeout(() => {
          setConnectionStatus('idle');
          setConnectionError('');
        }, 3000);
      }
    } catch (error) {
      console.error('[Settings] TTS preview error:', error);
      setIsPreviewingTTS(false);
      setConnectionStatus('error');
      setConnectionError(String(error));
      // 3秒后自动重置状态
      setTimeout(() => {
        setConnectionStatus('idle');
        setConnectionError('');
      }, 3000);
    }
  };

  const categories = React.useMemo(() => [
    { id: 'assistant' as const, label: t('settings.categories.assistant'), icon: Bot },
    { id: 'voice-recognition' as const, label: t('settings.categories.voiceRecognition'), icon: Mic },
    { id: 'ai-model' as const, label: t('settings.categories.aiModel'), icon: Brain },
    { id: 'tts' as const, label: t('settings.categories.tts'), icon: Volume2 },
    { id: 'shortcuts' as const, label: t('settings.categories.shortcuts'), icon: Keyboard },
    { id: 'appearance' as const, label: t('settings.categories.appearance'), icon: Palette },
    { id: 'advanced' as const, label: t('settings.categories.advanced'), icon: Zap },
  ], [t]);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[900px] w-[95vw] h-[680px] max-h-[90vh] p-0 gap-0 bg-muted border-border flex flex-col">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-border">
          <DialogTitle className="text-xl font-semibold text-foreground">{t('settings.title')}</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {t('settings.description')}
          </DialogDescription>
        </DialogHeader>

        {/* Main Content: Left Sidebar + Right Panel */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Navigation */}
          <nav className="w-60 bg-background border-r border-border p-3 space-y-1 overflow-y-auto">
            {categories.map((category) => {
              const Icon = category.icon;
              const isActive = activeCategory === category.id;

              return (
                <button
                  key={category.id}
                  onClick={() => setActiveCategory(category.id)}
                  className={`
                    relative overflow-hidden w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium
                    transition-all duration-200
                    ${
                      isActive
                        ? 'bg-gradient-to-r from-blue-500/15 to-purple-600/10 text-blue-400 before:absolute before:left-0 before:top-1/2 before:-translate-y-1/2 before:h-8 before:w-1 before:rounded-r-full before:bg-gradient-to-b before:from-blue-500 before:to-purple-600'
                        : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
                    }
                  `}
                >
                  <Icon className={`h-4 w-4 ${isActive ? 'text-blue-400' : ''}`} />
                  <span>{category.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Right Content Area */}
          <div className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-background to-muted">
            {/* Fixed Section Header */}
            <div className="flex-shrink-0 px-8 pt-8 pb-4 border-b border-border/50 bg-gradient-to-br from-background to-muted">
              {activeCategory === 'assistant' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.assistant')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.assistant')}</p>
                </>
              )}
              {activeCategory === 'voice-recognition' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.voiceRecognition')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.voiceRecognition')}</p>
                </>
              )}
              {activeCategory === 'ai-model' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.aiModel')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.aiModel')}</p>
                </>
              )}
              {activeCategory === 'tts' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.tts')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.tts')}</p>
                </>
              )}
              {activeCategory === 'shortcuts' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.shortcuts')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.shortcuts')}</p>
                </>
              )}
              {activeCategory === 'appearance' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.appearance')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.appearance')}</p>
                </>
              )}
              {activeCategory === 'advanced' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">{t('settings.categories.advanced')}</h3>
                  <p className="text-sm text-muted-foreground">{t('settings.descriptions.advanced')}</p>
                </>
              )}
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6 animate-in fade-in-50 duration-200">
              {/* Assistant Settings */}
              {activeCategory === 'assistant' && (
                <div className="space-y-6">

                  <div className="space-y-2">
                    <Label htmlFor="system-prompt" className="text-foreground">{t('settings.fields.systemPrompt')}</Label>
                    <textarea
                      id="system-prompt"
                      value={localConfig.system_prompt || ''}
                      onChange={(e) => updateLocalConfig('system_prompt', e.target.value)}
                      placeholder={t('settings.placeholders.systemPrompt')}
                      className="flex min-h-[120px] w-full rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:border-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.systemPrompt')}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">{t('settings.fields.maxHistory')}</Label>
                      <span className="text-sm text-muted-foreground">
                        {localConfig.max_history || 10} {t('settings.fields.items')}
                      </span>
                    </div>
                    <Slider
                      value={[localConfig.max_history || 10]}
                      onValueChange={([value]) => updateLocalConfig('max_history', Math.round(value))}
                      min={5}
                      max={50}
                      step={5}
                      className="w-full [&_[role=slider]]:bg-gradient-to-r [&_[role=slider]]:from-blue-500 [&_[role=slider]]:to-purple-600 [&_[role=slider]]:border-0"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.maxHistory')}
                    </p>
                  </div>
                </div>
              )}

              {/* Voice Recognition Settings */}
              {activeCategory === 'voice-recognition' && (
                <div className="space-y-6">
                  {/* Work Mode Selector - 新增 */}
                  <div className="space-y-2">
                    <Label htmlFor="work-mode" className="text-foreground">
                      {t('settings.fields.workMode')}
                    </Label>
                    <Select
                      value={localConfig.work_mode || workMode}
                      onValueChange={(v) => {
                        // 同时更新 localConfig 和调用 onWorkModeChange
                        updateLocalConfig('work_mode', v);
                        onWorkModeChange?.(v as 'conversation' | 'text-input');
                      }}
                    >
                      <SelectTrigger
                        id="work-mode"
                        className="bg-muted border-border text-foreground
                                   focus:border-blue-500 focus:ring-blue-500
                                   focus-visible:ring-offset-2
                                   focus-visible:ring-offset-background"
                      >
                        <SelectValue placeholder={t('settings.workModes.conversation')} />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="conversation">
                          <div className="flex items-center gap-2">
                            <MessageCircle className="h-4 w-4 text-blue-400" />
                            <span>{t('settings.workModes.conversation')}</span>
                          </div>
                        </SelectItem>
                        <SelectItem value="text-input">
                          <div className="flex items-center gap-2">
                            <Type className="h-4 w-4 text-green-400" />
                            <span>{t('settings.workModes.text')}</span>
                          </div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.workMode')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-foreground">{t('settings.fields.recordingMode')}</Label>
                    <Select
                      value={recordMode}
                      onValueChange={(v) => onRecordModeChange?.(v as 'push-to-talk' | 'continuous')}
                    >
                      <SelectTrigger className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="push-to-talk">{t('settings.fields.pushToTalk')}</SelectItem>
                        <SelectItem value="continuous">{t('settings.fields.continuous')}</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {recordMode === 'push-to-talk'
                        ? t('settings.hints.recordingMode')
                        : t('settings.hints.autoDetection')}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">{t('settings.fields.vadThreshold')}</Label>
                      <span className="text-sm text-muted-foreground">
                        {(localConfig.vad_threshold || 0.5).toFixed(2)}
                      </span>
                    </div>
                    <Slider
                      value={[localConfig.vad_threshold || 0.5]}
                      onValueChange={([value]) => updateLocalConfig('vad_threshold', value)}
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      className="w-full [&_[role=slider]]:bg-gradient-to-r [&_[role=slider]]:from-blue-500 [&_[role=slider]]:to-purple-600 [&_[role=slider]]:border-0"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.vadThreshold')}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">{t('settings.fields.silenceTimeout')}</Label>
                      <span className="text-sm text-muted-foreground">
                        {localConfig.silence_timeout || 1.5}{t('settings.fields.seconds')}
                      </span>
                    </div>
                    <Slider
                      value={[localConfig.silence_timeout || 1.5]}
                      onValueChange={([value]) => updateLocalConfig('silence_timeout', value)}
                      min={0.5}
                      max={5.0}
                      step={0.5}
                      className="w-full [&_[role=slider]]:bg-gradient-to-r [&_[role=slider]]:from-blue-500 [&_[role=slider]]:to-purple-600 [&_[role=slider]]:border-0"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.silenceTimeout')}
                    </p>
                  </div>
                </div>
              )}

              {/* AI Model Settings */}
              {activeCategory === 'ai-model' && (() => {
                const currentProvider = localConfig.llm_provider || 'ollama';
                const providerConfig = getCurrentProviderConfig(localConfig);
                const { base_url = '', api_key = '', model = '' } = providerConfig;

                // Debug: 打印 provider config
                console.log('[Settings] AI Model Settings:', {
                  currentProvider,
                  providerConfig,
                  apiKey: api_key,
                  apiKeyLength: api_key?.length || 0
                });

                return (
                  <div className="space-y-6">
                    <div className="space-y-2">
                      <Label htmlFor="llm-provider" className="text-foreground">{t('settings.fields.llmBackend')}</Label>
                      <Select
                        value={currentProvider}
                        onValueChange={(value) => updateLocalConfig('llm_provider', value)}
                      >
                        <SelectTrigger id="llm-provider" className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                          <SelectValue placeholder={t('settings.placeholders.selectLlmBackend')} />
                        </SelectTrigger>
                        <SelectContent className="bg-muted border-border">
                          <SelectItem value="ollama">Ollama (Local)</SelectItem>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="openrouter">OpenRouter</SelectItem>
                          <SelectItem value="zhipu">智谱AI (BigModel)</SelectItem>
                          <SelectItem value="custom">Custom (OpenAI-compatible)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {/* API Key (for providers that require it) */}
                    {['openai', 'openrouter', 'custom', 'zhipu'].includes(currentProvider) && (
                      <div className="space-y-2">
                        <Label htmlFor="provider-api-key" className="text-foreground">
                          {currentProvider === 'zhipu' ? '智谱AI API Key' : `${currentProvider === 'custom' ? 'API Key (Optional)' : `${currentProvider.charAt(0).toUpperCase() + currentProvider.slice(1)} API Key`}`}
                        </Label>
                        <div className="relative">
                          <Input
                            id="provider-api-key"
                            type={showApiKey ? 'text' : 'password'}
                            value={api_key}
                            onChange={(e) => updateProviderConfig('api_key', e.target.value)}
                            placeholder={currentProvider === 'custom' ? 'Optional - leave empty if not required' : t('settings.placeholders.apiKey')}
                            className="bg-muted border-border text-foreground pr-10 focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                          />
                          <button
                            type="button"
                            onClick={() => setShowApiKey(!showApiKey)}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {currentProvider === 'custom' ? 'API key for your custom endpoint (if required)' : t('settings.hints.apiKey')}
                        </p>
                      </div>
                    )}

                    {/* Base URL (for providers that need it) */}
                    {['custom', 'ollama', 'zhipu'].includes(currentProvider) && (
                      <div className="space-y-2">
                        <Label htmlFor="provider-base-url" className="text-foreground">
                          {currentProvider === 'ollama' ? t('settings.fields.ollamaUrl') : 'API Base URL'}
                        </Label>
                        <Input
                          id="provider-base-url"
                          value={base_url}
                          onChange={(e) => updateProviderConfig('base_url', e.target.value)}
                          placeholder={
                            currentProvider === 'ollama' ? t('settings.placeholders.ollamaUrl') :
                            currentProvider === 'zhipu' ? 'https://open.bigmodel.cn/api/paas/v4' :
                            'http://localhost:8000/v1'
                          }
                          className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                        />
                        <p className="text-xs text-muted-foreground">
                          {currentProvider === 'ollama' ? t('settings.hints.ollamaUrl') :
                           currentProvider === 'zhipu' ? 'ZhipuAI API endpoint (default: https://open.bigmodel.cn/api/paas/v4)' :
                           'Base URL of your OpenAI-compatible API (e.g., http://localhost:8000/v1)'}
                        </p>
                      </div>
                    )}

                    {/* Model Selection */}
                    <div className="space-y-2">
                      {currentProvider === 'ollama' && (
                        <div className="flex items-center justify-between">
                          <Label htmlFor="provider-model" className="text-foreground">{t('settings.fields.ollamaModel')}</Label>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={async () => {
                              setIsLoadingOllamaModels(true);
                              try {
                                const models = await invoke<string[]>('list_ollama_models', {
                                  baseUrl: base_url || 'http://localhost:11434'
                                });
                                setOllamaModels(models);
                                alert(`Found ${models.length} models:\n\n${models.join('\n')}`);
                              } catch (error) {
                                console.error('[Settings] Failed to load models:', error);
                                alert('Failed to load Ollama models. Make sure Ollama is running.');
                              } finally {
                                setIsLoadingOllamaModels(false);
                              }
                            }}
                            disabled={isLoadingOllamaModels}
                            className="h-7 px-2 text-xs"
                          >
                            <RefreshCw className={`h-3 w-3 mr-1 ${isLoadingOllamaModels ? 'animate-spin' : ''}`} />
                            Refresh
                          </Button>
                        </div>
                      )}
                      {currentProvider !== 'ollama' && (
                        <Label htmlFor="provider-model" className="text-foreground">Model</Label>
                      )}
                      {customModelInput[currentProvider as keyof typeof customModelInput] ? (
                        <div className="flex gap-2">
                          <Input
                            id="provider-model"
                            value={model}
                            onChange={(e) => updateProviderConfig('model', e.target.value)}
                            placeholder="Enter custom model name"
                            className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950 flex-1"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => setCustomModelInput(prev => ({ ...prev, [currentProvider]: false }))}
                            className="h-9 px-3"
                          >
                            ← Select
                          </Button>
                        </div>
                      ) : (
                        <Select
                          value={model || (
                            currentProvider === 'openai' ? 'gpt-4o-mini' :
                            currentProvider === 'openrouter' ? 'google/gemini-2.5-flash' :
                            currentProvider === 'zhipu' ? 'glm-4-flash' :
                            currentProvider === 'custom' ? CUSTOM_MODELS[0] :
                            ollamaModels[0]
                          )}
                          onValueChange={(value) => {
                            if (value === '__custom__') {
                              setCustomModelInput(prev => ({ ...prev, [currentProvider]: true }));
                            } else {
                              updateProviderConfig('model', value);
                            }
                          }}
                        >
                          <SelectTrigger id="provider-model" className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                            <SelectValue placeholder="Select a model" />
                          </SelectTrigger>
                          <SelectContent className="bg-muted border-border max-h-60">
                            {currentProvider === 'openai' && OPENAI_MODELS.map(m => (
                              <SelectItem key={m} value={m} className="text-foreground">{m}</SelectItem>
                            ))}
                            {currentProvider === 'openrouter' && OPENROUTER_MODELS.map(m => (
                              <SelectItem key={m} value={m} className="text-foreground">{m}</SelectItem>
                            ))}
                            {currentProvider === 'zhipu' && ZHIPU_MODELS.map(m => (
                              <SelectItem key={m} value={m} className="text-foreground">{m}</SelectItem>
                            ))}
                            {currentProvider === 'custom' && CUSTOM_MODELS.map(m => (
                              <SelectItem key={m} value={m} className="text-foreground">{m}</SelectItem>
                            ))}
                            {currentProvider === 'ollama' && ollamaModels.map(m => (
                              <SelectItem key={m} value={m} className="text-foreground">{m}</SelectItem>
                            ))}
                            <SelectItem value="__custom__" className="text-foreground">Custom model...</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                      <p className="text-xs text-muted-foreground">
                        {currentProvider === 'ollama' ? t('settings.hints.ollamaModel') :
                         currentProvider === 'openai' ? 'Select from common models or enter a custom model name' :
                         currentProvider === 'openrouter' ? 'Select from popular models or enter any OpenRouter model ID' :
                         currentProvider === 'zhipu' ? 'Select from popular ZhipuAI models or enter a custom model name' :
                         'Select from common models or enter your model name'}
                      </p>
                    </div>

                    <div className="pt-2 space-y-2">
                      <Button
                        onClick={handleTestConnection}
                        disabled={isTestingConnection}
                        className="w-full bg-muted hover:bg-muted/80 text-foreground border border-border"
                      >
                        {isTestingConnection ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            {t('settings.connection.testing')}
                          </>
                        ) : connectionStatus === 'success' ? (
                          <>
                            <CheckCircle2 className="h-4 w-4 mr-2 text-green-400" />
                            {t('settings.connection.success')}
                          </>
                        ) : connectionStatus === 'error' ? (
                          <>
                            <XCircle className="h-4 w-4 mr-2 text-red-400" />
                            {t('settings.connection.failed')}
                          </>
                        ) : (
                          t('settings.connection.test')
                        )}
                      </Button>
                      {connectionStatus === 'error' && connectionError && (
                        <p className="text-xs text-red-400 px-2">
                          {connectionError}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* TTS Settings */}
              {activeCategory === 'tts' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="tts-rate" className="text-foreground">{t('settings.fields.ttsRate')}</Label>
                    <Input
                      id="tts-rate"
                      value={localConfig.tts_rate || '+0%'}
                      onChange={(e) => updateLocalConfig('tts_rate', e.target.value)}
                      placeholder="+0%"
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.ttsRate')}
                    </p>
                  </div>

                  <div className="flex items-center justify-between py-2 px-3 rounded-lg border border-border bg-muted">
                    <div className="space-y-0.5">
                      <Label htmlFor="auto-tts" className="text-foreground">{t('settings.fields.autoTTS')}</Label>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.hints.autoTTS')}
                      </p>
                    </div>
                    <Switch
                      id="auto-tts"
                      checked={autoTTS}
                      onCheckedChange={onAutoTTSChange}
                      className="data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-blue-500 data-[state=checked]:to-purple-600"
                    />
                  </div>

                  <div className="pt-2 space-y-2">
                    <Button
                      onClick={handlePreviewTTS}
                      disabled={isPreviewingTTS && connectionStatus !== 'error'}
                      className="w-full bg-muted hover:bg-muted/80 text-foreground border border-border"
                    >
                      {isPreviewingTTS ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          {t('status.loading')}
                        </>
                      ) : (
                        <>
                          <Volume2 className="h-4 w-4 mr-2" />
                          {t('settings.tts.preview')}
                        </>
                      )}
                    </Button>
                    {connectionStatus === 'error' && connectionError && (
                      <p className="text-xs text-red-400 px-2">
                        {connectionError}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* Shortcuts Settings */}
              {activeCategory === 'shortcuts' && (
                <div className="space-y-6">
                  {/* Push-to-Talk Hotkey */}
                  <div className="space-y-2">
                    <Label className="text-foreground">{t('settings.fields.pushToTalk')}</Label>
                    <p className="text-sm text-muted-foreground">
                      {t('settings.hints.ptt')}
                    </p>
                    <HotkeyRecorder
                      value={config?.push_to_talk_hotkey || {
                        modifiers: ['CmdOrCtrl'],
                        key: 'Digit3',
                        displayName: '⌘3',
                      }}
                      onChange={(hotkey) => updateHotkey(hotkey)}
                      disabled={saveStatus === 'saving'}
                    />
                  </div>

                  {/* Show/Hide Window Info */}
                  <div className="p-4 rounded-lg border border-border bg-muted">
                    <div className="flex items-center justify-between">
                      <div className="space-y-0.5">
                        <Label className="text-foreground">{t('settings.fields.toggleWindow')}</Label>
                        <p className="text-xs text-muted-foreground">
                          {t('settings.hints.toggleWindow')}
                        </p>
                      </div>
                      <kbd className="px-3 py-1.5 text-xs font-mono font-semibold text-foreground bg-muted/80 border border-border rounded-md shadow-sm">
                        ⌘⇧Space
                      </kbd>
                    </div>
                  </div>
                </div>
              )}

              {/* Appearance Settings */}
              {activeCategory === 'appearance' && (
                <div className="space-y-6">
                  <div className="p-4 rounded-lg border border-border bg-muted">
                    <div className="flex items-center justify-between mb-2">
                      <div className="space-y-0.5">
                        <Label className="text-foreground">{t('settings.fields.theme')}</Label>
                        <p className="text-xs text-muted-foreground">
                          Choose interface theme
                        </p>
                      </div>
                      <ThemeToggle />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      {t('settings.hints.theme')}
                    </p>
                  </div>

                  <div className="p-4 rounded-lg border border-border bg-muted">
                    <div className="flex items-center justify-between mb-2">
                      <div className="space-y-0.5">
                        <Label className="text-foreground">{t('settings.fields.language')}</Label>
                        <p className="text-xs text-muted-foreground">
                          Select interface language
                        </p>
                      </div>
                      <LanguageSwitcher />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      {t('settings.hints.language')}
                    </p>
                  </div>
                </div>
              )}

              {/* Advanced Settings */}
              {activeCategory === 'advanced' && (
                <div className="space-y-6">
                  <div className="p-4 rounded-lg border border-border bg-muted">
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-foreground">{t('settings.fields.serviceStatus')}</Label>
                      <span className="flex items-center gap-2 text-sm">
                        <span className="h-2 w-2 rounded-full bg-green-400"></span>
                        <span className="text-muted-foreground">{t('settings.fields.running')}</span>
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {t('settings.service.allServicesNormal')}
                    </p>
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-foreground mb-3">{t('settings.danger.title')}</h4>
                    <Button
                      variant="outline"
                      className="w-full justify-start bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/30"
                      onClick={() => {
                        if (confirm(t('settings.danger.clearHistoryConfirm'))) {
                          onClearHistory?.();
                          onClose();
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {t('settings.danger.clearHistory')}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-border bg-gradient-to-t from-background to-background/95 backdrop-blur-sm">
          <SaveStatusIndicator status={saveStatus} error={saveError} />
          <Button variant="outline" onClick={onClose} className="bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground">
            {t('buttons.close')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
