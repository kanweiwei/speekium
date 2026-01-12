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

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (title: string | null) => void;
}

const MAX_TITLE_LENGTH = 30;

export function NewSessionDialog({ isOpen, onClose, onCreate }: Props) {
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
      <DialogContent className="bg-gradient-to-br from-[#1C1C1F] to-[#141416] border-zinc-800/50 sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle className="text-zinc-200">新建会话</DialogTitle>
          <DialogDescription className="text-zinc-500">
            为新会话设置一个标题，留空将在发送第一条消息时自动命名。
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value.slice(0, MAX_TITLE_LENGTH))}
            onKeyDown={handleKeyDown}
            placeholder="输入标题..."
            className="bg-[#0A0A0B] border-zinc-800 text-zinc-200 placeholder:text-zinc-600 focus-visible:ring-blue-500"
            autoFocus
          />
          <p className="text-xs text-zinc-500 mt-2 text-right">
            {title.length}/{MAX_TITLE_LENGTH}
          </p>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="ghost"
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
          >
            取消
          </Button>
          <Button
            onClick={handleCreate}
            className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white shadow-lg shadow-blue-500/20"
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
