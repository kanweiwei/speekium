import { useState, useEffect, useCallback } from 'react';
import { X, Clock, Trash2, MessageSquare, ChevronLeft, PenSquare, Star, StarOff, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { historyAPI, Session, HistoryMessage } from '../useTauriAPI';
import { useTranslation } from '@/i18n';

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

export function HistoryDrawer({ isOpen, onClose, onLoadSession, onNewSession }: Props) {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [sessionMessages, setSessionMessages] = useState<HistoryMessage[]>([]);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [favoriteFilter, setFavoriteFilter] = useState<boolean | undefined>(undefined);

  // Load sessions function - defined before useEffect
  const loadSessions = useCallback(async () => {
    console.log('[History] ===== Loading sessions with filter:', favoriteFilter);
    setIsLoading(true);
    try {
      console.log('[History] Calling historyAPI.listSessions...');
      const result = await historyAPI.listSessions(1, 50, favoriteFilter);
      console.log('[History] API returned:', result);
      console.log('[History] Number of sessions:', result?.items?.length);
      console.log('[History] Sessions:', result?.items);
      setSessions(result?.items || []);
      console.log('[History] ===== Load completed successfully');
    } catch (error) {
      console.error('[History] ===== Load failed with error:', error);
      console.error('[History] Error type:', error?.constructor?.name);
      console.error('[History] Error message:', error?.message);
      console.error('[History] Error details:', JSON.stringify(error));
      setSessions([]);
    } finally {
      setIsLoading(false);
    }
  }, [favoriteFilter]);

  // Load sessions when drawer opens or filter changes
  useEffect(() => {
    if (isOpen) {
      loadSessions();
    }
  }, [isOpen, favoriteFilter, loadSessions]);

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

  const handleToggleFavorite = async (sessionId: string) => {
    try {
      console.log('[Favorite] ===== Starting toggle for session:', sessionId);
      const newFavoriteState = await historyAPI.toggleFavorite(sessionId);
      console.log('[Favorite] Backend returned state:', newFavoriteState);
      // Update local state
      setSessions((prev) => {
        const updated = prev.map((s) =>
          s.id === sessionId ? { ...s, is_favorite: newFavoriteState } : s
        );
        const updatedSession = updated.find(s => s.id === sessionId);
        console.log('[Favorite] Updated session in state:', updatedSession);
        return updated;
      });
      // Also update selected session if it's the same
      if (selectedSession?.id === sessionId) {
        setSelectedSession((prev) =>
          prev ? { ...prev, is_favorite: newFavoriteState } : null
        );
      }
      console.log('[Favorite] ===== Toggle completed successfully');
    } catch (error) {
      console.error('[Favorite] ===== Toggle failed with error:', error);
      console.error('[Favorite] Error type:', error?.constructor?.name);
      console.error('[Favorite] Error message:', error?.message);
      console.error('[Favorite] Error stack:', error?.stack);
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
          'fixed left-0 top-0 h-full w-96 z-50',
          'bg-gradient-to-br from-background to-muted border-r border-border/50',
          'flex flex-col',
          'animate-in slide-in-from-left duration-300'
        )}
      >
        {/* Header */}
        <header className="shrink-0 border-b border-border/50">
          {/* Top row */}
          <div className="h-14 px-4 flex items-center justify-between">
            {selectedSession ? (
              <>
                <button
                  onClick={handleBack}
                  className="flex items-center gap-2 px-2 py-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/30 transition-all duration-200"
                >
                  <ChevronLeft className="w-4 h-4" />
                  <span className="text-sm">{t('buttons.back')}</span>
                </button>
                <span className="text-sm font-medium text-foreground truncate max-w-[140px]">
                  {selectedSession.title}
                </span>
              </>
            ) : (
              <div className="flex items-center gap-2 flex-1">
                <Clock className="w-5 h-5 text-blue-500" />
                <h2 className="text-lg font-semibold text-foreground">{t('history.title')}</h2>
              </div>
            )}
            <div className="flex items-center gap-1">
              {/* 新建会话按钮 - 仅在列表视图显示 */}
              {!selectedSession && onNewSession && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  onClick={onNewSession}
                  title={t('history.newSession')}
                >
                  <PenSquare className="w-5 h-5" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="text-muted-foreground hover:text-foreground"
                onClick={onClose}
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
          </div>

          {/* Filter bar - Only show in list view */}
          {!selectedSession && (
            <div className="px-4 pb-3">
              <div className="flex items-center gap-1 p-1 bg-muted/50 rounded-lg">
                <button
                  onClick={() => setFavoriteFilter(undefined)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 whitespace-nowrap",
                    favoriteFilter === undefined
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                  )}
                >
                  {t('history.filter.all')}
                </button>
                <button
                  onClick={() => setFavoriteFilter(true)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 whitespace-nowrap",
                    favoriteFilter === true
                      ? "bg-yellow-500 text-white shadow-sm"
                      : "text-muted-foreground hover:text-yellow-500 hover:bg-muted/30"
                  )}
                >
                  <Star className={cn("w-3.5 h-3.5", favoriteFilter === true && "fill-white")} />
                  {t('history.filter.starredOnly')}
                </button>
                <button
                  onClick={() => setFavoriteFilter(false)}
                  className={cn(
                    "flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 whitespace-nowrap",
                    favoriteFilter === false
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/30"
                  )}
                >
                  {t('history.filter.unstarredOnly')}
                </button>
              </div>
            </div>
          )}
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
                      : 'bg-muted text-foreground mr-4 border border-border/50 rounded-tl-sm'
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
                  {t('history.actions.load')}
                </Button>
              )}
            </div>
          ) : isLoading ? (
            // Loading state
            <div className="flex items-center justify-center h-32">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          ) : sessions.length === 0 ? (
            // Empty state
            <div className="flex flex-col items-center justify-center h-64 text-center px-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-muted to-muted-foreground/20 flex items-center justify-center shadow-lg mb-4">
                <MessageSquare className="w-8 h-8 text-muted-foreground" />
              </div>
              <p className="text-muted-foreground mb-2">{t('history.empty.title')}</p>
              <p className="text-sm text-muted-foreground">{t('history.empty.description')}</p>
            </div>
          ) : (
            // Session list
            <div className="p-2">
              {Object.entries(grouped).map(([key, sessionList]) => {
                if (sessionList.length === 0) return null;

                return (
                  <div key={key} className="mb-4">
                    <h3 className="text-xs font-medium text-muted-foreground px-3 py-2 bg-muted/50 rounded-lg mb-2">
                      {t(`history.timeGroups.${key}`)}
                    </h3>
                    <div className="space-y-1">
                      {sessionList.map((session) => (
                        <div
                          key={session.id}
                          className="group relative"
                        >
                          <button
                            onClick={() => handleViewSession(session)}
                            className="w-full text-left px-3 py-2.5 rounded-lg bg-muted/30 border border-border/30 hover:bg-muted hover:border-muted-foreground/50 transition-all duration-200"
                          >
                            <p className="text-sm text-foreground truncate pr-8">
                              {session.title}
                            </p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {new Date(session.updated_at).toLocaleString()}
                            </p>
                          </button>

                          {/* Action buttons */}
                          {deleteConfirm === session.id ? (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                              <button
                                onClick={() => handleDeleteSession(session.id)}
                                className="p-1.5 rounded bg-red-600 text-white text-xs"
                              >
                                {t('history.actions.confirm')}
                              </button>
                              <button
                                onClick={() => setDeleteConfirm(null)}
                                className="p-1.5 rounded bg-muted text-muted-foreground text-xs"
                              >
                                {t('history.actions.cancel')}
                              </button>
                            </div>
                          ) : (
                            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-0.5">
                              {/* Star button - always visible if favorited, otherwise show on hover */}
                              <button
                                onClick={(e) => {
                                  console.log('[Favorite] Button clicked, session:', session.id);
                                  e.stopPropagation();
                                  e.preventDefault();
                                  handleToggleFavorite(session.id);
                                }}
                                className={cn(
                                  "p-1.5 rounded-md transition-all duration-200",
                                  session.is_favorite
                                    ? "text-yellow-500 hover:bg-yellow-500/10 opacity-100"
                                    : "text-muted-foreground hover:text-yellow-500 hover:bg-yellow-500/10 opacity-0 group-hover:opacity-100"
                                )}
                                title={session.is_favorite ? t('history.actions.unstar') : t('history.actions.star')}
                              >
                                <Star className={cn("w-4 h-4", session.is_favorite && "fill-yellow-500")} />
                              </button>

                              {/* Delete button */}
                              <button
                                onClick={() => setDeleteConfirm(session.id)}
                                className="p-1.5 rounded-md opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-muted-foreground hover:text-red-400 border border-transparent hover:border-red-500/20 transition-all duration-200"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
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
