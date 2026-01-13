import React, { useState, useRef, useEffect } from 'react';
import { Mic, ChevronDown, ChevronUp, AlertCircle, X, Loader2, Send } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import { useSettings } from '@/contexts/SettingsContext';
import { getHotkeyDisplayName } from '@/utils/hotkeyParser';

interface CollapsibleInputProps {
  /** Input value */
  value: string;
  /** Value change callback */
  onChange: (value: string) => void;
  /** Send callback */
  onSend: () => void;
  /** Whether processing */
  isProcessing?: boolean;
}

export function CollapsibleInput({
  value,
  onChange,
  onSend,
  isProcessing = false,
}: CollapsibleInputProps) {
  const { t } = useTranslation();
  const { config } = useSettings();
  const [isExpanded, setIsExpanded] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [isSmallScreen, setIsSmallScreen] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  // Get hotkey display name from config
  const hotkeyDisplay = getHotkeyDisplayName(config?.push_to_talk_hotkey);
  const expandButtonRef = useRef<HTMLButtonElement>(null);
  const collapseTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Detect screen height
  useEffect(() => {
    const checkScreenSize = () => {
      setIsSmallScreen(window.innerHeight < 800);
    };

    checkScreenSize();
    window.addEventListener('resize', checkScreenSize);

    return () => window.removeEventListener('resize', checkScreenSize);
  }, []);

  // Start countdown after blur
  const handleBlur = () => {
    if (isExpanded && !value.trim()) {
      const warningTimer = setTimeout(() => {
        setShowWarning(true);

        const collapseTimer = setTimeout(() => {
          handleCollapse();
        }, 3000);

        collapseTimerRef.current = collapseTimer;
      }, 5000);

      collapseTimerRef.current = warningTimer;
    }
  };

  // Cancel countdown on user interaction
  const handleInteraction = () => {
    if (collapseTimerRef.current) {
      clearTimeout(collapseTimerRef.current);
      collapseTimerRef.current = null;
    }
    setShowWarning(false);
  };

  // Expand
  const handleExpand = () => {
    setIsExpanded(true);
    setShowWarning(false);
    // Delay focus, wait for animation to complete
    setTimeout(() => {
      inputRef.current?.focus();
    }, 300);
  };

  // Collapse
  const handleCollapse = () => {
    setIsExpanded(false);
    setShowWarning(false);
    if (collapseTimerRef.current) {
      clearTimeout(collapseTimerRef.current);
      collapseTimerRef.current = null;
    }
    expandButtonRef.current?.focus();
  };

  // Cancel collapse
  const handleCancelCollapse = () => {
    handleInteraction();
    inputRef.current?.focus();
  };

  // Keyboard events
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    } else if (e.key === 'Escape') {
      handleCollapse();
    }
  };

  // Send
  const handleSend = () => {
    if (!value.trim() || isProcessing) return;
    onSend();
    handleInteraction();
  };

  return (
    <div className="border-t border-border/50 bg-background/80 backdrop-blur-xl px-4 py-4">
      <div className="max-w-[680px] mx-auto">
        {/* 自动折叠警告 */}
        {showWarning && (
          <div className="mb-3 animate-in slide-in-from-bottom-2 duration-300">
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
              <AlertCircle className="h-4 w-4 text-yellow-500 flex-shrink-0" />
              <span className="flex-1 text-xs text-yellow-500 dark:text-yellow-400">
                {t('app.autoCollapse.warning')}
              </span>
              <button
                onClick={handleCancelCollapse}
                className="text-yellow-500 hover:text-yellow-600 dark:text-yellow-400 dark:hover:text-yellow-300 transition-colors"
                aria-label={t('app.autoCollapse.cancel')}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* 主容器 - 高度动画 */}
        <div
          className={cn(
            "transition-all duration-300 ease-in-out",
            isSmallScreen && isExpanded ? "min-h-[80px]" : "",
            !isSmallScreen && isExpanded ? "min-h-[108px]" : "",
            !isExpanded && "min-h-[48px]"
          )}
          role="region"
          aria-label="文本输入区域"
          aria-expanded={isExpanded}
        >
          {/* 输入行 - 展开时显示 */}
          {isExpanded && (
            <div className="flex items-center gap-3 mb-3 animate-in fade-in slide-in-from-top-2 duration-200">
              <Input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => {
                  onChange(e.target.value);
                  handleInteraction();
                }}
                onKeyPress={handleKeyPress}
                onBlur={handleBlur}
                placeholder={t('app.messages.placeholder')}
                disabled={isProcessing}
                className="flex-1 bg-muted border-border/50 text-foreground placeholder:text-muted-foreground focus-visible:ring-blue-500"
                aria-label="输入消息"
              />
              <Button
                onClick={handleSend}
                disabled={!value.trim() || isProcessing}
                className="bg-blue-600 hover:bg-blue-700 text-white disabled:bg-muted disabled:text-muted-foreground transition-all duration-200 active:scale-[0.98]"
                aria-label="发送消息"
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          )}

          {/* PTT 提示行 - 始终显示 */}
          <div className="flex items-center justify-between">
            {/* PTT 提示 */}
            <div
              id="ptt-hint"
              className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
              aria-live="polite"
            >
              <Mic className="w-3 h-3" />
              <span>
                {t('app.ptt.hint')}{' '}
                <kbd className="mx-1 px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono border border-border">
                  {hotkeyDisplay}
                </kbd>{' '}
                {t('app.ptt.hintAction')}
              </span>
            </div>

            {/* 展开/折叠按钮 */}
            <button
              ref={expandButtonRef}
              onClick={isExpanded ? handleCollapse : handleExpand}
              onFocus={handleInteraction}
              className={cn(
                "inline-flex items-center gap-2 px-3 py-2 rounded-md",
                "text-sm font-medium transition-all duration-200",
                "hover:bg-muted active:scale-[0.98]",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500",
                "disabled:opacity-50 disabled:pointer-events-none"
              )}
              aria-label={isExpanded ? "折叠输入框" : "展开输入框"}
              aria-pressed={isExpanded}
            >
              {isExpanded ? (
                <>
                  <ChevronUp className="w-4 h-4 transition-transform duration-300" />
                  <span>{t('app.collapse')}</span>
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4 transition-transform duration-300" />
                  <span>{t('app.expand')}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
