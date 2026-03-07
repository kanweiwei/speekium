import React from 'react';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/i18n';
import { Button } from '@/components/ui/button';

interface DownloadProgress {
  show: boolean;
  model: string;
  percent: number;
  speed: string;
  totalSize: string;
  eventType: 'started' | 'progress' | 'completed';
}

interface ModelLoadingStages {
  vad: 'pending' | 'loading' | 'loaded';
  asr: 'pending' | 'loading' | 'loaded';
}

interface LoadingScreenProps {
  message: string;
  status: 'loading' | 'error';
  downloadProgress?: DownloadProgress;
  modelLoadingStages?: ModelLoadingStages;
}

export function LoadingScreen({
  message,
  status,
  downloadProgress,
  modelLoadingStages
}: LoadingScreenProps) {
  const { t } = useTranslation();

  // Determine visual display state based on message content
  // Even if status is 'error', show loading style if message indicates loading is in progress
  const displayStatus = React.useMemo(() => {
    const loadingKeywords = ['loading', '加载', 'starting', '启动', 'initializing', '初始化', 'waiting', '等待'];
    const messageLower = (message || '').toLowerCase();
    const isLoadingMessage = loadingKeywords.some(keyword => messageLower.includes(keyword));
    return isLoadingMessage ? 'loading' : status;
  }, [message, status]);

  const handleRetry = () => {
    // Reload the app to retry daemon initialization
    window.location.reload();
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-background relative overflow-hidden">
      {/* Animated gradient mesh background */}
      {displayStatus === 'loading' && (
        <>
          <div className="absolute inset-0 overflow-hidden pointer-events-none">
            {/* Layer 1 - Slow blue gradient */}
            <div
              className="absolute top-1/4 left-1/4 w-[600px] h-[600px] bg-blue-500/8 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '8s', animationDelay: '0s' }}
            />
            {/* Layer 2 - Purple gradient, offset timing */}
            <div
              className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-purple-500/8 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '10s', animationDelay: '2s' }}
            />
            {/* Layer 3 - Small accent */}
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-cyan-500/5 rounded-full blur-3xl animate-pulse"
              style={{ animationDuration: '12s', animationDelay: '4s' }}
            />
          </div>

          {/* Subtle grid overlay */}
          <div
            className="absolute inset-0 opacity-[0.02]"
            style={{
              backgroundImage: `
                linear-gradient(to right, currentColor 1px, transparent 1px),
                linear-gradient(to bottom, currentColor 1px, transparent 1px)
              `,
              backgroundSize: '60px 60px'
            }}
          />
        </>
      )}

      {/* Content container */}
      <div className="relative z-10 flex flex-col items-center">
        {/* Logo with animated sound wave rings */}
        <div className="relative mb-10">
          {/* Outer glow */}
          <div className={cn(
            "absolute -inset-8 rounded-full bg-gradient-to-br opacity-20 blur-2xl -z-10 transition-all duration-500",
            displayStatus === 'loading'
              ? "from-blue-500 via-purple-500 to-cyan-500 animate-pulse"
              : "from-destructive to-destructive/50"
          )}
          style={displayStatus === 'loading' ? { animationDuration: '3s' } : {}}
          />

          {/* Animated wave rings - only when loading */}
          {displayStatus === 'loading' && (
            <>
              {/* Ring 1 */}
              <div
                className="absolute inset-0 rounded-full border border-blue-500/30 animate-wave-ring"
                style={{ animationDelay: '0s' }}
              />
              {/* Ring 2 */}
              <div
                className="absolute inset-0 rounded-full border border-purple-500/25 animate-wave-ring"
                style={{ animationDelay: '0.8s' }}
              />
              {/* Ring 3 */}
              <div
                className="absolute inset-0 rounded-full border border-cyan-500/20 animate-wave-ring"
                style={{ animationDelay: '1.6s' }}
              />
            </>
          )}

          {/* Logo container */}
          <div className={cn(
            "w-28 h-28 transition-all duration-500 relative",
            displayStatus === 'loading' && "animate-logo-glow",
            displayStatus === 'error' && "opacity-50 scale-90"
          )}>
            <img
              src="/logo.svg"
              alt="Speekium"
              className="w-full h-full drop-shadow-2xl"
            />
          </div>
        </div>

        {/* Title with subtle gradient */}
        <h1 className={cn(
          "text-3xl font-semibold mb-8 tracking-tight transition-all duration-300",
          displayStatus === 'loading' ? "animate-fade-in" : "opacity-60"
        )}>
          <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent dark:from-blue-400 dark:via-purple-400 dark:to-cyan-400">
            {t('app.title')}
          </span>
        </h1>

        {/* Rhythmic loading dots - only when loading */}
        {displayStatus === 'loading' && (
          <div className="flex items-center gap-2 mb-6">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="w-1.5 h-6 rounded-full bg-gradient-to-t from-blue-500 to-purple-500 animate-dot-wave"
                style={{
                  animationDelay: `${i * 0.1}s`,
                  height: `${12 + Math.sin(i * 0.8) * 8}px`
                }}
              />
            ))}
          </div>
        )}

        {/* Status message */}
        <div className={cn(
          "flex items-center gap-3 px-5 py-3 rounded-2xl transition-all duration-300 backdrop-blur-sm",
          displayStatus === 'error'
            ? "bg-destructive/10 border border-destructive/30 text-destructive"
            : "bg-muted/50 border border-border/30 text-muted-foreground"
        )}>
          {displayStatus === 'loading' ? (
            <div className="relative">
              <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
              <div className="absolute inset-0 w-5 h-5 rounded-full border-2 border-transparent border-t-purple-500/50 animate-spin" style={{ animationDuration: '1.5s' }} />
            </div>
          ) : (
            <AlertCircle className="w-5 h-5" />
          )}
          <span className="text-sm font-medium">{message || t('app.loading.startingService')}</span>
        </div>

        {/* Progress bar */}
        {displayStatus === 'loading' && downloadProgress?.show && (
          <div className="mt-4 w-72 animate-fade-in">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>{downloadProgress.model}</span>
              <span>{downloadProgress.percent}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden border border-border/50">
              <div 
                className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 transition-all duration-300"
                style={{ width: `${downloadProgress.percent}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-muted-foreground mt-1">
              <span>{downloadProgress.speed}</span>
              <span>{downloadProgress.totalSize}</span>
            </div>
          </div>
        )}

        {/* Model loading stages */}
        {modelLoadingStages && displayStatus === 'loading' && (
          <div className="mt-4 w-72 animate-fade-in">
            <div className="bg-muted/80 border border-border/50 rounded-xl p-4 backdrop-blur-sm">
              <div className="text-xs text-muted-foreground mb-3">{t('app.loading.loadingModels')}</div>
              <div className="space-y-2">
                {[
                  { key: 'vad', label: t('app.loading.vad'), desc: t('app.loading.vadDesc') },
                  { key: 'asr', label: t('app.loading.asr'), desc: t('app.loading.asrDesc') },
                ].map((model) => {
                  const stage = modelLoadingStages[model.key as keyof typeof modelLoadingStages];
                  const isLoading = stage === 'loading';
                  const isLoaded = stage === 'loaded';
                  const isPending = stage === 'pending';

                  return (
                    <div key={model.key} className="flex items-center gap-2 text-sm">
                      {isLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-500" />
                      ) : isLoaded ? (
                        <div className="w-3.5 h-3.5 rounded-full bg-green-500 flex items-center justify-center">
                          <span className="text-white text-[8px]">✓</span>
                        </div>
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-muted-foreground/30" />
                      )}
                      <span className={cn(
                        "flex-1",
                        isPending && "text-muted-foreground/50",
                        isLoaded && "text-foreground"
                      )}>
                        {model.label}
                      </span>
                      <span className={cn(
                        "text-xs text-muted-foreground",
                        isPending && "opacity-50"
                      )}>
                        {model.desc}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Download progress card */}
        {downloadProgress?.show && (
          <div className="mt-4 w-72 animate-fade-in">
            <div className="bg-muted/80 border border-border/50 rounded-xl p-4 backdrop-blur-sm">
              {/* Model name */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                <span className="text-sm font-medium">{downloadProgress.model}</span>
              </div>

              {/* Progress bar */}
              <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-cyan-500 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${downloadProgress.percent}%` }}
                />
              </div>

              {/* Progress info */}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{downloadProgress.percent}%</span>
                {downloadProgress.speed && (
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500/60" />
                    {downloadProgress.speed}
                  </span>
                )}
                {downloadProgress.totalSize && (
                  <span>{downloadProgress.totalSize}</span>
                )}
              </div>

              {/* Completed state */}
              {downloadProgress.eventType === 'completed' && (
                <div className="mt-2 text-xs text-green-500 flex items-center gap-1">
                  <span>✓</span>
                  <span>{t('app.loading.downloadComplete')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* First launch hint */}
        {displayStatus === 'loading' && !downloadProgress?.show && (
          <p className="text-sm text-muted-foreground/60 mt-6 animate-fade-in-delayed flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500/60 animate-pulse" />
            {t('app.loading.firstLaunchHint')}
          </p>
        )}

        {/* Retry button for error state */}
        {displayStatus === 'error' && (
          <Button
            variant="outline"
            size="sm"
            className="mt-6 gap-2"
            onClick={handleRetry}
          >
            <RefreshCw className="w-4 h-4" />
            {t('app.loading.retry')}
          </Button>
        )}
      </div>
    </div>
  );
}
