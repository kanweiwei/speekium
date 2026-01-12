import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useTranslation } from '@/i18n';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (title: string | null) => void;
}

const MAX_TITLE_LENGTH = 30;

export function NewSessionDialog({ isOpen, onClose, onCreate }: Props) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');

  // Reset title when dialog opens
  useEffect(() => {
    if (isOpen) {
      setTitle('');
    }
  }, [isOpen]);

  const handleCreate = () => {
    const trimmedTitle = title.trim();
    onCreate(trimmedTitle || null);
    onClose();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleCreate();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="bg-gradient-to-br from-muted to-background border-border/50 sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-foreground">{t('session.newSession.title')}</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {t('session.newSession.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, MAX_TITLE_LENGTH))}
            onKeyDown={handleKeyDown}
            placeholder={t('session.newSession.placeholder')}
            className="bg-background border-border text-foreground placeholder:text-muted-foreground focus-visible:ring-blue-500"
            autoFocus
          />
          <p className="text-xs text-muted-foreground mt-2 text-right">
            {t('session.newSession.characterLimit', { count: title.length, max: MAX_TITLE_LENGTH })}
          </p>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
          >
            {t('buttons.cancel')}
          </Button>
          <Button
            onClick={handleCreate}
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white shadow-lg shadow-blue-500/20"
          >
            {t('buttons.create')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
