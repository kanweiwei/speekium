import { useState } from 'react';
import { Plus, X, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';

interface Template {
  id: string;
  name: string;
  description: string;
  icon: string;
  prompt: string;
}

interface ConversationTemplatesProps {
  onSelectTemplate: (prompt: string) => void;
  onClose: () => void;
  className?: string;
}

/**
 * 预设对话模板
 */
const PRESET_TEMPLATES: Template[] = [
  {
    id: 'interview',
    name: '面试模拟',
    description: '模拟技术面试官，帮你练习',
    icon: '🎤',
    prompt: '你是一位资深的技術面試官，專注於軟體工程師職位。你會根據求職者的經驗水平提出相關的技術問題，包括但不限於：\n- 數據結構與算法\n- 系統設計\n- 编程语言特性\n- 項目經驗深入\n\n請用中文提問，並根據求職者的回答給予反饋和改進建議。',
  },
  {
    id: 'language',
    name: '语言学习',
    description: '外语陪练，纠正语法',
    icon: '🌍',
    prompt: '你是一位耐心的语言学习陪练。我会发送中文或英文句子请你翻译，或者请你纠正我的外语语法错误。请：\n1. 提供准确的翻译\n2. 指出语法错误并解释原因\n3. 给出改进建议\n\n请用中文回复。',
  },
  {
    id: 'business',
    name: '商务邮件',
    description: '帮你撰写专业邮件',
    icon: '💼',
    prompt: '你是一位专业的商务邮件写作助手。请帮我撰写专业、简洁、清晰的商务邮件。\n\n请根据我提供的主题和要点：\n1. 撰写完整的邮件内容\n2. 使用恰当的商业用语\n3. 确保格式规范\n\n请用中文回复邮件内容。',
  },
  {
    id: 'code-review',
    name: '代码审查',
    description: '代码评审建议',
    icon: '👨‍💻',
    prompt: '你是一位资深的代码审查专家。请帮我审查代码并提供改进建议。\n\n请从以下方面审查：\n1. 代码质量和可读性\n2. 潜在的 bug 和问题\n3. 性能优化建议\n4. 安全问题\n5. 最佳实践\n\n请用中文详细说明问题和建议。',
  },
];

/**
 * ConversationTemplates - 对话模板选择组件
 */
export function ConversationTemplates({
  onSelectTemplate,
  onClose,
  className
}: ConversationTemplatesProps) {
  const { t } = useTranslation();
  const [customMode, setCustomMode] = useState(false);
  const [customName, setCustomName] = useState('');
  const [customPrompt, setCustomPrompt] = useState('');

  const handleSelectTemplate = (template: Template) => {
    onSelectTemplate(template.prompt);
    onClose();
  };

  const handleSaveCustom = () => {
    if (customName && customPrompt) {
      const customTemplate: Template = {
        id: 'custom-' + Date.now(),
        name: customName,
        description: '自定义模板',
        icon: '➕',
        prompt: customPrompt,
      };
      // 保存到 localStorage
      const saved = localStorage.getItem('customTemplates');
      const templates = saved ? JSON.parse(saved) : [];
      templates.push(customTemplate);
      localStorage.setItem('customTemplates', JSON.stringify(templates));
      
      onSelectTemplate(customPrompt);
      onClose();
    }
  };

  return (
    <div className={cn("absolute inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4", className)}>
      <div className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">💬 {t('app.templates.title') || '对话模板'}</h2>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 max-h-[60vh] overflow-y-auto">
          {!customMode ? (
            <>
              {/* 预设模板 */}
              <div className="grid gap-3">
                {PRESET_TEMPLATES.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => handleSelectTemplate(template)}
                    className="flex items-start gap-3 p-4 rounded-xl border border-border bg-muted/50 hover:bg-muted transition-all hover:border-blue-500/50 text-left group"
                  >
                    <span className="text-2xl">{template.icon}</span>
                    <div className="flex-1">
                      <h3 className="font-medium text-foreground group-hover:text-blue-400 transition-colors">
                        {template.name}
                      </h3>
                      <p className="text-sm text-muted-foreground mt-0.5">
                        {template.description}
                      </p>
                    </div>
                  </button>
                ))}
              </div>

              {/* 自定义模板按钮 */}
              <button
                onClick={() => setCustomMode(true)}
                className="w-full mt-4 p-4 rounded-xl border-2 border-dashed border-border hover:border-blue-500/50 transition-colors flex items-center justify-center gap-2 text-muted-foreground hover:text-foreground"
              >
                <Plus className="w-5 h-5" />
                <span>{t('app.templates.createCustom') || '创建自定义模板'}</span>
              </button>
            </>
          ) : (
            /* 自定义模板表单 */
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  模板名称
                </label>
                <input
                  type="text"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  placeholder="例如：我的面试助手"
                  className="w-full px-4 py-2 rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-2">
                  System Prompt
                </label>
                <textarea
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="输入你的自定义 prompt..."
                  rows={6}
                  className="w-full px-4 py-2 rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-blue-500 resize-none"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setCustomMode(false)}
                  className="flex-1"
                >
                  取消
                </Button>
                <Button
                  onClick={handleSaveCustom}
                  disabled={!customName || !customPrompt}
                  className="flex-1 bg-blue-500 hover:bg-blue-600"
                >
                  保存并使用
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * TemplateButton - 模板选择按钮
 */
export function TemplateButton({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation();

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
      title={t('app.templates.select') || '选择模板'}
    >
      <Edit3 className="w-4 h-4" />
      <span className="hidden sm:inline">{t('app.templates.button') || '模板'}</span>
    </button>
  );
}
