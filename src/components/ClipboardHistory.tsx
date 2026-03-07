import { useState, useEffect } from 'react';
import { Clipboard, Copy, Trash2, X, Search, Mic } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ClipboardHistoryItem {
  id: string;
  content: string;
  timestamp: number;
}

interface ClipboardHistoryProps {
  onClose: () => void;
  onSelect: (content: string) => void;
  className?: string;
}

/**
 * ClipboardHistory - 剪贴板历史组件
 * 
 * 显示语音转文字后自动复制到剪贴板的内容历史
 */
export function ClipboardHistory({
  onClose,
  onSelect,
  className
}: ClipboardHistoryProps) {
  const [items, setItems] = useState<ClipboardHistoryItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');

  // 加载历史记录
  useEffect(() => {
    const saved = localStorage.getItem('clipboardHistory');
    if (saved) {
      try {
        setItems(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load clipboard history:', e);
      }
    }
  }, []);

  // 保存到 localStorage
  const saveItems = (newItems: ClipboardHistoryItem[]) => {
    localStorage.setItem('clipboardHistory', JSON.stringify(newItems));
    setItems(newItems);
  };

  // 删除单条记录
  const handleDelete = (id: string) => {
    const newItems = items.filter(item => item.id !== id);
    saveItems(newItems);
  };

  // 复制到剪贴板
  const handleCopy = async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
    } catch (e) {
      console.error('Copy failed:', e);
    }
  };

  // 清除全部
  const handleClearAll = () => {
    saveItems([]);
  };

  // 过滤搜索
  const filteredItems = items.filter(item => 
    item.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className={cn("absolute inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4", className)}>
      <div className="w-full max-w-lg bg-card border border-border rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Clipboard className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">剪贴板历史</h2>
            <span className="text-xs text-muted-foreground">({items.length})</span>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        {/* Search */}
        <div className="p-4 border-b border-border">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="搜索历史记录..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background text-foreground focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* List */}
        <div className="p-4 max-h-[50vh] overflow-y-auto space-y-2">
          {filteredItems.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Mic className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>暂无历史记录</p>
              <p className="text-sm mt-1">语音转文字后会自动保存</p>
            </div>
          ) : (
            filteredItems.map((item) => (
              <div
                key={item.id}
                className="group p-3 rounded-xl border border-border bg-muted/50 hover:bg-muted transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div 
                    className="flex-1 cursor-pointer"
                    onClick={() => onSelect(item.content)}
                  >
                    <p className="text-sm text-foreground line-clamp-3">
                      {item.content}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {new Date(item.timestamp).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => handleCopy(item.content)}
                      className="p-1.5 rounded hover:bg-background"
                      title="复制"
                    >
                      <Copy className="w-4 h-4 text-muted-foreground" />
                    </button>
                    <button
                      onClick={() => handleDelete(item.id)}
                      className="p-1.5 rounded hover:bg-background"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4 text-muted-foreground" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className="p-4 border-t border-border flex justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearAll}
              className="text-muted-foreground"
            >
              <Trash2 className="w-4 h-4 mr-1" />
              清除全部
            </Button>
            <Button
              size="sm"
              onClick={onClose}
            >
              关闭
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 添加到剪贴板历史
 */
export function addToClipboardHistory(content: string) {
  if (!content || content.trim().length === 0) return;
  
  const saved = localStorage.getItem('clipboardHistory');
  let items: ClipboardHistoryItem[] = [];
  
  if (saved) {
    try {
      items = JSON.parse(saved);
    } catch (e) {
      items = [];
    }
  }
  
  // 避免重复
  if (items.length > 0 && items[0].content === content) {
    return;
  }
  
  // 添加新记录（最多保存 50 条）
  const newItem: ClipboardHistoryItem = {
    id: Date.now().toString(),
    content: content,
    timestamp: Date.now(),
  };
  
  items.unshift(newItem);
  
  // 限制数量
  if (items.length > 50) {
    items = items.slice(0, 50);
  }
  
  localStorage.setItem('clipboardHistory', JSON.stringify(items));
}
