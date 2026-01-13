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
} from 'lucide-react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from '@/i18n';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
  config: Record<string, any> | null;
  onSave: (config: Record<string, any>) => Promise<void>;
  autoTTS?: boolean;
  onAutoTTSChange?: (value: boolean) => void;
  recordMode?: 'push-to-talk' | 'continuous';
  onRecordModeChange?: (value: 'push-to-talk' | 'continuous') => void;
  workMode?: 'conversation' | 'text';
  onWorkModeChange?: (value: 'conversation' | 'text') => void;
  onClearHistory?: () => void;
}

type SettingsCategory = 'assistant' | 'voice-recognition' | 'ai-model' | 'tts' | 'shortcuts' | 'appearance' | 'advanced';

export function Settings({
  isOpen,
  onClose,
  config,
  onSave,
  autoTTS,
  onAutoTTSChange,
  recordMode,
  onRecordModeChange,
  workMode,
  onWorkModeChange,
  onClearHistory,
}: SettingsProps) {
  const { t } = useTranslation();
  const [localConfig, setLocalConfig] = React.useState<Record<string, any>>({});
  const [isSaving, setIsSaving] = React.useState(false);
  const [activeCategory, setActiveCategory] = React.useState<SettingsCategory>('assistant');
  const [showApiKey, setShowApiKey] = React.useState(false);
  const [isTestingConnection, setIsTestingConnection] = React.useState(false);
  const [connectionStatus, setConnectionStatus] = React.useState<'idle' | 'success' | 'error'>('idle');
  const [connectionError, setConnectionError] = React.useState<string>('');
  const [isPreviewingTTS, setIsPreviewingTTS] = React.useState(false);
  const [previewAudio, setPreviewAudio] = React.useState<HTMLAudioElement | null>(null);

  React.useEffect(() => {
    if (config) {
      setLocalConfig({ ...config });
    }
  }, [config]);

  // 清理音频播放器
  React.useEffect(() => {
    return () => {
      if (previewAudio) {
        previewAudio.pause();
        previewAudio.src = '';
      }
    };
  }, [previewAudio]);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(localConfig);
      onClose();
    } catch (error) {
      console.error('Failed to save config:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const updateConfig = (key: string, value: any) => {
    setLocalConfig(prev => ({ ...prev, [key]: value }));
  };

  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setConnectionStatus('idle');
    setConnectionError('');

    try {
      // 调用 Rust 后端的测试连接命令
      const result = await invoke<{
        success: boolean;
        message?: string;
        error?: string;
      }>('test_ollama_connection', {
        baseUrl: localConfig.ollama_base_url || 'http://localhost:11434',
        model: localConfig.ollama_model || 'qwen2.5:1.5b'
      });

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
      }
    } catch (error) {
      console.error('[Settings] TTS preview error:', error);
      setIsPreviewingTTS(false);
      setConnectionStatus('error');
      setConnectionError(String(error));
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
                      onChange={(e) => updateConfig('system_prompt', e.target.value)}
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
                      onValueChange={([value]) => updateConfig('max_history', Math.round(value))}
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
                        updateConfig('work_mode', v);
                        onWorkModeChange?.(v as 'conversation' | 'text');
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
                        <SelectItem value="text">
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
                      onValueChange={([value]) => updateConfig('vad_threshold', value)}
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
                      onValueChange={([value]) => updateConfig('silence_timeout', value)}
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
              {activeCategory === 'ai-model' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="llm-backend" className="text-foreground">{t('settings.fields.llmBackend')}</Label>
                    <Select
                      value={localConfig.llm_backend || 'ollama'}
                      onValueChange={(value) => updateConfig('llm_backend', value)}
                    >
                      <SelectTrigger id="llm-backend" className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                        <SelectValue placeholder={t('settings.placeholders.selectLlmBackend')} />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="ollama">Ollama (Local)</SelectItem>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="api-key" className="text-foreground">{t('settings.fields.apiKey')}</Label>
                    <div className="relative">
                      <Input
                        id="api-key"
                        type={showApiKey ? 'text' : 'password'}
                        value={localConfig.api_key || ''}
                        onChange={(e) => updateConfig('api_key', e.target.value)}
                        placeholder={t('settings.placeholders.apiKey')}
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
                      {t('settings.hints.apiKey')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="model-name" className="text-foreground">{t('settings.fields.ollamaModel')}</Label>
                    <Input
                      id="model-name"
                      value={localConfig.ollama_model || ''}
                      onChange={(e) => updateConfig('ollama_model', e.target.value)}
                      placeholder={t('settings.placeholders.ollamaModel')}
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.ollamaModel')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="ollama-base-url" className="text-foreground">{t('settings.fields.ollamaUrl')}</Label>
                    <Input
                      id="ollama-base-url"
                      value={localConfig.ollama_base_url || ''}
                      onChange={(e) => updateConfig('ollama_base_url', e.target.value)}
                      placeholder={t('settings.placeholders.ollamaUrl')}
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      {t('settings.hints.ollamaUrl')}
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
              )}

              {/* TTS Settings */}
              {activeCategory === 'tts' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="tts-rate" className="text-foreground">{t('settings.fields.ttsRate')}</Label>
                    <Input
                      id="tts-rate"
                      value={localConfig.tts_rate || '+0%'}
                      onChange={(e) => updateConfig('tts_rate', e.target.value)}
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
                  <div className="space-y-3">
                    <div className="p-4 rounded-lg border border-border bg-muted">
                      <div className="flex items-center justify-between mb-2">
                        <Label className="text-foreground">{t('settings.fields.pushToTalk')}</Label>
                        <kbd className="px-3 py-1.5 text-xs font-mono font-semibold text-foreground bg-muted/80 border border-border rounded-md shadow-sm">
                          Cmd + Alt
                        </kbd>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t('settings.hints.ptt')}
                      </p>
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
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-border bg-gradient-to-t from-background to-background/95 backdrop-blur-sm">
          <Button variant="outline" onClick={onClose} className="bg-transparent border-border text-muted-foreground hover:bg-muted hover:text-foreground">
            {t('buttons.cancel')}
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-foreground border-0"
          >
            {isSaving ? t('status.loading') : t('buttons.saveSettings')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
