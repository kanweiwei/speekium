/**
 * SaveStatusIndicator Component
 *
 * Displays the current save status with visual feedback
 */

import { Check, AlertCircle, Loader2, Cloud } from 'lucide-react';
import { cn } from '@/lib/utils';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

interface SaveStatusIndicatorProps {
  status: SaveStatus;
  error?: string | null;
  className?: string;
}

export function SaveStatusIndicator({ status, error, className }: SaveStatusIndicatorProps) {
  if (status === 'idle') {
    return (
      <div className={cn("flex items-center gap-1.5 text-xs text-muted-foreground", className)}>
        <Cloud className="h-3.5 w-3.5" />
        <span>Auto-save enabled</span>
      </div>
    );
  }

  if (status === 'saving') {
    return (
      <div className={cn("flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400", className)}>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        <span>Saving...</span>
      </div>
    );
  }

  if (status === 'saved') {
    return (
      <div className={cn("flex items-center gap-1.5 text-xs text-green-600 dark:text-green-400", className)}>
        <Check className="h-3.5 w-3.5" />
        <span>Saved</span>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className={cn("flex items-center gap-1.5 text-xs text-destructive", className)}>
        <AlertCircle className="h-3.5 w-3.5" />
        <span>Save failed</span>
        {error && (
          <span className="max-w-[200px] truncate" title={error}>
            : {error}
          </span>
        )}
      </div>
    );
  }

  return null;
}
