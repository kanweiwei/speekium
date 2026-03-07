import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { AlertTriangle, CheckCircle, RefreshCw, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTranslation } from '@/i18n';

interface ErrorStats {
  total: number;
  pending: number;
  reported: number;
}

export function ErrorReportButton() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const result = await invoke<ErrorStats>('get_error_stats');
      setStats(result);
    } catch (error) {
      console.error('Failed to fetch error stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    setUploading(true);
    setMessage(null);
    try {
      const result = await invoke<{ success: boolean; message: string }>('upload_errors_to_github');
      setMessage(result.message);
      await fetchStats();
    } catch (error) {
      setMessage(`Error: ${error}`);
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>{t('status.loading')}</span>
      </div>
    );
  }

  if (!stats || stats.total === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <CheckCircle className="w-4 h-4 text-green-500" />
        <span>{t('settings.service.allServicesNormal')}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-500" />
          <span className="text-sm">
            {stats.pending} {t('settings.errors.pending')}
          </span>
        </div>
        
        <Button
          variant="outline"
          size="sm"
          onClick={handleUpload}
          disabled={uploading || stats.pending === 0}
        >
          {uploading ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4 mr-2" />
          )}
          {t('settings.errors.report')}
        </Button>
      </div>

      {message && (
        <div className={`text-xs ${message.includes('Error') ? 'text-red-500' : 'text-green-500'}`}>
          {message}
        </div>
      )}

      <div className="flex gap-4 text-xs text-muted-foreground">
        <span>{t('settings.errors.total')}: {stats.total}</span>
        <span>{t('settings.errors.reported')}: {stats.reported}</span>
      </div>
    </div>
  );
}
