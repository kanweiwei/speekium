import { useState, useEffect } from 'react';
import { X, Clock, Trash2, MessageSquare, ChevronLeft, PenSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { historyAPI, Session, HistoryMessage } from '../useTauriAPI';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onLoadSession?: (messages: Array<{ role: 'user' | 'assistant'; content: string }>) => void;
  onNewSession?: () => void;
}

// Time grouping helper
function groupSessionsByDate(sessions: Session[]) {
  const today = new Date().setHours(0, 0, 0, 0);
  const yesterday = today - 86400000;
  const thisWeekStart = today - new Date().getDay() * 86400000;
  const thisMonthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1).getTime();

  return {
    today: sessions.filter((s) => s.updated_at >= today),
    yesterday: sessions.filter((s) => s.updated_at >= yesterday && s.updated_at < today),
    thisWeek: sessions.filter((s) => s.updated_at >= thisWeekStart && s.updated_at < yesterday),
    thisMonth: sessions.filter((s) => s.updated_at >= thisMonthStart && s.updated_at < thisWeekStart),
    earlier: sessions.filter((s) => s.updated_at < thisMonthStart),
  };
}

const timeLabels: Record<string, string> = {
  today: '今天',
  yesterday: '昨天',
  thisWeek: '本周',
  thisMonth: '本月',
  earlier: '更早',
};

export function HistoryDrawer({ isOpen, onClose, onLoadSession, onNewSession }: Props) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [sessionMessages, setSessionMessages] = useState<HistoryMessage[]>([]);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Load sessions when drawer opens
  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen]);

  const loadSessions = async () => {
    setIsLoading(true);
    try {
      const result = await historyAPI.listSessions(1, 50);
      setSessions(result.items);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleViewSession = async (session: Session) => {
    try {
      const result = await historyAPI.getSessionMessages(session.id, 1, 100);
      setSelectedSession(session);
      setSessionMessages(result.items);
    } catch (error) {
      console.error('Failed to load session messages:', error);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await historyAPI.deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setDeleteConfirm(null);
      if (selectedSession?.id === sessionId) {
        setSelectedSession(null);
        setSessionMessages([]);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const handleLoadSession = () => {
    if (onLoadSession && sessionMessages.length > 0) {
      onLoadSession(
        sessionMessages.map((m) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
        }))
      );
      onClose();
    }
  };

  const handleBack = () => {
    setSelectedSession(null);
    setSessionMessages([]);
  };

  // ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (selectedSession) {
          handleBack();
        } else {
          onClose();
        }
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedSession, onClose]);

  if (!isOpen) return null;

  const grouped = groupSessionsByDate(sessions);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className={cn(
          'fixed left-0 top-0 h-full w-80 z-50',
          'bg-gradient-to-br from-[#0A0A0B] to-[#141416] border-r border-zinc-800/50',
          'flex flex-col',
          'animate-in slide-in-from-left duration-300'
        )}
      >
        {/* Header */}
        <header className="h-14 px-4 flex items-center justify-between border-b border-zinc-800/50 shrink-0">
          {selectedSession ? (
            <>
              <button
                onClick={handleBack}
                className="flex items-center gap-2 px-2 py-1 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30 transition-all duration-200"
              >
                <ChevronLeft className="w-4 h-4" />
                <span className="text-sm">返回</span>
              </button>
              <span className="text-sm font-medium text-zinc-200 truncate max-w-[140px]">
                {selectedSession.title}
              </span>
            </>
          ) : (
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold text-zinc-200">历史记录</h2>
            </div>
          )}
          <div className="flex items-center gap-1">
            {/* 新建会话按钮 - 仅在列表视图显示 */}
            {!selectedSession && onNewSession && (
              <Button
                variant="ghost"
                size="icon"
                className="text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                onClick={onNewSession}
                title="新建会话"
              >
                <PenSquare className="w-5 h-5" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="text-zinc-400 hover:text-zinc-200"
              onClick={onClose}
            >
              <X className="w-5 h-5" />
            </Button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {selectedSession ? (
            // Session detail view
            <div className="p-4 space-y-3">
              {sessionMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    'p-3 rounded-2xl text-sm',
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white ml-4 rounded-tr-sm'
                      : 'bg-[#1C1C1F] text-zinc-200 mr-4 border border-zinc-800/50 rounded-tl-sm'
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                  <p className="text-xs opacity-60 mt-1">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              ))}

              {/* Load session button */}
              {sessionMessages.length > 0 && onLoadSession && (
                <Button
                  onClick={handleLoadSession}
                  className="w-full mt-4 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white shadow-lg shadow-blue-500/20"
                >
                  加载此对话
                </Button>
              )}
            </div>
          ) : isLoading ? (
            // Loading state
            <div className="flex items-center justify-center h-32">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-zinc-500 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          ) : sessions.length === 0 ? (
            // Empty state
            <div className="flex flex-col items-center justify-center h-64 text-center px-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-zinc-700 to-zinc-800 flex items-center justify-center shadow-lg mb-4">
                <MessageSquare className="w-8 h-8 text-zinc-500" />
              </div>
              <p className="text-zinc-400 mb-2">还没有对话记录</p>
              <p className="text-sm text-zinc-500">开始对话后会自动保存</p>
            </div>
          ) : (
            // Session list
            <div className="p-2">
              {Object.entries(grouped).map(([key, sessionList]) => {
                if (sessionList.length === 0) return null;

                return (
                  <div key={key} className="mb-4">
                    <h3 className="text-xs font-medium text-zinc-400 px-3 py-2 bg-[#141416]/50 rounded-lg mb-2">
                      {timeLabels[key]}
                    </h3>
                    <div className="space-y-1">
                      {sessionList.map((session) => (
                        <div
                          key={session.id}
                          className="group relative"
                        >
                          <button
                            onClick={() => handleViewSession(session)}
                            className="w-full text-left px-3 py-2.5 rounded-lg bg-[#1C1C1F]/30 border border-zinc-800/30 hover:bg-[#1C1C1F] hover:border-zinc-700 transition-all duration-200"
                          >
                            <p className="text-sm text-zinc-200 truncate pr-8">
                              {session.title}
                            </p>
                            <p className="text-xs text-zinc-500 mt-0.5">
                              {new Date(session.updated_at).toLocaleString()}
                            </p>
                          </button>

                          {/* Delete button */}
                          {deleteConfirm === session.id ? (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                              <button
                                onClick={() => handleDeleteSession(session.id)}
                                className="p-1.5 rounded bg-red-600 text-white text-xs"
                              >
                                确认
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="p-1.5 rounded bg-zinc-700 text-zinc-300 text-xs"
                              >
                                取消
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDeleteConfirm(session.id)}
                              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-zinc-400 hover:text-red-400 border border-transparent hover:border-red-500/20 transition-all duration-200"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
