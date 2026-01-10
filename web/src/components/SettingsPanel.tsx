import React, { useState, useEffect } from 'react';
import { AppConfig, PywebviewApi } from '../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  api?: PywebviewApi;
}

export function SettingsPanel({ isOpen, onClose, api }: Props) {
  const [config, setConfig] = useState<AppConfig>({
    llm_backend: 'ollama',
    ollama_model: 'qwen2.5:1.5b',
    ollama_base_url: 'http://localhost:11434',
    tts_backend: 'edge',
    tts_rate: '+0%',
    vad_threshold: 0.7,
    max_history: 10
  });

  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && api) {
      api.get_config().then(setConfig);
    }
  }, [isOpen, api]);

  const handleSave = async () => {
    if (!api) return;
    setIsLoading(true);

    try {
      await api.save_config(config);
      await api.restart_assistant();
      onClose();
    } catch (error) {
      console.error('保存配置失败:', error);
      alert('保存失败，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-2xl">
            <span>⚙️</span>
            <span>设置</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <section className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              🤖 LLM 配置
            </h3>
            
            <div className="grid gap-4">
              <div className="space-y-2">
                <Label>后端</Label>
                <Select
                  value={config.llm_backend}
                  onValueChange={(value) => setConfig(prev => ({ ...prev, llm_backend: value as 'claude' | 'ollama' }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="claude">Claude Code CLI</SelectItem>
                    <SelectItem value="ollama">Ollama（本地）</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {config.llm_backend === 'ollama' && (
                <>
                  <div className="space-y-2">
                    <Label>Ollama 模型</Label>
                    <Input
                      value={config.ollama_model}
                      onChange={(e) => setConfig(prev => ({ ...prev, ollama_model: e.target.value }))}
                      placeholder="qwen2.5:7b"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>API 地址</Label>
                    <Input
                      value={config.ollama_base_url}
                      onChange={(e) => setConfig(prev => ({ ...prev, ollama_base_url: e.target.value }))}
                      placeholder="http://localhost:11434"
                    />
                  </div>
                </>
              )}
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              🔊 TTS 配置
            </h3>
            
            <div className="grid gap-4">
              <div className="space-y-2">
                <Label>后端</Label>
                <Select
                  value={config.tts_backend}
                  onValueChange={(value) => setConfig(prev => ({ ...prev, tts_backend: value as 'edge' | 'piper' }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="edge">Edge TTS（在线，高音质）</SelectItem>
                    <SelectItem value="piper">Piper（离线，快速）</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-4">
                <div>
                  <Label>语速: {config.tts_rate}</Label>
                  <Slider
                    value={[parseInt(config.tts_rate) || 0]}
                    onValueChange={(value) => setConfig(prev => ({ ...prev, tts_rate: `${value[0]}%` }))}
                    min={-50}
                    max={50}
                    step={5}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground mt-1">
                    <span>-50%</span>
                    <span>+0%</span>
                    <span>+50%</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              🎤 VAD 配置
            </h3>
            
            <div className="space-y-4">
              <div>
                <Label>语音检测阈值: {config.vad_threshold.toFixed(2)}</Label>
                <Slider
                  value={[config.vad_threshold]}
                  onValueChange={(value) => setConfig(prev => ({ ...prev, vad_threshold: value[0] }))}
                  min={0.1}
                  max={0.9}
                  step={0.05}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span className="text-destructive">更敏感 (0.1)</span>
                  <span>默认 0.7</span>
                  <span className="text-primary">更严格 (0.9)</span>
                </div>
              </div>
            </div>
          </section>

          <Separator />

          <section className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              💾 对话设置
            </h3>
            
            <div className="space-y-2">
              <div>
                <Label>最大历史轮数: {config.max_history}</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={config.max_history.toString()}
                  onChange={(e) => setConfig(prev => ({ ...prev, max_history: parseInt(e.target.value) || 10 }))}
                />
              </div>
            </div>
          </section>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={isLoading}>
            {isLoading ? '💾 保存中...' : '💾 保存并重启'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
