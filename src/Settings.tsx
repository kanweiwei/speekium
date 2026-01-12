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
  Trash2
} from 'lucide-react';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
  config: Record<string, any> | null;
  onSave: (config: Record<string, any>) => Promise<void>;
  autoTTS?: boolean;
  onAutoTTSChange?: (value: boolean) => void;
  recordMode?: 'push-to-talk' | 'continuous';
  onRecordModeChange?: (value: 'push-to-talk' | 'continuous') => void;
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
  onClearHistory,
}: SettingsProps) {
  const [localConfig, setLocalConfig] = React.useState<Record<string, any>>({});
  const [isSaving, setIsSaving] = React.useState(false);
  const [activeCategory, setActiveCategory] = React.useState<SettingsCategory>('assistant');
  const [showApiKey, setShowApiKey] = React.useState(false);
  const [isTestingConnection, setIsTestingConnection] = React.useState(false);
  const [connectionStatus, setConnectionStatus] = React.useState<'idle' | 'success' | 'error'>('idle');

  React.useEffect(() => {
    if (config) {
      setLocalConfig({ ...config });
    }
  }, [config]);

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

    // TODO: Implement actual connection test
    await new Promise(resolve => setTimeout(resolve, 1500));

    // Simulate success/error
    const success = Math.random() > 0.3;
    setConnectionStatus(success ? 'success' : 'error');
    setIsTestingConnection(false);
  };

  const handlePreviewTTS = () => {
    // TODO: Implement TTS preview
    console.log('Preview TTS with current settings');
  };

  const categories = [
    { id: 'assistant' as const, label: '助手设置', icon: Bot },
    { id: 'voice-recognition' as const, label: '语音识别', icon: Mic },
    { id: 'ai-model' as const, label: 'AI 模型', icon: Brain },
    { id: 'tts' as const, label: '语音合成', icon: Volume2 },
    { id: 'shortcuts' as const, label: '快捷键', icon: Keyboard },
    { id: 'appearance' as const, label: '外观设置', icon: Palette },
    { id: 'advanced' as const, label: '高级设置', icon: Zap },
  ];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-[900px] w-[95vw] h-[680px] max-h-[90vh] p-0 gap-0 bg-muted border-border flex flex-col">
        {/* Header */}
        <DialogHeader className="px-6 py-4 border-b border-border">
          <DialogTitle className="text-xl font-semibold text-foreground">设置</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            配置语音助手的各项参数
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
                  <h3 className="text-lg font-semibold text-foreground mb-1">助手设置</h3>
                  <p className="text-sm text-muted-foreground">配置 AI 助手的行为和对话参数</p>
                </>
              )}
              {activeCategory === 'voice-recognition' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">语音识别</h3>
                  <p className="text-sm text-muted-foreground">配置录音模式和语音检测参数</p>
                </>
              )}
              {activeCategory === 'ai-model' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">AI 模型</h3>
                  <p className="text-sm text-muted-foreground">选择 AI 服务商和模型配置</p>
                </>
              )}
              {activeCategory === 'tts' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">语音合成</h3>
                  <p className="text-sm text-muted-foreground">配置文本转语音引擎和参数</p>
                </>
              )}
              {activeCategory === 'shortcuts' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">快捷键</h3>
                  <p className="text-sm text-muted-foreground">查看和配置快捷键</p>
                </>
              )}
              {activeCategory === 'appearance' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">外观设置</h3>
                  <p className="text-sm text-muted-foreground">自定义界面外观和主题</p>
                </>
              )}
              {activeCategory === 'advanced' && (
                <>
                  <h3 className="text-lg font-semibold text-foreground mb-1">高级设置</h3>
                  <p className="text-sm text-muted-foreground">危险操作和系统信息</p>
                </>
              )}
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-8 py-6 space-y-6 animate-in fade-in-50 duration-200">
              {/* Assistant Settings */}
              {activeCategory === 'assistant' && (
                <div className="space-y-6">

                  <div className="space-y-2">
                    <Label htmlFor="system-prompt" className="text-foreground">系统提示词</Label>
                    <textarea
                      id="system-prompt"
                      value={localConfig.system_prompt || ''}
                      onChange={(e) => updateConfig('system_prompt', e.target.value)}
                      placeholder="你是一个有帮助的语音助手..."
                      className="flex min-h-[120px] w-full rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50 focus-visible:border-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    />
                    <p className="text-xs text-muted-foreground">
                      自定义 AI 助手的行为和角色
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">最大历史记录</Label>
                      <span className="text-sm text-muted-foreground">
                        {localConfig.max_history || 10} 条
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
                      保留的对话历史条数
                    </p>
                  </div>
                </div>
              )}

              {/* Voice Recognition Settings */}
              {activeCategory === 'voice-recognition' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label className="text-foreground">录音模式</Label>
                    <Select
                      value={recordMode}
                      onValueChange={(v) => onRecordModeChange?.(v as 'push-to-talk' | 'continuous')}
                    >
                      <SelectTrigger className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="push-to-talk">按键录音 (推荐)</SelectItem>
                        <SelectItem value="continuous">自动检测</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {recordMode === 'push-to-talk'
                        ? '按住 Cmd+Alt 开始录音，松开停止'
                        : '自动检测语音开始和结束'}
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">VAD 灵敏度</Label>
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
                      语音活动检测灵敏度，值越低越敏感
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label className="text-foreground">静音检测时长</Label>
                      <span className="text-sm text-muted-foreground">
                        {localConfig.silence_timeout || 1.5}s
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
                      检测到静音后等待的时间
                    </p>
                  </div>
                </div>
              )}

              {/* AI Model Settings */}
              {activeCategory === 'ai-model' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="llm-backend" className="text-foreground">服务商</Label>
                    <Select
                      value={localConfig.llm_backend || 'ollama'}
                      onValueChange={(value) => updateConfig('llm_backend', value)}
                    >
                      <SelectTrigger id="llm-backend" className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                        <SelectValue placeholder="选择 LLM 后端" />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="ollama">Ollama (本地)</SelectItem>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="api-key" className="text-foreground">API Key</Label>
                    <div className="relative">
                      <Input
                        id="api-key"
                        type={showApiKey ? 'text' : 'password'}
                        value={localConfig.api_key || ''}
                        onChange={(e) => updateConfig('api_key', e.target.value)}
                        placeholder="sk-..."
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
                      仅在使用云端服务时需要填写
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="model-name" className="text-foreground">模型名称</Label>
                    <Input
                      id="model-name"
                      value={localConfig.ollama_model || ''}
                      onChange={(e) => updateConfig('ollama_model', e.target.value)}
                      placeholder="qwen2.5:1.5b"
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      输入模型名称，如 qwen2.5:1.5b, llama3.2:latest
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="ollama-base-url" className="text-foreground">API URL</Label>
                    <Input
                      id="ollama-base-url"
                      value={localConfig.ollama_base_url || ''}
                      onChange={(e) => updateConfig('ollama_base_url', e.target.value)}
                      placeholder="http://localhost:11434"
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      API 服务地址，默认为本地 Ollama 服务
                    </p>
                  </div>

                  <div className="pt-2">
                    <Button
                      onClick={handleTestConnection}
                      disabled={isTestingConnection}
                      className="w-full bg-muted hover:bg-zinc-700 text-foreground border border-border"
                    >
                      {isTestingConnection ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          测试中...
                        </>
                      ) : connectionStatus === 'success' ? (
                        <>
                          <CheckCircle2 className="h-4 w-4 mr-2 text-green-400" />
                          连接成功
                        </>
                      ) : connectionStatus === 'error' ? (
                        <>
                          <XCircle className="h-4 w-4 mr-2 text-red-400" />
                          连接失败
                        </>
                      ) : (
                        '测试连接'
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* TTS Settings */}
              {activeCategory === 'tts' && (
                <div className="space-y-6">
                  <div className="space-y-2">
                    <Label htmlFor="tts-backend" className="text-foreground">TTS 引擎</Label>
                    <Select
                      value={localConfig.tts_backend || 'piper'}
                      onValueChange={(value) => updateConfig('tts_backend', value)}
                    >
                      <SelectTrigger id="tts-backend" className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950">
                        <SelectValue placeholder="选择 TTS 后端" />
                      </SelectTrigger>
                      <SelectContent className="bg-muted border-border">
                        <SelectItem value="piper">Piper (离线)</SelectItem>
                        <SelectItem value="edge">Edge TTS (在线)</SelectItem>
                        <SelectItem value="openai">OpenAI TTS</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="tts-rate" className="text-foreground">语速调整</Label>
                    <Input
                      id="tts-rate"
                      value={localConfig.tts_rate || '+0%'}
                      onChange={(e) => updateConfig('tts_rate', e.target.value)}
                      placeholder="+0%"
                      className="bg-muted border-border text-foreground focus:border-blue-500 focus:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-zinc-950"
                    />
                    <p className="text-xs text-muted-foreground">
                      语速调整，如 +0%、+20%、-10%
                    </p>
                  </div>

                  <div className="flex items-center justify-between py-2 px-3 rounded-lg border border-border bg-muted">
                    <div className="space-y-0.5">
                      <Label htmlFor="auto-tts" className="text-foreground">自动播放</Label>
                      <p className="text-xs text-muted-foreground">
                        AI 回复后自动朗读
                      </p>
                    </div>
                    <Switch
                      id="auto-tts"
                      checked={autoTTS}
                      onCheckedChange={onAutoTTSChange}
                      className="data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-blue-500 data-[state=checked]:to-purple-600"
                    />
                  </div>

                  <div className="pt-2">
                    <Button
                      onClick={handlePreviewTTS}
                      className="w-full bg-muted hover:bg-zinc-700 text-foreground border border-border"
                    >
                      <Volume2 className="h-4 w-4 mr-2" />
                      预览语音
                    </Button>
                  </div>
                </div>
              )}

              {/* Shortcuts Settings */}
              {activeCategory === 'shortcuts' && (
                <div className="space-y-6">
                  <div className="space-y-3">
                    <div className="p-4 rounded-lg border border-border bg-muted">
                      <div className="flex items-center justify-between mb-2">
                        <Label className="text-foreground">按键录音 (PTT)</Label>
                        <kbd className="px-3 py-1.5 text-xs font-mono font-semibold text-foreground bg-muted/80 border border-border rounded-md shadow-sm">
                          Cmd + Alt
                        </kbd>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        按住开始录音，松开停止并发送
                      </p>
                    </div>

                    <div className="p-4 rounded-lg border border-border bg-muted opacity-50">
                      <div className="flex items-center justify-between mb-2">
                        <Label className="text-foreground">全局唤醒</Label>
                        <kbd className="px-3 py-1.5 text-xs font-mono font-semibold text-foreground bg-muted/80 border border-border rounded-md shadow-sm">
                          未设置
                        </kbd>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        即将推出...
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
                        <Label className="text-foreground">主题模式</Label>
                        <p className="text-xs text-muted-foreground">
                          选择界面外观主题
                        </p>
                      </div>
                      <ThemeToggle />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">
                      点击图标切换：浅色 → 深色 → 跟随系统
                    </p>
                  </div>
                </div>
              )}

              {/* Advanced Settings */}
              {activeCategory === 'advanced' && (
                <div className="space-y-6">
                  <div className="p-4 rounded-lg border border-border bg-muted">
                    <div className="flex items-center justify-between mb-2">
                      <Label className="text-foreground">服务状态</Label>
                      <span className="flex items-center gap-2 text-sm">
                        <span className="h-2 w-2 rounded-full bg-green-400"></span>
                        <span className="text-muted-foreground">运行中</span>
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      所有服务正常运行
                    </p>
                  </div>

                  <div className="pt-4 border-t border-border">
                    <h4 className="text-sm font-medium text-foreground mb-3">危险操作</h4>
                    <Button
                      variant="outline"
                      className="w-full justify-start bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20 hover:text-red-300 hover:border-red-500/30"
                      onClick={() => {
                        if (confirm('确定要清空所有历史记录吗？此操作不可恢复。')) {
                          onClearHistory?.();
                          onClose();
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      清空历史记录
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
            取消
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-foreground border-0"
          >
            {isSaving ? '保存中...' : '保存设置'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
